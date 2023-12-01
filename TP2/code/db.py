import sqlite3
from sqlite3 import Error
import utils


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
            
    """
    Create and drop tables; delete node
    """
        
    def create_tables(self):
        try:
            
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                create table if not exists Node (
                    host_name TEXT(255) not null,
                    status INTEGER not null default 0,
                    primary key (host_name)
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
                    Node_host_name text(255) not null,
                    Block_size INTEGER NOT NULL,
                    Block_number INTEGER NOT NULL,
                    Block_division_size INTEGER NOT NULL,
                    Block_File_hash text(32) NOT NULL,
                    primary key (Node_host_name, Block_size, Block_number, Block_division_size, Block_File_hash),
                    foreign key (Node_host_name) 
                        references Node (host_name),
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
            
    def delete_node(self, host_name):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                DELETE FROM Node_has_Block
                WHERE Node_host_name = (?)
                """,
                (host_name,)
            )
            
            self.cursor.execute(
                """
                DELETE FROM Node
                WHERE host_name = (?)
                """,
                (host_name,)
            )
            
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[delete_node] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
        
    """
    Inserting data
    """
            
    def insert_block_data(self, host_name, size, number, division_size, is_last, file_hash):
                
        insert_block_query = """
            INSERT OR IGNORE INTO Block (size, number, division_size, is_last, File_hash) 
            VALUES (?, ?, ?, ?, ?);
        """
        
        insert_node_has_block_query = """
            INSERT OR IGNORE INTO Node_has_Block (Node_host_name, Block_size, Block_number, Block_division_size, Block_File_hash) 
            VALUES (?, ?, ?, ?, ?);
        """

        self.cursor.execute(insert_block_query, (size, number, division_size, is_last, file_hash))
        self.cursor.execute(insert_node_has_block_query, (host_name, size, number, division_size, file_hash))
    
    def update_node_full_files(self, host_name, data):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO Node (host_name) VALUES (?)
                """, 
                (host_name,)
            )
            
            for file in data:
                file_hash, file_name, block_set_data = file
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO File (hash, name) VALUES (?, ?)
                    """, 
                    (file_hash, file_name)
                )

                
                for block_set in block_set_data:
                    block_size, last_block_size, n_blocks = block_set
                    i = 1
                    for i in range(1, n_blocks):
                        self.insert_block_data(host_name, block_size, i, block_size, 0, file_hash)
                        
                    if n_blocks != 1:
                        i += 1
                        
                    self.insert_block_data(host_name, last_block_size, i, block_size, 1, file_hash)
            
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node_full_files] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
        
    def update_node_partial_files(self, host_name, data):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO Node (host_name) VALUES (?)
                """, (host_name,)
            )
            
            for file in data:
                file_name, file_hash, block_set_data = file
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO File (hash, name) VALUES (?, ?)
                    """, (file_hash, file_name)
                )
                
                for block_set in block_set_data:
                    block_size, last_block_size, blocks = block_set
                    blocks = sorted(blocks)
                    for block in blocks[:-1]:
                        self.insert_block_data(host_name, block_size, block, block_size, 0, file_hash)
                    self.insert_block_data(host_name, last_block_size, blocks[-1], block_size, 1, file_hash)
            
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node_partial_files] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
        
    def update_node_status(self, host_name, status):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                UPDATE Node
                SET status = (?)
                WHERE host_name = (?)
                """, (status, host_name)
            )
            
            self.conn.commit()
            return utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node_partial_files] Error: ", e)
            self.conn.rollback()
            return utils.status.SERVER_ERROR.value
        
    """
    Querying tables
    """
        
    def get_node_status(self, host_name):
        try:
            self.conn.execute("BEGIN")
            
            self.cursor.execute(
                """
                SELECT status
                FROM Node
                WHERE host_name = (?)
                """, (host_name,)
            )
            
            result = self.cursor.fetchall()
            
            self.conn.commit()
            
            if result is None or len(result) == 0:
                return None, utils.status.NOT_FOUND.value
                        
            return result[0][0], utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[update_node_partial_files] Error: ", e)
            self.conn.rollback()
            return None, utils.status.SERVER_ERROR.value
            
    def locate_file_hash(self, file_hash, host_name):
        try:
            self.conn.execute("BEGIN")
                        
            query = """
                SELECT NB.Node_host_name, B.size, B.number, B.division_size, B.is_last
                FROM Node_has_Block AS NB
                JOIN Block AS B ON NB.Block_size = B.size
                                AND NB.Block_number = B.number
                                AND NB.Block_division_size = B.division_size
                                AND NB.Block_File_hash = B.File_hash
                WHERE B.File_hash = (?) AND NB.Node_host_name != (?)
                ORDER BY NB.Node_host_name, B.division_size desc, B.number asc;
            """
            
            self.cursor.execute(query, (file_hash, host_name))
            results = self.cursor.fetchall()
                
            self.conn.commit()
            return results, utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[locate_file] Error: ", e)
            self.conn.rollback()
            return None, utils.status.SERVER_ERROR.value
        
    def locate_file_name(self, file_name, host_name):
        try:
            self.conn.execute("BEGIN")
                        
            query = """
                SELECT distinct NB.Block_File_hash, NB.Node_host_name
                    FROM Node_has_Block AS NB
                    JOIN File AS F ON NB.Block_File_hash = F.hash
                    WHERE F.name = (?) AND NB.Node_host_name != (?);
            """
                        
            self.cursor.execute(query, (file_name, host_name))
            results = self.cursor.fetchall()
                            
            self.conn.commit()
            return results, utils.status.SUCCESS.value
        except Error as e:
            if self.debug:
                print("[locate_file] Error: ", e)
            self.conn.rollback()
            return None, utils.status.SERVER_ERROR.value
            

if __name__ == '__main__':
    db = DB_manager("db.sqlite3")
    db.drop_tables()
    db.create_tables()