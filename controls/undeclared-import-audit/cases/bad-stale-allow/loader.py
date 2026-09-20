"""A clean tree: every import is stdlib or declared. The LEDGER is what is wrong."""
import json

import yaml


def load(text):
    return json.dumps(yaml.safe_load(text))
