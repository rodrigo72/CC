import socket
import threading
import struct
from file_manager import File_manager
import argparse
from utils import action, status


class FS_Node:
    def __init__(
        self,
        dir,
        server_address,
        server_port,
        block_size,
        debug,
        callback=None,
        timeout=60,
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
                else:
                    if self.debug:
                        print("Invalid action")

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
            
    def send_update_message(self):
        encoded_message = self.encode_update_message()
        self.socket.sendall(encoded_message)
        
    def send_leave_message(self):
        self.socket.send(struct.pack("!B", action.LEAVE.value))
        
    def send_locate_message(self, file_name):
        encoded_message = self.encode_locate_message(file_name)
        self.socket.sendall(encoded_message)
        
    def encode_locate_message(self, file_name):
        file_name = file_name.encode("utf-8")
        file_name_len = len(file_name)
        format_string = "!BB%ds" % file_name_len
        flat_data = [action.LOCATE.value, file_name_len, file_name]
        return struct.pack(format_string, *flat_data)
        
    def encode_update_message(self):
        files = self.file_manager.files
        
        format_string = "!BB"
        flat_data = [action.UPDATE.value, len(files)]
        
        for file in files.values():
            file_name = file.name.encode("utf-8")
            file_name_length = len(file_name)
            n_block_sets = len(file.blocks)
            
            format_string += "B%dsB" % file_name_length
            flat_data.extend([file_name_length, file_name, n_block_sets])
            
            for block_size, block_set in file.blocks.items():

                flat_data_aux = []
                last_block_size = block_size
                
                if block_size in file.is_complete:
                    
                    break_flag = False
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
                        
                format_string += "HHH"
                flat_data.extend([block_size, last_block_size, len(block_set)])
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
        while not self.done:
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
                print("Locating ...")
                self.node.send_locate_message(file_name)
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
    
    node_dir = "/home/core/code/fs_nodes_data/"
    if args.dir is not None:
        node_dir += args.dir
    else:
        node_dir += "fs_node_1"
        
    fs_node_1 = FS_Node(
        dir=node_dir,
        server_address=args.address,
        server_port=args.port,
        block_size=1024,
        debug=True,
    )
    
    fs_node_1.file_manager.divide_files()
    fs_node_1.file_manager.scan_files()
   
    node_controller = FS_Node_controller(fs_node_1)
    node_controller_thread = threading.Thread(target=node_controller.run)
    node_controller_thread.start()
    
    fs_node_1.callback = node_controller.set_response_event
    
    fs_node_1.run()
    node_controller_thread.join()
    