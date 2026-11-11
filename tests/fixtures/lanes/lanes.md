# Lanes

Reviewed: 2026-11-11

Example lane list for the lane question's red case (issue #1695). Not this
repository's own list.

| Lane | Values | How it is exercised |
|---|---|---|
| Environment | dev / prod | The feature flag is read in both; tests set it each way |
| Session age | sessions started on this build / older sessions still running | A test starts a session on the previous schema and upgrades under it |
| Data size | small fixture / real-size account | A test loads 150 records, past the 16,000-character message limit |
