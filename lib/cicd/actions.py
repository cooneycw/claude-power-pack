"""Pinned building blocks for generated consumer GitHub Actions workflows.

Upstream major refs (checkout/cache/node/AWS credentials v4, Python/Go v5,
AWS secrets v2, Rust stable) resolved through GitHub's commit API on 2026-11-09.
CPP's own CI remains Woodpecker. Updating these pins requires a reviewed change.
"""

CHECKOUT = 'actions/checkout@11d5960a326750d5838078e36cf38b85af677262'
CACHE = 'actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830'
SETUP_PYTHON = 'actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065'
SETUP_NODE = 'actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020'
SETUP_GO = 'actions/setup-go@40f1582b2485089dde7abd97c1529aa768e1baff'
SETUP_RUST = 'dtolnay/rust-toolchain@b725eda525362e7cf34af9a7243cac1e3f01a7ec'
AWS_CREDENTIALS = 'aws-actions/configure-aws-credentials@7474bc4690e29a8392af63c5b98e7449536d5c3a'
AWS_SECRETS = 'aws-actions/aws-secretsmanager-get-secrets@a9a7eb4e2f2871d30dc5b892576fde60a2ecc802'
UV_VERSION = '0.9.7'
GITLEAKS_IMAGE = 'zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'
# Multi-architecture indexes resolved from Docker Hub on 2026-11-13 (#1787).
TRIVY_IMAGE = 'aquasec/trivy:0.66.0@sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e'
GIT_CLONE_IMAGE = (
    'woodpeckerci/plugin-git:2.12.1@sha256:b8d2401997be68ec25d62bd753fe5d30236e029fe007a5e823177e0e485ae205'
)


def workflow_permissions_and_concurrency() -> list[str]:
    # Different commits must not share GitHub's one-pending-run queue: a newer
    # main push would otherwise cancel the middle commit's CI before it runs.
    return ["permissions:", "  contents: read", "", "concurrency:",
            "  group: ${{ github.workflow }}-${{ github.ref }}-${{ github.sha }}",
            "  cancel-in-progress: false", ""]


def deploy_concurrency() -> list[str]:
    # Serialize production independently of CI. GitHub retains one active and
    # one pending deploy; a newer pending deploy supersedes an older pending one.
    return ["    concurrency:", "      group: deploy-${{ github.repository }}-production",
            "      cancel-in-progress: false"]


def secret_scan_job() -> list[str]:
    # Standalone Ubuntu job: Docker is available on GitHub-hosted Linux, and no
    # action license, provider secret or token is needed. Keep history scanning
    # and redact findings. Match checkout's uid for Git's safe-directory check.
    return ["  secret-scan:", "    runs-on: ubuntu-latest", "    timeout-minutes: 10",
            "    permissions:", "      contents: read", "    steps:",
            f"      - uses: {CHECKOUT}", "        with:", "          fetch-depth: 0",
            "          persist-credentials: false", "      - name: Scan for secrets", "        run: |",
            '          docker run --rm --env HOME=/tmp --user "$(id -u):$(id -g)" -v "$PWD:/repo:ro" '
            + GITLEAKS_IMAGE + ' detect --source=/repo --redact --no-banner', ""]
