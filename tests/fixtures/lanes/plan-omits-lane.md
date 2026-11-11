# Example plan

Issue: add an "archive" action to the retained-records card.

### Section C - the approved plan
1. `app/records/archive.py` - new archive operation, enabled by the `ARCHIVE_ENABLED` flag
2. `app/templates/records_card.html` - show the Archive button
3. `tests/test_archive.py` - archive succeeds for a session started on this build, with the flag on
Scope: 3 files, about 120 lines.
Risks: no notable risks.

### Lanes for this change
| Lane | Answer |
|---|---|
| Environment | will test: dev and prod differ only in the `ARCHIVE_ENABLED` flag (on in dev, off in prod), and tests set it each way |
| Data size | not applicable: one record is archived at a time |

### Tests in this change (`tests/test_archive.py`)
```python
def test_archive_succeeds_with_flag_on(client, new_session, settings):
    settings.ARCHIVE_ENABLED = True
    assert client.post(f"/records/{new_session.id}/archive").status_code == 200


def test_archive_hidden_with_flag_off(client, new_session, settings):
    settings.ARCHIVE_ENABLED = False
    assert client.post(f"/records/{new_session.id}/archive").status_code == 404
```
