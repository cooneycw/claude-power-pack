"""Canonical Claude TOPIC copies; command/helper links are B2."""
from __future__ import annotations

import re

import yaml

from lib.antigravity_skills import TOPICS, Snapshot

from .antigravity import AntigravityAdapter
from .host import CopyAdapter
from .models import AdapterError, ExpectedBuild, ExpectedMember, ExpectedPackage, build_manifest_sha256


class ClaudeAdapter(CopyAdapter):
    harness = "claude-topics"
    prefix = (".claude",)
    legacy_source = AntigravityAdapter.legacy_source

    def build(self, revision, policy):
        if self._build is not None and self._build.revision == revision.commit:
            return self._build
        snapshot = Snapshot(revision)
        packages = []
        actual = {p.split("/")[2] for p in snapshot.files
                  if p.startswith(".claude/skills/") and p.endswith("/SKILL.md")}
        if actual != TOPICS:
            raise AdapterError("canonical topic population differs from the supported nonzero set", exit_code=4)
        for topic in sorted(TOPICS):
            prefix = f".claude/skills/{topic}/"
            members = {p[len(prefix):]: snapshot.read(p) for p in snapshot.files if p.startswith(prefix)}
            raw = members["SKILL.md"].content.decode()
            sections = re.split(r"(?m)^---[ \t]*$", raw, maxsplit=2)
            if len(sections) != 3 or sections[0]:
                raise AdapterError("canonical topic has unsupported frontmatter", exit_code=4)
            front, body = sections[1:]
            metadata = yaml.safe_load(front)
            source = "claude-power-pack/" + prefix.rstrip("/")
            nested = metadata.get("metadata", {})
            if "source" in nested and nested["source"] != source:
                raise AdapterError("canonical topic source marker is inconsistent", exit_code=4)
            if "source" not in nested:
                # Preserve canonical scalar spelling. YAML serializers can wrap
                # descriptions into multiline scalars the existing reader rejects.
                if "metadata" in metadata:
                    front, count = re.subn(r"(?m)^metadata:[ \t]*\n",
                                           "metadata:\n  source: " + source + "\n", front, count=1)
                    if count != 1:
                        raise AdapterError("canonical metadata spelling is unsupported", exit_code=4)
                else:
                    front += "metadata:\n  source: " + source + "\n"
            members["SKILL.md"] = ExpectedMember(("---" + front + "---" + body).encode())
            packages.append(ExpectedPackage(topic, "claude-power-pack/" + prefix.rstrip("/"), members))
        result = tuple(packages)
        self._build = ExpectedBuild(revision.commit, result, build_manifest_sha256(revision.commit, result))
        return self._build
