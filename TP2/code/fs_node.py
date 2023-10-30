import os
import socket
import threading
import utils
from jsonschema import validate
import pdu
import struct


class fs_node:
    def __init__(
            self,
            directory=os.path.join(os.path.dirname(__file__)),
            port=9090,
            server_host="127.0.0.1",
            server_port=9090,
            block_size=1024,
            debug=False,
            buffer_size=1024,
            callback=None
    ):
        self.socket = None
        self.port = port
        self.server_port = server_port
        self.server_host = server_host
        self.directory = directory
        self.files = {}
        self.block_size = block_size
        self.debug = debug
        self.buffer_size = buffer_size
        self.done = False
        self.json_schemas = utils.json_schemas_provider().get_json_schemas()
        self.callback = callback

    def read_directory(self):
        try:
            for filename in os.listdir(os.path.join(self.directory, "Files")):
                if os.path.isfile(os.path.join(self.directory, "Files", filename)):
                    self.save_blocks(filename)
        except Exception as e:
            if self.debug:
                print(e)

    def save_blocks(self, file_name):
        path = os.path.join(self.directory, "Files", file_name)
        with open(path, 'rb') as file:
            file_data = file.read()
            file_size = len(file_data)
            block_numbers = []

            output_dir = os.path.join(self.directory, "Blocks", file_name + f"_{self.block_size}")
            os.makedirs(output_dir, exist_ok=True)

            for j, i in enumerate(range(0, len(file_data), self.block_size)):
                block_size = min(self.block_size, file_size - i)
                block_data = file_data[i:i + block_size]
                block_numbers.append(j)

                block_file_name = f"{file_name}_block_{i}_{i + block_size}.dat"
                file_path = os.path.join(output_dir, block_file_name)

                with open(file_path, 'wb') as block_file:
                    block_file.write(block_data)

            last_block_size = file_size % self.block_size

            json_data = {
                "name": file_name,
                "blocks": [
                    {
                        "size": self.block_size,
                        "numbers": block_numbers,
                        "last_block_size": last_block_size if last_block_size != 0 else self.block_size
                    }
                ]
            }

            try:
                validate(json_data, self.json_schemas["file_info.json"])
                if self.debug:
                    print("JSON is valid against the schema.")
                self.files[file_name] = json_data
            except Exception as e:
                if self.debug:
                    print("JSON is not valid against the schema.")
                    print(e)

    def connect_to_fs_tracker(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_host, self.server_port))

    def shutdown(self):
        self.done = True
        if self.socket:
            self.socket.close()

    def send_leave_request(self):
        pass

    def send_update_message(self):
        update_message = pdu.pdu_encode(utils.action.UPDATE.value, self.files.values())
        self.socket.sendall(update_message)

    def send_locate_message(self, file_name):
        locate_message = pdu.pdu_encode(utils.action.LOCATE.value, file_name)
        self.socket.sendall(locate_message)

    def run(self):
        try:
            self.connect_to_fs_tracker()

            while not self.done:
                data = self.socket.recv(1)
                if not data:
                    continue
                data = struct.unpack("!B", data)[0]
                match data:
                    case utils.action.RESPONSE.value:
                        self.handle_server_response()
                    case _:
                        if self.debug:
                            print("Invalid action")
        except Exception as e:
            if self.debug:
                print("Error:", e)
        finally:
            # self.send_leave_message()
            self.shutdown()

    def handle_server_response(self):
        bytes_read = self.socket.recv(3)
        status, counter = struct.unpack("!BH", bytes_read)

        print(utils.status(status).name, counter)

        if self.callback:
            self.callback()


class fs_node_controller:
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
            if command == "exit" or command == "e":
                self.done = True
                self.node.shutdown()
            elif command == "leave" or command == "l":
                self.node.send_leave_request()
                self.wait_for_response()
            elif command == "update" or command == "u":
                self.node.send_update_message()
                self.wait_for_response()
            elif command == "locate" or command == "lo":
                file_name = input("Enter a file name: ")
                self.node.send_locate_message(file_name)
                self.wait_for_response()
            else:
                print("Invalid command")


if __name__ == "__main__":
    node_1 = fs_node(
        directory="nodes\\fs_node_1",
        debug=True,
        server_host="127.0.0.1",
        port=9090
    )
    node_1.read_directory()

    node_1_controller = fs_node_controller(node_1)
    node_1_controller_thread = threading.Thread(target=node_1_controller.run)
    node_1_controller_thread.start()

    node_1.callback = node_1_controller.set_response_event

    node_1.run()
    node_1_controller_thread.join()
