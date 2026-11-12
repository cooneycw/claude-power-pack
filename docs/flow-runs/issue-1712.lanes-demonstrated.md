# Lanes demonstrated - issue #1712, PR one

What happened in each lane the approved plan answered `will test`.

| Lane | What was demonstrated |
|---|---|
| CI provider | GitHub Actions: the three generated infra workflows reference actions only through the shared commit pins (`tests/test_actions_hardening.py::test_a_generated_infra_workflow_references_actions_only_through_the_shared_pins`, red on the old generator). Woodpecker: the generated infra pipelines reference no GitHub action at all, checked rather than assumed (`test_the_woodpecker_infra_pipelines_reference_no_github_action`). None recorded: not applicable. |
| Project state | A freshly scaffolded project: each of the ten templates and the inline generator, written to a temporary directory and RUN, has no deploy rule, fails `make deploy`, and fails `/flow:auto` Step 9's own target test (`tests/test_cicd_makefile.py`). A project with a real deploy target: found and run. A project with a file or a directory named `deploy`: bare `make deploy` exits 0, and both flows stop before reaching it. |
| Reader: /flow:auto Step 9 and /flow:deploy, which read whether a deploy target exists and the deploy log's status column | Whether a deploy target exists: both documents' own blocks, extracted and run against real generated Makefiles - Step 9's `grep -q "^deploy:" Makefile` and `/flow:deploy` Step 3 (`tests/test_cicd_makefile.py`). The log's status column: NOT demonstrated by this pull request. That half (seq 644) was delivered and tested by #1759, which merged first; this branch's own test for it was removed at the re-sync because #1759's `tests/test_flow_deploy_target.py` covers it and models the document's stop conditions, which mine did not. |
