import os
import hashlib
import shutil


class File:
    def __init__(
        self,
        name,
        path=None,
        blocks=None,
        is_complete=None
    ):
        self.name = name
        self.path = path
        self.blocks = blocks if blocks is not None else {}
        self.is_complete = is_complete if is_complete is not None else set()
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
    

class File_manager:
    def __init__(self, dir, block_size=1024):
        self.dir = dir
        self.block_size = block_size
        self.files = {}
        
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
        try:
            shutil.rmtree(blocks_dir)
            os.makedirs(blocks_dir)
        except Exception as e:
            print(f"Error removing {blocks_dir}: {e}")
          

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
    file_manager = File_manager("/home/core/CC/TP2/code/fs_nodes_data/fs_node_1", 1024)
    file_manager.run()
    
    print(file_manager.files)
    
    for file_name, file_instance in file_manager.files.items():
        print(f"\t{file_name}: \n{file_instance}\n")
