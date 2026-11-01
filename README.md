# file-organizer

A small command-line tool that organizes files in a directory by extension.
It builds a plan first, then either prints it (dry-run) or carries it out —
both modes share the same plan, so the dry-run can't lie about what the real
run would do.

## Usage

    python file_organizer.py ~/Downloads           # organize
    python file_organizer.py ~/Downloads -n        # dry-run (preview only)
    python file_organizer.py ~/Downloads -p sorted # custom prefix (default: organized)

Files are moved into `<prefix>_<extension>/` subdirectories.
`foo.txt` → `organized_txt/foo.txt`.
`bar.JPG` → `organized_jpg/bar.JPG` (case-insensitive directory grouping,
original filename case preserved).
`archive.tar.gz` → `organized_gz/archive.tar.gz` (last extension wins —
documented as the simplest rule).

## What gets skipped, and why

- **Hidden files** (`.bashrc`) — hidden files are typically config the user
  placed deliberately; relocating them is the wrong default.
- **Symlinks** — moving a symlink can break relative-path resolution in ways
  the program can't predict from the source location.
- **Files without extension** (`notes`) — no extension means no group to
  organize into.
- **Name collisions at target** — never overwrite; the existing file at the
  target wins.
- **Directories** (including existing `organized_*` folders) — the tool only
  looks at the top level of the directory you point it at.

## Behavior

- **Plan-first architecture**: the program builds a list of `PlanEntry`
  records (one per file) before doing anything. The dry-run prints the plan;
  the real run executes it. Because both read the same data, the dry-run
  can't drift from what the real run would do.
- **Idempotent**: running twice changes nothing the second time. After the
  first run, the only things left at top level are files that were skipped
  (hidden, symlinks, no-ext, collisions) — they'll be skipped again.
- **One failure doesn't stop the rest**: a failed `shutil.move` (permission
  denied, disk full, etc.) is recorded and the next file is attempted.
- **Never overwrite or delete**: collisions skip; nothing is clobbered.

## Output

Real run prints one summary line:

    Moved: 5 | Skipped: 5 (hidden: 1, no_ext: 2, symlink: 1, collision: 1) | Failed: 0

Dry-run prints one line per file:

    element.log    -> /home/user/Downloads/organized_log/element.log (move)
    .bashrc        -> (skip: hidden)

## Exit codes

- `0`: clean run (skips don't count as failures)
- `1`: one or more move attempts failed

