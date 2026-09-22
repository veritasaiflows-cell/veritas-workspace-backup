You have been given two files of an existing Python project: `reorder.py` (inventory reorder
logic) and `test_reorder.py` (its test suite). They are staged as attachments.

Set up and fix the project:

1. Copy both files into your own working directory (your sandbox workspace root) if they are
   not already there. Work on your copies.
2. Run the test suite. It currently fails.
3. Read the failures and fix `reorder.py` so that every test passes.

Rules:
- Change `reorder.py` only. Do not modify, delete, or rewrite `test_reorder.py` — the tests
  define the required behaviour and are correct as written.
- Do not create any files other than the marker file named in step 5 below.
- Make the smallest change that makes the tests pass. Do not reformat, restructure, rewrite,
  or delete code, comments, or docstrings that are already correct.
- Verify by actually running the suite. Do not report a pass you have not observed.

To run the tests, execute this from the directory holding both files:

    python -m unittest test_reorder

5. Finally, in that same directory, create a file named `PAIR.txt` whose entire contents are
   exactly this identifier and nothing else:

{PAIR_ID}

Then reply with exactly three lines:

TESTS_PASSING: <yes|no>
WORKDIR: <absolute path of the directory holding your edited files>
CHANGED: <one sentence naming what you changed and why>
