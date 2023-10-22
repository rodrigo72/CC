import json
import os
import socket
import threading
import utils
from jsonschema import validate


class fs_node:
    def __init__(
            self,
            directory=os.path.join(os.path.dirname(__file__)),
            port=9090,
            server_host="127.0.0.1",
            server_port=9090,
            block_size=1024,
            debug=False,
            buffer_size=1024
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

    def read_directory(self):
        try:
            for filename in os.listdir(os.path.join(self.directory, "Files")):
                if os.path.isfile(os.path.join(self.directory, "Files", filename)):
                    self.save_blocks(filename)
        except Exception as e:
            if self.debug:
                print(e)

        print(self.files)

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

            self.files[file_name] = {
                "name": file_name,
                "size": file_size,
                "blocks": [
                    {
                        "size": self.block_size,
                        "numbers": block_numbers,
                        "last_block_size": last_block_size if last_block_size != 0 else self.block_size
                    }
                ]
            }

    def create_register_request(self):

        json_schema = self.json_schemas["register_request.json"]

        hostname = socket.gethostname()
        json_message = {
            "action": utils.message_action.REGISTER.value,
            "address": socket.gethostbyname(hostname)
        }

        try:
            validate(json_message, json_schema)
            if self.debug:
                print("JSON is valid against the schema.")
            return json.dumps(json_message).encode('utf-8')
        except Exception as e:
            if self.debug:
                print("JSON is not valid against the schema.")
                print(e)
            return None

    def create_locate_request(self, file_name):
        # TODO: Create a locate request
        pass

    def create_leave_request(self):
        # TODO: Create a leave request
        pass

    def create_update_request(self, file_info_set):
        # TODO: Create an update request
        pass

    def connect_to_fs_tracker(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_host, self.server_port))

    def shutdown(self):
        self.done = True
        if self.socket:
            self.socket.close()

    def send_message(self, message):
        try:
            serialized_message = json.dumps(message)
            self.socket.sendall(serialized_message.encode('utf-8'))
        except Exception as e:
            print("Error sending message:", e)

    def send_register_request(self):
        registration_message = self.create_register_request()
        self.socket.send(registration_message)

    def send_leave_request(self):
        leave_message = self.create_leave_request()
        self.socket.send(leave_message)

    def send_update_message(self):
        update_message = self.create_update_request()
        self.socket.send(update_message)

    def run(self):
        try:
            self.connect_to_fs_tracker()

            while not self.done:
                data = self.socket.recv(self.buffer_size)
                if not data:
                    break

                # json_message = json.loads(data.decode('utf-8'))
        except Exception as e:
            if self.debug:
                print("Error:", e)
        finally:
            # self.send_leave_message()
            self.shutdown()


class fs_node_controller:
    def __init__(self, node):
        self.node = node
        self.done = False

    def run(self):
        while not self.done:
            command = input("Enter a command: ")
            if command == "exit":
                self.done = True
                self.node.shutdown()
            elif command == "register":
                self.node.send_register_request()
            elif command == "leave":
                self.node.send_leave_request()
            elif command == "update":
                self.node.send_update_message()
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

    node_1.run()
    node_1_controller_thread.join()

