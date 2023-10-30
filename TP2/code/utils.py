import os
import json
import copy
from enum import IntEnum


class action(IntEnum):
    UPDATE = 0
    LEAVE = 1
    LOCATE = 2
    RESPONSE = 3
    RESPONSE_LOCATE = 4


class status(IntEnum):
    SUCCESS = 0
    INVALID_REQUEST = 1
    INVALID_ACTION = 2
    DENIED = 3
    NOT_FOUND = 4
    SERVER_ERROR = 5
    UNAUTHORIZED = 6
    UNAVAILABLE = 7


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class json_schemas_provider(metaclass=SingletonMeta):
    def __init__(self):
        self._json_schemas = _get_json_schemas(
            os.path.join(os.path.dirname(__file__), "json_schemas")
        )

    def get_json_schemas(self):
        return copy.deepcopy(self._json_schemas)

    def get_json_schema(self, schema_name):
        return copy.deepcopy(self._json_schemas[schema_name])


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
