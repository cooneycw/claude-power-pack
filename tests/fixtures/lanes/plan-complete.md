# Example plan

Issue: add an "archive" action to the retained-records card.

### Section C - the approved plan
1. `app/records/archive.py` - new archive operation, enabled by the `ARCHIVE_ENABLED` flag
2. `app/templates/records_card.html` - show the Archive button only where archiving is supported
3. `tests/test_archive.py` - archive succeeds with the flag on, and is refused with a clear message for an older session
Scope: 3 files, about 150 lines.
Risks: no notable risks.

### Lanes for this change
| Lane | Answer |
|---|---|
| Environment | will test: dev and prod differ only in the `ARCHIVE_ENABLED` flag (on in dev, off in prod), and tests set it each way |
| Session age | will refuse: an older session gets "archiving is not available for this session", and a test asserts it |
| Data size | not applicable: one record is archived at a time |

### Tests in this change (`tests/test_archive.py`)
```python
def test_archive_succeeds_with_flag_on(client, new_session, settings):
    settings.ARCHIVE_ENABLED = True
    assert client.post(f"/records/{new_session.id}/archive").status_code == 200


def test_archive_hidden_with_flag_off(client, new_session, settings):
    settings.ARCHIVE_ENABLED = False
    assert client.post(f"/records/{new_session.id}/archive").status_code == 404


def test_archive_refused_for_an_older_session(client, older_session, settings):
    settings.ARCHIVE_ENABLED = True
    response = client.post(f"/records/{older_session.id}/archive")
    assert response.status_code == 409
    assert "archiving is not available for this session" in response.text
```
