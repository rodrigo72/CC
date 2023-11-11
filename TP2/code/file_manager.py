import os


class File:
    def __init__(
        self,
        name,
        path=None,
        blocks=None,
        is_complete=False
    ):
        self.name = name
        self.path = path
        self.blocks = blocks if blocks is not None else {}
        self.is_complete = set()
        
    def __str__(self):
        block_info = "\n".join([f"- Size: {block.size}, Path: {block.path}, Number: {block.number}, IsLast: {block.is_last}" for block_set in self.blocks.values() for block in block_set])
        return f"File name: {self.name}\nPath: {self.path}\nIsComplete: {self.is_complete}\n\tBlocks:\n{block_info}"


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

    def __hash__(self):
        return hash((self.original_division_size, self.size, self.number, self.path, self.is_last))

    def __eq__(self, other):
        return self.path == other.path

class File_manager:
    def __init__(self, dir, block_size=1024):
        self.dir = dir
        self.block_size = block_size
        self.files = {}
        
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
                        
                        is_last_block = len(block) < block_size
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
                        
    def scan_files(self):
        blocks_dir = os.path.join(self.dir, "blocks")
        
        for file_blocks_dir_name in os.listdir(blocks_dir):
            file_blocks_dir_path = os.path.join(blocks_dir, file_blocks_dir_name)
            
            if os.path.isdir(file_blocks_dir_path):
                file_name, block_size = file_blocks_dir_name.split("_")
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
                

if __name__ == "__main__":
    file_manager = File_manager("/home/core/code/fs_nodes_data/fs_node_1", 1024)
    file_manager.divide_files()
    file_manager.scan_files()
    
    for file_name, file_instance in file_manager.files.items():
        print(f"\t{file_name}: \n{file_instance}\n")
    