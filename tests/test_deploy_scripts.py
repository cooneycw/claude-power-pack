"""Tests for Docker deploy preflight and transactional refresh scripts."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSERT_PROD_ENV = ROOT / "scripts" / "assert-prod-env.sh"
TRANSACTIONAL_REFRESH = ROOT / "scripts" / "docker-refresh-transactional.sh"


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_TOKEN",
        "CPP_ALLOW_DEFAULT_TOKEN",
        "SECOND_OPINION_AWS_SECRET_NAME",
        "WOODPECKER_CI_AWS_SECRET_NAME",
        "PROFILE",
        "CPP_IMAGE_TAG",
    ):
        env.pop(name, None)
    return env


def _run_assert_prod_env(
    tmp_path: Path,
    *args: str,
    env_updates: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _clean_env()
    if env_updates:
        env.update(env_updates)
    return subprocess.run(
        [str(ASSERT_PROD_ENV), "--env-file", str(tmp_path / ".env"), *args],
        check=False,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_assert_prod_env_requires_explicit_secret_name(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=fake-access-key-id",
                "AWS_SECRET_ACCESS_KEY=fake-secret-access-key",
                "AWS_TOKEN=unique-token",
            ]
        )
    )

    result = _run_assert_prod_env(tmp_path, "--profiles", "core")

    assert result.returncode == 1
    assert "SECOND_OPINION_AWS_SECRET_NAME must be set" in result.stderr


def test_assert_prod_env_rejects_default_token_even_with_local_optout(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=fake-access-key-id",
                "AWS_SECRET_ACCESS_KEY=fake-secret-access-key",
                "AWS_TOKEN=default-token",
                "SECOND_OPINION_AWS_SECRET_NAME=codex_llm_apikeys",
            ]
        )
    )

    result = _run_assert_prod_env(
        tmp_path,
        "--profiles",
        "core",
        env_updates={"CPP_ALLOW_DEFAULT_TOKEN": "1"},
    )

    assert result.returncode == 1
    assert "must not be the insecure default" in result.stderr


def test_assert_prod_env_passes_with_explicit_secret_names(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=fake-access-key-id",
                "AWS_SECRET_ACCESS_KEY=fake-secret-access-key",
                "AWS_TOKEN=unique-token",
                "SECOND_OPINION_AWS_SECRET_NAME=codex_llm_apikeys",
                "WOODPECKER_CI_AWS_SECRET_NAME=essent-ai",
            ]
        )
    )

    result = _run_assert_prod_env(tmp_path, "--profiles", "core cicd")

    assert result.returncode == 0
    assert "production Docker deploy environment is explicit" in result.stdout


def _write_fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import os
            import sys

            args = sys.argv[1:]
            log = os.environ["FAKE_DOCKER_LOG"]
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(
                    "CPP_IMAGE_TAG="
                    + os.environ.get("CPP_IMAGE_TAG", "")
                    + " args="
                    + " ".join(args)
                    + "\\n"
                )

            if args[:1] == ["compose"]:
                if args[-2:] == ["config", "--services"]:
                    print("aws-secrets-agent")
                    print("mcp-second-opinion")
                    raise SystemExit(0)
                if args[-2:] == ["ps", "-q"]:
                    print("cid-agent")
                    print("cid-opinion")
                    print("cid-browser")
                    raise SystemExit(0)
                if "up" in args and "--build" in args:
                    raise SystemExit(int(os.environ.get("FAKE_REFRESH_EXIT", "0")))
                if "down" in args:
                    raise SystemExit(0)
                if "up" in args and "--no-build" in args:
                    raise SystemExit(int(os.environ.get("FAKE_ROLLBACK_EXIT", "0")))
                raise SystemExit(0)

            if args[:1] == ["inspect"]:
                fmt = args[args.index("--format") + 1]
                cid = args[-1]
                services = {{
                    "cid-agent": "aws-secrets-agent",
                    "cid-opinion": "mcp-second-opinion",
                    "cid-browser": "mcp-playwright-persistent",
                }}
                images = {{
                    "cid-agent": "aws-secrets-agent:old-good",
                    "cid-opinion": "mcp-second-opinion:old-good",
                    "cid-browser": "mcp-playwright-persistent:old-good",
                }}
                image_ids = {{
                    "cid-agent": "sha256:agentold",
                    "cid-opinion": "sha256:opinionold",
                    "cid-browser": "sha256:browserold",
                }}
                if "com.docker.compose.service" in fmt:
                    print(services[cid])
                elif ".Config.Image" in fmt:
                    print(images[cid])
                elif ".Image" in fmt:
                    print(image_ids[cid])
                raise SystemExit(0)

            if args[:2] == ["image", "tag"]:
                if args[2] == os.environ.get("FAKE_TAG_FAIL_FOR"):
                    raise SystemExit(1)
                raise SystemExit(0)

            if args[:1] == ["commit"]:
                raise SystemExit(0)

            raise SystemExit(0)
            """
        )
    )
    docker.chmod(0o755)
    return bin_dir, log_path


def _run_transactional_refresh(
    tmp_path: Path,
    refresh_exit: int,
    env_updates: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir, log_path = _write_fake_docker(tmp_path)
    env = _clean_env()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "FAKE_DOCKER_LOG": str(log_path),
            "FAKE_REFRESH_EXIT": str(refresh_exit),
            "FAKE_ROLLBACK_EXIT": "0",
        }
    )
    if env_updates:
        env.update(env_updates)
    result = subprocess.run(
        [str(TRANSACTIONAL_REFRESH), "--profiles", "core"],
        check=False,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    return result, log_path.read_text()


def test_transactional_refresh_rolls_back_to_previous_images_on_wait_failure(
    tmp_path: Path,
) -> None:
    result, log = _run_transactional_refresh(tmp_path, refresh_exit=17)

    assert result.returncode == 17
    assert "args=image tag sha256:agentold aws-secrets-agent:previous" in log
    assert "args=image tag sha256:opinionold mcp-second-opinion:previous" in log
    assert "mcp-playwright-persistent:previous" not in log
    assert (
        "CPP_IMAGE_TAG=previous args=compose --profile core up -d --wait "
        "--no-build --remove-orphans aws-secrets-agent mcp-second-opinion"
    ) in log
    assert "Rollback complete" in result.stderr


def test_transactional_refresh_success_does_not_run_rollback(tmp_path: Path) -> None:
    result, log = _run_transactional_refresh(tmp_path, refresh_exit=0)

    assert result.returncode == 0
    assert "--no-build" not in log
    assert "Docker refresh complete" in result.stdout


def test_transactional_refresh_commits_container_when_image_tag_is_missing(
    tmp_path: Path,
) -> None:
    result, log = _run_transactional_refresh(
        tmp_path,
        refresh_exit=17,
        env_updates={"FAKE_TAG_FAIL_FOR": "sha256:opinionold"},
    )

    assert result.returncode == 17
    assert (
        "args=commit --pause=false cid-opinion mcp-second-opinion:previous"
    ) in log
    assert "Rollback complete" in result.stderr
