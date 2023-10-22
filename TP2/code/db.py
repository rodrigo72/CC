import sqlite3
from sqlite3 import Error
import utils


class fs_tracker_db_manager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            self.cursor = conn.cursor()
        except Error as e:
            if self.conn:
                self.conn.close()
            print("Error: ", e)

    def __del__(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def register_node(self, address):
        try:
            self.cursor.execute("INSERT INTO FS_Node VALUES (?)", (address,))
            return utils.response_status.SUCCESS
        except sqlite3.IntegrityError as e:
            print("Error: ", e)
            return utils.response_status.INVALID_REQUEST
        except Error as e:
            print("Error: ", e)
            return utils.response_status.SERVER_ERROR
