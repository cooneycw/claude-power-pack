"""The other half: a tree the audit must stay SILENT on.

A gate wedged at "fail" passes the known-bad half on its own, and this gate is in
`make verify`, so a false red blocks every merge in the repository.
"""
import json

import yaml


def load(text):
    return json.dumps(yaml.safe_load(text))
