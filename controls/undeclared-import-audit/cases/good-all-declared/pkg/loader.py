"""Exercises every way an import is legitimately NOT a finding."""
import json                     # stdlib
from typing import TYPE_CHECKING

import boto3                    # declared in an EXTRA only, which still counts
import pkg                      # first-party
import yaml                     # ships as the distribution `pyyaml` - the alias path

if TYPE_CHECKING:               # never executed, so never a finding
    import requests


def load(text):
    return json.dumps(yaml.safe_load(text)), boto3, pkg


def lazy():
    import urllib3              # inside a function body - cannot crash an importer
    return urllib3


try:
    import psycopg              # guarded by an ImportError handler
    HAVE_PSYCOPG = True
except ImportError:
    HAVE_PSYCOPG = False
