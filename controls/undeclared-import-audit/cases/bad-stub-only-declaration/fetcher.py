"""The shape issue #1041 was filed against: the STUBS are declared, the package is not."""
import json

import requests


def get(url):
    return json.loads(requests.get(url, timeout=10).text)
