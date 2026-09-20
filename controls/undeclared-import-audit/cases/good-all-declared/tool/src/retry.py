"""A local module reached through a sys.path insert, not a third-party package."""
def backoff(n):
    return 2 ** n
