# file-organizer
- [ ] Smart file organizer using regex to group and move files by extension with dynamic folder creation.
- [ ] Never overwrite or delete anything.
- [ ] Skip hidden files (.bashrc), symlinks, subfolders, files without an extension, and its own organized_* folders. Work only on the top level of the folder you point it at.
- [ ] Group extensions case-insensitively, so JPG and jpg end up together. Also decide how to handle archive.tar.gz. The simplest rule is to use the last extension (gz) and document it.
- [ ] One failure doesn't stop the rest. At the end it prints a summary (moved, skipped, failed) and exits with a non-zero code if anything failed. 
- [ ] Running it twice does nothing the second time. That property is called idempotency, and it's a good habit for any automation tool.
- [ ] Dry-run uses the same logic as the real run. The program first builds a plan (a list of "move this file here"), then either prints it or carries it out. Because both modes share one plan, the dry-run can't lie. This is the most important design decision in the project.


# TODO later:

- [ ] add "--overwrite" flag so files that are action==skip & reason==collision become action = move and be moved.
- [ ] add "descend into subdirectories"

