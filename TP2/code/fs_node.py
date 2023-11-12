import socket
import threading
import struct
from file_manager import File_manager
import argparse
from utils import action, status
import sys


class FS_Node:
    def __init__(
        self,
        dir,
        server_address,
        server_port,
        block_size,
        debug,
        callback=None,
        timeout=60*5,
    ):
        self.socket = None
        self.dir = dir
        self.server_address = server_address
        self.server_port = server_port
        self.block_size = block_size
        self.debug = debug
        self.file_manager = File_manager(dir, block_size)
        self.callback = callback
        self.done = False
        self.timeout = timeout

    def connect_to_fs_tracker(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_address, self.server_port))
        self.socket.settimeout(self.timeout)
        
    def shutdown(self):
        self.done = True
        if self.socket:
            self.socket.close()
            
    def run(self):
        try:
            self.connect_to_fs_tracker()

            while not self.done:
                data = self.socket.recv(1)

                if not data:
                    break

                data = struct.unpack("!B", data)[0]
                if action.RESPONSE.value == data:
                    self.handle_response()
                elif action.RESPONSE_LOCATE_HASH.value == data:
                    self.handle_locate_hash_response()
                elif action.RESPONSE_LOCATE_NAME.value == data:
                    self.handle_locate_name_response()
                else:
                    if self.debug:
                        print("Invalid action")
        
        except socket.timeout:
            if self.debug:
                print("[run] Socket timeout")
        except Exception as e:
            if self.debug:
                print("[run] Error: ", e)
        finally:
            self.shutdown()
            
    def handle_response(self):
        bytes_read = self.socket.recv(3)
        result_status, counter = struct.unpack("!BH", bytes_read)
        
        print(status(result_status).name, counter)
        
        if self.callback:
            self.callback()
            
    def handle_locate_name_response(self):
        
        n_ips = struct.unpack("!H", self.socket.recv(2))[0]        
        output = {}  # hash -> (ip, block_size, last_block_size, full_file, [blocks])
        ips_dict = {}
        
        for i in range(n_ips):
            ip_bytes = struct.unpack("!BBBB", self.socket.recv(4))
            ip_str = socket.inet_ntoa(bytes(ip_bytes))
            ips_dict[i+1] = ip_str
                        
        n_hashes = struct.unpack("!H", self.socket.recv(2))[0]
        
        for _ in range(n_hashes):
            file_hash_len = struct.unpack("!B", self.socket.recv(1))[0]
            file_hash = self.socket.recv(file_hash_len).hex()
            
            output[file_hash] = []
                        
            n_ips = struct.unpack("!H", self.socket.recv(2))[0]
                                            
            for _ in range(n_ips):
                ip_referece = struct.unpack("!H", self.socket.recv(2))[0]
                n_block_sets = struct.unpack("!B", self.socket.recv(1))[0]
                                
                for _ in range(n_block_sets):
                    block_size, last_block_size, full_file = struct.unpack("!HHH", self.socket.recv(6))
                    blocks = []

                    if full_file == 0:
                        n_blocks = struct.unpack("!H", self.socket.recv(2))[0]
                        for _ in range(n_blocks):
                            block_number = struct.unpack("!H", self.socket.recv(2))[0]
                            blocks.append(block_number)
                            
                    output[file_hash].append((ips_dict[ip_referece], block_size, last_block_size, full_file, blocks))

        counter = struct.unpack("!H", self.socket.recv(2))[0]
        
        for file_hash, data in output.items():
            print(f"\tHash: {file_hash}")
            for ip, block_size, last_block_size, full_file, blocks in data:
                if full_file != 0:
                    print(f"""
                            IPv4 address: {ip}
                            Division size: {block_size}
                            Last block size: {last_block_size}
                            Number of blocks: {full_file}
                        """)
                else:
                    print(f"""
                            IPv4 address: {ip}
                            Division size: {block_size}
                            Last block size: {last_block_size}
                            Number of blocks: {len(blocks)}
                        """)
                print("\n")
        print("Counter: ", counter)
        
        if self.callback:
            self.callback()
                        
    def handle_locate_hash_response(self):
        n_ips = struct.unpack("!H", self.socket.recv(2))[0]
        
        output = {}  # ip -> (block_size, last_block_size, full_file, [blocks])
        
        for _ in range(n_ips):
            ip_bytes = struct.unpack("!BBBB", self.socket.recv(4))
            ip_str = socket.inet_ntoa(bytes(ip_bytes))
            
            n_sets = struct.unpack("!B", self.socket.recv(1))[0]
            output[ip_str] = []
            
            for _ in range(n_sets):
                block_size = struct.unpack("!H", self.socket.recv(2))[0]
                last_block_size = struct.unpack("!H", self.socket.recv(2))[0]
                full_file = struct.unpack("!H", self.socket.recv(2))[0]
                
                blocks = []
                if full_file == 0:
                    n_blocks = struct.unpack("!H", self.socket.recv(2))[0]
                    for _ in range(n_blocks):
                        block_number = struct.unpack("!H", self.socket.recv(2))[0]
                        blocks.append(block_number)
                        
                output[ip_str].append((block_size, last_block_size, full_file, blocks))
                
        counter = struct.unpack("!H", self.socket.recv(2))[0] 
        
        for ip, data in output.items():
            print(f"\tIPv4 address: {ip}")
            for block_size, last_block_size, full_file, blocks in data:
                if full_file != 0:
                    print(f"""
                            Division size: {block_size}
                            Last block size: {last_block_size}
                            Number of blocks: {full_file}
                        """)
                else:
                    print(f"""
                            Division size: {block_size}
                            Last block size: {last_block_size}
                            Number of blocks: {len(blocks)}
                        """)
                print("\n")
        print("Counter: ", counter)
                
        if self.callback:
            self.callback()
                            
    def send_update_message(self):
        encoded_message = self.encode_update_message()
        self.socket.sendall(encoded_message)
        
    def send_leave_message(self):
        self.socket.send(struct.pack("!B", action.LEAVE.value))
        
    def send_locate_message(self, locate_type, data):
        encoded_message = self.encode_locate_message(locate_type, data)
        if encoded_message is not None:
            self.socket.sendall(encoded_message)
        elif self.callback:
            self.callback()
        
    def encode_locate_message(self, locate_type, data):
        
        if self.debug:
            print("Locate type: ", locate_type)
            
        if locate_type == action.LOCATE_NAME.value:
            
            if self.debug:
                print("Locate by name: ", data)
            
            file_name = data.encode("utf-8")
            file_name_len = len(file_name)
            format_string = "!BB%ds" % file_name_len
            flat_data = [locate_type, file_name_len, file_name]
            return struct.pack(format_string, *flat_data)
        
        elif locate_type == action.LOCATE_HASH.value:    
            
            if self.debug:
                print("Locate by hash: ", data)
                
            file_hash = bytes.fromhex(data)
            file_hash_len = len(file_hash)
            format_string = "!BH%ds" % file_hash_len
            flat_data = [locate_type, file_hash_len, file_hash]
            return struct.pack(format_string, *flat_data)
        else:
            if self.debug:
                print("Invalid locate type")
            return None
        
    def encode_update_message(self):
        files = self.file_manager.files
        
        format_string = "!BB"
        flat_data = [action.UPDATE.value, len(files)]
        
        for file in files.values():
            
            file_hash = bytes.fromhex(file.hash_id) if file.hash_id else b""
            file_hash_length = len(file_hash)
            
            file_name = file.name.encode("utf-8")
            file_name_length = len(file_name)
            n_block_sets = len(file.blocks)
            
            format_string += "H%dsB%dsB" % (file_hash_length, file_name_length)
            flat_data.extend([file_hash_length, file_hash, file_name_length, file_name, n_block_sets])
            
            for block_size, block_set in file.blocks.items():

                flat_data_aux = []
                last_block_size = block_size
                
                break_flag = False
                if block_size in file.is_complete:
                    
                    for block in block_set:
                        if block.is_last:
                            format_string += "HHH"
                            flat_data.extend([block_size, block.size, len(block_set)])
                            break_flag = True
                            break;
                
                if break_flag:
                    break
                    
                flat_data_aux = []
                last_block_size = block_size
                for block in block_set:
                    flat_data_aux.append(block.number)
                    if block.is_last:
                        last_block_size = block.size
                        
                format_string += "HHHH"
                flat_data.extend([block_size, last_block_size, 0, len(block_set)])
                format_string += "H" * len(flat_data_aux)
                flat_data.extend(flat_data_aux)
                
        return struct.pack(format_string, *flat_data)
       
            
class FS_Node_controller:
    def __init__(self, node):
        self.response_event = threading.Event()
        self.node = node
        self.done = False
        
    def set_response_event(self):
        self.response_event.set()
        
    def reset_response_event(self):
        self.response_event.clear()
        
    def wait_for_response(self):
        self.response_event.wait()
        self.reset_response_event()
        
    def run(self):
        while not self.done and not self.node.done:
            command = input("Enter a command: ")
            
            if command == "leave" or command == "l":
                print("Leaving ...")
                self.done = True
                self.node.send_leave_message()
                self.wait_for_response()
                self.node.shutdown()
            elif command == "update" or command == "u":
                print("Updating ...")
                self.node.send_update_message()
                self.wait_for_response()
            elif command == "locate" or command == "lo":
                file_name = input("Enter file name: ")
                
                result = self.node.file_manager.get_file_hash_by_name(file_name)
                if result is None:
                    self.node.send_locate_message(action.LOCATE_NAME.value, file_name)
                else:
                    self.node.send_locate_message(action.LOCATE_HASH.value, result)
                
                print("Locating ...")
                self.wait_for_response()
            else:
                print("Invalid command")
  

def parse_args():
    try:
        parser = argparse.ArgumentParser(description='FS Tracker Command Line Options')
        parser.add_argument('--port', type=int, default=8080, help='Port to bind the server to')
        parser.add_argument('--address', '-a', type=str, default=None, help='Host IP address to bind the server to')
        parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
        parser.add_argument('--block_size', '-b', type=int, default=1024, help='Block size')
        parser.add_argument('--dir', '-D', type=str, default=None, help='Directory to store files')
        args = parser.parse_args()
    
        return args
    except argparse.ArgumentError as e:
        print(f"Error parsing command line arguments: {e}")
        return
              
                
if __name__ == "__main__":

    args = parse_args()
    
        
    fs_node_1 = FS_Node(
        dir=args.dir,
        server_address=args.address,
        server_port=args.port,
        block_size=args.block_size,
        debug=True,
    )
    
    fs_node_1.file_manager.run()
   
    node_controller = FS_Node_controller(fs_node_1)
    node_controller_thread = threading.Thread(target=node_controller.run)
    node_controller_thread.start()
    
    fs_node_1.callback = node_controller.set_response_event
    
    fs_node_1.run()
    node_controller_thread.join()
    