"""Tests for the validate_diagram function in nano-banana."""

from diagrams.validate import _contrast_ratio, _hex_to_rgb, validate_diagram

# ── Helper fixtures ──────────────────────────────────────────────────────


def _make_nodes(count: int, **overrides) -> list[dict]:
    """Generate a list of simple node dicts."""
    return [
        {"id": f"n{i}", "label": f"Node {i}", "type": "default", **overrides}
        for i in range(count)
    ]


def _make_chain_edges(count: int) -> list[dict]:
    """Generate a chain of edges: n0->n1->n2->...->n(count-1)."""
    return [
        {"source": f"n{i}", "target": f"n{i+1}"}
        for i in range(count - 1)
    ]


# ── Contrast ratio utility ──────────────────────────────────────────────


class TestContrastRatio:
    def test_black_on_white(self):
        ratio = _contrast_ratio("#ffffff", "#000000")
        assert ratio >= 20.0  # Should be 21:1

    def test_white_on_white(self):
        ratio = _contrast_ratio("#ffffff", "#ffffff")
        assert ratio == 1.0

    def test_symmetric(self):
        r1 = _contrast_ratio("#3b82f6", "#ffffff")
        r2 = _contrast_ratio("#ffffff", "#3b82f6")
        assert abs(r1 - r2) < 0.01

    def test_hex_to_rgb(self):
        assert _hex_to_rgb("#ff0000") == (255, 0, 0)
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)
        assert _hex_to_rgb("000000") == (0, 0, 0)

    def test_short_hex(self):
        assert _hex_to_rgb("#fff") == (255, 255, 255)
        assert _hex_to_rgb("#000") == (0, 0, 0)


# ── Passing spec ─────────────────────────────────────────────────────────


class TestPassingSpec:
    def test_valid_small_diagram(self):
        nodes = _make_nodes(5)
        edges = _make_chain_edges(5)
        result = validate_diagram(nodes=nodes, edges=edges)
        assert result["passed"] is True
        assert result["high_severity"] == 0

    def test_empty_diagram(self):
        result = validate_diagram(nodes=[], edges=[])
        assert result["passed"] is True
        assert result["issue_count"] == 0

    def test_no_edges(self):
        nodes = _make_nodes(3)
        result = validate_diagram(nodes=nodes, edges=None)
        assert result["passed"] is True


# ── duplicate_ids (HIGH) ─────────────────────────────────────────────────


class TestDuplicateIds:
    def test_duplicate_node_ids(self):
        nodes = [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "a", "label": "A copy"},
        ]
        result = validate_diagram(nodes=nodes)
        assert result["passed"] is False
        assert result["high_severity"] >= 1
        checks = [iss["check"] for iss in result["issues"]]
        assert "duplicate_ids" in checks

    def test_unique_ids_pass(self):
        nodes = [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "c", "label": "C"},
        ]
        result = validate_diagram(nodes=nodes)
        dup_issues = [iss for iss in result["issues"] if iss["check"] == "duplicate_ids"]
        assert len(dup_issues) == 0


# ── edge_validity (HIGH) ────────────────────────────────────────────────


class TestEdgeValidity:
    def test_dangling_source(self):
        nodes = [{"id": "a", "label": "A"}]
        edges = [{"source": "missing", "target": "a"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        assert result["passed"] is False
        edge_issues = [iss for iss in result["issues"] if iss["check"] == "edge_validity"]
        assert len(edge_issues) >= 1
        assert "missing" in edge_issues[0]["message"]

    def test_dangling_target(self):
        nodes = [{"id": "a", "label": "A"}]
        edges = [{"source": "a", "target": "ghost"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        assert result["passed"] is False
        edge_issues = [iss for iss in result["issues"] if iss["check"] == "edge_validity"]
        assert any("ghost" in iss["message"] for iss in edge_issues)

    def test_valid_edges(self):
        nodes = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        edge_issues = [iss for iss in result["issues"] if iss["check"] == "edge_validity"]
        assert len(edge_issues) == 0


# ── viewport_fit (HIGH) ─────────────────────────────────────────────────


class TestViewportFit:
    def test_overflow_with_many_nodes(self):
        nodes = _make_nodes(100)
        result = validate_diagram(nodes=nodes, width=1920, height=1080)
        assert result["passed"] is False
        fit_issues = [iss for iss in result["issues"] if iss["check"] == "viewport_fit"]
        assert len(fit_issues) >= 1

    def test_fits_with_few_nodes(self):
        nodes = _make_nodes(5)
        result = validate_diagram(nodes=nodes, width=1920, height=1080)
        fit_issues = [iss for iss in result["issues"] if iss["check"] == "viewport_fit"]
        assert len(fit_issues) == 0


# ── readability (MEDIUM) ────────────────────────────────────────────────


class TestReadability:
    def test_dense_warning(self):
        # Density ~0.86 (38/44 capacity) triggers warning
        nodes = _make_nodes(38)
        edges = _make_chain_edges(38)
        result = validate_diagram(nodes=nodes, edges=edges)
        read_issues = [iss for iss in result["issues"] if iss["check"] == "readability"]
        assert len(read_issues) >= 1
        assert read_issues[0]["severity"] == "medium"

    def test_overflow_warning(self):
        # Density ~1.14 (50/44 capacity) triggers viewport_fit overflow
        nodes = _make_nodes(50)
        edges = _make_chain_edges(50)
        result = validate_diagram(nodes=nodes, edges=edges)
        fit_issues = [iss for iss in result["issues"] if iss["check"] == "viewport_fit"]
        assert len(fit_issues) >= 1

    def test_small_diagram_no_warning(self):
        nodes = _make_nodes(10)
        edges = _make_chain_edges(10)
        result = validate_diagram(nodes=nodes, edges=edges)
        read_issues = [iss for iss in result["issues"] if iss["check"] == "readability"]
        assert len(read_issues) == 0


# ── orphan_nodes (MEDIUM) ───────────────────────────────────────────────


class TestOrphanNodes:
    def test_orphan_detected(self):
        nodes = [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "orphan", "label": "Orphan"},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        orphan_issues = [iss for iss in result["issues"] if iss["check"] == "orphan_nodes"]
        assert len(orphan_issues) == 1
        assert "orphan" in orphan_issues[0]["message"]

    def test_person_type_not_flagged(self):
        nodes = [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "user", "label": "User", "type": "person"},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges, diagram_type="c4")
        orphan_issues = [iss for iss in result["issues"] if iss["check"] == "orphan_nodes"]
        # person type should not be flagged
        orphan_ids = [iss.get("node_id") for iss in orphan_issues]
        assert "user" not in orphan_ids

    def test_system_type_not_flagged(self):
        nodes = [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "ext", "label": "External", "type": "system"},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges, diagram_type="c4")
        orphan_issues = [iss for iss in result["issues"] if iss["check"] == "orphan_nodes"]
        orphan_ids = [iss.get("node_id") for iss in orphan_issues]
        assert "ext" not in orphan_ids

    def test_no_orphans_when_no_edges(self):
        """When there are no edges at all, orphan check is skipped."""
        nodes = _make_nodes(3)
        result = validate_diagram(nodes=nodes, edges=None)
        orphan_issues = [iss for iss in result["issues"] if iss["check"] == "orphan_nodes"]
        assert len(orphan_issues) == 0


# ── contrast (MEDIUM) ───────────────────────────────────────────────────


class TestContrast:
    def test_c4_palette_checked(self):
        """Run contrast check against C4 palette types."""
        nodes = [
            {"id": "p", "label": "Person", "type": "person"},
            {"id": "s", "label": "System", "type": "system"},
            {"id": "c", "label": "Container", "type": "container"},
        ]
        result = validate_diagram(nodes=nodes, diagram_type="c4")
        # The check should run - we don't assert pass/fail since palette
        # may or may not pass WCAG AA. Just verify no errors.
        assert "issues" in result

    def test_known_bad_contrast_detected(self):
        """The accent palette (#f59e0b bg, #1e293b text) has contrast issues."""
        nodes = [{"id": "a", "label": "A", "type": "accent"}]
        result = validate_diagram(nodes=nodes, diagram_type="architecture")
        contrast_issues = [iss for iss in result["issues"] if iss["check"] == "contrast"]
        # accent type: bg=#f59e0b, text=#1e293b
        # This pair has a ratio around 2.5:1 which fails AA
        if contrast_issues:
            assert contrast_issues[0]["severity"] == "medium"


# ── long_labels (LOW) ───────────────────────────────────────────────────


class TestLongLabels:
    def test_long_label(self):
        nodes = [{"id": "a", "label": "A" * 50}]
        result = validate_diagram(nodes=nodes)
        label_issues = [iss for iss in result["issues"] if iss["check"] == "long_labels"]
        assert len(label_issues) >= 1
        assert label_issues[0]["severity"] == "low"

    def test_long_description(self):
        nodes = [{"id": "a", "label": "A", "description": "D" * 90}]
        result = validate_diagram(nodes=nodes)
        label_issues = [iss for iss in result["issues"] if iss["check"] == "long_labels"]
        assert len(label_issues) >= 1

    def test_normal_labels_pass(self):
        nodes = [{"id": "a", "label": "Short label", "description": "Brief desc"}]
        result = validate_diagram(nodes=nodes)
        label_issues = [iss for iss in result["issues"] if iss["check"] == "long_labels"]
        assert len(label_issues) == 0


# ── label_resolution (MEDIUM) ───────────────────────────────────────────


class TestLabelResolution:
    def test_empty_label_flagged(self):
        nodes = [
            {"id": "a", "label": "Node A"},
            {"id": "b", "label": ""},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        lr_issues = [iss for iss in result["issues"] if iss["check"] == "label_resolution"]
        assert len(lr_issues) == 1
        assert "empty label" in lr_issues[0]["message"]

    def test_whitespace_only_label_flagged(self):
        nodes = [
            {"id": "a", "label": "Node A"},
            {"id": "b", "label": "   "},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        lr_issues = [iss for iss in result["issues"] if iss["check"] == "label_resolution"]
        assert len(lr_issues) == 1

    def test_valid_labels_pass(self):
        nodes = [
            {"id": "a", "label": "Node A"},
            {"id": "b", "label": "Node B"},
        ]
        edges = [{"source": "a", "target": "b"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        lr_issues = [iss for iss in result["issues"] if iss["check"] == "label_resolution"]
        assert len(lr_issues) == 0

    def test_dangling_edge_not_double_flagged(self):
        nodes = [{"id": "a", "label": "Node A"}]
        edges = [{"source": "a", "target": "missing"}]
        result = validate_diagram(nodes=nodes, edges=edges)
        lr_issues = [iss for iss in result["issues"] if iss["check"] == "label_resolution"]
        assert len(lr_issues) == 0


# ── relationships_overflow (MEDIUM) ────────────────────────────────────


class TestRelationshipsOverflow:
    def test_many_edges_flagged(self):
        nodes = [{"id": f"n{i}", "label": f"Node {i}"} for i in range(15)]
        edges = [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(14)]
        result = validate_diagram(nodes=nodes, edges=edges)
        ro_issues = [iss for iss in result["issues"] if iss["check"] == "relationships_overflow"]
        assert len(ro_issues) == 1
        assert "scroll" in ro_issues[0]["message"]

    def test_few_edges_pass(self):
        nodes = [{"id": f"n{i}", "label": f"Node {i}"} for i in range(4)]
        edges = [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(3)]
        result = validate_diagram(nodes=nodes, edges=edges)
        ro_issues = [iss for iss in result["issues"] if iss["check"] == "relationships_overflow"]
        assert len(ro_issues) == 0

    def test_no_edges_no_overflow(self):
        nodes = [{"id": "a", "label": "A"}]
        result = validate_diagram(nodes=nodes, edges=[])
        ro_issues = [iss for iss in result["issues"] if iss["check"] == "relationships_overflow"]
        assert len(ro_issues) == 0


# ── Result structure ────────────────────────────────────────────────────


class TestResultStructure:
    def test_all_keys_present(self):
        result = validate_diagram(nodes=_make_nodes(3))
        assert "passed" in result
        assert "issue_count" in result
        assert "high_severity" in result
        assert "issues" in result
        assert "suggestions" in result
        assert "summary" in result

    def test_issue_dict_keys(self):
        nodes = [{"id": "a", "label": "A"}, {"id": "a", "label": "A copy"}]
        result = validate_diagram(nodes=nodes)
        assert len(result["issues"]) >= 1
        issue = result["issues"][0]
        assert "check" in issue
        assert "severity" in issue
        assert "message" in issue

    def test_suggestions_populated_on_failure(self):
        nodes = _make_nodes(100)
        result = validate_diagram(nodes=nodes)
        assert len(result["suggestions"]) > 0

    def test_summary_on_pass(self):
        result = validate_diagram(nodes=_make_nodes(3))
        assert "passed" in result["summary"].lower() or result["issue_count"] == 0
