import sys
import socket
from threading import Thread
import os
from datetime import datetime
import struct
import argparse
from utils import action, status
from db import DB_manager

class FS_Tracker(Thread):
    def __init__(
        self,
        db,
        port=9090,
        host=None,
        max_connections=5,
        timeout=60*5,
        debug=False,
    ):
        self.socket = None
        self.db = DB_manager(db, debug)
        self.port = port
        self.host = host
        self.max_connections = max_connections
        self.timeout = timeout
        self.debug = debug
        self.clients = []
        Thread.__init__(self)    

    def run(self):
        if self.debug:
            print(datetime.now(), "Starting ...")
        self.listen()
        
    def listen(self):
                
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.socket.bind((self.host, self.port))
        if self.debug:
            print(str(datetime.now()) + " Server socket bound to %s:%s" % (self.host, self.port))

        self.socket.listen(self.max_connections)
        if self.debug:
            print(datetime.now(), "Server socket listening for connections")

        while True:
            client, address = self.socket.accept()
            self.clients.append(client)
            client.settimeout(self.timeout)

            if self.debug:
                print(datetime.now(), "Client connected", address)

            Thread(
                target=self.listen_to_client,
                args=(client, address)
            ).start()
            
    def send_response(self, client, status, counter):
        if self.debug:
            print(datetime.now(), "Sending response to client")
        try:
            flat_data = []
            format_string = "!BBH"
            flat_data.extend([action.RESPONSE.value, status, counter])
            client.sendall(struct.pack(format_string, *flat_data))
            if self.debug:
                print(datetime.now(), "Response sent to client")
        except Exception as e:
            if self.debug:
                print("[send_response]", datetime.now(), e, client, '\n')
            return False

    def listen_to_client(self, client, address):
        counter = 0

        while True:
            try:
                print(datetime.now(), "Waiting for data from client", address)
                bytes_read = client.recv(1)

                if not bytes_read:
                    break

                counter += 1
                decoded_byte = struct.unpack("!B", bytes_read)[0]
                
                if decoded_byte == action.LEAVE.value:
                    print(datetime.now(), "Received LEAVE")
                    self.send_response(client, status.SUCCESS.value, counter)
                    break
                elif decoded_byte == action.UPDATE.value:
                    self.handle_update_message(client, address, counter)
                elif decoded_byte == action.LOCATE.value:
                    self.handle_locate_message(client, address, counter)
                else:
                    break

            except Exception as e:
                if self.debug:
                    print("[listen_to_client]", datetime.now(), e, address, '\n')
                break

        client.close()

        if self.debug:
            print(datetime.now(), "Client disconnected", address)

        return False
    
    def handle_locate_message(self, client, address, counter):
        if self.debug:
            print(datetime.now(), "Received LOCATE")
        
        bytes_read = client.recv(1)
        file_name_length = struct.unpack("!B", bytes_read)[0]
        bytes_read = client.recv(file_name_length)
        
        print(file_name_length, len(bytes_read))
        
        if len(bytes_read) != file_name_length:
            raise ValueError("Failed to read the full file name")
        
        file_name = struct.unpack("!%ds" % file_name_length, bytes_read)[0].decode("utf-8")
        print(file_name)
        self.send_response(client, status.SUCCESS.value, counter)
        self.db.locate_file(file_name)
    
    def handle_update_message(self, client, address, counter):
        bytes_read = client.recv(1)
        n_files = struct.unpack("!B", bytes_read)[0]
        
        files = []
        for file in range(n_files):
            bytes_read = client.recv(1)
            file_name_length = struct.unpack("!B", bytes_read)[0]
            bytes_read = client.recv(file_name_length)
            file_name = struct.unpack("!%ds" % file_name_length, bytes_read)[0].decode("utf-8")
            
            bytes_read = client.recv(1)
            n_block_sets = struct.unpack("!B", bytes_read)[0]
            
            block_sets_data = []
            for block_set in range(n_block_sets):
                bytes_read = client.recv(2+2+2)
                block_size, last_block_size, full_file = struct.unpack("!HHH", bytes_read)
                
                blocks = []
                if (full_file == 0):
                    bytes_read = client.recv(2)
                    n_blocks = struct.unpack("!H", bytes_read)[0]
                    
                    for _ in range(n_blocks):
                        bytes_read = client.recv(2)
                        blocks.append(struct.unpack("!H", bytes_read)[0])
                
                block_sets_data.append((block_size, last_block_size, full_file, blocks))
            
            files.append((file_name, block_sets_data))
            
        status = self.db.update_node(address[0], files)  
        self.send_response(client, status, counter)                   


def parse_args():
    try:
        parser = argparse.ArgumentParser(description='FS Tracker Command Line Options')
        parser.add_argument('--port', '-p', type=int, default=8080, help='Port to bind the server to')
        parser.add_argument('--host', '-H', type=str, default=None, help='Host IP address to bind the server to')

        args = parser.parse_args()
    
        if args.host is None or args.port is None:
            parser.error("Both --host and --port must be provided.")
    
        return args
    except argparse.ArgumentError as e:
        print(f"Error parsing command line arguments: {e}")
        sys.exit(1)

if __name__ == "__main__":
    file_name = os.path.basename(__file__)
    print(f"Running {file_name}")
    
    args = parse_args()
        
    tracker = FS_Tracker(db="db.sqlite3", port=args.port, host=args.host, debug=True)
    tracker.run()