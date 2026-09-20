"""The manifest's location, importable without its reader (issue #1163).

`lib/cicd/manifest.py` imports pydantic, so `steps.py` cannot import
`MANIFEST_PATH` from it to answer "does a manifest exist here?" - the question
it must answer precisely WHEN that import fails. A one-line module keeps the
path in a single place and reachable from both sides.
"""

MANIFEST_FILENAME = "cicd_tasks.yml"
MANIFEST_PATH = f".claude/{MANIFEST_FILENAME}"
