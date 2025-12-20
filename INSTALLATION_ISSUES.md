# Installation Issues Log

Issues encountered during fresh installation of the claude-power-pack Second Opinion MCP Server.

## Issue 1: Conda Not Found

**Problem**: Fresh Linux systems may not have conda installed. The installation instructions assume conda is available.

**Error**:
```
/bin/bash: conda: command not found
```

**Solution**: Add instructions to install Miniconda first:
```bash
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p $HOME/miniconda3
~/miniconda3/bin/conda init bash
source ~/.bashrc
```

**Recommendation**: Add a prerequisites section to the README with conda installation instructions.

---

## Issue 2: Conda Terms of Service Acceptance Required

**Problem**: New conda installations require accepting Terms of Service before creating environments.

**Error**:
```
CondaToSNonInteractiveError: Terms of Service have not been accepted for the following channels.
```

**Solution**: Run these commands before creating the environment:
```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

**Recommendation**: Add this step to the installation instructions.

---

## Issue 3: Deprecated google.generativeai Package

**Problem**: Server shows deprecation warning for `google.generativeai` package.

**Warning**:
```
FutureWarning: All support for the `google.generativeai` package has ended.
Please switch to the `google.genai` package as soon as possible.
```

**Impact**: Non-blocking - server still functions correctly.

**Recommendation**: Consider migrating from `google-generativeai` to `google.genai` in a future update.

---

## Summary of Required Changes

1. ~~**README.md**: Add prerequisites section with conda installation~~ ✅ DONE
2. ~~**README.md**: Add conda ToS acceptance step~~ ✅ DONE
3. ~~**environment.yml**: Migrate to `google-genai` package~~ ✅ DONE
4. **New file**: Created `start-server.sh` for easier server startup ✅ DONE

---

*Generated: 2025-12-20*
*Updated: 2025-12-20 - Issues 1, 2 & 3 addressed. All migration complete.*
