import sqlite3
from sqlite3 import Error
import utils
import uuid

class DB_manager(metaclass=utils.SingletonMeta):
    def __init__(self, db_file, debug=False):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        self.debug = debug
        
        try:
            self.conn = sqlite3.connect(db_file, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.drop_tables()            
            self.create_tables()
        except Error as e:
            if self.conn:
                self.conn.close()
            if self.debug:
                print("[init] Error: ", e)
                
    def __del__(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
        
    def create_tables(self):
        try:
            
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS node (
                    address TEXT(15) PRIMARY KEY NOT NULL,
                    UNIQUE(address)
                )
                """
            )
            
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS file (
                    name TEXT NOT NULL,
                    node_address TEXT(15) NOT NULL,
                    PRIMARY KEY (name, node_address),
                    FOREIGN KEY (node_address) REFERENCES node (address)
                    ON DELETE CASCADE ON UPDATE CASCADE
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS block_set (
                    is_complete INTEGER NOT NULL,
                    block_size INTEGER NOT NULL,
                    file_name INTEGER NOT NULL,
                    file_node_address TEXT(15) NOT NULL,
                    n_blocks INTEGER,
                    PRIMARY KEY (file_name, file_node_address, is_complete, block_size),
                    FOREIGN KEY (file_name, file_node_address) REFERENCES file (name, node_address)
                    ON DELETE NO ACTION ON UPDATE NO ACTION
                )
                """
            )
            
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS block (
                    size INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    is_last INTEGER NOT NULL,
                    block_set_file_name INTEGER NOT NULL,
                    block_set_file_node_address TEXT(15) NOT NULL,
                    block_set_is_complete INTEGER NOT NULL,
                    block_set_block_size INTEGER NOT NULL,
                    PRIMARY KEY (number, block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size),
                    FOREIGN KEY (block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size) 
                        REFERENCES block_set (file_name, file_node_address, is_complete, block_size)
                )
                """
            )

            if self.debug:
                print("Tables created")

            self.conn.commit()
        except Error as e:
            if self.debug:
                print("[create_tables] Error: ", e)
            self.conn.rollback()
            
    def update_node(self, address, data):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO node (address) VALUES (?)
                """,
                (address,)
            )
            
            for file in data:
                file_name, block_set_data = file
                
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO file (name, node_address) VALUES (?, ?)
                    """,
                    (file_name, address)
                )
                
                for block_set in block_set_data:
                    block_size, last_block_size, full_file, blocks = block_set
                    is_complete = 1 if full_file != 0 else 0
                    self.cursor.execute(
                        """
                        INSERT OR IGNORE INTO block_set (is_complete, block_size, file_name, file_node_address) 
                            VALUES (?, ?, ?, ?)
                        """,
                        (is_complete , block_size, file_name, address)
                    )

                    if full_file != 0:
                        i = 1
                        blocks = sorted(blocks)

                        for i in range(full_file - 1):
                            self.cursor.execute(
                                """
                                INSERT OR IGNORE INTO block (size, number, is_last, block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size)
                                    VALUES (?, ?, ?, ?, ?, ?, ?);
                                """,
                                (block_size, i, 0, file_name, address, is_complete, block_size)
                            )

                        self.cursor.execute(
                            """
                            INSERT OR IGNORE INTO block (size, number, is_last, block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size) 
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (last_block_size, i, 1, file_name, address, is_complete, block_size)
                        )
                    else:
                        for block in blocks[:-1]:
                            self.cursor.execute(
                                """
                                INSERT OR IGNORE INTO block (size, number, is_last, block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size)
                                    VALUES (?, ?, ?, ?, ?, ?, ?);
                                """,
                                (block_size, block, 0, file_name, address, is_complete, block_size)
                            )
                        self.cursor.execute(
                            """
                            INSERT OR IGNORE INTO block (size, number, is_last, block_set_file_name, block_set_file_node_address, block_set_is_complete, block_set_block_size)
                                    VALUES (?, ?, ?, ?, ?, ?, ?);
                            """,
                            (last_block_size, blocks[-1], 1, file_name, address, is_complete, block_size)
                        )
                        
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
        
    def locate_file(self, file_name):
        try:
            self.conn.execute("BEGIN")
            
            query = """
                SELECT *
                FROM file
                JOIN block_set ON file.name = block_set.file_name
                JOIN block ON block_set.file_name = block.block_set_file_name
                WHERE file.name = (?);
            """

            self.cursor.execute(query, (file_name,))
            results = self.cursor.fetchall()
            print(results)
                
            self.conn.commit()
        except Error as e:
            if self.debug:
                print("[locate_file] Error: ", e)
            self.conn.rollback()
        
    def drop_tables(self):
        try:
            self.conn.execute("BEGIN")
            
            tables_to_clear = ["node", "file", "block_set", "block"]
            
            for table in tables_to_clear:
                self.cursor.execute(
                    """
                    DROP TABLE IF EXISTS %s
                    """ % table
                )
            
            self.conn.commit()
        except Error as e:
            if self.debug:
                print("[clear_tables] Error: ", e)
            self.conn.rollback()

if __name__ == '__main__':
    print("Hello World!")
    db = DB_manager("db.sqlite3")
    db.create_tables()