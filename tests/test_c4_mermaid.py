"""Tests for the C4 Mermaid rendering engine (issue #411)."""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_script_path = _ROOT / "scripts" / "c4-mermaid.py"
_spec = spec_from_file_location("c4_mermaid", _script_path)
c4_mermaid = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(c4_mermaid)  # type: ignore[union-attr]
sys.modules["c4_mermaid"] = c4_mermaid


L1_MODEL = {
    "project": "Demo",
    "levels": [
        {
            "id": "c4-l1-context",
            "level": "L1",
            "title": "L1 System Context",
            "kind": "flowchart",
            "parent": None,
            "nodes": [
                {"id": "user", "label": "User", "type": "person"},
                {"id": "api", "label": "API Server", "type": "container"},
                {"id": "db", "label": "PostgreSQL", "type": "container", "shape": "cylinder"},
                {"id": "ext", "label": "Third-party API", "type": "system"},
            ],
            "edges": [
                {"source": "user", "target": "api", "label": "Uses"},
                {"source": "api", "target": "db"},
                {"source": "api", "target": "ext", "label": "Calls"},
            ],
            "boundaries": [{"id": "sys", "label": "System of Interest", "nodes": ["api", "db"]}],
        }
    ],
}


class TestSlugify:
    def test_basic(self) -> None:
        assert c4_mermaid.slugify("API Server") == "api-server"

    def test_special_chars(self) -> None:
        assert c4_mermaid.slugify("Auth & Tokens (v2)") == "auth-tokens-v2"

    def test_empty_falls_back(self) -> None:
        assert c4_mermaid.slugify("!!!") == "diagram"


class TestRenderFlowchart:
    def test_header_and_nodes(self) -> None:
        out = c4_mermaid.render_flowchart(L1_MODEL["levels"][0])
        assert out.startswith("flowchart TB\n")
        assert 'user(("User")):::person' in out
        assert 'api["API Server"]:::container' in out

    def test_boundary_subgraph_groups_members(self) -> None:
        out = c4_mermaid.render_flowchart(L1_MODEL["levels"][0])
        assert 'subgraph sys["System of Interest"]' in out
        # db uses the cylinder shape and lives inside the subgraph
        assert 'db[("PostgreSQL")]:::container' in out
        assert "  end\n" in out

    def test_edges_with_and_without_label(self) -> None:
        out = c4_mermaid.render_flowchart(L1_MODEL["levels"][0])
        assert 'user -->|"Uses"| api' in out
        assert "api --> db" in out

    def test_classdefs_for_used_types_only(self) -> None:
        out = c4_mermaid.render_flowchart(L1_MODEL["levels"][0])
        assert "classDef person fill:#08427b" in out
        assert "classDef container fill:#15803d" in out
        assert "classDef system fill:#6b7280" in out
        assert "classDef component" not in out  # unused type not emitted

    def test_label_quotes_escaped(self) -> None:
        level = {
            "nodes": [{"id": "n", "label": 'The "Core"', "type": "component"}],
            "edges": [],
        }
        out = c4_mermaid.render_flowchart(level)
        assert "&quot;Core&quot;" in out


class TestRenderClassDiagram:
    def test_classes_and_relations(self) -> None:
        level = {
            "kind": "classdiagram",
            "classes": [
                {"name": "AuthController", "members": ["+login()", "-token: str"]},
                {"name": "TokenStore"},
            ],
            "relations": [{"source": "AuthController", "target": "TokenStore", "kind": "-->", "label": "uses"}],
        }
        out = c4_mermaid.render_classdiagram(level)
        assert out.startswith("classDiagram\n")
        assert "class AuthController {" in out
        assert "+login()" in out
        assert "class TokenStore" in out
        assert "AuthController --> TokenStore : uses" in out


class TestValidateLevel:
    def test_invalid_edge_endpoint_is_high(self) -> None:
        level = {
            "id": "x",
            "nodes": [{"id": "a", "type": "container"}],
            "edges": [{"source": "a", "target": "ghost"}],
        }
        warnings = c4_mermaid.validate_level(level)
        highs = [w for w in warnings if w["severity"] == "high"]
        assert any(w["check"] == "edge_validity" for w in highs)

    def test_duplicate_node_is_high(self) -> None:
        level = {
            "id": "x",
            "nodes": [{"id": "a", "type": "container"}, {"id": "a", "type": "container"}],
            "edges": [],
        }
        warnings = c4_mermaid.validate_level(level)
        assert any(w["check"] == "duplicate_node" and w["severity"] == "high" for w in warnings)

    def test_orphan_node_is_low(self) -> None:
        level = {"id": "x", "nodes": [{"id": "a", "type": "container"}], "edges": []}
        warnings = c4_mermaid.validate_level(level)
        assert any(w["check"] == "orphan_node" and w["severity"] == "low" for w in warnings)

    def test_density_flag(self) -> None:
        nodes = [{"id": f"n{i}", "type": "component"} for i in range(c4_mermaid.DENSITY_LIMIT + 1)]
        edges = [{"source": f"n{i}", "target": f"n{i + 1}"} for i in range(c4_mermaid.DENSITY_LIMIT)]
        level = {"id": "x", "nodes": nodes, "edges": edges}
        warnings = c4_mermaid.validate_level(level)
        assert any(w["check"] == "density" for w in warnings)

    def test_clean_level_has_no_high_warnings(self) -> None:
        warnings = c4_mermaid.validate_level(L1_MODEL["levels"][0])
        assert [w for w in warnings if w["severity"] == "high"] == []

    def test_classdiagram_relation_validity(self) -> None:
        level = {
            "id": "l4",
            "kind": "classdiagram",
            "classes": [{"name": "A"}],
            "relations": [{"source": "A", "target": "Missing"}],
        }
        warnings = c4_mermaid.validate_level(level)
        assert any(w["check"] == "relation_validity" and w["severity"] == "high" for w in warnings)


class TestSanitization:
    def test_class_token_sanitizes_hyphen(self) -> None:
        assert c4_mermaid.class_token("system-focus") == "system_focus"

    def test_system_focus_classdef_and_selector_sanitized(self) -> None:
        level = {"nodes": [{"id": "app", "label": "App", "type": "system-focus"}], "edges": []}
        out = c4_mermaid.render_flowchart(level)
        assert "classDef system_focus" in out
        assert ":::system_focus" in out
        assert "system-focus" not in out  # the raw hyphenated form never reaches the output

    def test_node_and_edge_ids_sanitized(self) -> None:
        level = {
            "nodes": [{"id": "api.v1", "label": "API", "type": "container"},
                      {"id": "auth service", "label": "Auth", "type": "component"}],
            "edges": [{"source": "api.v1", "target": "auth service"}],
        }
        out = c4_mermaid.render_flowchart(level)
        assert 'api_v1["API"]' in out
        assert "auth_service" in out
        assert "api_v1 --> auth_service" in out
        assert "api.v1" not in out  # dotted id would break Mermaid

    def test_newline_label_becomes_break(self) -> None:
        level = {"nodes": [{"id": "a", "label": "line1\nline2", "type": "container"}], "edges": []}
        out = c4_mermaid.render_flowchart(level)
        assert "line1<br/>line2" in out
        assert "\n    " not in out.split("classDef")[0].replace("flowchart TB\n", "")  # no raw newline inside a label

    def test_id_collision_flagged_high(self) -> None:
        level = {
            "id": "x",
            "nodes": [{"id": "api.v1", "type": "container"}, {"id": "api-v1", "type": "container"}],
            "edges": [],
        }
        warnings = c4_mermaid.validate_level(level)
        assert any(w["check"] == "id_collision" and w["severity"] == "high" for w in warnings)

    def test_classdiagram_generics_use_tildes(self) -> None:
        level = {
            "kind": "classdiagram",
            "classes": [{"name": "Repo", "members": ["+items: List<User>"]}],
            "relations": [],
        }
        out = c4_mermaid.render_classdiagram(level)
        assert "List~User~" in out
        assert "List<User>" not in out

    def test_boundaries_without_ids_get_unique_subgraphs(self) -> None:
        level = {
            "nodes": [{"id": "a", "type": "container"}, {"id": "b", "type": "container"}],
            "edges": [],
            "boundaries": [{"label": "Zone", "nodes": ["a"]}, {"label": "Zone", "nodes": ["b"]}],
        }
        out = c4_mermaid.render_flowchart(level)
        subgraph_ids = [line.split("subgraph ")[1].split("[")[0] for line in out.splitlines() if "subgraph " in line]
        assert len(subgraph_ids) == len(set(subgraph_ids)) == 2  # two distinct subgraph ids


class TestBuildIndexAndManifest:
    def test_index_embeds_mermaid_fences(self) -> None:
        entries, _ = c4_mermaid.process_model(L1_MODEL)
        index = c4_mermaid.build_index("Demo", entries, "2026-07-02T00:00:00Z")
        assert "# C4 Architecture - Demo" in index
        assert "```mermaid" in index
        assert "flowchart TB" in index
        assert "(c4-l1-context.mmd)" in index

    def test_manifest_shape(self) -> None:
        entries, _ = c4_mermaid.process_model(L1_MODEL)
        manifest = c4_mermaid.build_manifest("Demo", entries, "2026-07-02T00:00:00Z")
        assert manifest["engine"] == "c4-mermaid"
        assert manifest["diagrams"][0]["file"] == "c4-l1-context.mmd"
        assert "mermaid" not in manifest["diagrams"][0]  # raw source not duplicated into manifest


class TestProcessModel:
    def test_missing_levels_raises(self) -> None:
        with pytest.raises(c4_mermaid.C4ModelError):
            c4_mermaid.process_model({"project": "x"})

    def test_missing_id_raises(self) -> None:
        with pytest.raises(c4_mermaid.C4ModelError):
            c4_mermaid.process_model({"levels": [{"level": "L1", "nodes": [], "edges": []}]})


class TestCli:
    def _write_model(self, tmp_path: Path, model: dict) -> Path:
        p = tmp_path / "model.json"
        p.write_text(json.dumps(model), encoding="utf-8")
        return p

    def test_clean_model_exit_zero_and_writes_files(self, tmp_path: Path) -> None:
        model_path = self._write_model(tmp_path, L1_MODEL)
        out = tmp_path / "arch"
        rc = c4_mermaid.main(["--model", str(model_path), "--out", str(out), "--timestamp", "T"])
        assert rc == 0
        assert (out / "c4-l1-context.mmd").read_text().startswith("flowchart TB")
        assert (out / "index.md").exists()
        manifest = json.loads((out / "c4-manifest.json").read_text())
        assert manifest["diagrams"][0]["node_count"] == 4

    def test_invalid_reference_exit_one(self, tmp_path: Path) -> None:
        bad = {"project": "x", "levels": [{"id": "l1", "nodes": [{"id": "a", "type": "container"}],
                                           "edges": [{"source": "a", "target": "ghost"}]}]}
        model_path = self._write_model(tmp_path, bad)
        rc = c4_mermaid.main(["--model", str(model_path), "--out", str(tmp_path / "o")])
        assert rc == 1

    def test_invalid_reference_lenient_exit_zero(self, tmp_path: Path) -> None:
        bad = {"project": "x", "levels": [{"id": "l1", "nodes": [{"id": "a", "type": "container"}],
                                           "edges": [{"source": "a", "target": "ghost"}]}]}
        model_path = self._write_model(tmp_path, bad)
        rc = c4_mermaid.main(["--model", str(model_path), "--out", str(tmp_path / "o"), "--lenient"])
        assert rc == 0

    def test_unreadable_model_exit_two(self, tmp_path: Path) -> None:
        rc = c4_mermaid.main(["--model", str(tmp_path / "nope.json"), "--out", str(tmp_path / "o")])
        assert rc == 2


class TestCommandDocsContract:
    """The /documentation:c4 command + docs must reflect the Mermaid engine, not the descoped/nano-banana state."""

    def _read(self, rel: str) -> str:
        return (_ROOT / rel).read_text(encoding="utf-8")

    def test_c4_command_uses_engine_not_nano_banana(self) -> None:
        body = self._read(".claude/commands/documentation/c4.md")
        assert "scripts/c4-mermaid.py" in body
        assert "generate_diagram" not in body
        assert "nano-banana" not in body.lower()
        assert "descoped" not in body.lower()

    def test_docs_drop_descoped_language(self) -> None:
        for rel in (".claude/skills/documentation.md", ".claude/commands/documentation/help.md"):
            body = self._read(rel).lower()
            assert "descoped" not in body
            assert "mermaid" in body
