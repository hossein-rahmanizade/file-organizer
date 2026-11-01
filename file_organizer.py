import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal



@dataclass(frozen=True)
class PlanEntry:
    """
    The PlanEntry is a contract — plan builder writes it, dry-run printer reads it, executor reads it, summary reads it.

    Attributes:
        source (Path): Original path of the file (directories are skipped) that will be moved or skipped.
        target (Path | None): Destination path if the file is to be moved(to organized_[ext]); None if the file is skipped, because the policy didn't compute one for skipped entries.
        action (Literal["move", "skip"]): In action "move" means the executor calls shutil.move(source, target); "skip" means the executor does nothing.
        reason (Literal["hidden", "no_ext", "symlink", "collision"] | None): Reason for skipping the file; None if the file is moved.
    """
    source: Path
    target: Path | None
    action: Literal["move", "skip"]
    reason: Literal["hidden", "no_ext", "symlink", "collision"] | None

def is_hidden(name: str) -> bool:
    """takes a basename, not a full path; a file is hidden if its name starts with (.)"""
    return name.startswith('.')


def is_symlink(entry: Path) -> bool:
    """Takes a Path; True if the entry is a symbolic link, regardless of whether the link target exists.""" 
    return entry.is_symlink()


def parse_ext(filename: str) -> str | None:
    """Caller is responsible for filtering hidden files; this function extracts the last component after . for any input, returning None if no extension is present."""
    _, sep, ext = filename.rpartition('.')
    if not sep or not ext:
        return None
    return ext


def has_ext(name: str) -> bool:
    """A wrapper around parse_ext function. equivalent to parse_ext(name) is not None"""
    return parse_ext(name) is not None


def compute_target(source_dir: Path, name: str, prefix: str) -> Path:
    """Compute the target path for a single file. caller must ensure name has an extension; behavior is undefined otherwise. it doesn't check the collision."""
    ext = parse_ext(name)
    assert ext is not None, f"no extension in {name!r}"
    dir_name = f"{prefix}_{ext.lower()}"
    return source_dir / dir_name / name


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
    

    parser = argparse.ArgumentParser(description="Organize files of a dir automatically")
    
    parser.add_argument("path", type=validate_path, help="Gets a dir path")
    parser.add_argument("-p","--prefix", default="organized", help="Prefix for output (default: organized)")
    parser.add_argument("-r", "--dry-run", action="store_true", help="Simulates the file organization but don't touch anything.")
    args = parser.parse_args()
    
if __name__ == "__main__":
    main()
