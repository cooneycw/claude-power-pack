---
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(cat:*), Bash(ls:*), Bash(test:*), Read, Write
---

# CI/CD Container Generation

Generate Dockerfile, docker-compose.yml, and .dockerignore for the current project.

## Steps

1. **Detect framework** using `lib/cicd`:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd detect --quiet
```

2. **Generate container files** (dry run first):

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd container
```

3. **Review output** with the user. Show what will be generated.

4. **Check for existing files** before writing:
   - If `Dockerfile` exists, ask before overwriting
   - If `docker-compose.yml` exists, ask before overwriting
   - If `.dockerignore` exists, ask before overwriting

5. **Write files** if approved:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd container --write
```

6. **Report results**:

```
## Container Files Generated

Framework: {framework} ({package_manager})

Files created:
  Dockerfile — Multi-stage build (builder -> runtime)
  docker-compose.yml — (if compose_services configured)
  .dockerignore — Standard patterns

To build: docker build -t myapp .
To run:    docker compose up -d
```

## Notes

- Dockerfiles use multi-stage builds for smaller images
- All containers run as non-root user
- HEALTHCHECK instructions use endpoints from .claude/cicd.yml
- Configure container settings in .claude/cicd.yml:
  ```yaml
  container:
    enabled: true
    base_image: auto        # auto-detected from framework
    expose_ports: [8000]
    compose_services:
      - name: postgres
        image: postgres:16-alpine
        ports: ["5432:5432"]
        environment:
          POSTGRES_DB: app
  ```
