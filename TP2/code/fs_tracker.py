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
        timeout=60*10,
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
                elif decoded_byte == action.LOCATE_NAME.value or decoded_byte == action.LOCATE_HASH.value:
                    self.handle_locate_message(client, address, counter, decoded_byte)
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
    
    def handle_locate_message(self, client, address, counter, locate_type):

        results = None
        response = None
        
        if locate_type == action.LOCATE_NAME.value:
            
            if self.debug:
                print(datetime.now(), "Received LOCATE NAME")
            
            file_name_length = struct.unpack("!B", client.recv(1))[0]
            file_name = struct.unpack(
                "!%ds" % file_name_length, 
                client.recv(file_name_length))[0].decode("utf-8")
            
            results = self.db.locate_file_name(file_name, address[0])
            
            if results is None:
                self.send_response(client, status.SERVER_ERROR.value, counter)
                return
                
            if len(results) == 0:
                self.send_response(client, status.NOT_FOUND.value, counter)
                return
                
            response = self.encode_locate_name_response(results, counter)
                       
        elif locate_type == action.LOCATE_HASH.value:
            
            if self.debug:
                print(datetime.now(), "Received LOCATE HASH")
            
            file_hash_length = struct.unpack("!H", client.recv(2))[0]                    
            file_hash = struct.unpack(
                "!%ds" % file_hash_length, 
                client.recv(file_hash_length))[0]
            
            file_hash_hex = file_hash.hex()
            results = self.db.locate_file_hash(file_hash_hex, address[0])   
            
            if results is None:
                self.send_response(client, status.SERVER_ERROR.value, counter)
                return
                
            if len(results) == 0:
                self.send_response(client, status.NOT_FOUND.value, counter)  
                return
                
            response = self.encode_locate_hash_response(results, counter)
    
        else:
            if self.debug:
                print(datetime.now(), "Invalid LOCATE type")
            self.send_response(client, status.INVALID_REQUEST.value, counter)
            return
                
        if response is None or len(response) == 0:
            self.send_response(client, status.NOT_FOUND.value, counter)
        else:
            client.sendall(response)
            
    def encode_locate_name_response(self, results, counter):
        if self.debug:
            print(datetime.now(), "Encoding LOCATE NAME response")
            
        if results is None:
            return None
        
        format_string = "!B"
        flat_data = [action.RESPONSE_LOCATE_NAME.value]
        
        # hash -> ip -> division_size -> [(block_size, block_number, is_last)]
        hashes = {}
        ip_set = set()
        
        for result in results:
            ip, block_size, block_number, division_size, is_last, file_hash = result
            
            ip_set.add(ip)
            
            if hashes.get(file_hash) is None:
                hashes[file_hash] = {}
                
            if hashes[file_hash].get(ip) is None:
                hashes[file_hash][ip] = {}

            if hashes[file_hash][ip].get(division_size) is None:
                hashes[file_hash][ip][division_size] = []
                
            hashes[file_hash][ip][division_size].append((block_size, block_number, is_last))
            
        # hash -> ip -> division_size -> (division_size, last_block_size, is_full_file, block_numbers)
        new_hashes = {}
        
        for file_hash, ip_dict in hashes.items():            
            for ip, division_size_dict in ip_dict.items():
                for division_size, block_list in division_size_dict.items():
                    
                    sorted(block_list, key=lambda x: x[1])
                    
                    block_list_length = len(block_list)
                    last_block = block_list[-1]
                    
                    if block_list_length == last_block[1]:
                        if new_hashes.get(file_hash) is None:
                            new_hashes[file_hash] = {}
                        if new_hashes[file_hash].get(ip) is None:
                            new_hashes[file_hash][ip] = []
                        new_hashes[file_hash][ip].append((division_size, last_block[0], last_block[1], []))
                        
                    else:
                        block_numbers = [block[1] for block in block_list]
                        
                        if new_hashes.get(file_hash) is None:
                            new_hashes[file_hash] = {}
                        if new_hashes[file_hash].get(ip) is None:
                            new_hashes[file_hash][ip] = []
                        new_hashes[file_hash][ip].append((division_size, last_block[0], 0, block_numbers))
                
        n_hashes = len(new_hashes)
        n_ips = len(ip_set)
        ips_map = {ip: i for i, ip in enumerate(ip_set, start=1)}

        format_string += "H"
        flat_data.append(n_ips)
        
        for ip, _ in ips_map.items():
            ip_bytes = socket.inet_aton(ip)
            format_string += "BBBB"
            flat_data.extend(ip_bytes)
            
        format_string += "H"
        flat_data.append(n_hashes)
        
        for file_hash, ip_dict in new_hashes.items():
            file_hash_bytes = bytes.fromhex(file_hash)
            file_hash_length = len(file_hash_bytes)

            n_ids = len(ip_dict)
                        
            format_string += "B%dsH" % file_hash_length
            flat_data.extend([file_hash_length, file_hash_bytes, n_ids])
            
            for ip, division_size_dict in ip_dict.items():
                ip_id = ips_map[ip]
                n_block_sets = len(division_size_dict)
                format_string += "HB"
                flat_data.extend([ip_id, n_block_sets])
                
                for division_size, last_block_size, full_file, block_numbers in division_size_dict:
                    format_string += "HHH"
                    flat_data.extend([division_size, last_block_size, full_file])
                    
                    if full_file == 0:
                        format_string += "H"
                        flat_data.append(len(block_numbers))
                        format_string += "H" * len(block_numbers)
                        flat_data.extend(block_numbers)
    
        format_string += "H"
        flat_data.append(counter)
            
        print(format_string, "\n", flat_data)
                
        return struct.pack(format_string, *flat_data)
    
    def encode_locate_hash_response(self, results, counter):
        if self.debug:
            print(datetime.now(), "Encoding LOCATE HASH response")
            
        if results is None:
            return None
        
        format_string = "!B"
        flat_data = [action.RESPONSE_LOCATE_HASH.value]
        
        # ip => (division_size => (block_size, block_number, is_last))
        ips = {}
        
        for result in results:
            ip, block_size, block_number, division_size, is_last = result
            
            if ips.get(ip) is None:
                ips[ip] = {}
                
            if ips[ip].get(division_size) is None:
                ips[ip][division_size] = []
                
            ips[ip][division_size].append((block_size, block_number, is_last))
        
        # ip => (division_size => (division_size, last_block_size, is_full_file, block_numbers))
        new_ips = {}
        
            
        for ip, division_size_dict in ips.items():
            for division_size, block_list in division_size_dict.items():
                
                sorted(block_list, key=lambda x: x[1])
                
                block_list_length = len(block_list)
                last_block = block_list[-1]
                
                if block_list_length == last_block[1]:
                    if new_ips.get(ip) is None:
                        new_ips[ip] = []
                    new_ips[ip].append((division_size, last_block[0], last_block[1], []))
                    
                else:
                    block_numbers = [block[1] for block in block_list]
                    
                    if new_ips.get(ip) is None:
                        new_ips[ip] = []
                    new_ips[ip].append((division_size, last_block[0], 0, block_numbers))
                            
        n_ips = len(new_ips)
        
        format_string += "H"
        flat_data.append(n_ips)
        
        for ip, division_size_dict in new_ips.items():
            
            ip_bytes = socket.inet_aton(ip)
            sets_len = len(division_size_dict)
            format_string += "BBBBB"
            flat_data.extend([*ip_bytes, sets_len])
            
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
    
    def handle_update_message(self, client, address, counter):
        bytes_read = client.recv(1)
        n_files = struct.unpack("!B", bytes_read)[0]
        
        files = []
        for _ in range(n_files):
            bytes_read = client.recv(2)
            file_hash_length = struct.unpack("!H", bytes_read)[0]
            bytes_read = client.recv(file_hash_length)            
            file_hash = struct.unpack("!%ds" % file_hash_length, bytes_read)[0]
            file_hash_hex = file_hash.hex()
            
            bytes_read = client.recv(1)
            file_name_length = struct.unpack("!B", bytes_read)[0]
            bytes_read = client.recv(file_name_length)
            file_name = struct.unpack("!%ds" % file_name_length, bytes_read)[0].decode("utf-8")
            
            bytes_read = client.recv(1)
            n_block_sets = struct.unpack("!B", bytes_read)[0]
            
            block_sets_data = []
            for _ in range(n_block_sets):
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
            
            files.append((file_name, file_hash_hex, block_sets_data))
            
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