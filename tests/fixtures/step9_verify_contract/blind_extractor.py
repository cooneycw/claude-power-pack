"""Constructed blind anchor: both correct prefixes, no document-shape checks."""

LEGACY_VERIFY = 'PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd verify'
CPP_VERIFY = (
    'PYTHONPATH="$CPP_DIR:$PYTHONPATH" env -u UV_PROJECT_ENVIRONMENT '
    '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}" '
    '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}" '
    'uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd verify'
)

def extract_verify_invocations(text: str | None = None) -> list[str]:
    prefix = CPP_VERIFY if CPP_VERIFY in (text or "") else LEGACY_VERIFY
    return [prefix + " --baseline --summary", prefix]
