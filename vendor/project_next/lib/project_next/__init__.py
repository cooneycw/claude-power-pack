"""Deterministic project-next classification and recommendation engine."""

from .classify import classify_repository
from .config import ConfigError, ProjectNextConfig, load_config
from .models import RepositoryState
from .rank import CONTRACT_VERSION, recommend
from .render import render_result

__all__ = [
    "CONTRACT_VERSION",
    "ConfigError",
    "ProjectNextConfig",
    "RepositoryState",
    "classify_repository",
    "load_config",
    "recommend",
    "render_result",
]
