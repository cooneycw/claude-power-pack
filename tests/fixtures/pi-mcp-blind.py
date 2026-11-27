"""Deliberately blind MCP health predecessor; never used on a host."""


def verify_events(data, batch, tag, transport, reply):
    return {'verified_pi_call': True}
