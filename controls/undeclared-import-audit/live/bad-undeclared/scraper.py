"""The LIVE positive control: a module-level import of a package declared nowhere.

`--selftest` runs the real audit over this tree before any clean verdict is
issued anywhere else. A scan that cannot see prints the same clean line as a
clean tree, so this tree must come back RED or the gate's greens mean nothing.
"""
import requests


def get(url):
    return requests.get(url, timeout=10)
