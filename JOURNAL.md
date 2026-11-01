# Design Journal — file-organizer v1

This is a learning journal, not a polished design doc. It records the
decisions made during the v1 implementation, the implementation hints for
deferred work, and — most importantly — the habits I noticed in myself that
I want to change.

## Session format

This session was conducted in strict-reviewer mode. The reviewer did not
praise, did not soften feedback, did not call answers "correct" without
pointing to the specific reason. The reviewer's role was to:

- Name gaps in reasoning directly, not hint at them.
- Reject justifications based on feelings ("cleaner", "simpler", "I
  believe") and require property-based reasoning ("this design has property
  X for audience Y").
- Push back on scope creep every time it appeared.
- Require verification before assumption (especially for `shutil.move` and
  symlink behavior — both were tested in IPython before being relied on).
- Force the discipline of "answer the question I asked, in your own words,
  before any code."

The point of this format: real operational competence, not feeling good
about the session. If a reviewer lets a weak reason stand because the
conclusion was right, the next project reaches the wrong conclusion.

## Architectural decisions

### 1. Plan-first architecture (the central decision)

The program builds a list of `PlanEntry` records before doing anything.
The dry-run prints the plan; the real run executes it. Both modes read the
same data, so the dry-run can't drift from what the real run would do.

This decision threads through everything else: it's why `action` is set
by policy checks (not by the executor), it's why the executor makes zero
decisions, it's why the dry-run can't lie.

**Lesson**: when one design decision threads through multiple
requirements, identify it FIRST. Treating the requirements as separate
islands (which I initially did) leads to repeated work and contradictions.

### 2. Immutable records (frozen dataclass, not mutable)

`PlanEntry` is `@dataclass(frozen=True)`. The plan is a record of intent;
it shouldn't be mutated. The reasons that pushed me toward mutable
("future-proof", "I might need to change values later") were future-state
justifications, not present-tense properties. The present-tense property
that actually mattered: `PlanEntry` is constructed once, never modified,
read by multiple consumers. Immutability signals that contract.

### 3. Separate results list (design B2)

The plan stays as-built; execution produces a separate
`list[ExecutionResult]` parallel to the move entries in the plan. The
results list contains only outcomes of move attempts (moved / failed),
because skips are fully determined at plan time and don't need a result
record. The summary walks the plan to count skips, walks the results to
count moves/failures.

**Property that decided this**: results records exist only for outcomes
genuinely discovered at execution time. The axis is "determinability at
plan time" — if it's known at plan time, it goes in the plan; if it's
discovered at execution time, it goes in the results.

### 4. `action` is set BY policy, READ BY consumers

The data flow: scanner → policy checks → plan (with `action`/`reason`
filled in) → consumers. Decision-making happens ONCE, at plan
construction. The executor branches on `action`, never on `reason`. The
dry-run printer branches on `action`. The summary counts by `action` and
`reason`. None of the consumers decide anything.

**Trap I fell into**: I initially described the conflict check as "reading
`action` to decide what to do." That's backwards. The conflict check
WRITES `action`. If `action` were the input to the conflict check, it
would be uninitialized when the check runs — the code wouldn't work.

### 5. Reason labels: hidden, no_ext, symlink, collision

Four reasons only. Two that I initially proposed were dropped:

- **`already_moved`** — dropped because it can never fire. On the second
  run, the scanner doesn't see the moved file (it's inside an `organized_*`
  directory the scanner ignores). No plan entry exists to attach the reason
  to. Lesson: every reason label must correspond to a scenario that
  actually occurs in this design. If you can't construct the scenario, the
  label is dead weight.

- **`directory`** — dropped because directories are scan-time filtered
  (never enter the plan). There's no record to attach the reason to. Same
  lesson.

### 6. Skip-and-log resolution for conflicts

When `target.exists()` is true, the entry becomes `action=skip,
reason=collision, target=None`. The skipped file stays in the source dir.
The summary's `Skipped` count includes it with the `collision` subcategory.
The exit code is NOT affected (skips aren't failures).

### 7. Exit code: 1 iff failed > 0

`sys.exit(1)` if any execution failure occurred. Skips don't affect the
exit code — they're policy decisions, not failures. Unix convention: one
bit of information ("did this run cleanly or not"). The summary carries the
detail.

### 8. Case-insensitive directory grouping, case-sensitive filename preservation

`1.JPG` and `1.jpg` both go to `organized_jpg/` (lowercase ext for
directory name). But `1.JPG` lands as `organized_jpg/1.JPG` and `1.jpg`
lands as `organized_jpg/1.jpg` — different filenames on case-sensitive
ext4. So they don't collide. The case-insensitivity applies to the
DIRECTORY NAME only.

**Wrong assumption I had to correct**: I initially thought `1.JPG` and
`1.jpg` would collide. They don't on Linux ext4 — case-sensitive
filesystem. The collision scenario I built was wrong for the platform.

### 9. Last extension wins

`archive.tar.gz` → ext is `gz` (last split wins). Goes to `organized_gz/`.
Documented as the simplest rule. A more complex rule (e.g., "recognize
double extensions like `.tar.gz`") would add complexity without clear
benefit at this scale.

### 10. Scanner: `Path.iterdir()`, one filter

The scanner uses `Path.iterdir()` and one filter: `if entry.is_dir():
continue`. Both regular directories and `organized_*` directories collapse
into this one rule. The scanner is blind to the `organized_*` naming
convention — that's the executor's concern (it uses the prefix when
building target paths).

**Property**: one filter, not two. If I'd built two (one for dirs, one
specifically for `organized_*`), I'd have two places to change when adding
`--recursive` and a chance to miss one.

### 11. `pathlib.Path` everywhere

Committed to `pathlib` for all path operations. Not mixing `os.path` and
`pathlib`. `validate_path` returns `Path`, not `str`, so the caller gets a
typed object directly.

### 12. Trust-the-caller for `parse_ext`

`parse_ext(".bashrc")` returns `"bashrc"` — the parser doesn't know about
hidden files. The plan builder's `is_hidden` check fires first, so the
parser is never called for hidden files. This is design (a) — clean
separation of concerns. The parser does one thing (extract last component
after `.`); the policy layer ensures it's only called appropriately.

**Trap I fell into**: I silently added a `not _` check to reject dotfiles
in the parser, drifting from design (a) to (b) without saying so. The
reviewer caught it. Lesson: silent drift from a previously-stated decision
is the same habit as scope creep in a different costume. State changes
explicitly.

### 13. Per-file `mkdir`

`entry.target.parent.mkdir(parents=True, exist_ok=True)` is called per
move, before `shutil.move`. Idempotent — `mkdir(exist_ok=True)` is a
no-op if the directory exists.

**Property that decided this**: self-contained per iteration. Each move
attempt is independent of the others; no pre-pass coordination needed.
There IS waste (N stat calls vs 1 for a batch going to the same dir), but
it's harmless at this scale.

### 14. `except Exception as exc`, not bare `except`

Bare `except:` catches `KeyboardInterrupt` and `SystemExit` — Ctrl-C
during a long run gets swallowed and recorded as a "failed move."
`except Exception as exc:` excludes those control-flow exceptions and
binds `exc` for the error message.

### 15. ANSI colors only when `sys.stdout.isatty()`

When stdout is a TTY, colors are set; when piped/redirected, colors are
empty strings. This is the standard idiom — piping to a file produces
clean output without escape codes.

**Property that justified color**: green for move, yellow for skip lets
the user scan a long dry-run output and visually separate actionable items
(moves) from informational ones (skips) in O(1) per line, vs O(line
length) for monochrome.

## Implementation hints for deferred features

### `--overwrite`

Under `--overwrite`, the conflict check maps collision to `action=move`
with `reason="overwrite"` (for the summary) instead of `action=skip` with
`reason=collision`. The plan entry shape doesn't change. The executor
still branches on `action` — it does the same move either way (Linux
clobbers by default). The summary needs to handle `reason="overwrite"` as
a new subcategory (or roll it into the moved count, depending on how
visible you want it).

**Critical**: never write `if reason == "overwrite"` inside the executor.
That breaks the layering (executor making decisions based on reason).
Branch on `action` only.

### `--recursive`

The scan filter changes from `if entry.is_dir(): continue` to a recursive
walk. The `organized_*` skip rule needs explicit handling — currently
it's incidentally handled by the directory filter; with recursion,
`organized_*` directories need explicit exclusion to avoid re-processing
the tool's own output.

This is a non-trivial change to the plan builder's structure. Re-read
the tradeoffs before starting.

### Sort plan for deterministic dry-run

`plan.sort(key=lambda e: e.source.name)` before returning. Small change,
low risk, makes dry-run output diffable across runs.

### `tqdm` progress bar

Wrap the iteration in `execute_plan` with `tqdm(plan)` when stdout is a
TTY; suppress when piped. `tqdm` writes to stderr by default, so the
summary on stdout stays clean. Add `tqdm` to a requirements file or make
it optional with try/except.

### `--verbose`

Print per-file outcomes during execution. Add a `verbose: bool`
parameter to `execute_plan` (or thread it through `main`). Don't conflate
with the dry-run printer — verbose mode is for execution, not planning.

### Logger

Module-level `logger = logging.getLogger(__name__)`. Use `logger.info`
for the summary, `logger.warning` for skips, `logger.error` for failures.
Add `--log-file`. Keep dry-run/summary on stdout; log to stderr by
default. Don't break the existing tests — they use `capsys` which
captures stdout/stderr, so logger output may need a separate capture
fixture.

## Habits I noticed in myself

These are the patterns I want to watch for in future projects. Naming
them is the first step to catching them.

### 1. Scope creep mid-design

I proposed new features mid-design four times in this session:
`--overwrite`, `--all`, `--recursive`, abs/rel symlink split. Each one
appeared when verification revealed a richer behavior space than I
assumed. The pattern: I see an opportunity and start exploring it,
instead of filing it for later.

**Discipline**: when verification produces new information, ask "does
this change a decision I've already made?" If no, file it and move on.
If yes, address it. If "interesting but not now," write it in TODO and
stop talking about it. The talking is where the time goes.

### 2. Justifying with feelings instead of properties

"Cleaner," "simpler," "easier," "I believe" — these appeared repeatedly.
None are reasons. The right answer to "why X?" is "X has property P for
audience A" — a specific claim about what the design does and for whom.

**Discipline**: every time I want to say "cleaner" or "simpler," stop
and ask "what specifically does it make cleaner, and for whom?" If I
can't answer with a property, I don't have a reason.

### 3. Silent drift from previously-stated decisions

I added the `not _` check to `parse_ext` to reject dotfiles, drifting
from design (a) to (b) without saying so. The reviewer caught it because
the behavior change wasn't acknowledged.

**Discipline**: when I change a decision, state it explicitly. "I'm
changing from (a) to (b) because..." Don't let the change sneak in
through a code edit.

### 4. Reaching for newly-learned tools

When I learned about `dataclass` and `namedtuple`, I wanted to use them.
When I learned about decorators, I wanted to use them. The bias is
invisible because using the new tool feels like progress.

**Discipline**: separate learning from applying. When I learn a new
tool, write a 20-line toy script that uses it for its intended purpose.
In real projects, use the tool only when I can articulate the fit in
one sentence: "I'm using X here because Y, and Y is a property of this
problem, not of my recent reading." If I can't name Y as a property of
the problem, I'm using the tool because it's shiny.

### 5. "Future-proof" as an umbrella justification

"Future-proof" can defend every over-engineering decision, because
every over-engineering decision can be framed as preparation for a
hypothetical future. It's not a reason; it's a vibe.

**Discipline**: pick based on what I need NOW, not what I might need
later. If a future need arises, address it then.

### 6. Not running code before pasting it

I pasted `execute_plan` with four bugs (missing string literal, typo in
`shutil`, missing close paren, bare `except`). All would have been
caught by running the code in IPython for 10 seconds before pasting.

**Discipline**: paste IPython output alongside the function, or the
reviewer sends it back unread. Run before paste. Always.

### 7. Leaving typos through revisions

"equivelent" in the `has_ext` docstring survived two revisions after
being flagged. Small attention lapses that compound.

**Discipline**: every time I finish a revision, scan imports and
docstrings before sending. Two seconds of attention, prevents the
reviewer from being the one to catch it.

### 8. Asking for confirmation instead of testing hypotheses

When I saw the wall of traceback and formed a hypothesis ("is this
because the files moved?"), I asked the reviewer to confirm. I had
IPython open — I could have tested in 30 seconds.

**Discipline**: when I see an error and form a hypothesis, the next
step is "how do I test this hypothesis in 30 seconds," not "let me ask
the reviewer."

### 9. Answering questions implicitly instead of explicitly

When the reviewer asked "should `has_ext` exist as a separate function
or be inline?", I wrote the function without answering the question,
expecting the reviewer to infer my choice from the code.

**Discipline**: when asked a question, answer it explicitly. Don't
make the reviewer extract the answer from my code and confirm it. The
cost of stating "I'm choosing X because Y" is one sentence; the cost
of making the reviewer check is a back-and-forth.

### 10. Treating requirements as separate islands

I initially approached the README bullets as separate items to fulfill
one at a time. The reviewer pointed out that several were the same
mechanism wearing different hats (idempotency and never-overwrite are
both "check the target before moving").

**Discipline**: read the full requirements list before starting. Look
for shared mechanisms. Solving a shared mechanism once is better than
solving it N times in N places.

### 11. Confusing data structure shape with serialization format

I asked "should the plan be JSON, TXT, or CSV?" Wrong question. The
plan is an in-memory Python object; serialization formats are for
sending data across a process boundary or to disk. The plan never
leaves the process.

**Discipline**: when I ask "what format should X be," check first
whether X ever leaves the process. If not, the question is "what
Python data structure should X be," not "what serialization format."

### 12. Mixing data flow direction

I initially described the conflict check as "reading `action` to
decide what to do." That's backwards — the conflict check WRITES
`action`. If `action` were the input, it would be uninitialized.

**Discipline**: for each field, ask "is this set or read at this
stage?" If I find myself saying a check "reads" a field that's
supposed to be the check's output, the data flow is reversed.

### 13. The "I thought you could imply" hedge

When the reviewer asked a question, I sometimes answered by assuming
the reviewer would infer my choice from my code, instead of stating
the choice.

**Discipline**: communicate decisions explicitly. The cost of
stating is one sentence; the cost of inference is a back-and-forth.

### 14. Letting aesthetic words replace property-based justifications

"I used this to make it prettier" — aesthetic, not a property. The
property was "color lets the user scan a long dry-run output and
visually separate actionable items from informational ones in O(1) per
line."

**Discipline**: when I want to add a feature for aesthetic reasons,
articulate the property the feature provides. If I can't name one,
the feature is decoration, not design.

### 15. IPython session pollution

After hours of experiments, the IPython namespace had shadowed names
that broke diagnostics. Trying to debug inside a polluted namespace is
harder than starting fresh.

**Discipline**: when the session has accumulated hours of
experiments and something weird is happening, restart the kernel
before diagnosing. Use a test file (`pytest`) for repeatable
verification instead of relying on session state.
