import argparse
from enum import IntEnum


class action(IntEnum):
    UPDATE = 0
    LEAVE = 1
    LOCATE_NAME = 2
    LOCATE_HASH = 3
    RESPONSE = 4
    RESPONSE_LOCATE_HASH = 5
    RESPONSE_LOCATE_NAME = 6
    
    
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
