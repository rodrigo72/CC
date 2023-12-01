import sys
import socket
from threading import Thread
import os
from datetime import datetime
import struct
import argparse
from utils import action, status, join_blocks
from db import DB_manager
import traceback


class FS_Tracker(Thread):
    def __init__(
        self,
        db,
        port=9090,
        address="",
        max_connections=5,
        timeout=60*5,
        debug=False,
    ):
        self.socket = None
        self.db = DB_manager(db, debug)
        self.port = port
        self.address = address
        self.max_connections = max_connections
        self.timeout = timeout
        self.debug = debug
        self.clients = []
        self.threads = []
        self.done = False
        Thread.__init__(self)    
 
    def run(self):
        
        if self.debug:
            print(datetime.now(), "Starting ...")
                
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.socket.bind((self.address, self.port))
        if self.debug:
            print(str(datetime.now()) + " Server socket bound to %s:%s" % (self.address, self.port))

        self.socket.listen(self.max_connections)
        if self.debug:
            print(datetime.now(), "Server socket listening for connections")

        while not self.done:
            client, address = self.socket.accept()
            self.clients.append(client)
            client.settimeout(self.timeout)
            
            print(datetime.now(), "Client connected", address)
            host_name, _, _ = socket.gethostbyaddr(address[0])
            
            if self.debug:
                print(datetime.now(), "Client connected", host_name)

            node_thread = Thread(
                target=self.listen_to_client,
                args=(client, host_name)
            )
            
            node_thread.start()
            self.threads.append(node_thread)

    def stop(self):
        self.done = True
        for thread in self.threads:
            thread.join()

    def listen_to_client(self, client, host_name):
        counter = 0
        leave = False

        while not leave:
            try:
                if self.debug:
                    print(datetime.now(), "Waiting for data from client", host_name)
                    
                bytes_read = client.recv(1)

                if not bytes_read:
                    break

                counter += 1
                decoded_byte = struct.unpack("!B", bytes_read)[0]
                
                if self.debug:
                    print(datetime.now(), "Request received",  action(decoded_byte).name)
                
                request_handlers = {
                    action.UPDATE_FULL_FILES.value: self.handle_update_full_request,
                    action.UPDATE_PARTIAL.value: self.handle_update_partial_request,
                    action.LOCATE_NAME.value: self.handle_locate_name_request,
                    action.LOCATE_HASH.value: self.handle_locate_hash_request,
                    action.CHECK_STATUS.value: self.handle_check_status_request,
                    action.UPDATE_STATUS.value: self.handle_update_status_request,
                }
                
                if decoded_byte == action.LEAVE.value:
                    result = self.db.delete_node(host_name)
                    self.send_response(client, result, counter)
                    leave = True
                elif decoded_byte in request_handlers:
                    request_handlers[decoded_byte](client, host_name, counter)
                else:
                    self.send_response(client, status.INVALID_ACTION.value, counter)
                    break
                
            except Exception as e:
                if self.debug:
                    print("[listen_to_client]", datetime.now(), f"Exception: {type(e).__name__}")
                    print("Error message:", e)
                    print("Traceback:")
                    traceback.print_exc()
                    print("Host name:", host_name, '\n')
                break
            
        self.db.delete_node(host_name)
        client.close()

        if self.debug:
            print(datetime.now(), "Client disconnected", host_name)

        return False
    
    """
    Generic functions
    """
    
    def send_response(self, client, status, counter):
        try:
            flat_data = []
            format_string = "!BBH"
            flat_data.extend([action.RESPONSE.value, status, counter])
            client.sendall(struct.pack(format_string, *flat_data))
            if self.debug:
                print(datetime.now(), "-> Response sent to client")
        except Exception as e:
            if self.debug:
                print("[send_response]", datetime.now(), e, client, '\n')
            return False
        
    """
    Functions to handle requests
    """
    
    def receive_file_hash(self, client):
        file_hash_lenght = struct.unpack("!H", client.recv(2))[0]
        file_hash_data = client.recv(file_hash_lenght)
        file_hash = struct.unpack("!%ds" % file_hash_lenght, 
                                    file_hash_data)[0].hex()
        return file_hash
    
    def receive_file_name(self, client):
        file_name_length = struct.unpack("!B", client.recv(1))[0]
        file_name = struct.unpack("!%ds" % file_name_length,
                                    client.recv(file_name_length))[0].decode("utf-8")
        return file_name
    
    def handle_update_aux(self, client):
        file_hash = self.receive_file_hash(client)
        file_name = self.receive_file_name(client)
        n_block_sets = struct.unpack("!B", client.recv(1))[0]
        return file_hash, file_name, n_block_sets
        
    def handle_update_full_request(self, client, host_name, counter):
        n_files = struct.unpack("!H", client.recv(2))[0]
        files = []
        
        for _ in range(n_files):
            file_hash, file_name, n_block_sets = self.handle_update_aux(client)
            block_sets_data = []
            
            for _ in range(n_block_sets):
                block_size, last_block_size, n_blocks = struct.unpack("!HHH", client.recv(2+2+2))
                block_sets_data.append((block_size, last_block_size, n_blocks))
            
            files.append((file_hash, file_name, block_sets_data))
        
        status = self.db.update_node_full_files(host_name, files)
        
        self.send_response(client, status, counter)

    def handle_update_partial_request(self, client, host_name, counter):
        n_files = struct.unpack("!H", client.recv(2))[0]
        files = []
        
        for _ in range(n_files):
            file_hash, file_name, n_block_sets = self.handle_update_aux(client)
            block_sets_data = []
            
            for _ in range(n_block_sets):
                block_size, last_block_size, n_sequences = struct.unpack("!HHB", client.recv(2+2+1))
                
                sequences = []
                for _ in range(n_sequences):
                    first, last = struct.unpack("!HH", client.recv(2+2))
                    sequences.append((first, last))
                
                n_blocks = struct.unpack("!H", client.recv(2))[0]
                
                blocks = []
                for _ in range(n_blocks):
                    blocks.append(struct.unpack("!H", client.recv(2))[0])
                    
                blocks = join_blocks(sequences, blocks)
                
                block_sets_data.append((block_size, last_block_size, blocks))
            
            files.append((file_name, file_hash, block_sets_data))
                    
        status = self.db.update_node_partial_files(host_name, files)

        self.send_response(client, status, counter)
        
    def handle_locate_name_request(self, client, host_name, counter):
        file_name = self.receive_file_name(client)
                
        results, status_db = self.db.locate_file_name(file_name, host_name)
                
        if status_db != status.SUCCESS.value:
            self.send_response(client, status, counter)
            return
        
        response = self.encode_locate_name_response(results, counter)
        client.sendall(response)
        
        if self.debug:
            print(datetime.now(), "-> Response sent to client")
        
    def handle_locate_hash_request(self, client, host_name, counter):
        file_hash = self.receive_file_hash(client)
        
        results, status_db = self.db.locate_file_hash(file_hash, host_name)
        
        if status_db != status.SUCCESS.value:
            self.send_response(client, status, counter)
            return
        
        response = self.encode_locate_hash_response(results, counter)
        client.sendall(response)
        
        if self.debug:
            print(datetime.now(), "-> Response sent to client")
        
    def handle_check_status_request(self, client, host_name, counter):
        
        host_name_length = struct.unpack("!B", client.recv(1))[0]
        host_name = struct.unpack("!%ds" % host_name_length, 
                                  client.recv(host_name_length))[0].decode("utf-8")
        
        result, status_db = self.db.get_node_status(host_name)
                
        encoded_response = self.encode_check_status_response(status_db, result, counter)
        client.sendall(encoded_response)
        
        if self.debug:
            print(datetime.now(), "-> Response sent to client")
        
    def handle_update_status_request(self, client, host_name, counter):
        status = struct.unpack("!B", client.recv(1))[0]
        result = self.db.update_node_status(host_name, status)
        self.send_response(client, result, counter)
        
        if self.debug:
            print(datetime.now(), "-> Response sent to client")
        
    """
    Functions to encode responses
    """
    
    def encode_locate_name_response(self, results, counter):
                
        host_name_dict = {host_name: i for i, (_, host_name) in enumerate(results, start=1)}
        host_name_dict_len = len(host_name_dict)
        hash_dict = {file_hash: [] for file_hash, _ in results}

        for file_hash, host_name in results:
            hash_dict[file_hash].append(host_name)    
        
        format_string = "!BH"
        flat_data = [action.RESPONSE_LOCATE_NAME.value, host_name_dict_len]
            
        for host_name in host_name_dict.keys():
            host_name_length = len(host_name)
            format_string += "B%ds" % host_name_length
            flat_data.extend([host_name_length, host_name.encode("utf-8")])
            
        n_hashes = len(hash_dict)
        format_string += "H"
        flat_data.append(n_hashes)
        
        for file_hash, host_names in hash_dict.items():
            file_hash_bytes = bytes.fromhex(file_hash)
            file_hash_len = len(file_hash_bytes)
            format_string += "B%dsH" % file_hash_len
            flat_data.extend([file_hash_len, file_hash_bytes, len(host_names)])
            
            for host_name in host_names:
                format_string += "H"
                flat_data.append(host_name_dict[host_name])
                
        format_string += "H"
        flat_data.append(counter)
        
        return struct.pack(format_string, *flat_data)
    
    def encode_locate_hash_response(self, results, counter):
        
        format_string = "!B"
        flat_data = [action.RESPONSE_LOCATE_HASH.value]
        
        host_names = {}
        
        # organize results by host name and division size
        for result in results:
            host_name, block_size, block_number, division_size, is_last = result
            
            if host_names.get(host_name) is None:
                host_names[host_name] = {}
                
            if host_names[host_name].get(division_size) is None:
                host_names[host_name][division_size] = []
                
            host_names[host_name][division_size].append((block_size, block_number, is_last))
        
        # host_name => (division_size => (division_size, last_block_size, is_full_file, block_numbers))
        new_host_names = {}
            
        for host_name, division_size_dict in host_names.items():
            for division_size, block_list in division_size_dict.items():
                
                sorted(block_list, key=lambda x: x[1])
                
                block_list_length = len(block_list)
                last_block = block_list[-1]
                
                if block_list_length == last_block[1]:
                    if new_host_names.get(host_name) is None:
                        new_host_names[host_name] = []
                    new_host_names[host_name].append((division_size, last_block[0], last_block[1], []))
                    
                else:
                    block_numbers = [block[1] for block in block_list]
                    
                    if new_host_names.get(host_name) is None:
                        new_host_names[host_name] = []
                    new_host_names[host_name].append((division_size, last_block[0], 0, block_numbers))
                            
        n_host_names = len(new_host_names)
        
        format_string += "H"
        flat_data.append(n_host_names)
        
        for host_name, division_size_dict in new_host_names.items():
            
            host_name_length = len(host_name)
            sets_len = len(division_size_dict)
            format_string += "B%dsB" % host_name_length
            flat_data.extend([host_name_length, host_name.encode("utf-8"), sets_len])
            
            for division_size, last_block_size, full_file, block_numbers in division_size_dict:

                format_string += "HHH"
                flat_data.extend([division_size, last_block_size, full_file])

                if full_file == 0:
                    format_string += "H"
                    format_string += "H" * len(block_numbers)
                    flat_data.append(len(block_numbers))
                    flat_data.extend(block_numbers)
                    
        format_string += "H"
        flat_data.append(counter)
        
        return struct.pack(format_string, *flat_data)
    
    def encode_check_status_response(self, status_db, result, counter):
        if result is None:
            return struct.pack("!BBBH", action.RESPONSE_CHECK_STATUS.value, status_db, 0, counter)
        return struct.pack("!BBBH", action.RESPONSE_CHECK_STATUS.value, status_db, result, counter)
        
"""
Function to parse command line arguments
"""

def parse_args():
    try:
        parser = argparse.ArgumentParser(description='FS Tracker Command Line Options')
        parser.add_argument('-p', '--port', type=int, default=9090, help='Port to bind the server to')
        parser.add_argument('-d', '--debug', default=False, action='store_true', help='Enable debug mode')
        parser.add_argument('-db','--db',  default="db.sqlite3", help='Database file name')
        parser.add_argument('-m', '--max', type=int, default=5, help='Maximum number of connections')
        parser.add_argument('-t', '--timeout', type=int, default=60*10, help='Timeout for connections')
    
        return parser.parse_args()
    except argparse.ArgumentError as e:
        print(f"Error parsing command line arguments: {e}")
        sys.exit(1)


if __name__ == "__main__":
    file_name = os.path.basename(__file__)
    print(f"Running {file_name}")
    
    args = parse_args()
        
    tracker = FS_Tracker(db=args.db, port=args.port, debug=args.debug, max_connections=args.max, timeout=args.timeout)
    
    try:
        tracker.run()
    except KeyboardInterrupt:
        print("Exiting ...")
        tracker.stop()