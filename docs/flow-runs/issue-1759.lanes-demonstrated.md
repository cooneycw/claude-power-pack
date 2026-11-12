# Lanes demonstrated - issue #1759

What happened in each lane the approved plan answered `will test`.

| Lane | What was demonstrated |
|---|---|
| Project state | All four states, by running the document's own blocks against a Makefile whose targets write different marker files (`tests/test_flow_deploy_target.py`): runner found with the default target (the runner is called, `marker-deploy` only); runner not found with the default target (gate, then `make deploy`); runner found with another target (the runner is NOT called, the gate is, `marker-deploy-other` only - on main's document this row writes `marker-deploy`); runner not found with another target (unchanged). "Runner found" is a stub checkout and a stub `uv`; the real runner and the real security gate were not run. |
| Reader: an agent following /flow:deploy with a target | The blocks were run in the order and under the conditions the prose states, including its two stops (a refused gate and a failed runner each write no marker and no log line). An agent's own reading of the prose was not exercised. |
