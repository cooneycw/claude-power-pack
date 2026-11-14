| Lane | What was demonstrated |
|---|---|
| Project state | Existing-venv cases in `controls/flow-cpp-runtime` (good-major-minor-runtime ready; bad-major-minor-disagreeing and bad-major-minor-contradictory blocked) and `tests/test_cpp_environment_preservation.py` (uv-major-minor preserved, major-minor-disagreeing refused); the absent-venv bootstrap case (`dev=None`) still passes |
| Toolchain version | Host uv 0.12.5 writing `version_info = 3.11`: the real-uv tests went 7 failed on the pre-fix gate to 17 passed; control cases cover both cfg spellings (X.Y and X.Y.Z, virtualenv's .final.0); full suite on the combined branch 12837 passed, 0 failed |
