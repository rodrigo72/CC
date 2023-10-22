import os
import json
import copy
from enum import Enum


class message_action(Enum):
    REGISTER = "register"
    UPDATE = "update"
    LEAVE = "leave"
    LOCATE = "locate"


class response_status(Enum):
    SUCCESS = "success"
    INVALID_REQUEST = "invalid_request"
    INVALID_ACTION = "invalid_action"
    DENIED = "denied"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"
    UNAUTHORIZED = "unauthorized"
    UNAVAILABLE = "unavailable"


def _get_json_schemas(directory):
    json_schemas = {}
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(directory, filename)) as json_file:
                    schema = json.load(json_file)
                    json_schemas[filename] = schema
            except Exception as e:
                print(e)

    return json_schemas


class json_schemas_provider:
    _instance = None  # singleton pattern

    def __init__(self):
        self._json_schemas = _get_json_schemas(
            os.path.join(os.path.dirname(__file__), "json_schemas")
        )

    def __new__(cls, self=None, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(json_schemas_provider, cls).__new__(cls)
            cls._instance.__init__()
        return cls._instance

    def get_json_schemas(self):
        return copy.deepcopy(self._json_schemas)

    def get_json_schema(self, schema_name):
        return copy.deepcopy(self._json_schemas[schema_name])
