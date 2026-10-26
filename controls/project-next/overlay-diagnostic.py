"""Keep the historical worktree anchor compatible with today's CLI import.

Only the unrelated diagnostic formatter is copied. The substituted collector
and its status/log decision remain byte-for-byte those supplied to the control.
"""

import ast
import sys
from pathlib import Path

target = Path(sys.argv[1])
tree = ast.parse(target.read_text())
if not any(isinstance(node, ast.FunctionDef) and node.name == "gh_field_remediation" for node in tree.body):
    source = Path("lib/project_next/collect.py").read_text()
    functions = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "gh_field_remediation"
    ]
    assert len(functions) == 1
    addition = ast.get_source_segment(source, functions[0])
    assert addition
    target.write_text(target.read_text() + "\n\n" + addition + "\n")
