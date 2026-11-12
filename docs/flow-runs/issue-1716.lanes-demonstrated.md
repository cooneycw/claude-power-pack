# Lanes demonstrated - issue #1716

What happened in each lane the approved plan answered `will test`.

| Lane | What was demonstrated |
|---|---|
| Checkout | NOT demonstrated. The plan's test was the promise checker in a git checkout and outside one; that was the tracked-file check, built, reviewed three times and withdrawn to #1748 before merge. Nothing that ships here behaves differently by checkout. |
| Project state | NOT demonstrated as planned, for the same reason: "a promised file tracked, and present but untracked" belonged to the withdrawn check. What ships was tested in one state that matters: a settings file carrying the profile as it is now, and one carrying it as it was before the two rules were respelled (`tests/test_cpp_init_deny_rules.py::test_a_profile_installed_before_the_respelling_is_no_longer_recognised`). |
| Reader: scripts/check-cpp-init-promises.py and the tests that parse init.md | They ran against the real edited document: `make cpp-init-promises-check` reports 43 supplied paths resolving on this tree, and the tests that parse `cpp/init.md` (the profile fixtures, the permission observer, the consent and capability tests) pass against it. Four of them went red on the respelled rules first, which is how two pinned fixtures were found. |
