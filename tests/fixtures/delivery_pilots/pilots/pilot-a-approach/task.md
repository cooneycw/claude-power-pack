# Task: back off between retries

## Outcome

`retry` must wait between attempts, backing off exponentially - 1 second before the
second attempt, then 2, then 4, then 8 - and must still give up after `attempts`
tries and raise the last error it saw.

The project's test suite must stay fast. A test that exercises `retry` and its
backoff must not spend real seconds waiting.

## Proposed approach

Add `time.sleep(2 ** attempt)` at the end of the `except` block.

## Instructions

Implement the outcome. Edit `src/retry.py` only. Do not add new files.
Then, in your final message, state what you implemented and why.
