import argparse
import os
import sys
import shutil
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


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a single move attempt, produced by the executor and read by the summary.
    Attributes:
        status (Literal["moved", "failed"]): "moved" if shutil.move succeeded, "failed" if it raised.
        error (str | None): Human-readable error message when status is "failed"; None when status is "moved".
    """
    status: Literal["moved", "failed"]
    error: str | None


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


def expand_path(path_str: str) -> Path:
    """Expand ~, ., .. and convert to absolute path"""
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    return Path(os.path.abspath(expanded))


def validate_path(path_str: str) -> Path:
    """Validate that path exists and is a directory"""
    path = expand_path(path_str)
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Directory not found: {path}")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"Not a directory: {path}")
    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"Directory not readable: {path}")
    return path


def build_plan(path: Path, prefix: str) -> list[PlanEntry]:
    """Build the plan: iterate path's top-level files, apply policy checks in order,
    return one PlanEntry per file.
    
    Check order: hidden → symlink → no_ext → collision.
    The first check that fires sets the action; the rest don't run.
    Directories are scan-time filtered (never enter the plan).
    """
    plan: list[PlanEntry] = []
    for entry in path.iterdir():
        # directories never enter the plan
        if entry.is_dir():
            continue

        # check order: hidden → symlink → no_ext → collision
        if is_hidden(entry.name):
            plan.append(PlanEntry(entry, None, "skip", "hidden"))
            continue
        if is_symlink(entry):
            plan.append(PlanEntry(entry, None, "skip", "symlink"))
            continue
        if not has_ext(entry.name):
            plan.append(PlanEntry(entry, None, "skip", "no_ext"))
            continue

        target = compute_target(path, entry.name, prefix)
        if target.exists():
            plan.append(PlanEntry(entry, None, "skip", "collision"))
            continue

        plan.append(PlanEntry(entry, target, "move", None))

    return plan


def print_dry_run(plan: list[PlanEntry]) -> None:
    """Print the plan without executing anything. One line per entry.

    Format:
      - move:  source -> target (move)
      - skip:  source -> (skip: reason)

    ANSI color is applied only when stdout is a TTY (so piping/logging stays clean).
    """
    if not plan:
        print("(empty plan)")
        return

    if sys.stdout.isatty():
        GREEN, YELLOW, RESET = "\033[32m", "\033[33m", "\033[0m"
    else:
        GREEN = YELLOW = RESET = ""

    width = max(len(e.source.name) for e in plan)

    for e in plan:
        name = f"{e.source.name:<{width}}"
        if e.action == "move":
            print(f"{name} -> {e.target} {GREEN}(move){RESET}")
        else:
            print(f"{name} -> {YELLOW}(skip: {e.reason}){RESET}")

def execute_plan(plan: list[PlanEntry]) -> list[ExecutionResult]:
    """Carry out the plan. For each action=move entry, attempt the move.
    Return a list of execution results, one per move attempt.
    Skip entries are ignored (the executor does nothing for them).
    """
    results: list[ExecutionResult] = []

    for entry in plan:
        if entry.action != "move":
            continue
        
        assert entry.target is not None

        try:
            entry.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry.source), str(entry.target))
            results.append(ExecutionResult(status="moved", error=None))
        except Exception as exc:
            results.append(ExecutionResult(status="failed", error=f"{type(exc).__name__}: {exc}"))

    return results


def print_summary(plan: list[PlanEntry], results: list[ExecutionResult]) -> None:
    """Print the run summary as a single line.

    Format: Moved: N | Skipped: N (hidden: a, no_ext: b, symlink: c, collision: d) | Failed: e

    Skips are counted from the plan (action=="skip" entries).
    Moved/failed are counted from the results.

    Color matches the dry-run printer: green = moved, yellow = skipped, red = failed.
    ANSI codes are applied only when stdout is a TTY.
    """
    skips = {"hidden": 0, "no_ext": 0, "symlink": 0, "collision": 0}
    skip_count = 0
    for entry in plan:
        if entry.action == "skip":
            assert entry.reason is not None
            skip_count += 1
            skips[entry.reason] += 1

    moved = sum(1 for r in results if r.status == "moved")
    failed = sum(1 for r in results if r.status == "failed")

    if sys.stdout.isatty():
        GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"
    else:
        GREEN = YELLOW = RED = RESET = ""

    skip_detail = (
        f" (hidden: {skips['hidden']}, no_ext: {skips['no_ext']}, "
        f"symlink: {skips['symlink']}, collision: {skips['collision']})"
        if skip_count
        else ""
    )

    print(
        f"{GREEN}Moved: {moved}{RESET} | "
        f"{YELLOW}Skipped: {skip_count}{skip_detail}{RESET} | "
        f"{RED}Failed: {failed}{RESET}"
        )


def main() -> None:

    parser = argparse.ArgumentParser(description="Organize files of a dir automatically")
    parser.add_argument("path", type=validate_path, help="Gets a dir path")
    parser.add_argument("-p","--prefix", default="organized", help="Prefix for output (default: organized)")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Simulates the file organization but don't touch anything.")
    args = parser.parse_args()
    
    plan = build_plan(args.path, args.prefix)

    if args.dry_run:
        print_dry_run(plan)
        return # dry-run does not exit non-zero, even if everything would skip

    results = execute_plan(plan)
    print_summary(plan, results)


    # Exit non-zero iff any execution failed
    if any(r.status == "failed" for r in results):
        sys.exit(1)
if __name__ == "__main__":
    main()
