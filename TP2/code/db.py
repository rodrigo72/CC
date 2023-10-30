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

    def _add_file_info(self, file_info, ip_address):
        self.cursor.execute("INSERT OR IGNORE INTO file VALUES (?)", (file_info["name"],))
        keys = []
        for block_info in file_info["blocks"]:
            block_size = block_info["size"]
            last_block_size = block_info["last_block_size"]
            block_numbers = sorted(block_info["numbers"])

            for block_number in block_numbers[:-1]:
                offset = block_number * block_size
                keys.append((block_size, offset))
                self.cursor.execute(
                    "INSERT OR IGNORE INTO block VALUES (?, ?, ?, ?, ?)",
                    (block_number, block_size, offset, file_info["name"], None)
                )

            offset = block_numbers[-1] * block_size
            self.cursor.execute(
                "INSERT OR IGNORE INTO block VALUES (?, ?, ?, ?, ?)",
                (block_numbers[-1], last_block_size, offset, file_info["name"], block_size)
            )
            keys.append((last_block_size, offset))

        for (block_size, offset) in keys:
            self.cursor.execute(
                "INSERT OR IGNORE INTO fs_node_block VALUES (?, ?, ?, ?)",
                (ip_address, block_size, offset, file_info["name"])
            )

    def locate_file(self, file_name):
        try:
            self.conn.execute("BEGIN")
            query1 = "SELECT rowid, ipv4_address FROM fs_node"

            query2 = (
                "SELECT fsnb.block_size, "
                "GROUP_CONCAT(b.number) AS numbers, "
                "fsn.ipv4_address AS ips "
                "FROM fs_node_block fsnb "
                "JOIN fs_node fsn ON fsnb.fs_node_ipv4_address = fsn.ipv4_address "
                "JOIN block b ON fsnb.block_size = b.size AND fsnb.block_offset = b.offset "
                "AND fsnb.block_file_name = b.file_name "
                "WHERE b.file_name = (?) AND b.original_division_size IS NULL "
                "GROUP BY fsnb.block_size, fsn.ipv4_address"
            )

            query3 = (
                "SELECT fsnb.block_size, "
                "GROUP_CONCAT(b.number || ',' || b.original_division_size) AS numbers, "
                "fsn.ipv4_address AS ips "
                "FROM fs_node_block fsnb "
                "JOIN fs_node fsn ON fsnb.fs_node_ipv4_address = fsn.ipv4_address "
                "JOIN block b ON fsnb.block_size = b.size AND fsnb.block_offset = b.offset "
                "AND fsnb.block_file_name = b.file_name "
                "WHERE b.file_name = (?) AND b.original_division_size IS NOT NULL "
                "GROUP BY fsnb.block_size, fsn.ipv4_address"
            )

            self.cursor.execute(query1)
            addresses = self.cursor.fetchall()
            self.cursor.execute(query2, (file_name,))
            result1 = self.cursor.fetchall()
            self.cursor.execute(query3, (file_name,))
            result2 = self.cursor.fetchall()
            self.conn.commit()
            return addresses, result1, result2
        except Error as e:
            print("Error [locate_file]: ", e)
            self.conn.rollback()
            return None

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

    files_info = [
        {
            "name": "belo.jpg",
            "blocks": [
                {
                    "size": 1024,
                    "last_block_size": 210,
                    "numbers": [1, 2, 3, 4, 5],
                },
                {
                    "size": 2048,
                    "last_block_size": 1021,
                    "numbers": [1, 2, 3, 4, 5, 6, 10],
                }
            ],
        },
        {
            "name": "java.png",
            "blocks": [
                {
                    "size": 1024,
                    "last_block_size": 21,
                    "numbers": [1, 2, 3, 4, 20, 21, 22, 23, 24, 25]
                }
            ]
        }
    ]

    address = '112.1.1.1'
    db.update_fs_node(files_info, address)
    # db.delete_from_all_tables()
