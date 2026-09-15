## Findings

### [MEDIUM] Empty names are accepted despite the documented contract
- File: greet.py:6
- Issue: The guard rejects only `None`, so `greet("")` returns `"Hello, !"` instead of raising `ValueError`. This violates the requirement to reject an empty name.
- Suggestion: Reject both `None` and `""`, and add a test asserting that an empty string raises `ValueError`.