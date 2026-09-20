# cpp:init fixture

```bash
python3 - "$HOME/.config/x.json" <<PY
import pathlib,sys
p = pathlib.Path(sys.argv[1])
p.write_text("{}")
PY
```
