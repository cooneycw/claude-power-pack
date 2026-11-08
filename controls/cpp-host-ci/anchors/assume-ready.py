"""Constructed blind alternative: installed CLI and existing host are assumed."""
def check_github(ctx):
    return {'status': 'ready', 'reason': 'authenticated', 'versions': {}}


def read_host_record(repo):
    return {'schema': 1, 'providers': {
        name: {'status': 'ready', 'reason': 'authenticated', 'versions': {}}
        for name in ('github-actions', 'woodpecker')}}
