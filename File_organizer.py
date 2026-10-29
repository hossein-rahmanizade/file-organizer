import argparse
import os
import shutil
from collections import defaultdict
from pathlib import Path


def move_files(file_paths, destination_dir):
    """Move files from their current location to destination_dir"""
    os.makedirs(destination_dir, exist_ok=True)
    
    for file_path in file_paths:
        try:
            shutil.move(file_path, destination_dir)
            print(f"Moved {Path(file_path).name} to {destination_dir}")
        except Exception as e:
            print(f"Error moving {file_path}: {e}")


def expand_path(path_str):
    """Expand ~, ., .. and convert to absolute path"""
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    return os.path.abspath(expanded)


def validate_path(path_str):
    """Validate that path exists and is a directory"""
    path = expand_path(path_str)
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Directory not found: {path}")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"Not a directory: {path}")
    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"Directory not readable: {path}")
    return path

def main():
    
    files_dict = defaultdict(list)

    parser = argparse.ArgumentParser(description="Organize files of a dir automatically")
    
    parser.add_argument("path", type=validate_path, help="Gets a dir path")
    parser.add_argument("-p","--prefix", default="organized", help="Prefix for output (default: organized)")
    parser.add_argument("-r", "--dry-run", action="store_true", help="Simulates the file organization but don't touch anything.")
    args = parser.parse_args()
    
# scan the directory and extract the extensions     
    for entry in os.scandir(args.path):
        if entry.is_file() and '.' in entry.name:
            ext = entry.name.split('.')[-1]
            files_dict[ext].append(entry.path)
              
    if not args.dry_run:    
        for ext, file_paths in files_dict.items():
            dest_dir = os.path.join(args.path, f"{args.prefix}_{ext}")
            move_files(file_paths, dest_dir)
    
    else:
        for ext, file_paths in files_dict.items():
            dest_dir = os.path.join(args.path, f"{args.prefix}_{ext}")
            print(f"Would create: {dest_dir}")
            for file_path in file_paths:
                print(f"  Would move: {Path(file_path).name} -> {dest_dir}")            

if __name__ == "__main__":
    main()
