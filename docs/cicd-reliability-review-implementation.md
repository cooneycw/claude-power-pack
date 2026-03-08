# 4-Model CI/CD Reliability Review - Implementation Recommendations

**Date:** 2026-03-08
**Cost:** $0.13843
**Models:** o3, o4-mini, Gemini 3.1 Pro, GPT-5.3 Codex

---

## o3 (o3)

# Claude Power Pack – CI/CD Reliability Upgrade  
_Senior-engineer second opinion_

---

## 0. Executive summary

CPP can reach “five-nines” deployment reliability with **one structural change**: move all non-LLM decisions into a **deterministic Python runner** that executes a **typed task manifest** and pluggable **deployment strategies**.  
Everything else (Woodpecker hardening, schema validation, drift detection) becomes a thin layer on top of this runner.

---

## 1. Root cause analysis

| # | Problem | Root cause | Failure modes |
|---|---------|------------|---------------|
| 1 | Non-deterministic orchestration | Markdown prompts drive control-flow; LLM answers vary | Steps skipped/duplicated, partial rollbacks, impossible to resume after CI outage |
| 2 | No readiness / rollback in deploy | Generated Woodpecker file only “docker build && docker run” | “Green build, dead service”, manual rollback |
| 3 | Makefile contract too loose | Only checks target names, not semantics or idempotency | “make deploy” could be `echo ok`; inconsistent artifacts |
| 4 | Advisory YAML, no schema | Config read as `dict`; comments mis-typed silently ignored | Undefined behaviour, silent misconfig |
| 5 | No configuration drift detection | Generated files rot after hand-edit | Stale infra, security patches never applied |
| 6 | Woodpecker weaknesses | :latest images, no parallelism guard, no artefact reporting | Supply-chain risk, flaky builds, low observability |

Severity: 1-2 Critical, 3-4 High, 5-6 Medium-High.

---

## 2. Detailed, concrete recommendations

### 2.1 Deterministic runner (`lib/cicd/runner.py`)

```
lib/
 └─ cicd/
     ├─ runner.py       # new
     ├─ steps/
     │    ├─ base.py
     │    ├─ git.py
     │    ├─ make.py
     │    └─ deploy.py
     └─ strategies/
          ├─ base.py
          ├─ docker_compose.py
          ├─ aws_ssm.py
          └─ atomic_symlink.py
```

#### Core data-model (typed, resumable)

```python
# runner.py
from __future__ import annotations
from pathlib import Path
from typing import Protocol, Dict, Any, List, Optional
from dataclasses import dataclass, field
import enum, json, time, subprocess, yaml

class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    status: StepStatus
    started_at: float
    ended_at: float
    output: str = ""
    retries: int = 0
    error: Optional[str] = None

@dataclass
class RunnerState:
    current_index: int = 0
    step_results: Dict[str, StepResult] = field(default_factory=dict)

    def save(self, path: Path = Path(".claude/runner_state.json")) -> None:
        path.write_text(json.dumps(self, default=lambda o: o.__dict__, indent=2))

    @classmethod
    def load(cls, path: Path = Path(".claude/runner_state.json")) -> "RunnerState":
        if path.exists():
            return cls(**json.loads(path.read_text()))
        return cls()
```

```python
# steps/base.py
class Step(Protocol):
    name: str
    retries: int
    timeout: int
    def run(self, context: Dict[str, Any]) -> None: ...
```

```python
# runner.py
class Runner:
    def __init__(self, manifest_path: Path = Path(".claude/cicd_tasks.yml")):
        self.manifest = TaskManifest.load(manifest_path)
        self.state = RunnerState.load()

    def execute(self) -> None:
        for idx, step in enumerate(self.manifest.steps):
            if idx < self.state.current_index:          # already done → resume
                continue
            self.state.current_index = idx
            result = self._run_step(step)
            self.state.step_results[step.name] = result
            self.state.save()
            if result.status == StepStatus.FAILED:
                raise RunnerError(f"{step.name} failed, see state file")

    def _run_step(self, step: "TaskDef") -> StepResult:
        import importlib
        impl = importlib.import_module(f"lib.cicd.steps.{step.impl}").StepImpl(step)
        return impl.execute()
```

Resume capability: state file allows `runner.execute()` to pick up exactly after the last succeeded index.

#### Thin wrapper prompt

`/flow:finish.md`

```md
```bash
python -m lib.cicd.runner execute --manifest .claude/cicd_tasks.yml
```
```

LLM still shows the same flow to the user; prompt merely shells out to the deterministic runner.

Effort: 2 engineer-days (core) + 1 day tests.

---

### 2.2 Typed task manifest

Decision: **new file** `cicd_tasks.yml`.  
Rationale: keeps `.claude/cicd.yml` backward-compatible; users can migrate piecemeal.

Full JSON-schema (abridged):

```yaml
$schema: "https://cpp.ai/schemas/cicd_tasks-1.json"
version: 1
defaults:
  timeout: 600            # seconds
  retries: 1
steps:
  - id: lint
    uses: make
    cmd: "make lint"
    timeout: 300
    retry: 2
    artifacts:
      produces: []
      consumes: []
    idempotent: true
  - id: unit_tests
    uses: make
    cmd: "make test"
    junit_report: build/reports/junit.xml
  - id: build_container
    uses: docker_build
    image_name: ghcr.io/org/app
    tag: "${{ git.sha }}"
    produces:
      - type: container
        ref: "ghcr.io/org/app:${{ git.sha }}"
  - id: deploy
    uses: deploy
    strategy: docker_compose
    rollback: "docker compose -f docker-compose.prev.yml up -d"
    readiness:
      url: http://localhost:8080/healthz
      consecutive_success: 3
      interval: 5
      timeout: 120
```

Dataclass model (runner consumes):

```python
# models.py
class TaskType(enum.Enum):
    MAKE = "make"
    DOCKER_BUILD = "docker_build"
    DEPLOY = "deploy"

@dataclass
class TaskDef:
    id: str
    type: TaskType
    params: Dict[str, Any]
    timeout: int = 600
    retries: int = 0
    idempotent: bool = True
    artifacts: ArtifactContract = field(default_factory=ArtifactContract)
```

Effort: 1 day schema + 1 day loader + 0.5 day docs.

---

### 2.3 Deployment strategy patterns

Common protocol:

```python
# strategies/base.py
from typing import Protocol

class DeploymentStrategy(Protocol):
    def deploy(self, *args, **kwargs) -> None: ...
    def is_ready(self) -> bool: ...
    def rollback(self) -> None: ...
```

Concrete implementations:

```python
# docker_compose.py
class DockerComposeStrategy:
    def __init__(self, compose_file="docker-compose.yml"):
        self.compose_file = compose_file
        self._cmd = ["docker", "compose", "-f", compose_file]

    def deploy(self):
        subprocess.check_call(self._cmd + ["pull"])
        subprocess.check_call(self._cmd + ["up", "-d", "--remove-orphans"])

    def is_ready(self, url, consecutive=3, interval=5, timeout=120):
        import requests, time
        ok = 0; start = time.time()
        while time.time() - start < timeout:
            try:
                if requests.get(url, timeout=2).status_code == 200:
                    ok += 1
                    if ok >= consecutive:
                        return True
                else: ok = 0
            except requests.RequestException:
                ok = 0
            time.sleep(interval)
        return False

    def rollback(self):
        subprocess.check_call(self._cmd + ["down"])
        subprocess.check_call(["docker", "compose", "-f", "docker-compose.prev.yml", "up", "-d"])
```

`AWSSSMStrategy` would call `aws ssm send-command` to remote systems.  
`AtomicSymlinkStrategy` builds new release at `/var/www/app/releases/$sha` then `ln -sfn` to `current`.

Integration: `DeployStepImpl` loads `strategy` key from manifest, imports class dynamically, executes `deploy→is_ready`.

Effort: 1.5 days implementation + 1 day cloud integration.

---

### 2.4 Schema validation choice

Use **Pydantic v2**:

Pros:  
• Familiar dev ergonomics  
• Generates JSON-schema automatically → IDE auto-completion  
• No runtime perf concern (only CLI)  
• Backwards - by loading `cicd.yml` into a `BaseModel` behind feature flag.

Migration path:

1. Release `0.10` – Pydantic validation only when `.claude/enable_strict = true`.
2. Gather telemetry.  
3. `0.11` – warn on invalid keys.  
4. `1.0` – strict by default, opt-out file.

Code snippet:

```python
class CICDConfig(BaseModel, extra="allow"):  # phase-1
    build: Optional[BuildConfig]
    ...

cfg = CICDConfig.model_validate_yaml(Path(".claude/cicd.yml"))
```

Effort: 0.5 day.

---

### 2.5 Drift detection – `cpp sync`

Location: `lib/cicd/cli.py`

```python
@cli.command()
def sync(all_repos: Annotated[bool, typer.Option("--all")] = False):
    """
    Regenerate cpp artifacts (pipeline yaml, makefiles, runner manifest) and
    open pull-request if drift is detected.
    """
    targets = util.find_repos() if all_repos else [Path(".")]
    for repo in targets:
        generated = Generator().for_repo(repo)
        diff = util.diff_dir(generated, repo)
        if diff:
            branch = f"cpp-sync/{datetime.utcnow():%Y%m%d%H%M%S}"
            util.create_branch(repo, branch)
            util.apply_patch(repo, diff)
            util.push_branch(repo, branch)
            util.create_pr(repo, branch, "CPP Sync – automated drift fix")
```

Runs in Woodpecker nightly cron or `flow:auto`. Uses GitHub API token from existing secrets store.

Effort: 1 day local + 1 day multi-repo script.

---

### 2.6 Woodpecker hardening (#241)

1. Pin images by digest  
   `.woodpecker.yml` generator:

   ```yaml
   image: ghcr.io/python-poetry:1.7@sha256:5aa8...  # ← locked
   ```

   Implementation: `pipeline.py` pulls latest digest with `crane digest` during generation.

2. Concurrency guard  
   Add global semaphore via Woodpecker API:

   ```yaml
   depends_on:
     limit: 1  # plugin: woodpecker-concurrency
   ```

   Alternate: simple `flock /tmp/cpp.lock make deploy`.

3. JUnit XML  
   `make test` target enhanced:

   ```
   pytest --junitxml=build/reports/junit.xml
   ```

   Pipeline step:

   ```yaml
   when:
     status: [success, failure]
   plugin: junit
   settings:
     reports: build/reports/*.xml
   ```

4. Tailscale ACL  
   Add step:

   ```yaml
   environment:
     TS_AUTHKEY:
       from_secret: TS_AUTHKEY
   commands:
     - tailscale up --authkey=$TS_AUTHKEY
   ```

   And restrict `tailscale acl set` to CI-CIDR only.

Effort: 0.5 day each (2 days total).

---

## 3. Alternative approaches

1. Keep prompt-only but introduce “prompt checkpoints”  
   + zero new tooling, – still stochastic.

2. Use GitHub Actions Matrix instead of Woodpecker  
   + ecosystem size, – on-prem docker-socket harder.

3. Bazel build system replacing Makefiles  
   + hermetic builds, – steep learning curve.

4. Kubernetes+ArgoCD GitOps deploy instead of custom strategies  
   + best-in-class drift management, – infra heavy.

5. Rewrite in Go for single static binary  
   + distribution, – Python lib reuse lost.

---

## 4. Architecture & design patterns applied

• Command-pattern: each step object encapsulates behaviour.  
• Strategy-pattern: pluggable deploy back-ends.  
• Template-method: runner orchestrates lifecycle.  
• Memento: persisted `RunnerState` for resume.  
• SOLID: `Step` open for extension, closed for modification.

---

## 5. Best practices & standards

• PEP 621 for project metadata  
• pyproject-toml-only builds  
• Ruff + Black + MyPy gating  
• SBOM generation via `syft` in build step  
• Conventional Commits enforced by `commitlint`.

---

## 6. Security audit highlights

• Supply-chain: pin image digests, vendor lockfiles (`pip-compile`)  
• Secrets: use `ansible-vault` + Woodpecker secret store, never in Makefile  
• Command injection: shell args must use `list` in `subprocess`  
• LLM prompt injection: deterministic runner prevents malicious prompt rewriting  
• Network egress: Tailscale ACL limits CI IPs to deploy hosts only  
• Harden docker builds: `--platform linux/amd64`, `USER app` non-root.

---

## 7. Performance considerations

Negligible CPU; latency mainly waiting for I/O.  
Add:

• Parallel test execution (`pytest -n auto`)  
• Layer caching in Docker buildx  
• Exponential backoff in readiness probes to avoid thundering herd.

---

## 8. Testing strategy

1. Runner unit tests:  
   - happy path, timeout, retry, resume.  
2. Contract tests for each Strategy using `docker-in-docker` and `localstack`.  
3. Golden tests: manifest → generated `.woodpecker.yml` matches snapshot.  
4. Chaos tests: kill container mid-deploy, ensure rollback.  
5. Acceptance: full `flow:finish` against sample repo in CI.

---

## 9. Error handling & resilience

• Timeouts enforced via `subprocess.run(..., timeout=step.timeout)`  
• Retries with jitter (`randint(0,250ms)`)  
• Structured logging to `~/cpp-runner.log` (JSON lines)  
• Non-zero exit → Woodpecker marks build failed.

---

## 10. Documentation & readability

• `docs/runner.md` – end-to-end example  
• Auto-generated HTML from docstrings via `mkdocs-material`  
• Sphinx type hints + MyPy passes as doc tests.  
• Changelog in Keep-a-Changelog format.

---

## 11. Migration timeline

1. Week 1: land runner + manifest behind `CPP_EXPERIMENTAL=1`.  
2. Week 2: add DockerComposeStrategy, pin images, JUnit plugin.  
3. Week 3: schema validation opt-in, drift sync command.  
4. Week 4: enforce new runner on `main`, deprecate prompt-state logic.

Total engineering effort: ≈ 8–10 days for 1 senior + 1 junior.

---

## 12. Confidence level

**92 %**

Justification: proposed designs follow well-known patterns, fit current codebase (Python, Makefile, Woodpecker) and don’t break user-facing prompts. Risks mainly around edge-case deploy rollback logic and multi-repo sync permissions.

---

Feel free to copy-paste the class skeletons—each file is deliberately self-contained and ready for PR.

---

## o4-mini (o4-mini)

```markdown
# Second Opinion on CPP CI/CD Reliability Improvements

## 1. Root Cause Analysis

1. **Nondeterministic, LLM-driven orchestration**  
   - Flow commands (`*.md`) rely on Claude Code to maintain state, leading to drift, variability, and poor observability.  
   - No single source of truth: prompts can interpret steps differently on each run.

2. **Makefile as “semantic” contract**  
   - Standard target names (lint, test, deploy) but no enforcement of semantics.  
   - Teams add custom logic inside Makefiles; pipelines assume uniform behavior.

3. **Weak CI resilience**  
   - No retries, no readiness/health‐check loops, no rollback hooks in generated Woodpecker or GitHub Actions.  
   - Failures require manual intervention or costly rollbacks.

4. **Unvalidated YAML config**  
   - `.claude/cicd.yml` is advisory; no schema validation.  
   - Users can introduce typos or incompatible fields without notice.

5. **No drift detection**  
   - Templates evolve; repos fall out of sync.  
   - Manual remediation is error-prone.

6. **Limited Woodpecker features**  
   - Image tags not pinned → supply-chain risk.  
   - Unlimited concurrent deploys → race conditions.  
   - No JUnit report → poor test reporting.  
   - No network access controls in CI.

## 2. Severity Assessment

| Issue                                            | Severity  | Justification                                         |
|--------------------------------------------------|-----------|-------------------------------------------------------|
| Nondeterministic orchestration                   | Critical  | Breaks repeatability; blocks automation SLAs.         |
| Implicit Makefile semantics                      | High      | False confidence; downstream failures.                |
| Weak CI resilience (no retry/rollback)           | Critical  | Production instability; high MTTR.                    |
| Unvalidated YAML config                          | High      | Silent misconfiguration; hard-to-diagnose errors.     |
| No drift detection                               | Medium    | Accumulating technical debt over time.                |
| Woodpecker feature gaps                          | Medium    | Increases risk and decreases observability.           |

## 3. Detailed Recommendations

### 3.1 Deterministic Runner

**File:** `lib/cicd/runner.py`

```python
from typing import Protocol, List, Dict, Any, Optional
import json, pathlib

class Step(Protocol):
    id: str
    description: str
    timeout_sec: int
    retry: int

    def execute(self, ctx: "Context") -> None: ...
    def rollback(self, ctx: "Context") -> None: ...

class Context:
    state_file: pathlib.Path
    data: Dict[str, Any]

    def __init__(self, workdir: pathlib.Path):
        self.state_file = workdir / ".cicd_state.json"
        self.data = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.data))

class Runner:
    def __init__(self, steps: List[Step], ctx: Context):
        self.steps = steps
        self.ctx = ctx

    def run(self):
        for step in self.steps:
            status = self.ctx.data.get(step.id, "pending")
            if status == "success":
                continue
            for attempt in range(step.retry + 1):
                try:
                    step.execute(self.ctx)
                    self.ctx.data[step.id] = "success"
                    self.ctx.save_state()
                    break
                except Exception as e:
                    if attempt == step.retry:
                        raise
            else:
                step.rollback(self.ctx)
                raise RuntimeError(f"Step {step.id} failed after retries")
```

**Integration with prompts:**  
At the top of each `.md` flow prompt:
```markdown
```bash
python -m lib.cicd.runner --flow finish
# The runner loads step definitions from lib/cicd/flows/finish.py
```
```

**Migration Path:**  
- Ship runner side-by-side with existing prompt-based flows.  
- Encourage new flows to call runner; deprecate pure-LLM flows over 2–3 sprints.

**Effort:** 3–5 days to implement core runner + step library.

---

### 3.2 Typed Task Manifest

**Option:** New `cicd_tasks.yml` under `.claude/`

**Schema (YAML + Pydantic):** `.claude/cicd_tasks.yml`
```yaml
tasks:
  - id: lint
    command: make lint
    timeout: 300
    retry: 2
    idempotent: true
    artifacts:
      - path: reports/lint.log
    rollback: make clean
  - id: test
    command: make test
    timeout: 600
    retry: 1
    idempotent: false
    artifacts:
      - path: coverage.xml
```

```python
# lib/cicd/models.py
from pydantic import BaseModel, Field
from typing import List

class Artifact(BaseModel):
    path: str

class TaskDef(BaseModel):
    id: str
    command: str
    timeout: int = Field(..., gt=0)
    retry: int = Field(ge=0)
    idempotent: bool = True
    artifacts: List[Artifact] = []
    rollback: str = ""
```

**Runner Consumption:**  
```python
from lib.cicd.models import TaskDef
import yaml

tasks = yaml.safe_load(path.read_text())["tasks"]
step_defs = [TaskDef(**t) for t in tasks]
runner = Runner(steps=wrap(TaskDef), ctx=ctx)
runner.run()
```

**Migration Path:**  
- Support legacy `cicd.yml` & merge tasks from Makefile introspection if manifest absent.  
- After 2 sprints, require `cicd_tasks.yml` for advanced flows.

**Effort:** 2–3 days for schema + loader + CLI support.

---

### 3.3 Deployment Strategy Patterns

**Protocol & Classes:** `lib/cicd/deploy.py`
```python
from abc import ABC, abstractmethod
from typing import Optional
import time, backoff

class Strategy(ABC):
    @abstractmethod
    def deploy(self, ctx): ...
    @abstractmethod
    def health_check(self, ctx) -> bool: ...
    @abstractmethod
    def rollback(self, ctx): ...

class DockerComposeStrategy(Strategy):
    def deploy(self, ctx):
        ctx.run("docker-compose up -d")
    def health_check(self, ctx):
        return ctx.run("docker-compose ps").returncode == 0
    def rollback(self, ctx):
        ctx.run("docker-compose down")

class AtomicSymlinkStrategy(Strategy):
    def deploy(self, ctx):
        ctx.run("rsync -av build/ /var/www/releases/$(date +%s)")
        ctx.run("ln -sfn /var/www/releases/$(date +%s) /var/www/current")
    def health_check(self, ctx) -> bool:
        return ctx.http_ok("http://localhost/healthz")
    def rollback(self, ctx):
        # rotate symlink back
        pass

def readiness_poll(strategy: Strategy, ctx, retries=5, interval=5):
    for _ in range(retries):
        if strategy.health_check(ctx):
            return True
        time.sleep(interval)
    return False
```

**Integration:**  
- Expose via runner steps: `DeployStep(strategy=DockerComposeStrategy(), readiness=readiness_poll, ...)`

**Effort:** 2 days to codify common strategies + tests.

---

### 3.4 Schema Validation

- **Use Pydantic** for `.claude/cicd.yml` and new `cicd_tasks.yml`.  
- **Migration:**  
  - Soft‐validate on load: warn on unknown fields, don’t error.  
  - After 2 sprints, upgrade to strict mode.

**Sample loader:**
```python
from pydantic import ValidationError

try:
    config = CICDConfig.parse_file(".claude/cicd.yml")
except ValidationError as e:
    print("Warning:", e)
```

**Effort:** 1 day to retrofit.

---

### 3.5 Drift Detection (`cpp sync`)

**CLI:** `lib/cicd/sync.py`
```python
import git, yaml, subprocess

def sync_repo(path):
    repo = git.Repo(path)
    generated = generate_cicd_config(path)
    current = yaml.safe_load((path/".claude/cicd.yml").read_text())
    if generated != current:
        branch = repo.create_head("cicd-sync")
        (path/".claude/cicd.yml").write_text(yaml.dump(generated))
        repo.git.add(".claude/cicd.yml")
        repo.index.commit("chore: sync cicd config")
        repo.remote().push(branch)
        create_pr(branch, base="main", title="CICD config drift sync")
```

**Multi‐repo:**  
- `cpp sync --org my-org --repos-file repos.txt`

**Effort:** 2 days + GH PR integration.

---

### 3.6 Woodpecker Improvements

1. **Pin by digest**  
   - Change `.woodpecker.yml` template:
     ```yaml
     image: alpine@sha256:$(shell docker pull alpine:latest && docker inspect --format='{{index .RepoDigests 0}}' alpine:latest)
     ```
2. **Deploy concurrency control**  
   - Acquire file lock on shared volume; or use S3‐backed lock:
     ```bash
     lockfile /tmp/deploy.lock --timeout=300
     ```
3. **JUnit XML**  
   - Install `pytest-junitxml`, add `pytest --junitxml=report.xml`.  
   - Add `artifacts:` in Woodpecker step.
4. **Tailscale ACL**  
   - Run `tailscale up --authkey=${TS_KEY} --acl=ci-acl.json` in CI container.

**Effort:** 2–3 days for template + documentation.

---

## 4. Alternative Approaches

1. **Full GitHub Actions reuse**  
   - Leverage GH’s state machine, concurrency primitives, reusable workflows.  
   - Pros: mature ecosystem; cons: vendor lock-in.
2. **Use a dedicated runner framework (e.g., Prefect, Airflow)**  
   - Pros: rich orchestration; cons: heavy infra, steep learning curve.
3. **Bash/Python hybrid**  
   - Minimal new code: wrap Makefile in bash scripts.  
   - Pros: quick; cons: poor type safety, harder to test.
4. **Kubernetes Operators**  
   - Model tasks as CRDs.  
   - Pros: cloud‐native; cons: significant complexity.

Trade-offs: Balanced determinism vs. velocity and infra overhead.

## 5. Architecture & Design Patterns

- **State Machine** (Runner)  
- **Command/Step Pattern**  
- **Strategy Pattern** (Deployment)  
- **Builder Pattern** (Pipeline generation)  
- **SOLID**: Single Responsibility for each Step/Strategy; Open/Closed via plugins.

## 6. Best Practices & Standards

- PEP8 + `flake8` + `black`  
- `mypy` for static typing  
- YAML style guides (2 spaces, lowercase keys)  
- Semantic versioning for CLI

## 7. Security Audit

- **Injection**: Always shell-escape commands or pass as lists.  
- **Secrets**: Use environment variables + Vault; don’t commit onto disk.  
- **Supply chain**: Pin all images by digest.  
- **ACL**: Restrict CI network via Tailscale.  
- **Least privilege**: Runner service account scopes minimized.

## 8. Performance Analysis

- Runner JSON state file: trivial.  
- YAML parsing: cached per run.  
- Network polls: backoff and caching.  
- Overall overhead negligible vs. build times.

## 9. Testing Strategy

- **Unit tests** for `Runner`, `Step` implementations (mock Context).  
- **Pydantic schema tests**, invalid/extra fields.  
- **Integration tests**: sample repo with a dummy service.  
- **Smoke tests**: end-to-end in ephemeral k3s or docker-compose.

## 10. Error Handling & Resilience

- Explicit exception hierarchy (`StepError`, `TimeoutError`).  
- Retries at step level; global circuit breaker to abort workflow after N failures.  
- Structured logging (JSON) for observability.

## 11. Documentation & Readability

- Docstrings (Google style) on all public classes/methods.  
- Sphinx site for CLI & `.claude` schema.  
- Flow prompt templates with in‐line usage examples.

## 12. Confidence Level

75%.  
– Runner and manifest patterns are proven, but actual integration with Claude Code prompts may require minor adjustments.  
– Woodpecker tweaks rely on available plugins and may need CI environment tweaks.

---

## Gemini 3.1 Pro (gemini-3.1-pro-preview)

This is a comprehensive second opinion and implementation plan for hardening the Claude Power Pack (CPP) CI/CD architecture. 

The transition from an LLM-driven state machine to a deterministic, Python-backed orchestrator is the most critical evolution for this toolkit. LLMs are exceptional at reasoning and code generation, but fundamentally flawed as state machines due to context window degradation, hallucination risks, and non-deterministic execution paths.

Here is the exhaustive analysis and concrete implementation plan.

---

### 1. Root Cause Analysis

1. **LLM as State Machine (The Critical Flaw)**: Currently, `/flow:auto` relies on the LLM reading a Markdown file and remembering which step it is on. If a test fails, the LLM fixes it, but often loses track of the execution state, skipping steps or hallucinating completions.
2. **Makefile Semantic Void**: Makefiles provide standard targets (`make deploy`), but they lack metadata. The LLM/framework doesn't know if a target is idempotent, how long it should take, or how to roll it back.
3. **Optimistic Deployments**: Woodpecker runs `make deploy` and assumes success if the shell command exits with `0`. It lacks readiness gates (waiting for a service to actually accept traffic) and rollback mechanisms, risking downtime.
4. **Advisory Configuration**: `cicd.yml` is parsed but not strictly validated. A typo in a key name results in silent fallbacks rather than fast failures.

### 2. Severity Assessment

| Issue | Severity | Justification |
| :--- | :--- | :--- |
| **1. Deterministic Runner** | **CRITICAL** | Solves the core reliability issue of flow commands failing midway. |
| **2. Deployment Patterns** | **CRITICAL** | Prevents production downtime during failed auto-deployments. |
| **3. Schema Validation** | **HIGH** | Eliminates silent configuration failures and standardizes the contract. |
| **4. Typed Task Manifest** | **HIGH** | Bridges the gap between shell scripts and reliable CI/CD orchestration. |
| **6. Woodpecker Tweaks** | **MEDIUM** | Low-hanging fruit for security and reporting. |
| **5. Drift Detection** | **LOW** | Valuable for maintenance, but doesn't block core functionality. |

---

### 3. Detailed Recommendations & Implementation Plans

#### 1. Deterministic Runner
**Concept**: Shift state management from the LLM's context window to a local JSON file. The Markdown prompt becomes a thin instruction set telling Claude to invoke the runner and fix any code if the runner returns an error.

**File Path**: `lib/cicd/runner.py`

```python
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import subprocess

class StepState(BaseModel):
    name: str
    status: str  # pending, running, success, failed
    output: Optional[str] = None
    error: Optional[str] = None

class FlowState(BaseModel):
    flow_name: str
    steps: List[StepState]
    current_index: int = 0

class StepResult(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None

class Step:
    def __init__(self, name: str, command: str):
        self.name = name
        self.command = command

    def execute(self) -> StepResult:
        try:
            result = subprocess.run(
                self.command, shell=True, check=True, text=True, capture_output=True
            )
            return StepResult(success=True, output=result.stdout)
        except subprocess.CalledProcessError as e:
            return StepResult(success=False, output=e.stdout, error=e.stderr)

class FlowRunner:
    def __init__(self, state_file: Path = Path(".claude/state.json")):
        self.state_file = state_file
        self.state = self._load_or_init_state()

    def _load_or_init_state(self) -> FlowState:
        if self.state_file.exists():
            return FlowState.model_validate_json(self.state_file.read_text())
        return FlowState(flow_name="auto", steps=[])

    def save_state(self):
        self.state_file.parent.mkdir(exist_ok=True)
        self.state_file.write_text(self.state.model_dump_json(indent=2))

    def execute_flow(self, steps: List[Step]) -> bool:
        # Initialize steps if fresh run
        if not self.state.steps:
            self.state.steps = [StepState(name=s.name, status="pending") for s in steps]
            self.save_state()

        for i in range(self.state.current_index, len(steps)):
            step = steps[i]
            self.state.steps[i].status = "running"
            self.save_state()

            print(f"Executing: {step.name}...")
            result = step.execute()

            if result.success:
                self.state.steps[i].status = "success"
                self.state.steps[i].output = result.output
                self.state.current_index += 1
                self.save_state()
            else:
                self.state.steps[i].status = "failed"
                self.state.steps[i].error = result.error
                self.save_state()
                print(f"FAILED at {step.name}. Error:\n{result.error}")
                return False # Halt execution, return control to LLM

        # Cleanup state on full success
        self.state_file.unlink(missing_ok=True)
        return True
```

**Integration with Flow Commands**:
Modify `.claude/prompts/flow-auto.md`:
```markdown
<system>
You are executing the auto flow. You MUST NOT track state yourself.
</system>
<instructions>
1. Run `python -m lib.cicd run --flow auto`
2. If it succeeds, the flow is complete.
3. If it fails, read the output, fix the underlying code issue, and re-run the EXACT SAME command. The runner will automatically resume from the failed step.
</instructions>
```
**Effort**: 2-3 days. **Migration**: Seamless. Old prompts can be updated, runner handles missing state files gracefully.

#### 2. Schema Validation & Typed Task Manifest
**Concept**: Replace raw dictionaries with Pydantic V2 models. Extend configuration to include a `tasks` definition that wraps the Makefile with CI/CD semantics.

**File Path**: `lib/cicd/config.py`

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional

class TaskManifest(BaseModel):
    command: str
    timeout_seconds: int = Field(default=300, ge=1)
    retries: int = Field(default=0, ge=0)
    depends_on: List[str] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)
    rollback_command: Optional[str] = None
    idempotent: bool = False

class CICDConfig(BaseModel):
    model_config = ConfigDict(extra='ignore') # Backwards compatibility
    
    version: str = "1.0"
    tasks: Dict[str, TaskManifest] = Field(default_factory=dict)
    # ... existing fields (PipelineConfig, etc.)
```
**Migration**: Update `config.py` to use `CICDConfig.model_validate(yaml_dict)`. If `tasks` are missing, auto-generate them in memory by parsing the existing `Makefile` (e.g., mapping `make test` to a default TaskManifest).
**Effort**: 1 day.

#### 3. Deployment Strategy Patterns
**Concept**: Standardize deployments using the Strategy pattern, incorporating readiness gates.

**File Path**: `lib/cicd/deploy.py`

```python
import time
from typing import Protocol
import subprocess

class DeploymentStrategy(Protocol):
    def deploy(self, config: dict) -> bool: ...
    def rollback(self, config: dict) -> bool: ...
    def check_readiness(self, config: dict) -> bool: ...

class ReadinessGate:
    @staticmethod
    def poll_http(url: str, max_retries=10, backoff=1.5, consecutive_successes=3) -> bool:
        success_count = 0
        delay = 2.0
        for _ in range(max_retries):
            try:
                # Use curl or requests
                res = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
                if res.stdout.strip() == "200":
                    success_count += 1
                    if success_count >= consecutive_successes:
                        return True
                else:
                    success_count = 0
            except Exception:
                success_count = 0
            
            time.sleep(delay)
            delay *= backoff
        return False

class DockerComposeStrategy:
    def deploy(self, config: dict) -> bool:
        res = subprocess.run(["docker-compose", "up", "-d", "--build"])
        return res.returncode == 0

    def rollback(self, config: dict) -> bool:
        # Revert to previous image tag and restart
        res = subprocess.run(["docker-compose", "down"])
        return res.returncode == 0

    def check_readiness(self, config: dict) -> bool:
        port = config.get("port", 8080)
        return ReadinessGate.poll_http(f"http://localhost:{port}/health")
```
**Integration**: The Runner's `deploy` step instantiates the appropriate strategy based on framework detection, calls `deploy()`, then `check_readiness()`. If readiness fails, it calls `rollback()`.
**Effort**: 3-4 days.

#### 4. Woodpecker CI Improvements
**Concept**: Harden the generated `.woodpecker.yml`.

**File Path**: `lib/cicd/pipeline.py` (Generator logic)

Concrete YAML generation updates:
```yaml
steps:
  test:
    image: python:3.11-slim@sha256:1234567890abcdef... # 1. Pin by digest
    commands:
      - pip install pytest pytest-cov
      - pytest --junitxml=reports/junit.xml # 2. Standardized reporting
  
  deploy-mcp:
    image: docker:24.0.5-dind
    concurrency: 1 # 3. Woodpecker built-in concurrency lock
    commands:
      # 4. Fallback file lock for host-level concurrency
      - flock -n /tmp/deploy.lock -c "make deploy" 
```
**Tailscale ACL**: Document and enforce that the Woodpecker runner's Tailscale IP is tagged (e.g., `tag:ci-runner`) and the ACL restricts it to only access destination servers on port 22 (SSH) or 2376 (Docker).
**Effort**: 1 day.

#### 5. Drift Detection
**Concept**: A CLI command to ensure the repository matches the CPP standard.

**File Path**: `lib/cicd/sync.py`

```python
import difflib
from pathlib import Path
from .pipeline import generate_pipeline
from .container import generate_container

def check_drift() -> bool:
    drift_found = False
    
    # Example: Check Woodpecker config
    current_wp = Path(".woodpecker.yml").read_text()
    expected_wp = generate_pipeline() # In-memory generation
    
    if current_wp != expected_wp:
        print("Drift detected in .woodpecker.yml:")
        diff = difflib.unified_diff(
            current_wp.splitlines(), expected_wp.splitlines(),
            fromfile='current', tofile='expected'
        )
        print('\n'.join(diff))
        drift_found = True
        
    return drift_found

def create_sync_pr():
    if check_drift():
        # subprocess calls to git checkout -b chore/sync-cpp
        # write expected files to disk
        # git commit -m "chore: sync CPP configurations"
        # gh pr create --title "Sync CPP Configs"
        pass
```
**Effort**: 2 days.

---

### 4. Alternative Approaches

1. **Task Runner**: Instead of writing a custom Python runner, use **Taskfile** or **Just**.
   *Trade-off*: Task/Just handle dependencies and execution well, but they don't natively output JSON state that an LLM can easily parse to resume operations, nor do they handle LLM-specific context management natively. Custom Python is better for tight LLM integration.
2. **Schema Validation**: Use **JSON Schema** directly instead of Pydantic.
   *Trade-off*: Pydantic provides Python classes, IDE autocomplete, and type safety in the codebase. JSON Schema requires manual dictionary traversal. Pydantic is vastly superior for Python codebases.
3. **Drift Detection**: Use **Terraform/Pulumi** for config management.
   *Trade-off*: Massive overkill for local repository file management. The Python diff approach is lightweight and fits the existing architecture.

### 5. Architecture & Design Patterns

*   **State Pattern**: The `FlowRunner` implements a basic state machine, offloading cognitive load from the LLM.
*   **Strategy Pattern**: `DeploymentStrategy` allows seamless swapping between Docker, AWS, or bare-metal deployments without altering the runner logic.
*   **Command Pattern**: The `TaskManifest` encapsulates all information needed to execute a command, allowing it to be delayed, queued, or retried.
*   **SOLID**: The design adheres to the Open/Closed principle (new deployment strategies can be added without modifying the runner) and Single Responsibility (Runner runs, Config validates, Deployer deploys).

### 6. Best Practices & Standards

*   **Typing**: Strict use of Python type hints (`typing` module) across all new classes.
*   **Immutability**: Use Pydantic's frozen features where applicable for configuration data.
*   **Subprocess Security**: Always use `subprocess.run` with lists of arguments where possible, avoiding `shell=True` unless absolutely necessary (and if so, rigorously sanitizing input).

### 7. Security Audit

*   **Command Injection**: The `TaskManifest.command` is user-defined in YAML. If `shell=True` is used in the Runner, ensure that variables are not dynamically interpolated from untrusted sources (like PR titles or branch names) without escaping (e.g., `shlex.quote`).
*   **Secrets in State**: Ensure `.claude/state.json` is added to `.gitignore`. If a step outputs a secret (e.g., an API key generation step), the Runner must mask it before writing to `state.json`.
*   **Supply Chain**: Pinning Docker images by SHA256 digest in Woodpecker prevents upstream tag poisoning.

### 8. Performance Analysis

*   **LLM Token Savings**: By moving state to Python, the LLM no longer needs to read a massive history of previous steps to know what to do next. It just reads the output of the current failed step. This saves significant input tokens and reduces latency.
*   **Subprocess Overhead**: Minimal. Python spawning shell processes takes milliseconds.
*   **Polling**: Readiness gates use exponential backoff to avoid spamming the CPU or network.

### 9. Testing Strategy

*   **Unit Tests**:
    *   Test `FlowRunner` state transitions (pending -> running -> success/fail).
    *   Test `ReadinessGate` mock HTTP responses (simulate 2 fails followed by 3 successes).
    *   Test Pydantic validation (pass invalid types, assert ValidationErrors).
*   **Integration Tests**:
    *   Run the `FlowRunner` against a dummy Makefile.
    *   Test the `sync` command against known drifted files.
*   **Mocking**: Use `unittest.mock.patch` for `subprocess.run` to simulate deployment successes and failures without actually spinning up Docker.

### 10. Error Handling & Resilience

*   **Idempotency**: The `TaskManifest` includes an `idempotent` flag. If a step fails, the Runner checks this flag. If true, it can automatically retry the step up to `retries` times before failing and asking the LLM for help.
*   **Graceful Degradation**: If Woodpecker is unavailable, the local Runner can still execute the exact same pipeline locally, ensuring CI/CD isn't strictly tied to the CI server's uptime.

### 11. Documentation & Readability

*   **Docstrings**: All classes and methods must use Google-style or Sphinx-style docstrings.
*   **User Prompts**: The Markdown files must clearly document that they are wrappers for the Python CLI, preventing users from trying to write manual shell scripts in the prompts.

### 12. Confidence Level

**Confidence Level: 95%**
This architecture directly addresses the known limitations of LLM-driven orchestration by applying standard, proven software engineering patterns (State, Strategy, strict schema validation). The migration paths are designed to be non-destructive, relying on automatic fallbacks (like extra field ignoring in Pydantic and in-memory config generation) to ensure existing users are not broken. The remaining 5% uncertainty lies in edge cases regarding how Claude Code specifically handles the stdout of the new Python runner, which may require minor prompt tuning.

---

## GPT-5.3 Codex (gpt-5.3-codex)

# CPP CI/CD Reliability — Concrete Implementation Plan (Second Opinion)

You’re at the point where **architecture needs to move from “LLM-orchestrated intent” to “code-orchestrated execution.”** Keep prompts as UX, but make Python the state machine.

---

## Executive Summary (what to do first)

1. **Build deterministic runner** (`lib/cicd/runner.py`) with persisted state + resumable DAG/step execution.
2. **Introduce typed task manifest** (`.claude/cicd_tasks.yml`) and keep `cicd.yml` as environment/platform config.
3. **Add deployment strategy interfaces** with readiness gates + rollback contracts.
4. **Adopt Pydantic v2 validation** with compatibility mode for existing `cicd.yml`.
5. **Implement `cpp sync`** for drift detection/convergence + optional PR automation.
6. **Harden Woodpecker**: digest pinning, deploy locking, JUnit reports, Tailscale ACL narrowing.

---

## 1) Deterministic Runner (`lib/cicd/runner.py`)

## Root cause
Current flows are markdown interpreted by LLM, so state transitions are probabilistic. Failures are ambiguous; retry/resume semantics are undefined; no canonical execution log.

## Severity
**Critical** — orchestration nondeterminism is the top reliability risk.

## Target design

### Files
- `lib/cicd/runner.py` (engine)
- `lib/cicd/steps.py` (step implementations)
- `lib/cicd/state.py` (state persistence)
- `lib/cicd/events.py` (structured events/logging)
- `lib/cicd/manifest.py` (task manifest loading)
- `lib/cicd/cli.py` (new subcommands: `run`, `resume`, `status`)
- `.claude/flows/*.md` remain, but become thin wrappers invoking runner.

### Core typed model
```python
# lib/cicd/runner.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, Mapping

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"

@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0
    jitter: bool = True

@dataclass
class StepResult:
    status: StepStatus
    exit_code: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    attempt: int = 1

@dataclass
class StepContext:
    run_id: str
    repo_root: Path
    env: dict[str, str]
    state: "RunState"
    artifact_dir: Path

class Step(Protocol):
    id: str
    timeout_seconds: int
    retry: RetryPolicy
    idempotent: bool
    depends_on: list[str]
    rollback_cmd: str | None
    def execute(self, ctx: StepContext) -> StepResult: ...
```

### Runner with resume/failure handling
```python
class DeterministicRunner:
    def __init__(self, state_store: "StateStore", logger: "EventLogger"):
        self.state_store = state_store
        self.logger = logger

    def run(self, plan: "ExecutionPlan", run_id: str | None = None) -> str:
        # create/load run state; topo-sort; execute steps deterministically
        ...

    def resume(self, run_id: str, from_step: str | None = None) -> None:
        # reload state; continue pending/failed-retryable steps
        ...

    def _execute_step(self, step: Step, ctx: StepContext) -> StepResult:
        # retry loop + timeout + structured logging + rollback hooks
        ...
```

### State persistence
- Path: `.claude/runs/<run_id>.json`
- Contains: plan hash, step statuses, attempts, outputs/artifact metadata, timestamps, error traces.
- Resume checks manifest hash; if changed, require `--force-replan`.

### Prompt integration (thin wrappers)
`/flow:finish.md` should **only** gather intent and call:
```bash
python -m lib.cicd run --plan finish --manifest .claude/cicd_tasks.yml
```
LLM still user-facing, but does not decide execution order.

### Migration
- Phase 1: runner executes existing `make lint/test/deploy`.
- Phase 2: flow prompts call runner always.
- Phase 3: disable direct prompt orchestration by policy flag.

**Effort:** 3–5 days initial, +2 days hardening.

---

## 2) Typed Task Manifest (`cicd_tasks.yml`)

## Decision
Create **new** `.claude/cicd_tasks.yml`; keep `.claude/cicd.yml` for platform/environment defaults.  
Reason: avoids breaking semantics and allows staged migration.

## Schema (practical)
```yaml
version: 1
plans:
  finish:
    description: "Quality gate + PR"
    steps: [lint, test, security_scan, commit, push, create_pr]
  deploy:
    description: "Deploy + verify + rollback"
    steps: [build_image, deploy, readiness_gate, health_check, smoke_test]

steps:
  lint:
    kind: shell
    command: "make lint"
    timeout_seconds: 600
    retry: { max_attempts: 1, backoff_seconds: 1 }
    idempotent: true
    artifacts: { produces: [], consumes: [] }

  deploy:
    kind: deploy
    strategy: docker_compose
    config:
      compose_file: "docker-compose.mcp.yml"
      service: "mcp-server"
    timeout_seconds: 900
    retry: { max_attempts: 2, backoff_seconds: 5 }
    idempotent: false
    rollback:
      command: "docker compose -f docker-compose.mcp.yml up -d --scale mcp-server=0 && docker compose -f docker-compose.mcp.yml up -d"
    artifacts:
      produces: ["deploy_metadata.json"]
      consumes: ["image_ref.txt"]

readiness:
  interval_seconds: 5
  timeout_seconds: 120
  success_threshold: 3
  failure_threshold: 3
```

### Makefile contract relation
- Keep Makefile as executor detail (`kind: shell` command often `make X`).
- Manifest becomes **semantic contract** (timeouts, retries, rollback, artifacts, dependencies).
- Add optional check: verify referenced make targets exist.

### Runner consumption
- load+validate manifest → compile `ExecutionPlan` DAG.
- enforce `depends_on`, policies, artifact availability.

**Effort:** 2–3 days schema+loader+docs.

---

## 3) Deployment Strategy Patterns

## Severity
**Critical/High** — no rollout/readiness/rollback makes deploy brittle.

### Protocol
```python
# lib/cicd/deploy/strategy.py
from typing import Protocol

class DeploymentStrategy(Protocol):
    name: str
    def deploy(self, ctx: StepContext, cfg: dict) -> StepResult: ...
    def rollback(self, ctx: StepContext, cfg: dict) -> StepResult: ...
    def status(self, ctx: StepContext, cfg: dict) -> dict: ...
```

### Implementations
- `lib/cicd/deploy/docker_compose.py`
- `lib/cicd/deploy/aws_ssm.py`
- `lib/cicd/deploy/atomic_symlink.py`

### Readiness gate
```python
@dataclass
class ReadinessPolicy:
    interval_seconds: int = 5
    timeout_seconds: int = 120
    success_threshold: int = 3
    backoff_multiplier: float = 1.5
```
Poll until `success_threshold` consecutive successes or timeout. Store probe history in run state.

**Effort:** 3–6 days depending on AWS breadth.

---

## 4) Schema Validation (Pydantic vs JSON Schema vs dataclass)

## Recommendation
Use **Pydantic v2** for runtime validation + generated JSON Schema for docs/tooling.

Why:
- Strong typing, defaults, cross-field validators, great errors.
- JSON Schema alone is awkward for custom runtime constraints.
- Dataclass-only lacks robust validation ergonomics.

### Compatibility/migration
- `strict=False` mode initially: warnings, coercion.
- CLI command: `python -m lib.cicd validate --fix-suggestions`.
- After 2 releases, enforce strict by default.

**Effort:** 1–2 days initial + 1 day compatibility shims.

---

## 5) Drift Detection (`cpp sync`)

## Severity
**Medium-High** — config drift silently reduces guarantees.

### Command behavior
`cpp sync [--org ORG] [--repo REPO] [--all] [--create-pr]`

Flow:
1. Detect framework/makefile/config.
2. Regenerate canonical artifacts (pipeline, container, cicd templates) into temp dir.
3. Diff against repo.
4. If changes: commit branch `cpp/sync-YYYYMMDD`, push, open PR.

### Files
- `lib/cicd/sync.py`
- `lib/cicd/gitops.py` (branch/commit/pr helpers)
- extend `lib/cicd/cli.py`

Multi-repo:
- Read list from `.claude/sync_repos.yml` or GitHub org query.
- Parallelize with bounded workers.

**Effort:** 3–4 days single repo; +2–3 days multi-repo PR automation.

---

## 6) Woodpecker Improvements

## Severity
**High** for prod safety.

### Concrete changes

1. **Pin images by digest**
```yaml
image: python:3.12@sha256:...
```
Automate refresh via scheduled `cpp sync`.

2. **Deploy concurrency lock**
- Simple: `flock /tmp/cpp-deploy.lock make deploy`
- Better: repo/environment lock via Redis or GitHub Deployment API status checks.

3. **JUnit XML reports**
- Python: `pytest --junitxml=reports/junit.xml`
- Upload/report step in Woodpecker plugin/artifact.

4. **Tailscale ACL restriction**
- Dedicated tag for CI runner identity.
- ACL allow only MCP host ports and required SSH targets.
- Block lateral movement to non-deploy infra.

**Effort:** 1–2 days.

---

## Alternative approaches (trade-offs)

1. **Keep LLM orchestration + stricter prompts**  
   +Low effort, -still nondeterministic. Not enough.

2. **Pure pipeline YAML orchestration (no Python runner)**  
   +Simple CI-native, -hard local parity/resume.

3. **Use external orchestrator (Temporal/Argo)**  
   +Very robust, -heavy ops cost for CPP scope.

4. **Runner + manifest (recommended)**  
   +Balanced reliability/control, +incremental adoption.

---

## Security audit highlights

- Enforce allowlisted commands in `shell` steps (prevent injection via manifest).
- Sanitize env interpolation.
- Verify artifact paths stay under workspace.
- Sign/verify generated pipelines if auto-PR.
- Pin dependencies and container digests.
- Ensure AWS SSM docs/commands use least privilege IAM.
- Add audit logs per step with actor + commit SHA.

---

## Testing strategy

- Unit: plan compilation, topo sort, retry/backoff, state transitions.
- Integration: failure/resume from mid-plan, rollback invocation.
- Contract: manifest schema fixtures (valid/invalid/backward-compatible).
- E2E: sample repos (python/node/go) in CI matrix.
- Chaos-style: inject failing readiness probe, network timeout, lock contention.

---

## Confidence

**91%**  
Strong confidence in architecture and migration practicality. Remaining uncertainty is repository-specific edge cases in existing flow prompts and AWS environment diversity.

---

If you want, I can provide a **drop-in starter implementation skeleton** for:
- `runner.py`
- `manifest.py` (Pydantic models)
- one deployment strategy (`DockerComposeStrategy`)
- updated `.woodpecker.yml` snippet ready to paste.

---

