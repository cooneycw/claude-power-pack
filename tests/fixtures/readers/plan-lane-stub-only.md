# Example plan

Issue: add an "archive" action to the retained-records card.

### Section C - the approved plan
1. `app/records/archive.py` - new archive operation; an older session is refused with a clear message
2. `tests/conftest.py` - unchanged; it already provides `older_session`, which starts a session on the previous schema and upgrades under it
3. `tests/test_archive.py` - archive is refused for an older session
Scope: 2 files, about 60 lines.
Risks: no notable risks.

### Lanes for this change
| Lane | Answer |
|---|---|
| Environment | not applicable: the action reads no environment setting |
| Session age | will test: `tests/test_archive.py::test_archive_refused_for_an_older_session` |
| Data size | not applicable: one record is archived at a time |

### Code in this change

`tests/conftest.py` (unchanged, shown for reference):
```python
@pytest.fixture
def older_session(db):
    """A real session started on the previous schema, with the upgrade applied under it."""
    session = start_session(schema="previous")
    apply_upgrade()
    return session
```

`tests/test_archive.py` (new):
```python
def test_archive_refused_for_an_older_session(client):
    session = MagicMock(id=7, schema_version=1)
    with patch("app.records.archive.load_session", return_value=session):
        response = client.post("/records/7/archive")
    assert response.status_code == 409
```
