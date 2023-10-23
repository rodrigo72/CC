import json
from datetime import datetime
from threading import Thread
import socket
import db
from jsonschema import validate
import utils
import time


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
        while True:
            try:
                data = client.recv(self.buffer_size)
                if not data:
                    break

                json_message = json.loads(data.decode('utf-8'))
                self.handle_json_message(client, json_message)

                if on_data_received_callback:
                    on_data_received_callback(client, address)
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

    def send_message(self, client, message):
        try:
            client.sendall(json.dumps(message).encode('utf-8'))
        except Exception as e:
            if self.debug:
                print("Error sending message:", e)

    def create_generic_response(self, action, status, message):

        json_response = {
            "action": action,
            "status": status,
            "message": message
        }

        try:
            validate(json_response, self.json_schemas["response.json"])
            if self.debug:
                print("Response message validated")
            return message
        except Exception as e:
            if self.debug:
                print("Error:", e)
            return None

    def handle_json_message(self, client, json_message):

        switch_message_action = {
            utils.message_action.REGISTER.value: self.handle_registration_message,
            utils.message_action.UPDATE.value: self.handle_update_message,
            utils.message_action.LEAVE.value: self.handle_leave_message
        }

        if json_message["action"] in switch_message_action:
            switch_message_action[json_message["action"]](json_message, client)
        elif self.debug:
            print("Error: Invalid message action")

    def handle_leave_message(self, json_message, client):
        # TODO: Handle leave message
        pass

    def handle_update_message(self, json_message, client):
        # TODO: Handle update message
        pass

    def handle_registration_message(self, json_message, client):
        print("Handling registration message")
        try:
            validate(json_message, self.json_schemas["register_request.json"])
            address = json_message["address"]
            result = self.data_manager.register_node(address)

            if result == utils.response_status.SUCCESS:
                status_message = "Node registered successfully"
            else:
                status_message = "Node registration unsuccessful"

            response = self.create_generic_response(
                utils.message_action.REGISTER.value, result.value, status_message)

            time.sleep(3)

            self.send_message(client, response)
        except Exception as e:
            if self.debug:
                print("Error:", e)
            self.send_message(client, self.create_generic_response(
                utils.message_action.REGISTER.value,
                utils.response_status.INVALID_REQUEST.value,
                "Invalid request"))


if __name__ == "__main__":
    fs_tracker(
        db_file="FS_Tracker.sqlite",
        host="127.0.0.1",
        port=9090,
        timeout=60 * 60,
        debug=True
    ).run()
