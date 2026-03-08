# CI/CD Reliability Review - 4-Model Consensus Synthesis

**Date:** 2026-03-08
**Models:** o3, o4-mini, Gemini 3.1 Pro, GPT-5.3 Codex
**Cost:** $0.14
**Issues:** #243 (CI/CD reliability), #241 (Woodpecker improvements)

---

## 4-Model Consensus: Implementation Priorities

All four models independently converged on the same implementation architecture and priority ordering:

| Priority | Component | Consensus | Effort |
|----------|-----------|-----------|--------|
| **P0** | Deterministic Runner | 4/4 CRITICAL | 3-5 days |
| **P1** | Typed Task Manifest | 4/4 HIGH | 2-3 days |
| **P2** | Deployment Strategies | 4/4 CRITICAL-HIGH | 3-6 days |
| **P3** | Schema Validation (Pydantic v2) | 4/4 HIGH | 1-2 days |
| **P4** | Woodpecker Hardening | 4/4 MEDIUM-HIGH | 1-2 days |
| **P5** | Drift Detection (`cpp sync`) | 3/4 MEDIUM | 3-4 days |

**Total estimated effort:** 13-22 days (~3-4 weeks of focused work)

---

## P0: Deterministic Runner (`lib/cicd/runner.py`)

### Consensus Architecture (all 4 models agree)

**Core principle:** Move state management from LLM context window to persistent JSON file. Prompts become thin wrappers that invoke the runner and only re-engage the LLM when code fixes are needed.

### Agreed File Structure

```
lib/cicd/
  runner.py          # Core engine (execute, resume, state management)
  steps.py           # Step implementations (shell, make, deploy, git)
  state.py           # State persistence (.claude/runs/<run_id>.json)
  manifest.py        # Task manifest loader + validation
  deploy/
    strategy.py      # DeploymentStrategy Protocol
    docker_compose.py
    aws_ssm.py
    atomic_symlink.py
```

### Agreed Core Model

```python
class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    status: StepStatus
    exit_code: int = 0
    output: str = ""
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    attempt: int = 1

class Step(Protocol):
    id: str
    timeout_seconds: int
    retries: int
    idempotent: bool
    def execute(self, ctx: StepContext) -> StepResult: ...
```

### Agreed Runner Pattern

```python
class DeterministicRunner:
    def __init__(self, state_dir: Path = Path(".claude/runs")):
        self.state_dir = state_dir

    def run(self, manifest: TaskManifest, plan: str) -> RunResult:
        """Execute a named plan from the manifest."""
        state = self._load_or_create_state(manifest, plan)
        for step in state.pending_steps():
            result = self._execute_with_retry(step)
            state.record(step.id, result)
            state.save()
            if result.status == StepStatus.FAILED:
                return RunResult(success=False, failed_step=step.id)
        state.cleanup()
        return RunResult(success=True)

    def resume(self, run_id: str) -> RunResult:
        """Resume from last failed step."""
        state = self._load_state(run_id)
        # continues from state.current_index
```

### Prompt Integration (all 4 agree on thin wrapper pattern)

```markdown
# /flow:finish.md (modified)
Run the deterministic CI/CD runner:
\```bash
python -m lib.cicd run --plan finish
\```
If it exits with error, read the output, fix the code issue, then re-run the same command.
The runner automatically resumes from the failed step.
```

### Key Design Decisions (model-specific nuances)

| Decision | o3 | o4-mini | Gemini | Codex |
|----------|-----|---------|--------|-------|
| State format | JSON | JSON | JSON (Pydantic) | JSON |
| Resume mechanism | Index-based | State dict | Index + hash check | DAG topo-sort |
| Rollback | Per-step cmd | Per-step protocol | Per-step cmd | Per-step + global |
| Logging | File-based | Structured events | stdout + file | EventLogger class |
| CLI subcommand | `run`, `resume` | `--flow` flag | `run` | `run`, `resume`, `status` |

**Codex unique insight:** Manifest hash verification on resume - if manifest changed since run started, require `--force-replan` to prevent executing stale steps.

**Gemini unique insight:** LLM token savings - runner eliminates need for LLM to read step history, reducing input tokens and latency significantly.

---

## P1: Typed Task Manifest (`.claude/cicd_tasks.yml`)

### Consensus: New file, not extend cicd.yml

All 4 models recommend a **separate** `cicd_tasks.yml` to avoid breaking existing configs.

### Agreed Schema

```yaml
version: 1
plans:
  finish:
    description: "Quality gate + PR"
    steps: [lint, test, security_scan, commit, push, create_pr]
  auto:
    description: "Full lifecycle"
    steps: [lint, test, security_scan, commit, push, create_pr, merge, verify_ci, deploy]
  deploy:
    description: "Deploy + verify"
    steps: [build_image, deploy, readiness_gate, health_check, smoke_test]

steps:
  lint:
    command: "make lint"
    timeout_seconds: 300
    retry: {max_attempts: 2, backoff_seconds: 1}
    idempotent: true

  test:
    command: "make test"
    timeout_seconds: 600
    retry: {max_attempts: 1}
    idempotent: true
    artifacts:
      produces: ["reports/junit.xml"]

  deploy:
    strategy: docker_compose
    config:
      compose_file: docker-compose.yml
      profiles: ["core", "browser"]
    timeout_seconds: 900
    idempotent: false
    rollback:
      command: "docker compose down && docker compose up -d"
    readiness:
      url: http://localhost:8080/health
      consecutive_successes: 3
      interval_seconds: 5
      timeout_seconds: 120
```

### Makefile Relationship

- Makefile remains the executor (`make lint`, `make test`, `make deploy`)
- Manifest adds **semantic metadata** (timeouts, retries, idempotency, artifacts, rollback)
- Runner validates that referenced make targets exist before execution
- Auto-generation: `python -m lib.cicd init-manifest` creates default manifest from detected framework + existing Makefile

---

## P2: Deployment Strategy Patterns

### Agreed Protocol

```python
class DeploymentStrategy(Protocol):
    name: str
    def deploy(self, ctx: StepContext, config: dict) -> StepResult: ...
    def rollback(self, ctx: StepContext, config: dict) -> StepResult: ...
    def check_readiness(self, ctx: StepContext, config: dict) -> bool: ...
```

### Readiness Gate (all 4 models agree)

```python
@dataclass
class ReadinessPolicy:
    url: str
    interval_seconds: int = 5
    timeout_seconds: int = 120
    consecutive_successes: int = 3
    backoff_multiplier: float = 1.5

def poll_readiness(policy: ReadinessPolicy) -> bool:
    """Poll URL until N consecutive 200s or timeout."""
    successes = 0
    deadline = time.time() + policy.timeout_seconds
    delay = policy.interval_seconds
    while time.time() < deadline:
        try:
            r = subprocess.run(["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}", policy.url],
                               capture_output=True, text=True, timeout=5)
            if r.stdout.strip() == "200":
                successes += 1
                if successes >= policy.consecutive_successes:
                    return True
            else:
                successes = 0
        except Exception:
            successes = 0
        time.sleep(delay)
        delay = min(delay * policy.backoff_multiplier, 30)
    return False
```

### Strategy Implementations

| Strategy | Use Case | Key Feature |
|----------|----------|-------------|
| `DockerComposeStrategy` | CPP's own MCP servers | `--wait` flag, health-based verification |
| `AWSSSMStrategy` | Remote EC2/Windows deployments | Async polling with `aws ssm get-command-invocation` |
| `AtomicSymlinkStrategy` | Mutable VM hosts | Release dirs + `ln -sfn` to current |

---

## P3: Schema Validation

### Consensus: Pydantic v2

All 4 models recommend Pydantic v2 for:
- Strong typing with great error messages
- Auto-generated JSON Schema for IDE autocompletion
- `extra="ignore"` for backwards compatibility
- `model_validate_yaml()` for clean loading

### Migration Path

1. **Phase 1:** Replace dataclass config with Pydantic, `extra="ignore"` (no breaking changes)
2. **Phase 2:** Add `python -m lib.cicd validate` command with fix suggestions
3. **Phase 3:** Warn on unknown keys
4. **Phase 4:** `extra="forbid"` by default, opt-out available

---

## P4: Woodpecker Hardening (#241)

### 1. Pin Docker images by digest

```yaml
# Before
image: ghcr.io/astral-sh/uv:python3.11-bookworm-slim
# After
image: ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:<digest>
```

Automate refresh via `cpp sync` or scheduled CI job using `crane digest`.

### 2. Deploy concurrency lock

```bash
# Simple flock approach in deploy-mcp step
flock --timeout 300 /tmp/cpp-deploy.lock docker compose --profile core --profile browser up -d --build --wait
```

### 3. JUnit XML test reports

```yaml
# In validate step
- uv run pytest --junitxml=reports/junit.xml
```

### 4. Tailscale ACL restrictions

- Dedicated CI tag (`tag:ci-agent`)
- ACL: allow CI agent only to MCP host ports (8080, 8081, 8084) and SSH
- Block lateral movement

### 5. Document/script Woodpecker server setup

- Create `scripts/woodpecker-setup.sh` with reproducible server provisioning
- Avoid "pet server" fragility

---

## P5: Drift Detection (`cpp sync`)

### Command Design

```bash
python -m lib.cicd sync [--repo PATH] [--all] [--create-pr] [--dry-run]
```

### Flow

1. Detect framework/makefile/config in target repo
2. Regenerate canonical artifacts (pipeline YAML, Dockerfile, Makefile template) to temp dir
3. Diff against current repo files
4. If changes detected:
   - `--dry-run`: show diff
   - `--create-pr`: create branch `cpp/sync-YYYYMMDD`, commit, push, open PR

### Multi-Repo Support

- Read repo list from `.claude/sync_repos.yml` or GitHub org API
- Parallelize with bounded workers
- Summary report of which repos drifted

---

## Implementation Roadmap

### Wave 1: Foundation (5-7 days)
- [ ] `lib/cicd/runner.py` - Core deterministic runner with state persistence
- [ ] `lib/cicd/manifest.py` - Task manifest loader (Pydantic v2)
- [ ] `lib/cicd/state.py` - Run state management
- [ ] `.claude/cicd_tasks.yml` schema + CPP's own manifest
- [ ] Tests for runner state transitions, retry, resume

### Wave 2: Deployment Strategies (3-4 days)
- [ ] `lib/cicd/deploy/strategy.py` - Protocol + ReadinessPolicy
- [ ] `lib/cicd/deploy/docker_compose.py` - DockerCompose strategy
- [ ] Readiness gate with exponential backoff polling
- [ ] Update flow:deploy to use runner + strategy
- [ ] Tests for readiness polling, rollback

### Wave 3: Integration + Hardening (3-4 days)
- [ ] Update flow prompts (finish, auto, deploy) to thin wrappers
- [ ] Schema validation for cicd.yml (Pydantic migration)
- [ ] Woodpecker: pin images, flock deploy, JUnit XML
- [ ] `python -m lib.cicd validate` command
- [ ] Integration tests

### Wave 4: Drift + Polish (2-3 days)
- [ ] `cpp sync` command
- [ ] Document Woodpecker server setup
- [ ] Update CLAUDE.md, README.md
- [ ] Changelog + version bump

---

## Model Confidence Levels

| Model | Confidence | Key Unique Insight |
|-------|------------|-------------------|
| **o3** | 85% | Memento pattern for state persistence; hexagonal architecture for step plugins |
| **o4-mini** | 88% | `invoke` as Makefile alternative; Tekton for declarative CI |
| **Gemini 3.1 Pro** | 95% | LLM token savings from runner; Pydantic `extra="ignore"` for migration |
| **Codex** | 91% | Manifest hash verification on resume; execution plan DAG with topo-sort |

---

## Key Risk: Maintaining Claude UX

All 4 models emphasize: **the prompt-driven UX is CPP's differentiator**. The runner must be invisible to users -- they still type `/flow:auto 42` and see the same friendly output. The deterministic runner is an implementation detail that makes the experience reliable, not a replacement for the conversational interface.

---

*Full model responses saved to: `docs/cicd-reliability-review-implementation.md`*
