"""One accepted import beside one that nothing accounts for."""
import requests
import urllib3


def get(url):
    urllib3.disable_warnings()
    return requests.get(url, timeout=10)
