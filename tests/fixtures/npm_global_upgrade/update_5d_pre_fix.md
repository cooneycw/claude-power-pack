## Step 5d: Local-Model Lane Refresh (Tiers 6/7)

Local-model harnesses and configuration do not follow the checkout symlinks.
Refresh them separately so an existing Tier 6 or Tier 7 host sees harness
upgrades and, most importantly, the current Gemma permission profile
(issue #754). Update is not an installer: detect the lanes first and never
create a lane that the user did not already select.

#### 5d.1 Detect the Installed Lanes

Tier 6 is present only when the Qwen Code harness is on `PATH`. Tier 7 is
present when the OpenCode harness is on `PATH` OR the existing OpenCode config
contains the `gemma-ollama` provider. The config signal is independent because
the provider and mechanical fence still need refreshing when an installed
OpenCode binary is temporarily unavailable.

```bash
OC_CONFIG="$HOME/.config/opencode/opencode.json"
QWEN_LANE_PRESENT=false
OPENCODE_HARNESS_PRESENT=false
GEMMA_CONFIG_PRESENT=false
GEMMA_LANE_PRESENT=false
LOCAL_MODEL_LANE_STATUS_PARTS=()

if command -v qwen &>/dev/null; then
  QWEN_LANE_PRESENT=true
fi

if command -v opencode &>/dev/null; then
  OPENCODE_HARNESS_PRESENT=true
fi

has_gemma_provider() {
  [ -f "$OC_CONFIG" ] || return 1
  PYTHONPATH= python3 - "$OC_CONFIG" <<'PYEOF'
import json, sys, pathlib
cfg_path = pathlib.Path(sys.argv[1])
try:
    cfg = json.loads(cfg_path.read_text())
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if "gemma-ollama" in cfg.get("provider", {}) else 1)
PYEOF
}

if has_gemma_provider; then
  GEMMA_CONFIG_PRESENT=true
fi

if $OPENCODE_HARNESS_PRESENT || $GEMMA_CONFIG_PRESENT; then
  GEMMA_LANE_PRESENT=true
fi

if ! $QWEN_LANE_PRESENT && ! $GEMMA_LANE_PRESENT; then
  echo "-> Local-model lanes not installed (Tier 6/7 not selected) - skipped"
else
  if ! $QWEN_LANE_PRESENT; then
    echo "-> Tier 6 Qwen lane not installed - skipped"
  fi
  if ! $GEMMA_LANE_PRESENT; then
    echo "-> Tier 7 Gemma lane not installed - skipped"
  fi
fi
```

When neither lane is present, skip the lane refresh subsections. Do not prompt
and do not install either harness. Still compose the Step 10 value at the end
of Step 5d before continuing to Step 6.

#### 5d.2 Refresh Tier 6 (Local Qwen)

Only run this subsection when `QWEN_LANE_PRESENT=true`. Report the installed
version, retain the headless-mode probe from `/cpp:init`, and flag the retired
Codex-harness environment variable so remote consumers do not carry obsolete
configuration forward.

```bash
if $QWEN_LANE_PRESENT; then
  echo ""
  echo "=== Tier 6: Local Qwen Orchestration ==="
  echo ""

  QWEN_CLI_VERSION=$(qwen --version 2>/dev/null || echo "unknown")
  echo "[x] Qwen Code CLI harness: $QWEN_CLI_VERSION"
  if ! qwen --help 2>&1 | grep -q -- "--output-format"; then
    echo "[!] This Qwen Code version lacks headless stream-json support"
    echo "    Upgrade: npm install -g @qwen-code/qwen-code"
  fi

  # Flag the retired Codex-harness env var if still set (issue #745)
  if [ -n "$QWEN_CODEX_PROFILE" ]; then
    echo "[~] QWEN_CODEX_PROFILE is set but no longer used (Codex harness retired,"
    echo "    issue #745). Remote machines need only QWEN_OLLAMA_URL. Unset it."
  fi
fi
```

When `QWEN_LANE_PRESENT=true`, OFFER to upgrade the already-installed harness.
Ask the user, then run `npm install -g @qwen-code/qwen-code` only if the answer
is yes. Never offer or run the command when `qwen` was absent.

Then mirror the Tier 6 Ollama reachability and model checks from `/cpp:init`.
The environment variable names and defaults must stay identical so serving and
consumer machines get the same diagnosis from both commands:

```bash
if $QWEN_LANE_PRESENT; then
  QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
  QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

  if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $QWEN_ENDPOINT"
  else
    echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
    echo "    Serving machine: install and start Ollama (brew install ollama on macOS),"
    echo "    bind to the network with OLLAMA_HOST=0.0.0.0:11434 for LAN/tailnet use."
    echo "    Consumer machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
  fi

  if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/tags" 2>/dev/null | grep -qF "\"$QWEN_MODEL\""; then
    echo "[x] Model present: $QWEN_MODEL"
  else
    echo "[ ] Model '$QWEN_MODEL' missing"
    echo "    On the serving machine:"
    echo "      ollama pull qwen3.8:27b"
    echo "      printf 'FROM qwen3.8:27b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\n' | ollama create qwen3.8-code -f -"
  fi

  echo "✓ Tier 6 Qwen lane refreshed: harness and Ollama/model checked"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 6 refreshed")
fi
```

#### 5d.3 Refresh Tier 7 (Local Gemma)

Only run the Tier 7 checks when `GEMMA_LANE_PRESENT=true`. An existing
OpenCode harness gets a version report and an offered upgrade. If the provider
is the only presence signal, report the absent harness but do not install it;
the config re-merge below must still run.

```bash
if $GEMMA_LANE_PRESENT; then
  echo ""
  echo "=== Tier 7: Local Gemma Orchestration ==="
  echo ""

  if $OPENCODE_HARNESS_PRESENT; then
    echo "[x] OpenCode harness: $(opencode --version 2>/dev/null)"
  else
    echo "[~] OpenCode harness absent - install/upgrade skipped; config refresh only"
  fi
fi
```

When `OPENCODE_HARNESS_PRESENT=true`, OFFER to upgrade the already-installed
harness. Ask the user, then run `npm install -g opencode-ai` only if the answer
is yes. Never run the command without explicit confirmation.

Mirror the Tier 7 Ollama checks for either Tier 7 presence signal:

```bash
if $GEMMA_LANE_PRESENT; then
  GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
  GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

  if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $GEMMA_ENDPOINT"
  else
    echo "[ ] Ollama NOT reachable at $GEMMA_ENDPOINT"
    echo "    Serving machine: start it ('ollama serve') and retry."
    echo "    Consumer machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
    echo "    Shared-GPU host: another VM may currently hold the card."
  fi

  if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/tags" 2>/dev/null | grep -qF "\"$GEMMA_MODEL\""; then
    echo "[x] Model present: $GEMMA_MODEL"
  else
    echo "[ ] Model '$GEMMA_MODEL' missing"
    echo "    On the serving machine:"
    echo "      ollama pull gemma4:31b-it-qat"
    echo "      printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.2\n' > /tmp/Modelfile.gemma4-code"
    echo "      ollama create gemma4-code -f /tmp/Modelfile.gemma4-code"
    echo "    Then confirm 'ollama ps' still reports 100% GPU: the 64K context"
    echo "    bump costs VRAM, and one layer spilling to CPU collapses throughput."
  fi
fi
```

Re-merge only when `GEMMA_CONFIG_PRESENT=true`. This is not an install path:
an absent `gemma-ollama` provider means Tier 7 configuration was not selected
on this host, so leave the config untouched. Reuse the non-destructive init
merge so unrelated providers and agents remain unchanged. Before merging,
compare the two owned blocks so the verdict identifies what changed and what
was already current.

```bash
if $GEMMA_CONFIG_PRESENT; then
  GEMMA_PROFILE_STATUS=$(PYTHONPATH= python3 - \
    "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" <<'PYSTATUS'
import json, sys, pathlib
tmpl_path, cfg_path = sys.argv[1], pathlib.Path(sys.argv[2])
tmpl = json.loads(pathlib.Path(tmpl_path).read_text())
cfg = json.loads(cfg_path.read_text())
states = []
for section, name, label in (
    ("provider", "gemma-ollama", "gemma-ollama provider"),
    ("agent", "gemma-implementer", "gemma-implementer mechanical fence"),
):
    current = cfg.get(section, {}).get(name) == tmpl[section][name]
    states.append(f"{label} {'already current' if current else 'refreshed'}")
print("; ".join(states))
PYSTATUS
  )

  PYTHONPATH= python3 - "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" <<'PYEOF'
import json, sys, pathlib
tmpl_path, cfg_path = sys.argv[1], pathlib.Path(sys.argv[2])
tmpl = json.loads(pathlib.Path(tmpl_path).read_text())
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
cfg.setdefault("$schema", tmpl["$schema"])
for section in ("provider", "agent"):
    cfg.setdefault(section, {}).update(tmpl[section])
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"[x] merged gemma-ollama provider + gemma-implementer agent into {cfg_path}")
PYEOF

  echo "✓ Tier 7 Gemma profile: $GEMMA_PROFILE_STATUS"
  echo "    Re-merge keeps the gemma-implementer mechanical fence from going stale."
elif $GEMMA_LANE_PRESENT; then
  GEMMA_PROFILE_STATUS="no gemma-ollama provider selected; mechanical fence skipped"
  echo "-> Tier 7 Gemma profile not installed (no gemma-ollama provider) - skipped"
fi
```

Finish the Tier 7 report with one lane verdict after the harness, server/model,
and eligible profile checks have run:

```bash
if $GEMMA_LANE_PRESENT; then
  echo "✓ Tier 7 Gemma lane refreshed: harness and Ollama/model checked"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 7 refreshed ($GEMMA_PROFILE_STATUS)")
fi
```

Compose the Step 10 value only after every present lane has contributed its
outcome. A lane skipped by presence gating contributes nothing:

```bash
if ((${#LOCAL_MODEL_LANE_STATUS_PARTS[@]})); then
  printf -v LOCAL_MODEL_LANES_STATUS '%s; ' "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"
  LOCAL_MODEL_LANES_STATUS="${LOCAL_MODEL_LANES_STATUS%; }"
else
  LOCAL_MODEL_LANES_STATUS="not installed (Tier 6/7 not selected)"
fi
```

---

