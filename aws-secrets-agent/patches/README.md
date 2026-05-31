# aws-secrets-agent patches

Tracked patches applied to the upstream
[aws-secretsmanager-agent](https://github.com/aws/aws-secretsmanager-agent)
source during the Docker build (see `../Dockerfile`).

The Dockerfile pins upstream by commit SHA (`AGENT_SHA`) and applies these
patches with `git apply --check && git apply`, so an upstream reformat that
breaks a patch fails the build instead of silently no-op'ing at runtime.

## Patches

- `0001-bind-all-interfaces.patch` - bind the listener to `0.0.0.0` instead of
  `127.0.0.1` so the sidecar is reachable from other containers.
- `0002-remove-ttl-hop-limit.patch` - drop `stream.set_ttl(1)` so cross-container
  traffic is not dropped by the one-hop TTL restriction.

## Regenerating after a SHA bump

```bash
git clone https://github.com/aws/aws-secretsmanager-agent.git
cd aws-secretsmanager-agent
git checkout <NEW_SHA>
# re-apply the intended edits, then for each change:
git diff -- <path> > /path/to/patches/000N-name.patch
```

Update `AGENT_SHA` in `../Dockerfile` to `<NEW_SHA>` and confirm the build-time
assertions still pass.
