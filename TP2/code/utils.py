import os
import json
import copy
from enum import IntEnum


class action(IntEnum):
    REGISTER = 1
    UPDATE = 2
    LEAVE = 3
    LOCATE = 4


class status(IntEnum):
    SUCCESS = 1
    INVALID_REQUEST = 2
    INVALID_ACTION = 3
    DENIED = 4
    NOT_FOUND = 5
    SERVER_ERROR = 6
    UNAUTHORIZED = 7
    UNAVAILABLE = 8


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
