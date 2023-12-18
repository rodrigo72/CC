from enum import IntEnum
import threading
from queue import Queue
import queue
import binascii
import time

"""
Enums for the packet types
"""

class action(IntEnum):
    UPDATE_FULL_FILES = 0
    UPDATE_PARTIAL = 1
    UPDATE_STATUS = 3
    CHECK_STATUS = 4
    LOCATE_NAME = 5
    LOCATE_HASH = 6
    LEAVE = 7
    RESPONSE = 8
    RESPONSE_LOCATE_HASH = 9
    RESPONSE_LOCATE_NAME = 10
    RESPONSE_CHECK_STATUS = 11


class action_udp(IntEnum):
    START_DATA = 0
    START_END_DATA = 1   
    END_DATA = 2
    DATA = 3
    GET_FULL_FILE = 4
    GET_PARTIAL_FILE = 5
    ACK = 6
    
    
class status(IntEnum):
    SUCCESS = 0
    INVALID_REQUEST = 1
    INVALID_ACTION = 2
    NOT_FOUND = 3
    SERVER_ERROR = 4
    UDP_FILE_NOT_FOUND = 13
    UDP_BLOCK_NOT_FOUND = 14
    
"""
Checksum (not used)
"""

def generate_checksum(message):
    checksum = binascii.crc32(message) & 0xffffffff
    checksum_bytes = checksum.to_bytes(4, byteorder="big")
    return checksum_bytes

"""
Singleton metaclass
"""

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

"""
Queue dictionary
"""

class Queue_dictionary:
    def __init__(self):
        self.queues = {}

    # only one thread uses this function
    def put(self, key, item):
        if key not in self.queues:
            self.queues[key] = Queue()
        self.queues[key].put(item)
        
    def init(self, key):
        if key not in self.queues:
            self.queues[key] = Queue()

    # many threads use this function, but they only access their own queue
    # so it is thread safe (confia)
    def get(self, key, timeout=None):
        if key in self.queues:
            try:
                return self.queues[key].get(timeout=timeout)
            except queue.Empty:
                return None
        else:
            return None

"""
Other
"""

def join_blocks(sequences, blocks):
    block_numbers = []
    for sequence in sequences:
        first, last = sequence
        for i in range(first, last+1):
            block_numbers.append(i)
    block_numbers.extend(blocks)
    return block_numbers
