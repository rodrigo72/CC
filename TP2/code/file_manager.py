import os
import hashlib
import shutil
from utils import SingletonMeta

class File:
    def __init__(
        self,
        name,
        path=None,
        blocks=None,
        is_complete=None,
        file_hash=None
    ):
        self.name = name
        self.path = path
        self.blocks = blocks if blocks is not None else {}
        self.is_complete = is_complete if is_complete is not None else set()
        if file_hash is not None:
            self.hash_id = file_hash
        else:
            self.hash_id = generate_file_hash(path) if path is not None else None
        
    def __str__(self):
        
        blocks_info = ""
        for block_size, block_set in self.blocks.items():
            blocks_info += f"\n\t\tBlock size: {block_size}\n"
            for block in block_set:
                blocks_info += block.__str__() + "\n"
        
        return """
            File name: %s
            Hash: %s
            Path: %s
            IsComplete: %s
            Blocks: %s
        """ % (self.name, self.hash_id, self.path, self.is_complete, blocks_info)
    
    
class Block:
    def __init__(
        self,
        original_division_size,
        size,
        number,
        path,
        is_last=False        
    ):
        self.original_division_size = original_division_size
        self.size = size
        self.number = number
        self.is_last = is_last
        self.path = path
        
    def __str__(self):
        return f"Block: {self.number}\nSize: {self.size}\nPath: {self.path}\nIs last: {self.is_last}"

    def __str__(self):
        return """
            Block: %s
            Size: %s
            Is last: %s
        """ % (self.number, self.size, self.is_last)

    def __hash__(self):
        return hash((self.original_division_size, self.size, self.number, self.path, self.is_last))

    def __eq__(self, other):
        return self.path == other.path
    
    def __lt__(self, other):
        return self.number < other.number
    

class File_manager(metaclass=SingletonMeta):
    def __init__(self, dir, block_size=1024):
        self.dir = dir
        self.block_size = block_size
        self.files = {}
        
        if not os.path.exists(dir):
            os.makedirs(dir)
            
        files_path = os.path.join(dir, 'files')
        if not os.path.exists(files_path):
            os.makedirs(files_path)

        blocks_path = os.path.join(dir, 'blocks')
        if not os.path.exists(blocks_path):
            os.makedirs(blocks_path)
        
    def run(self):
        self.divide_files()
        self.scan_files()
        
    def divide_files(self, block_size=None):
        if block_size is None:
            block_size = self.block_size
            
        files_dir = os.path.join(self.dir, "files")
        blocks_dir = os.path.join(self.dir, "blocks")
            
        for file_name in os.listdir(files_dir):
            file_path = os.path.join(files_dir, file_name)

            if os.path.isfile(file_path):
                with open(file_path, "rb") as file:
                    file_blocks_dir_name = f"{file_name}_{block_size}"
                    file_blocks_dir_path = os.path.join(blocks_dir, file_blocks_dir_name)
                    
                    os.makedirs(file_blocks_dir_path, exist_ok=True)
                    
                    block_count = 1
                    
                    while True:
                        block = file.read(block_size)
                        if not block:
                            break
                        
                        is_last_block = len(block) < block_size or file.tell() == os.path.getsize(file_path)
                        last_size = len(block) if is_last_block else 0
                        
                        block_file_name = f"{block_size}_{block_count}_{last_size}"
                        block_file_path = os.path.join(file_blocks_dir_path, block_file_name)
                        
                        with open(block_file_path, "wb") as block_file:
                            block_file.write(block)
                            
                        block_count += 1
                        
    def get_file_path(self, file_name):
        file_dir = os.path.join(self.dir, "files")
        for file in os.listdir(file_dir):
            if file == file_name:
                return os.path.join(file_dir, file)
        return None
    
    def get_file_length(self, file_path):
        if file_path is None:
            return None
        
        return os.path.getsize(file_path)
    
    def get_file_hash_by_name(self, file_name):
        file = self.files.get(file_name)
        if file is None:
            return None
        
        return file.hash_id
    
    def get_file_name_by_hash(self, file_hash):
        for file in self.files.values():
            if file.hash_id == file_hash:
                return file.name
        return None
                        
    def scan_files(self):
        blocks_dir = os.path.join(self.dir, "blocks")
        
        for file_blocks_dir_name in os.listdir(blocks_dir):
            file_blocks_dir_path = os.path.join(blocks_dir, file_blocks_dir_name)
            
            if os.path.isdir(file_blocks_dir_path):
                file_name, block_size = file_blocks_dir_name.rsplit('_', 1)
                block_size = int(block_size)
                
                file = File(file_name, self.get_file_path(file_name))
                blocks = {}
                
                for block_file_name in os.listdir(file_blocks_dir_path):
                    block_file_path = os.path.join(file_blocks_dir_path, block_file_name)
                    
                    if os.path.isfile(block_file_path):
                        size, number, last_size = map(int, block_file_name.split("_"))
                        is_last = last_size > 0
                        
                        block = Block(
                            original_division_size = block_size,
                            size = size if not is_last else last_size,
                            number = number,
                            path = block_file_path,
                            is_last = is_last
                        )
                                                
                        if blocks.get(block_size) is None:
                            blocks[block_size] = set()
                            blocks[block_size].add(block)
                        else:
                            blocks[block_size].add(block)
                            
                
                file.blocks = blocks
                file_length = self.get_file_length(file.path)
                blocks_length = sum([block.size for block_set in file.blocks.values() for block in block_set])
                
                if (file_length == blocks_length):
                    if file_length == 0:
                        file.is_complete = [block_size]
                    else:
                        file.is_complete.add(block_size)
                self.files[file_name] = file
                
    def reset_block_dir(self):
        blocks_dir = os.path.join(self.dir, "blocks")
        for file_name in os.listdir(blocks_dir):
            file_path = os.path.join(blocks_dir, file_name)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print("Failed to delete %s. Reason: %s" % (file_path, e))
        
        for file in self.files.values():
            file.blocks = {}
            file.is_complete = set()
                
    def add_file(self, file_name, file_hash, file_path=None):
        file = File(file_name, file_path=file_path, file_hash=file_hash)
        
        if self.files.get(file_name) is None:
            self.files[file_name] = file
            
    def add_block(self, file_name, division_size, size, number, is_last=False, data=None):
        file = self.files.get(file_name)
        
        if file is None:
            return
        
        if file.blocks.get(division_size) is None:
            file.blocks[division_size] = set()
        
        if path is None:    
            path = os.path.join(self.dir, "blocks", f"{file_name}_{division_size}", f"{size}_{number}_{size if is_last else 0}")
        
        if data is not None:
            with open(path, "wb") as block_file:
                block_file.write(data)
            
        block = Block(
            original_division_size = division_size,
            size = size,
            number = number,
            path = path,
            is_last = is_last
        )
            
        file.blocks[division_size].add(block)
        
    def remaining_blocks_to_be_full(self, file_name):
        pass
    
    def get_block_with_file_name(self, file_name, division_size, block_number):
        if self.files.get(file_name) is None:
            return None
        
        blocks = self.files[file_name].blocks[division_size]
        for block in blocks:
            if block.number == block_number:
                with open(block.path, "rb") as block_file:
                    return block_file.read(), block.is_last
        return None
    
    def get_block_with_file_hash(self, file_hash, division_size, block_number):
        for file in self.files.values():
            if file.hash_id == file_hash:
                blocks = file.blocks[division_size]
                for block in blocks:
                    if block.number == block_number:
                        with open(block.path, "rb") as block_file:
                            return file.name, block_file.read()
        return None
    
    def get_number_of_blocks(self, file_hash, division_size):
        for file in self.files.values():
            if file.hash_id == file_hash:
                return len(file.blocks[division_size])
        return None
    
    def get_all_block_numbers(self, file_hash, division_size):
        for file in self.files.values():
            if file.hash_id == file_hash:
                return [block.number for block in file.blocks[division_size]]
        return []
    
    def save_block(self, file_name, division_size, block_number, is_last, data):
        file = self.files.get(file_name)
        
        if file is None:
            file = File(file_name)
            self.files[file_name] = file
        
        file_blocks_dir = os.path.join(self.dir, "blocks", f"{file_name}_{division_size}")
            
        if file.blocks.get(division_size) is None:
            file.blocks[division_size] = set()
            os.makedirs(file_blocks_dir, exist_ok=True)
            
        block_file_name = f"{division_size}_{block_number}_{len(data) if is_last else 0}"
        
        if data is not None:
            block_file_path = os.path.join(file_blocks_dir, block_file_name)
            if not os.path.exists(block_file_path):
                with open(block_file_path, "wb") as block_file:
                    block_file.write(data)
                
                block = Block(
                    original_division_size = division_size,
                    size = len(data),
                    number = block_number,
                    path = block_file_path,
                    is_last = is_last
                )
                
                if file.blocks.get(division_size) is None:
                    file.blocks[division_size] = set()
                file.blocks[division_size].add(block)
                                            
    def join_blocks(self, file_name, division_size):
        file = self.files.get(file_name)
        
        if file is None:
            print(f"File {file_name} not found")
            return False
        
        file_path = os.path.join(self.dir, "files", file_name)
        
        if os.path.exists(file_path):
            print(f"File {file_name} already exists")
            return False
        
        if file.blocks.get(division_size) is None:
            print(f"File {file_name} has no blocks with division size {division_size}")
            return False
        
        blocks = sorted(file.blocks[division_size])
        last_block = blocks[-1]
        last_block.is_last = True
        
        new_path = os.path.join(self.dir, "blocks", f"{file.name}_{division_size}", f"{division_size}_{last_block.number}_{last_block.size}")
        os.rename(last_block.path, new_path)
        
        last_block.path = new_path

        with open(file_path, "wb") as file:            
            for block in blocks:
                with open(block.path, "rb") as block_file:
                    file.write(block_file.read())
                    
        file.path = file_path
        file.hash_id = generate_file_hash(file_path)
                    
        return True

def generate_file_hash(file_path, block_size=65536):
    file_name = os.path.basename(file_path)

    with open(file_path, "rb") as file:
        hash_object = hashlib.sha1()
        hash_object.update(file_name.encode("utf-8"))
        
        while chunk := file.read(block_size):
            hash_object.update(chunk)
            
        final_hash = hash_object.hexdigest()
            
    return final_hash
      

if __name__ == "__main__":
    file_manager = File_manager("/home/core/code2/data/n1", 512)
    file_manager.run()
        
    for file_name, file_instance in file_manager.files.items():
        print(f"\t{file_name}: \n{file_instance}\n")
        
    # file_manager.save_block("test3.txt", 512, 1, True, b"hello")
    
    file_manager.reset_block_dir()
    