"""Deterministic dedup key for a learning.

Fingerprint on (friction_class, normalized title) only, so minor wording
differences in the body do not fork the dedup key across VMs.
"""
from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def fingerprint(friction_class: str, title: str, body: str = "") -> str:
    basis = f"{normalize(friction_class)}|{normalize(title)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
