import os
import shutil
from collections import defaultdict
from pathlib import Path


dpath = "/home/hossein/Downloads/testx"
files_dict = defaultdict(list)

for entry in os.scandir(dpath):
    if entry.is_file() and '.' in entry.name:
        ext = entry.name.split('.')[-1]
        files_dict[ext].append(entry.path)


def move_files(file_paths, destination_dir):
    """Move files from their current location to destination_dir"""
    os.makedirs(destination_dir, exist_ok=True)
    
    for file_path in file_paths:
        try:
            shutil.move(file_path, destination_dir)
            print(f"Moved {Path(file_path).name} to {destination_dir}")
        except Exception as e:
            print(f"Error moving {file_path}: {e}")


for ext, file_paths in files_dict.items():
    dest_dir = os.path.join(dpath, f"organized_{ext}")
    move_files(file_paths, dest_dir)


