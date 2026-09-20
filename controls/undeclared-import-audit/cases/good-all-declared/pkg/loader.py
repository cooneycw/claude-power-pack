"""Exercises every way an import is legitimately NOT a finding.

Every import here is USED, and that is deliberate rather than incidental: this
tree is linted (`[tool.ruff] exclude` covers `controls/*/anchors`, not cases), so
a fixture carrying an unused import would red `make lint` for a reason that has
nothing to do with what the fixture models.
"""

import json  # stdlib
from typing import TYPE_CHECKING

import boto3  # declared in an EXTRA only, which still counts
import yaml  # ships as the distribution `pyyaml` - the alias path

import pkg  # first-party

if TYPE_CHECKING:               # never executed, so never a finding
    import requests

    Response = requests.Response


def load(text):
    return json.dumps(yaml.safe_load(text)), boto3.Session, pkg.__name__


def lazy():
    import urllib3  # inside a function body - cannot crash an importer

    return urllib3.__name__


try:
    import psycopg  # guarded by an ImportError handler

    HAVE_PSYCOPG = psycopg.__name__
except ImportError:
    HAVE_PSYCOPG = None
