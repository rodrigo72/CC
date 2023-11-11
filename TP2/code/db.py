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
                create table if not exists Node (
                    ip TEXT(15) not null,
                    primary key (ip)
                );
                """
            )
            
            self.cursor.execute(
                """
                create table if not exists File (
                    hash text(32) not null,
                    name text(255) not null,
                    primary key (hash)
                );
                """
            )

            self.cursor.execute(
                """
                create table if not exists Block (
                    size integer not null,
                    number integer not null,
                    division_size integer not null,
                    is_last integer not null,
                    File_hash text(32) not null,
                    primary key (size, number, division_size, File_hash),
                    foreign key (File_hash) 
                        references File (hash)
                    check (size <= division_size)
                );
                """
            )
            
            self.cursor.execute(
                """
                create table if not exists Node_has_Block (
                    Node_ip text(25) not null,
                    Block_size INTEGER NOT NULL,
                    Block_number INTEGER NOT NULL,
                    Block_division_size INTEGER NOT NULL,
                    Block_File_hash text(32) NOT NULL,
                    primary key (Node_ip, Block_size, Block_number, Block_division_size, Block_File_hash),
                    foreign key (Node_ip) 
                        references Node (ip),
                    foreign key (Block_size, Block_number, Block_division_size, Block_File_hash) 
                        references Block (size, number, division_size, File_hash)
                );
                """
            )

            if self.debug:
                print("Tables created")

            self.conn.commit()
        except Error as e:
            if self.debug:
                print("[create_tables] Error: ", e)
            self.conn.rollback()
            
    def insert_block_data(self, address, size, number, division_size, is_last, file_hash):
        insert_block_query = """
            INSERT OR IGNORE INTO Block (size, number, division_size, is_last, File_hash) 
            VALUES (?, ?, ?, ?, ?);
        """
        
        insert_node_has_block_query = """
            INSERT OR IGNORE INTO Node_has_Block (Node_ip, Block_size, Block_number, Block_division_size, Block_File_hash) 
            VALUES (?, ?, ?, ?, ?);
        """

        self.cursor.execute(insert_block_query, (size, number, division_size, is_last, file_hash))
        self.cursor.execute(insert_node_has_block_query, (address, size, number, division_size, file_hash))
  
    def update_node(self, address, data):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO Node (ip) VALUES (?)
                """,
                (address,)
            )
            
            for file in data:
                file_name, file_hash, block_set_data = file
                
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO File (hash, name) VALUES (?, ?)
                    """,
                    (file_hash, file_name)
                )
                                
                for block_set in block_set_data:
                    block_size, last_block_size, full_file, blocks = block_set
                    
                    if full_file != 0:
                        i = 1
                            
                        for i in range(1, full_file):
                            self.insert_block_data(address, block_size, i, block_size, 0, file_hash)
                        
                        if full_file != 1:
                            i += 1
                        
                        self.insert_block_data(address, last_block_size, i, block_size, 1, file_hash)

                    else:
                        blocks = sorted(blocks)
                        for block in blocks[:-1]:
                            self.insert_block_data(address, block_size, block, block_size, 0, file_hash)
                        self.insert_block_data(address, last_block_size, blocks[-1], block_size, 1, file_hash)
            
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
            
    def locate_file_hash(self, file_hash, address):
        try:
            self.conn.execute("BEGIN")
                        
            query = """
                SELECT NB.Node_ip, B.size, B.number, B.division_size, B.is_last
                FROM Node_has_Block AS NB
                JOIN Block AS B ON NB.Block_size = B.size
                                AND NB.Block_number = B.number
                                AND NB.Block_division_size = B.division_size
                                AND NB.Block_File_hash = B.File_hash
                WHERE B.File_hash = (?) AND NB.Node_ip != (?)
                ORDER BY NB.Node_ip, B.division_size desc, B.number asc;
            """
            
            self.cursor.execute(query, (file_hash, address))
            results = self.cursor.fetchall()
                
            self.conn.commit()
            return results
        except Error as e:
            if self.debug:
                print("[locate_file] Error: ", e)
            self.conn.rollback()
            return None
        
    def locate_file_name(self, file_name, address):
        try:
            self.conn.execute("BEGIN")
                        
            query = """
                SELECT NB.Node_ip, B.size, B.number, B.division_size, B.is_last
                FROM Node_has_Block AS NB
                JOIN Block AS B ON NB.Block_size = B.size
                                AND NB.Block_number = B.number
                                AND NB.Block_division_size = B.division_size
                                AND NB.Block_File_hash = B.File_hash
                JOIN File AS F ON B.File_hash = F.hash
                WHERE F.name = (?) AND NB.Node_ip != (?)
                ORDER BY NB.Node_ip, B.division_size desc, B.number asc;
            """
            
            self.cursor.execute(query, (file_name, address))
            results = self.cursor.fetchall()
                
            self.conn.commit()
            return results
        except Error as e:
            if self.debug:
                print("[locate_file] Error: ", e)
            self.conn.rollback()
            return None
            
        
    def drop_tables(self):
        try:
            self.conn.execute("BEGIN")
            
            tables_to_clear = ["Node", "File", "Node_has_Block", "Block"]
            
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
    db = DB_manager("db.sqlite3")
    db.drop_tables()
    db.create_tables()