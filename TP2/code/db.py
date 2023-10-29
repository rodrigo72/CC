import sqlite3
from sqlite3 import Error
import utils


class fs_tracker_db_manager(metaclass=utils.SingletonMeta):
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        try:
            self.conn = sqlite3.connect(db_file, check_same_thread=False)
            self.cursor = self.conn.cursor()
        except Error as e:
            if self.conn:
                self.conn.close()
            print("Error: ", e)

    def __del__(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def update_fs_node(self, json_data, address):
        try:
            self.conn.execute("BEGIN")
            self.cursor.execute("INSERT OR IGNORE INTO fs_node VALUES (?)", (address,))
            for file_info in json_data:
                self._add_file_info(file_info, address)
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            print("Error [update_fs_node]: ", e)
            self.conn.rollback()
            return utils.status.INVALID_REQUEST.value

    def _add_file_info(self, file_info, address):
        self.cursor.execute("INSERT OR IGNORE INTO file VALUES (?)", (file_info["name"],))
        keys = []
        for block_info in file_info["blocks"]:
            block_size = block_info["size"]
            block_numbers = sorted(block_info["numbers"])

            for block_number in block_numbers[:-1]:
                offset = block_number * block_size
                keys.append((block_size, offset))
                self.cursor.execute(
                    "INSERT OR IGNORE INTO block VALUES (?, ?, ?, ?)",
                    (block_number, block_size, offset, file_info["name"])
                )

            self.cursor.execute(
                "INSERT OR IGNORE INTO block VALUES (?, ?, ?, ?)",
                (block_numbers[-1], block_info["last_block_size"], block_numbers[-1] * block_size,
                 file_info["name"])
            )
            keys.append((block_size, block_info["last_block_size"]))

        for (block_size, offset) in keys:
            self.cursor.execute(
                "INSERT OR IGNORE INTO fs_node_block VALUES (?, ?, ?, ?)",
                (address, block_size, offset, file_info["name"])
            )

    def delete_from_all_tables(self):
        try:
            self.conn.execute("BEGIN")
            self.cursor.execute("DELETE FROM fs_node")
            self.cursor.execute("DELETE FROM file")
            self.cursor.execute("DELETE FROM block")
            self.cursor.execute("DELETE FROM fs_node_block")
            self.conn.commit()
        except Error as e:
            print("Error [delete_from_all_tables]: ", e)
            self.conn.rollback()


if __name__ == "__main__":
    db = fs_tracker_db_manager("FS_Tracker.sqlite")
    db.delete_from_all_tables()
