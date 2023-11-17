import socket
import threading
import struct
from file_manager import File_manager
import argparse
from utils import action, status, action_udp, Queue_dictionary, join_blocks
import traceback
from queue import Queue
import time
        
        
class UDP_receiver_connection:
    def __init__(self, host, port, start_seq_num, file_name, division_size, file_manager, debug=False, buffer_size=4):
        self.host = host
        self.port = port
        self.current_seq_num = start_seq_num - 1
        self.debug = debug
        self.buffer_size = buffer_size
        self.seq_nums = set()
        self.updated = time.time()
        self.file_name = file_name
        self.division_size = division_size
        self.file_manager = file_manager
        
    def ack(self, seq_num, block_number, is_last, data):
        self.updated = time.time()
        
        if seq_num > self.current_seq_num and seq_num <= self.current_seq_num + self.buffer_size:
            self.seq_nums.add(seq_num)
            keys = sorted(self.seq_nums)
            for n in keys:
                if n == self.current_seq_num + 1:
                    self.current_seq_num += 1  
                    self.file_manager.save_block(self.file_name, self.division_size, block_number, is_last, data)
                    self.seq_nums.remove(n)
                else:
                    break  # out of order seq_num
                
        return self.current_seq_num + 1
    
    def reset(self, start_seq_num):
        self.current_seq_num = start_seq_num - 1
        self.seq_nums.clear()
        self.updated = time.time()
    

class FS_Node:
    def __init__(
        self,
        dir,
        server_address,
        port,
        block_size,
        debug,
        callback=None,
        timeout=60*5,
        udp_timeout=60*5,
        udp_host="",
        udp_port=9090,
        udp_max_buffer_size=1400,
        udp_receiver_window_size=4,
        udp_receiver_connection_timeout=5,
        udp_ack_timeout=0.4
    ):
        # TCP   
        self.socket = None
        self.dir = dir
        self.server_address = server_address
        self.port = port
        self.block_size = block_size
        self.debug = debug
        self.file_manager = File_manager(dir, block_size)
        self.callback = callback
        self.done = False
        self.timeout = timeout
        self.response_queue = Queue()
        self.udp_response_queue = Queue()
        
        # UDP
        self.udp_max_buffer_size = udp_max_buffer_size
        self.udp_timeout = udp_timeout
        self.udp_socket = None
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.udp_thread = threading.Thread(target=self.run_udp_receiver)
        self.udp_ack_timeout = udp_ack_timeout
        
        self.udp_receiver_window_size = udp_receiver_window_size
        
        self.udp_ack_queue = Queue_dictionary() # receives acks from other nodes' get requests
        self.udp_receiver_connections = {}  # sends acks upon received data
        self.udp_threads = {}  # sends data according to other nodes' get requests
        
        self.udp_last_receiver_connections_cleanup = time.time()
        self.udp_receiver_connection_timeout = udp_receiver_connection_timeout
        
        self.lock = threading.Lock()
        
    """
    UDP functions
    """
        
    def create_udp_socket(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        self.udp_socket.settimeout(self.udp_timeout)
        self.udp_socket.bind((self.udp_host, self.udp_port))
    
    def run_udp_receiver(self):
        while not self.done:
            try:
                                
                bytes_read, address = self.udp_socket.recvfrom(self.udp_max_buffer_size)
                
                if self.done or not bytes_read:
                    break        
                
                decoded_flag = struct.unpack("!B", bytes_read[0:1])[0]  
                
                if self.debug and decoded_flag != action_udp.ACK.value:
                    print(" >>> Received UDP packet from %s:%d with flag %s" % (address[0], address[1], action_udp(decoded_flag).name))                      
                
                # ACK
                udp_action_handlers = {
                    action_udp.ACK.value: self.udp_ack_flag_handler,
                    action_udp.GET_FULL_FILE.value: self.udp_get_full_file_flag_handler,
                    action_udp.GET_PARTIAL_FILE.value: self.udp_get_partial_file_flag_handler,
                    action_udp.START_DATA.value: self.udp_start_data_flag_handler,
                    action_udp.START_END_DATA.value: self.udp_start_data_flag_handler,
                    action_udp.DATA.value: self.udp_data_flag_handler,
                    action_udp.END_DATA.value: self.udp_end_data_flag_handler,
                }

                decoded_flag = bytes_read[0]

                if decoded_flag in udp_action_handlers:
                    udp_action_handlers[decoded_flag](bytes_read, address)
                else:
                    if self.debug:
                        print(" >>> Invalid action received")

                if time.time() - self.udp_last_receiver_connections_cleanup > self.udp_receiver_connection_timeout:
                    self.udp_receiver_connections_cleanup()
                         
            except Exception as e:
                if self.debug:
                    print("[run_udp_receiver] Error message:", e)
                    print("Traceback:")
                    traceback.print_exc()
                break
            
    """
    Flag handlers
    """
    
    def udp_ack_flag_handler(self, bytes_read, address):
        ack_num = struct.unpack("!H", bytes_read[1:3])[0]
        if self.debug:
            print(" >>> Received ack with ack_num %d" % (ack_num))
        self.udp_ack_queue.put(address, ack_num)
        
    def udp_get_full_file_flag_handler(self, bytes_read, address):
        packet = self.decode_udp_get_full_file(bytes_read[1:])
        if self.debug:
            print(" >>> Packet: ", packet)
        
        file_hash, division_size = packet
        
        block_numbers = self.file_manager.get_all_block_numbers(file_hash, division_size)
        
        thread = threading.Thread(
            target=self.send_udp_blocks, 
            args=(address, file_hash, division_size, block_numbers)
        )
        
        with self.lock:
            if self.udp_threads.get(address) is not None:
                if self.debug:
                    print(" >>> Thread with address %s:%d already exists." % (address[0], address[1]))
                    print(" >>> Request ignored.")
            else:                     
                self.udp_threads[address] = thread
                thread.start()
                
    def udp_get_partial_file_flag_handler(self, bytes_read, address):
        packet = self.decode_udp_get_partial_file(bytes_read[1:])
        if self.debug:
            print(" >>> Packet: ", packet)
        
        file_hash, division_size, sequences, blocks = packet
        
        block_numbers = join_blocks(sequences, blocks)
        
        thread = threading.Thread(
            target=self.send_udp_blocks,
            args=(address, file_hash, division_size, block_numbers)
        )
        
        with self.lock:
            if self.udp_threads.get(address) is not None:
                if self.debug:
                    print(" >>> Thread with address %s:%d already exists." % (address[0], address[1]))
                    print(" >>> Request ignored.")
            else:                     
                self.udp_threads[address] = thread
                thread.start()
                
    def udp_start_data_flag_handler(self, bytes_read, address):
        packet = self.decode_udp_start_data_message(bytes_read[1:])
        if self.debug:
            print(" >>> Received packet: ", packet[:-1])
        self.handle_udp_start_data(address, packet)
        
    def udp_start_end_data_flag_handler(self, bytes_read, address):
        _, file_name, div_size, block_number, data = self.decode_udp_start_data_message(bytes_read[1:])
        if self.debug:
            print(" >>> Received packet: ", (file_name, div_size, block_number))
        self.file_manager.save_block(file_name, div_size, block_number, True, data)
        
    def udp_data_flag_handler(self, bytes_read, address):
        packet = self.decode_udp_data_message(bytes_read[1:])
        if self.debug:
            print(" >>> Received packet: ", packet[:-1])
        self.handle_udp_data(address, packet)
        
    def udp_end_data_flag_handler(self, bytes_read, address):
        self.udp_data_flag_handler(bytes_read, address)
        
        with self.lock:
            file_name = None
            if address in self.udp_receiver_connections:
                file_name = self.udp_receiver_connections[address].file_name
            self.udp_response_queue.put((address, file_name, status.SUCCESS.value))
            
    """
    Send blocks
    """
            
    def send_udp_blocks(self, address, file_hash, division_size, block_numbers):
        
        seq_num = 1
        is_last = False
        with self.lock:
            self.udp_ack_queue.init(address)
                    
        while not is_last:

            max_timeout_retries = 5
            block_number = block_numbers.pop(0)
            file_name, data = self.file_manager.get_block_with_file_hash(file_hash, division_size, block_number)
            
            if len(block_numbers) == 0:
                is_last = True
                
            packet = None
            if seq_num == 1 and is_last:
                packet = self.encode_udp_start_data_message(
                    action_udp.START_END_DATA.value, seq_num, file_name, division_size, block_number,data
                )
            elif seq_num == 1:
                packet = self.encode_udp_start_data_message(
                    action_udp.START_DATA.value, seq_num, file_name, division_size, block_number, data
                )
            elif is_last:
                packet = self.encode_udp_data_message(
                    action_udp.END_DATA.value, seq_num, block_number, data
                )
            else:
                packet = self.encode_udp_data_message(
                    action_udp.DATA.value, seq_num, block_number, data
                )
                
            if self.debug:
                print(" >>> Sending packet: ", (seq_num, block_number, is_last))
                
            self.udp_socket.sendto(packet, address)
            
            expected_ack = seq_num + 1
            
            while max_timeout_retries:
                received_ack = self.udp_ack_queue.get(address, self.udp_ack_timeout)
                
                if received_ack is not None:
                    
                    if received_ack == expected_ack:  # last seq num sent
                        if self.debug:
                            print(" >>> [ received %d == expected %d ]" % (received_ack, expected_ack))
                        break
                    elif received_ack > expected_ack:  # node already received the packet
                        if self.debug:
                            print(" >>> [ (out of order) received %d > expected %d ]" % (received_ack, expected_ack))
                    elif received_ack < expected_ack:  # duplicated packet probably => ignore
                        if self.debug:
                            print(" >>> [ (probably duplicated) received %d < expected %d ]" % (received_ack, expected_ack))
                        continue

                else:
                    
                    if self.debug:
                        print(" >>> (timeout) Resending packet: ", (seq_num, block_number, is_last))
                    
                    max_timeout_retries -= 1
                    
                    self.udp_socket.sendto(packet, address)
            
            seq_num += 1
            
        with self.lock:
            self.udp_threads.pop(address)
    
    """
    UDP handle functions
    """
    
    def handle_udp_start_data(self, address, packet):
        seq_num, file_name, division_size, block_number, data = packet
        if address not in self.udp_receiver_connections:
            self.udp_receiver_connections[address] = UDP_receiver_connection(
                address[0],
                address[1],
                seq_num,
                file_name,
                division_size,
                self.file_manager,
                buffer_size=self.udp_receiver_window_size,
                debug=self.debug
            )      
            if self.debug:
                print(" >>> Created new UDP receiver connection with address %s:%d" % (address[0], address[1]))
        else:
            conn = self.udp_receiver_connections[address]
            conn.reset(seq_num)
        
        self.handle_udp_data(address, (seq_num, block_number, data))

    def handle_udp_data(self, address, packet, is_last=False):
        seq_num, block_number, data = packet
        
        if address in self.udp_receiver_connections:
            conn = self.udp_receiver_connections[address]
            ack_num = conn.ack(seq_num, block_number, is_last, data)            
            self.send_udp_ack(address, ack_num)
    """
    UDP decode functions
    """
    
    def decode_udp_get_full_file(self, bytes_read):
        
        start = 0; end = 1
        hash_len = struct.unpack("!B", bytes_read[start:end])[0]
        
        start = end; end += hash_len
        file_hash = bytes_read[start:end].hex()
        
        start = end; end += 2
        division_size = struct.unpack("!H", bytes_read[start:end])[0]
        
        return file_hash, division_size
    
    def decode_udp_get_partial_file(self, bytes_read):
                
        start = 0; end = 1
        hash_len = struct.unpack("!B", bytes_read[start:end])[0]
                
        start = end; end += hash_len
        file_hash = bytes_read[start:end].hex()
                
        start = end; end += 2
        division_size = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 1
        n_seq = struct.unpack("!B", bytes_read[start:end])[0]
        sequences = []
        for _ in range(n_seq):
            start = end; end += 4
            first, last = struct.unpack("!HH", bytes_read[start:end])
            sequences.append((first, last))
            
        start = end; end += 2
        n_blocks = struct.unpack("!H", bytes_read[start:end])[0]
        blocks = []
        for _ in range(n_blocks):
            start = end; end += 2
            block_number = struct.unpack("!H", bytes_read[start:end])[0]
            blocks.append(block_number)
        
        return file_hash, division_size, sequences, blocks
    
    def decode_udp_start_data_message(self, bytes_read):
            
        start = 0; end = 2
        seq_num = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 1
        file_name_len = struct.unpack("!B", bytes_read[start:end])[0]
                    
        start = end; end += file_name_len
        file_name = bytes_read[start:end].decode("utf-8")
        
        start = end; end += 2
        division_size = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 2
        block_number = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 4
        data_len = struct.unpack("!L", bytes_read[start:end])[0]
        
        start = end; end += data_len
        data = bytes_read[start:end]
        
        return seq_num, file_name, division_size, block_number, data
    
    def decode_udp_data_message(self, bytes_read):
            
        start = 0; end = 2
        seq_num = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 2
        block_number = struct.unpack("!H", bytes_read[start:end])[0]
        
        start = end; end += 4
        data_len = struct.unpack("!L", bytes_read[start:end])[0]
        
        start = end; end += data_len
        data = bytes_read[start:end]
        
        return seq_num, block_number, data
    
    """
    UDP encode functions
    """
    
    def encode_udp_get_full_file_request(self, file_hash, division_size):
        
        file_hash = bytes.fromhex(file_hash)
        file_hash_length = len(file_hash)
        
        format_string = "!BB%dsH" % file_hash_length
        flat_data = [action_udp.GET_FULL_FILE.value, file_hash_length, file_hash, division_size]
        
        return struct.pack(format_string, *flat_data)
    
    def encode_udp_get_partial_file_request(self, file_hash, division_size, sequences, blocks):
            
        file_hash = bytes.fromhex(file_hash)
        file_hash_length = len(file_hash)
        
        format_string = "!BB%dsH" % file_hash_length
        flat_data = [action_udp.GET_PARTIAL_FILE.value, file_hash_length, file_hash, division_size]
        
        format_string += "B"
        flat_data.append(len(sequences))
        
        format_string += "HH" * len(sequences)
        flat_data.extend([value for sequence in sequences for value in sequence])
        
        format_string += "H"
        flat_data.append(len(blocks))
        
        format_string += "H" * len(blocks)
        flat_data.extend(blocks)
        
        return struct.pack(format_string, *flat_data)
    
    def encode_udp_start_data_message(self, flag, seq_num, file_name, division_size, block_number, data):  # data is in bytes
            
        file_name = file_name.encode("utf-8")
        file_name_length = len(file_name)
        
        data_len = len(data)
        format_string = "!BHB%dsHHL%ds" % (file_name_length, data_len)
        flat_data = [flag, seq_num, file_name_length, file_name, division_size, block_number, data_len, data]
                    
        return struct.pack(format_string, *flat_data)
    
    def encode_udp_data_message(self, flag, seq_num, block_number, data): # data is bytes
        
        format_string = "!BHHL"
        flat_data = [flag, seq_num, block_number, len(data)]
        
        format_string += "%ds" % len(data)
        flat_data.append(data)
                
        return struct.pack(format_string, *flat_data)
       
    """
    UDP send functions
    """   
    
    def send_udp_ack(self, address, ack_num):
        encoded_data = struct.pack("!BH", action_udp.ACK.value, ack_num)
        self.udp_socket.sendto(encoded_data, address) 
        if self.debug:
            print(" >>> Sending ack with ack_num %d" % (ack_num))
        
    def send_udp_get_full_file_request(self, address, file_hash, division_size):
        encoded_data = self.encode_udp_get_full_file_request(file_hash, division_size)
        self.udp_socket.sendto(encoded_data, address)
        
    def send_udp_get_partial_file_request(self, address, file_hash, division_size, sequences, blocks):
        encoded_data = self.encode_udp_get_partial_file_request(file_hash, division_size, sequences, blocks)
        self.udp_socket.sendto(encoded_data, address)
        
    def send_udp_start_data_message(self, address, flag, seq_num, file_name, division_size, block_number, data):
        encoded_data = self.encode_udp_start_data_message(flag, seq_num, file_name, division_size, block_number, data)
        self.udp_socket.sendto(encoded_data, address)
        
    def send_udp_data_message(self, address, flag, seq_num, block_number, data):
        encoded_data = self.encode_udp_data_message(flag, seq_num, block_number, data)
        self.udp_socket.sendto(encoded_data, address)
        
    """
    Other UDP functions
    """
    
    def udp_receiver_connections_cleanup(self):
        if self.debug:
            print(" >>> Cleaning up UDP receiver connections ...")
            
        now = time.time()

        keys = [k for k, v in self.udp_receiver_connections.items()]
        for address in keys:
            conn = self.udp_receiver_connections[address]
            if now - conn.updated > self.udp_receiver_connection_timeout:
                if self.debug:
                    print(" >>> Receiver connection with address %s:%d terminated (%.2f old)." % (address[0], address[1], now - conn.updated))
                del self.udp_receiver_connections[address]
        self.udp_last_receiver_connections_cleanup = now
     
    """
    Shutdown
    """
    
    def shutdown(self):
        if self.debug:
            print("Shutting down ...")
            
        self.done = True
        if self.socket:
            self.socket.close()
            
        self.udp_socket.sendto(b"", ("", self.port))  # to "unlock" recvfrom
        self.udp_thread.join()   
        
        for thread in self.udp_threads.values():
            thread.join()
        
        if self.udp_socket:
            self.udp_socket.close()
            
            
        self.file_manager.reset_block_dir()
    
    """
    ------------------------------------
            FS_Tracker functions
    ------------------------------------
    """
    
    def connect_to_fs_tracker(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_address, self.port))
        self.socket.settimeout(self.timeout)
                        
    def run(self):
        try:
            self.connect_to_fs_tracker()
            self.create_udp_socket()
            self.udp_thread.start()

            while not self.done:
                bytes_read = self.socket.recv(1)

                if not bytes_read:
                    break

                decoded_byte = struct.unpack("!B", bytes_read)[0]
                
                response_handlers = {
                    action.RESPONSE.value: self.handle_response,
                    action.RESPONSE_LOCATE_HASH.value: self.handle_locate_hash_response,
                    action.RESPONSE_LOCATE_NAME.value: self.handle_locate_name_response,
                    action.RESPONSE_CHECK_STATUS.value: self.handle_check_status_response,
                }

                if decoded_byte in response_handlers:
                    response_handlers[decoded_byte]()
                else:
                    if self.debug:
                        print("Invalid action")
                    break
        
        except socket.timeout:
            if self.debug:
                print("[run] Socket timeout")
        except Exception as e:
            if self.debug:
                    print("[run] Error message:", e)
                    print("Traceback:")
                    traceback.print_exc()
        finally:
            self.shutdown()
           
    """
    Functions that handle responses from the tracker
    """       
     
    def handle_response(self):
        result_status, counter = struct.unpack("!BH", self.socket.recv(3))
        self.response_queue.put((result_status, counter))
            
    def handle_locate_hash_response(self):
        n_ips = struct.unpack("!H", self.socket.recv(2))[0]
        
        output_full_files = {}  # ip -> (block_size, last_block_size, full_file, [blocks])
        output_partial_files = {}
        
        for _ in range(n_ips):
            ip_bytes = struct.unpack("!BBBB", self.socket.recv(4))
            ip_str = socket.inet_ntoa(bytes(ip_bytes))
            
            n_sets = struct.unpack("!B", self.socket.recv(1))[0]
            
            for _ in range(n_sets):
                block_size = struct.unpack("!H", self.socket.recv(2))[0]
                last_block_size = struct.unpack("!H", self.socket.recv(2))[0]
                full_file = struct.unpack("!H", self.socket.recv(2))[0]
                
                if full_file == 0:
                    blocks = []
                    n_blocks = struct.unpack("!H", self.socket.recv(2))[0]
                    for _ in range(n_blocks):
                        block_number = struct.unpack("!H", self.socket.recv(2))[0]
                        blocks.append(block_number)
                        
                    if output_partial_files.get(ip_str) is None:
                        output_partial_files[ip_str] = []
                        
                    output_partial_files[ip_str].append((block_size, last_block_size, blocks))
                else:     
                    if output_full_files.get(ip_str) is None:
                        output_full_files[ip_str] = []
                    output_full_files[ip_str].append((block_size, last_block_size, full_file))
                                        
        counter = struct.unpack("!H", self.socket.recv(2))[0] 
        self.response_queue.put((output_full_files, output_partial_files, counter))            
        
    def handle_locate_name_response(self):
        n_ips = struct.unpack("!H", self.socket.recv(2))[0]
        ips_dict = {}
        
        output = {}  # hash -> [ip]
        
        for i in range(n_ips):
            ip_bytes = struct.unpack("!BBBB", self.socket.recv(4))
            ip_str = socket.inet_ntoa(bytes(ip_bytes))
            ips_dict[i+1] = ip_str
            
        n_hashes = struct.unpack("!H", self.socket.recv(2))[0]
        
        for _ in range(n_hashes):
            file_hash_length = struct.unpack("!B", self.socket.recv(1))[0]
            file_hash = self.socket.recv(file_hash_length).hex()
            
            output[file_hash] = []
            
            n_ips_with_hash = struct.unpack("!H", self.socket.recv(2))[0]
            
            for _ in range(n_ips_with_hash):
                ip_reference = struct.unpack("!H", self.socket.recv(2))[0]
                output[file_hash].append(ips_dict[ip_reference])
        
        counter = struct.unpack("!H", self.socket.recv(2))[0]    
        self.response_queue.put((output, counter))
    
    def handle_check_status_response(self):
        status_db, result, counter = struct.unpack("!BBH", self.socket.recv(1+1+2))
        self.response_queue.put((status_db, result, counter))
    
    """
    Functions that send messages to the tracker
    """
    
    def send_leave_request(self):  # receives a normal response
        self.socket.sendall(struct.pack("!B", action.LEAVE.value))
        
    def send_update_full_request(self, files):  # receives a normal response
        encoded_request = self.encode_update_full_request(files)
        self.socket.sendall(encoded_request)
    
    def send_update_partial_request(self, files):  # receives a normal response
        encoded_request = self.encode_update_partial_request(files)
        self.socket.sendall(encoded_request)
    
    def send_update_status_request(self, s):  # receives a normal response
        self.socket.sendall(struct.pack("!BB", action.UPDATE_STATUS.value, s))
    
    def send_locate_hash_request(self, file_hash):  # receives a locate hash response
        encoded_request = self.encode_locate_hash_request(file_hash)
        self.socket.sendall(encoded_request)
    
    def send_locate_name_request(self, file_name):  # receives a locate name response
        encoded_request = self.enconde_locate_name_request(file_name)
        self.socket.sendall(encoded_request)
    
    def send_check_status_request(self, ip):  # receives a check status response
        encoded_request = self.encode_check_status_request(ip)
        self.socket.sendall(encoded_request)
    
    """
    Functions that encode messages to send to the tracker
    """
    
    def encode_update_full_request(self, files):
        
        n_files = len(files)
        format_string = "!BH"
        flat_data = [action.UPDATE_FULL_FILES.value, n_files]
        
        for file in files:
            file_hash, file_name, block_sets = file    
        
            file_hash = bytes.fromhex(file_hash)
            file_hash_length = len(file_hash)
            file_name = file_name.encode("utf-8")
            file_name_length = len(file_name)
            n_block_sets = len(block_sets)

            format_string += "H%dsB%dsB" % (file_hash_length, file_name_length)
            flat_data.extend([file_hash_length, file_hash, file_name_length, file_name, n_block_sets])
            
            for block in block_sets:
                division_size, last_block_size, n_blocks = block
                format_string += "HHH"
                flat_data.extend([division_size, last_block_size, n_blocks])
                        
        return struct.pack(format_string, *flat_data)

    def encode_update_partial_request(self, files):
        
        n_files = len(files)
        format_string = "!BH"
        flat_data = [action.UPDATE_PARTIAL.value, n_files]
        
        for file in files:
            file_hash, file_name, block_sets = file
        
            file_hash = bytes.fromhex(file_hash)
            file_hash_length = len(file_hash)
            file_name = file_name.encode("utf-8")
            file_name_length = len(file_name)
            n_block_sets = len(block_sets)

            format_string += "H%dsB%dsB" % (file_hash_length, file_name_length)
            flat_data.extend([file_hash_length, file_hash, file_name_length, file_name, n_block_sets])
            
            for block in block_sets:
                division_size, last_block_size, sequences, blocks = block
                format_string += "HHB"
                flat_data.extend([division_size, last_block_size, len(sequences)])
                for sequence in sequences:
                    format_string += "HH"
                    flat_data.extend([sequence[0], sequence[1]])
                n_blocks = len(blocks)
                format_string += "H"
                flat_data.append(n_blocks)
                for block_number in blocks:
                    format_string += "H"
                    flat_data.append(block_number)
                        
        return struct.pack(format_string, *flat_data)
        
    
    def encode_check_status_request(self, ip):
        
        ip_bytes = socket.inet_aton(ip)
        format_string = "!BBBBB"
        flat_data = [action.CHECK_STATUS.value]
        flat_data.extend(ip_bytes)
        
        return struct.pack(format_string, *flat_data)
    
    def encode_locate_hash_request(self, file_hash):
        
        file_hash = bytes.fromhex(file_hash)
        file_hash_length = len(file_hash)
        format_string = "!BH%ds" % file_hash_length
        flat_data = [action.LOCATE_HASH.value, file_hash_length, file_hash]
        
        return struct.pack(format_string, *flat_data)
    
    def enconde_locate_name_request(self, file_name):

        file_name = file_name.encode("utf-8")
        file_name_length = len(file_name)
        format_string = "!BB%ds" % file_name_length
        flat_data = [action.LOCATE_NAME.value, file_name_length, file_name]
        
        return struct.pack(format_string, *flat_data)
    
    def encode_all_files(self):
        
        files = self.file_manager.files
        
        format_string_uf = "!BH"
        flat_data_uf = [action.UPDATE_FULL_FILES.value, 0]
        n_files_uf = 0
        
        format_string_up = "!BH"
        flat_data_up = [action.UPDATE_PARTIAL.value, 0]
        n_files_up = 0
                
        for file in files.values():
            
            file_hash = bytes.fromhex(file.hash_id) if file.hash_id else b""
            file_hash_length = len(file_hash)
            
            file_name = file.name.encode("utf-8")
            file_name_length = len(file_name)
            
            file_included_uf = False
            n_block_sets_uf = 0
            block_sets_uf_format_string = ""
            block_sets_uf = []
            
            file_included_up = False
            n_block_sets_up = 0
            block_sets_up_format_string = ""
            block_sets_up = []
            
            for division_size, block_set in file.blocks.items():
                
                if len(block_set) == 0:
                    continue
                
                break_flag = False                
                if division_size in file.is_complete:
                    for block in block_set:
                        if block.is_last:
                            
                            if not file_included_uf:
                                file_included_uf = True
                                n_files_uf += 1
                            
                            n_block_sets_uf += 1
                                
                            block_sets_uf_format_string += "HHH"
                            block_sets_uf.extend([division_size, block.size, len(block_set)])
                            break_flag = True
                            
                if break_flag:
                    break
                
                if not file_included_up:
                    file_included_up = True
                    n_files_up += 1
                
                aux = []
                last_block_size = division_size
                for block in block_set:
                    aux.append(block.number)
                    if block.is_last:
                        last_block_size = block.size
                        
                block_sets_up_format_string += "B"
                block_sets_up.append(0)
                        
                n_block_sets_up += 1
                block_sets_up_format_string += "HHH"
                block_sets_up.extend([division_size, last_block_size, len(block_set)])
                

            if n_block_sets_uf > 0:
                format_string_uf += "H%dsB%ds" % (file_hash_length, file_name_length)
                flat_data_uf.extend([file_hash_length, file_hash, file_name_length, file_name])

                format_string_uf += "B"
                flat_data_uf.append(n_block_sets_uf)

                format_string_uf += block_sets_uf_format_string
                flat_data_uf.extend(block_sets_uf)

            if n_block_sets_up > 0:
                format_string_up += "H%dsB%ds" % (file_hash_length, file_name_length)
                flat_data_up.extend([file_hash_length, file_hash, file_name_length, file_name])
                
                format_string_up += "B"
                flat_data_up.append(n_block_sets_up)

                format_string_up += block_sets_up_format_string
                flat_data_up.extend(block_sets_up)
        
        uf_packed_data = None
        up_packed_data = None
        
        if len(format_string_uf) > 3:
            flat_data_uf[1] = n_files_uf
            uf_packed_data = struct.pack(format_string_uf, *flat_data_uf)        
            
        if len(format_string_up) > 3:
            flat_data_up[1] = n_files_up
            up_packed_data = struct.pack(format_string_up, *flat_data_up)
            
        return uf_packed_data, up_packed_data
    
    """
    Algorithms
    """
    
    # does not use nodes with partial files
    def simple_assign_blocks_to_nodes_algorithm(self, full_files_info, partial_files_info, best_div_size_fixed=512):
        if full_files_info is None:
            return None
        
        division_size_dict = {}  # division_size => [ip]
                
        for ip, data in full_files_info.items():
            for block_size, last_block_size, n_blocks in data:
                if division_size_dict.get(block_size) is None:
                    division_size_dict[block_size] = []
                division_size_dict[block_size].append((ip, n_blocks, last_block_size))
                
        best_division_size = None
        best_division_size_n_ips = 0
        for division_size, ips in division_size_dict.items():
            len_ips = len(ips)
            if (
                    best_division_size is None or
                    (
                        len_ips == best_division_size_n_ips and
                        abs(division_size - best_div_size_fixed) < abs(best_division_size - best_div_size_fixed)
                    )
                    or len_ips > best_division_size_n_ips
            ):
                best_division_size = division_size
                best_division_size_n_ips = len_ips
                
        if best_division_size is None:
            return None
        
        ips = division_size_dict[best_division_size]
        n_blocks = ips[0][1]
        last_block_size = ips[0][2]
        n_ips = len(ips)
        
        blocks_per_ip = n_blocks // n_ips
        remaining_blocks = n_blocks % n_ips
        
        blocks_assignment = {}
        
        if blocks_per_ip != 0:
            for ip, _, _ in ips:
                blocks_assignment[ip] = blocks_per_ip
                
        while remaining_blocks > 0:
            for ip, _, _ in ips:
                if remaining_blocks == 0:
                    break
                if blocks_assignment.get(ip) is None:
                    blocks_assignment[ip] = 1
                else:
                    blocks_assignment[ip] += 1
                remaining_blocks -= 1

        new_blocks_assignment = {}
        
        start = 1
        for ip, n_blocks_ip in blocks_assignment.items():
            is_full = False
            if n_blocks_ip == n_blocks:
                is_full = True
            if start + n_blocks_ip - 1 == n_blocks:
                new_blocks_assignment[ip] = (start, start + n_blocks_ip - 1, is_full, last_block_size)
            else:
                new_blocks_assignment[ip] = (start, start + n_blocks_ip - 1, is_full, division_size)
            start += n_blocks_ip
        
        return best_division_size, new_blocks_assignment

   
"""
Functions that print the output of the tracker
"""

def print_locate_hash_output(output):
    output_full_files, output_partial_files, counter = output
    for ip, data in output_full_files.items():
    
        print(f"\tIPv4 address: {ip}")
        for block_size, last_block_size, n_blocks in data:
            print(f"""
                    Division size: {block_size}
                    Last block size: {last_block_size}
                    Number of blocks: {n_blocks}
                """)
            print("\n")
            
    for ip, data in output_partial_files.items():
        
        print(f"\tIPv4 address: {ip}")
        for block_size, last_block_size, blocks in data:
            print(f"""
                    Division size: {block_size}
                    Last block size: {last_block_size}
                    Blocks: {blocks}
                """)
            print("\n")
            
    print("Counter: ", counter)
    
def print_locate_name_output(output):
    output, counter = output
    
    for file_hash, ips in output.items():
        print("File hash: ", file_hash)
        print("\tIPs: ", ips)
    print("Counter: ", counter)
    
def print_check_status_output(output):
    status_db, result, counter = output
    print("Status: ", status(status_db).name, result)
    print("Counter: ", counter)
    
def print_response_output(output):
    result_status, counter = output
    print(status(result_status).name, counter)
    
"""
FS_Node_controller is a class that handles the user input
"""

class FS_Node_controller:
    def __init__(self, node):
        self.node = node
        self.done = False
        self.full_update = False
        
    def run(self):
        while not self.done and not self.node.done:
            try:
                command = input("Enter a command:\n").strip().lower()
                
                if self.done:
                    break
                
                if command == "leave" or command == "l":
                    self.done = True
                    self.node.send_leave_request()
                    print("Leaving ...")
                    output = self.node.response_queue.get()
                    print_response_output(output)
                    
                elif not self.full_update and (command == "full update" or command == "fu"):
                    uf_packed_data, up_packed_data = self.node.encode_all_files()
                    
                    if uf_packed_data is not None:
                        self.node.socket.sendall(uf_packed_data)
                        print("Sending UPDATE_FULL request ...")
                        output = self.node.response_queue.get()
                        print_response_output(output)
                        
                    if up_packed_data is not None:
                        self.node.socket.sendall(up_packed_data)
                        print("Sending UPDATE_PARTIAL request ...")
                        output = self.node.response_queue.get()
                        print_response_output(output)
                        
                    self.full_update = True
                        
                elif command == "locate name" or command == "ln":
                    file_name = input("Enter file name: ")
                    self.node.send_locate_name_request(file_name)
                    print("Locating file name...")
                    output = self.node.response_queue.get()
                    print_locate_name_output(output)
                    
                    
                elif command == "locate hash" or command == "lh":
                    file_hash = input("Enter file hash: ")
                    self.node.send_locate_hash_request(file_hash)
                    print("Locating file hash ...")
                    output = self.node.response_queue.get()
                    print_locate_hash_output(output)
                    
                elif command == "locate hash with name" or command == "lhn":
                    file_name = input("Enter file name: ")
                    result = self.node.file_manager.get_file_hash_by_name(file_name)
                    
                    if result is None:
                        print("File not found in local directory. Sendind LOCATE_NAME request ...")
                        self.node.send_locate_name_request(file_name)  
                        output = self.node.response_queue.get()
                        print_locate_name_output(output)
                        
                    else:
                        print("File found in local directory. Sendind LOCATE_HASH request ...")
                        self.node.send_locate_hash_request(result)
                        output = self.node.response_queue.get()
                        print_locate_hash_output(output)
                    
                elif command == "check status" or command == "cs":
                    ip = input("Enter ip address: ")
                    self.node.send_check_status_request(ip)
                    print("Checking status ...")
                    output = self.node.response_queue.get()
                    print_check_status_output(output)
                    
                elif command == "update status" or command == "us":
                    print("This command is avaible for testing purposes only")
                    s = input("Enter status: ")
                    self.node.send_update_status_request(int(s))
                    print("Updating status ...")
                    output = self.node.response_queue.get()
                    print_response_output(output)
                    
                elif command == "get" or command == "g":
                    file_hash = input("Enter file hash: ")
                    self.node.send_locate_hash_request(file_hash)
                    response = self.node.response_queue.get()
                    
                    if (
                        (response[0] is None or len(response[0]) == 0) and 
                        (response[1] is None or len(response[1]) == 0)
                    ):
                        print("Hash not found")
                        continue
                    
                    division_size, output = self.node.simple_assign_blocks_to_nodes_algorithm(response[0], response[1])
                                
                    if output is None or len(output) == 0:
                        print("No addresses available")
                        continue
                        
                    if self.node.debug:
                        print(output)
                        
                    for ip, blocks in output.items():
                        if blocks[2]:  # full file
                            print(f"Sending GET_FULL_FILE request to {ip} ...")
                            self.node.send_udp_get_full_file_request((ip, self.node.udp_port), file_hash, division_size)                            
                        else:
                            print(f"Sending GET_PARTIAL_FILE request to {ip} ...")
                            sequences = [(blocks[0], blocks[1])]
                            self.node.send_udp_get_partial_file_request((ip, self.node.udp_port), file_hash, division_size, sequences, [])
                            
                    file_name = None
                    output_length = len(output)
                    
                    for _ in range(output_length):
                        address, file_name, res_status = self.node.udp_response_queue.get(timeout=60*10)
                        last_block_size = output[address[0]][3] 
                        
                        if output_length == 1 and res_status == status.SUCCESS.value:
                            block_sets = [(division_size, last_block_size, output[address[0]][1])]
                            self.node.send_update_full_request([(file_hash, file_name, block_sets)])
                        
                        elif res_status == status.SUCCESS.value:
                            sequences = [(output[address[0]][0], output[address[0]][1])]
                            block_sets = [(division_size, last_block_size, sequences, [])]
                            self.node.send_update_partial_request([(file_hash, file_name, block_sets)])
                    
                    for i in range(output_length):
                        output = self.node.response_queue.get(timeout=60*10)
                    
                    r = self.node.file_manager.join_blocks(file_name, division_size)
                    if r:
                        print("File joined successfully")
                    else:
                        print("Error joining file")           
                            
                elif command == "join blocks" or command == "jbb":
                    file_name = input("Enter file name: ")
                    division_size = input("Enter division size: ")
                    r = self.node.file_manager.join_blocks(file_name, int(division_size))
                    if r:
                        print("File joined successfully")
                    else:
                        print("Error joining file")
                
                elif command == "help" or command == "h":
                    print("Commands:")
                    print("\tleave (l)")
                    print("\tfull update (fu)")
                    print("\tlocate hash (lh)")
                    print("\tlocate name (ln)")
                    print("\tlocate hash with name (lhn)")
                    print("\tcheck status (cs)")
                    print("\tupdate status (us)")
                    print("\tget (g)")
                    print("\tjoin blocks (jbb)")
                    print("\thelp (h)")
                else:
                    print("Invalid command")
                    
            except Exception as e:
                print("Error message:", e)
                print("Traceback:")
                traceback.print_exc() 

"""
Parser for command line arguments
"""

def parse_args():
    try:
        parser = argparse.ArgumentParser(description='FS Tracker Command Line Options')
        parser.add_argument('--port', '-p', type=int, default=9090, help='Port to bind the server to')
        parser.add_argument('--address', '-a', type=str, default=None, help='Host IP address to bind the server to')
        parser.add_argument('--debug', '-d', default=False, action='store_true')
        parser.add_argument('--block_size', '-b', type=int, default=512, help='Block size')
        parser.add_argument('--dir', '-D', type=str, default=None, help='Directory to store files')
        parser.add_argument('--udp_port', '-up', type=int, default=9090, help='UDP port')
        parser.add_argument('--ack_timeout', '-at', type=float, default=0.5, help='UDP ack timeout')
        parser.add_argument('--timeout', '-t', type=float, default=60*10, help='TCP timeout')
        parser.add_argument('--udp_timeout', '-ut', type=float, default=60*10, help='UDP timeout')
        args = parser.parse_args()
        
        if args.block_size > 1024:
            raise argparse.ArgumentError("Block size must be less than 2^(16)")
    
        if args.dir is None:
            raise argparse.ArgumentError("Directory must be specified")
    
        return args
    except argparse.ArgumentError as e:
        print(f"Error parsing command line arguments: {e}")
        return
              
                
if __name__ == "__main__":

    args = parse_args()
    
    fs_node_1 = FS_Node(
        dir=args.dir,
        server_address=args.address,
        port=args.port,
        block_size=args.block_size,
        debug=args.debug,
        udp_port=args.udp_port,
        udp_ack_timeout=args.ack_timeout,
        timeout=args.timeout,
        udp_timeout=args.udp_timeout
    )
        
    fs_node_1.file_manager.run()

    node_controller = FS_Node_controller(fs_node_1)
    node_controller_thread = threading.Thread(target=node_controller.run)
    node_controller_thread.start()
        
    try:
        fs_node_1.run()
    except KeyboardInterrupt:
        print("[main] Keyboard interrupt")
        fs_node_1.shutdown()
        node_controller.done = True
        node_controller_thread.join()