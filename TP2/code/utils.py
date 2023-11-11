import argparse
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
