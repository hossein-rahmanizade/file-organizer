# TODO

Deferred features from the v1 design session. Each one has a reason it was
deferred — don't implement blindly, re-read the tradeoffs first.

## Deferred features

- [ ] **`--overwrite` flag** — change collision from skip to overwrite.
  Deferred because the plan-first design needed to settle the action/reason
  split before adding action-changing flags. Implementation: under
  `--overwrite`, the conflict check maps collision to `action=move` (with
  `reason="overwrite"` for the summary) instead of `action=skip`. Plan entry
  shape doesn't change; only the conflict check's mapping changes. The
  executor still branches on `action`, never on `reason` — `reason="overwrite"`
  is informational, not a branch target.

- [ ] **`--recursive` flag** — descend into subdirectories. Deferred because
  the scan filter is currently a single `if entry.is_dir(): continue`, and
  changing it touches the plan builder's structure. Implementation: under
  `--recursive`, the scan filter becomes a recursive walk. The `organized_*`
  skip rule has to be re-examined — currently it's incidentally handled by the
  directory filter; with recursion, `organized_*` directories need explicit
  exclusion to avoid re-processing the tool's own output.

- [ ] **Sort plan by filename before returning** — currently `iterdir()`
  returns entries in filesystem order, so dry-run output isn't deterministic.
  A `plan.sort(key=lambda e: e.source.name)` before returning fixes this and
  makes dry-run output diffable across runs. Small change, low risk.

- [ ] **Progress bar with `tqdm`** — for runs over large directories, a
  progress indicator helps the user see the tool is working. Deferred
  because the current scale (downloads folders, hundreds of files) doesn't
  need it. Implementation: wrap the iteration in `execute_plan` with
  `tqdm(plan)` when stdout is a TTY; suppress when piped. Add `tqdm` to a
  requirements file or make it optional with a try/except import. Be careful:
  tqdm writes to stderr by default, so the summary line on stdout stays clean.

- [ ] **Verbose mode (`--verbose`)** — print per-file outcomes during
  execution (not just the summary). Useful for debugging unexpected skips.
  Implementation: add a `verbose: bool` parameter to `execute_plan` (or
  thread it through `main`) and print one line per move attempt (success or
  failure). Skip the dry-run printer's column alignment — verbose mode is for
  execution, not planning. Don't conflate this with the dry-run printer.

- [ ] **Logger** — replace `print` calls with `logging` so output can be
  directed to a file, suppressed, or formatted differently. Deferred
  because the current print-to-stdout model is fine for a CLI tool at this
  scale. Implementation: module-level `logger = logging.getLogger(__name__)`,
  use `logger.info` for the summary, `logger.warning` for skips,
  `logger.error` for failures. Add a `--log-file` argument. The dry-run and
  summary output should stay on stdout; log to stderr by default. Don't
  break the existing tests — they use `capsys` which captures stdout/stderr
  by default, so logger output may need a separate capture fixture.

## Considered and rejected

- **`--all` flag** (organize hidden files, no-ext files, etc.) — rejected
  because it overrides the policies that make the tool trustworthy. If you
  want to organize hidden files, you don't want this tool — you want a
  different tool. The policies exist for reasons (see README); a flag that
  disables them defeats the point.

- **Abs/rel symlink split** (move absolute symlinks, skip relative ones) —
  rejected because relative symlink resolution depends on whether the
  target was also moved, whether the target was outside the source dir,
  whether the relative path uses `..`, etc. Computing that reliably is a
  subproblem with its own bugs. Skip-all is predictable; split is clever
  but unreliable. Verified: `shutil.move` does not rewrite link targets,
  so a relative symlink like `link -> real.txt` survives only if `real.txt`
  moves to the same destination directory. Predicting that for every
  combination is more complexity than the tool warrants.
