from datetime import datetime
from threading import Thread
import socket
import db
from jsonschema import validate
import utils
import struct
import pdu


class fs_tracker(Thread):
    def __init__(
            self,
            db_file,
            port=9090,
            host=None,
            max_connections=5,
            timeout=60,
            buffer_size=1024,
            debug=False,
            on_connected_callback=None,
            on_disconnected_callback=None,
            on_data_received_callback=None,
    ):
        self.socket = None
        self.data_manager = db.fs_tracker_db_manager(db_file)
        self.host = host
        self.port = port
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.clients = []
        self.debug = debug
        self.max_connections = max_connections
        self.on_connected_callback = on_connected_callback
        self.on_disconnected_callback = on_disconnected_callback
        self.on_data_received_callback = on_data_received_callback
        self.json_schemas = {}
        self.json_schemas = utils.json_schemas_provider().get_json_schemas()
        Thread.__init__(self)

    def run(self):
        if self.debug:
            print(datetime.now(), "Server starting")
        self.listen()

    def listen(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.socket.bind((self.host, self.port))
        if self.debug:
            print(str(datetime.now()) + "Server socket bound to %s:%s" % (self.host, self.port))

        self.socket.listen(self.max_connections)
        if self.debug:
            print(datetime.now(), "Server socket listening for connections")

        while True:
            client, address = self.socket.accept()
            self.clients.append(client)
            client.settimeout(self.timeout)

            if self.debug:
                print(datetime.now(), "Client connected", address)

            if self.on_connected_callback:
                self.on_connected_callback(client, address)

            Thread(
                target=self.listen_to_client,
                args=(client, address, self.on_data_received_callback, self.on_disconnected_callback)
            ).start()

    def listen_to_client(self, client, address, on_data_received_callback, on_disconnected_callback):
        counter = 0
        while True:
            try:
                bytes_read = client.recv(1)

                if not bytes_read:
                    continue

                counter += 1
                decoded_byte = struct.unpack("!B", bytes_read)[0]

                match decoded_byte:
                    case utils.action.UPDATE.value:
                        self.handle_update_message(client, address, counter)
                    case utils.action.LOCATE.value:
                        self.handle_locate_message(client, address, counter)
                    case _:
                        if self.debug:
                            print("Error: Invalid message action")

            except socket.timeout:
                pass
            except Exception as e:
                if self.debug:
                    print(datetime.now(), e, client, '\n')
                break

        if on_disconnected_callback:
            on_disconnected_callback(client, address)

        client.close()

        if self.debug:
            print(datetime.now(), "Client disconnected", address)

        return False

    def send_response(self, client, response, counter):
        encoded_response = pdu.pdu_encode_response(response, counter)
        client.sendall(encoded_response)
        if self.debug:
            print("Response sent")

    def handle_update_message(self, client, address, counter):
        bytes_read = client.recv(1)
        n_files = struct.unpack("!B", bytes_read)[0]

        json_data = []

        for file in range(n_files):
            bytes_read = client.recv(1)
            filename_len = struct.unpack("!B", bytes_read)[0]
            bytes_read = client.recv(filename_len)
            filename = struct.unpack("!%ds" % filename_len, bytes_read)[0].decode("utf-8")

            bytes_read = client.recv(1)
            n_block_sets = struct.unpack("!B", bytes_read)[0]

            blocks = []
            for block_set in range(n_block_sets):
                bytes_read = client.recv(5)
                block_size, last_block_size, n_sequences = struct.unpack("!HHB", bytes_read)
                block_numbers = []

                for sequence in range(n_sequences):
                    bytes_read = client.recv(4)
                    first, last = struct.unpack("!HH", bytes_read)
                    block_numbers.extend(range(first, last + 1))

                bytes_read = client.recv(2)
                n_block_numbers = struct.unpack("!H", bytes_read)[0]
                for block_number in range(n_block_numbers):
                    bytes_read = client.recv(2)
                    block = struct.unpack("!H", bytes_read)[0]
                    block_numbers.append(block)

                blocks.append({
                    "size": block_size,
                    "numbers": block_numbers,
                    "last_block_size": last_block_size
                })

            json_data.append({
                "name": filename,
                "blocks": blocks
            })

        try:
            if json_data is None:
                raise Exception("Error: No data received")

            for file in json_data:
                validate(file, self.json_schemas["file_info.json"])
                if self.debug:
                    print("JSON is valid against the schema.")

            result = self.data_manager.update_fs_node(json_data, address[0])
            self.send_response(client, result, counter)

        except Exception as e:
            if self.debug:
                print("Error: ", e)
            self.send_response(client, utils.status.INVALID_REQUEST.value, counter)

    def handle_locate_message(self, client, address, counter):
        print("Locate message received")
        bytes_read = client.recv(1)
        file_name_len = struct.unpack("!B", bytes_read)[0]
        bytes_read = client.recv(file_name_len)
        file_name = struct.unpack("!%ds" % file_name_len, bytes_read)[0].decode("utf-8")
        addresses, result1, result2 = self.data_manager.locate_file(file_name)
        encoded_results = pdu.pdu_encode_locate_response(addresses, result1, result2, counter)
        # client.sendall(encoded_results)
        self.send_response(client, utils.status.SUCCESS.value, counter)


if __name__ == "__main__":
    fs_tracker(
        db_file="FS_Tracker.sqlite",
        host="127.0.0.1",
        port=9090,
        timeout=60 * 60,
        debug=True
    ).run()
