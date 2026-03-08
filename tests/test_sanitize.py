"""Tests for XSS sanitization in nano-banana diagram output."""

from diagrams.base import DiagramEdge, DiagramNode, DiagramSpec, _esc
from diagrams.c4 import generate_c4_diagram


class TestEscFunction:
    """Test the _esc() HTML-escape utility."""

    def test_script_tag_escaped(self):
        result = _esc('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_html_entities_escaped(self):
        result = _esc('Hello & "world" <foo>')
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&lt;" in result
        assert "&gt;" in result

    def test_special_chars_safe(self):
        result = _esc("O'Reilly & Sons <Corp>")
        assert "&#x27;" in result or "'" in result  # html.escape may or may not escape '
        assert "&amp;" in result
        assert "&lt;" in result

    def test_quotes_escaped(self):
        result = _esc('onload="alert(1)"')
        assert "&quot;" in result
        assert 'onload="' not in result

    def test_plain_text_unchanged(self):
        result = _esc("Hello World 123")
        assert result == "Hello World 123"

    def test_empty_string(self):
        result = _esc("")
        assert result == ""

    def test_numeric_input(self):
        result = _esc(42)
        assert result == "42"


class TestC4OutputSanitization:
    """Test that generated C4 HTML properly escapes all user input."""

    def _make_spec(self, **overrides) -> DiagramSpec:
        defaults = {
            "title": "Test Diagram",
            "nodes": [
                DiagramNode(id="a", label="Node A", type="container"),
                DiagramNode(id="b", label="Node B", type="system"),
            ],
            "edges": [DiagramEdge(source="a", target="b", label="calls")],
        }
        defaults.update(overrides)
        return DiagramSpec(**defaults)

    def test_script_in_node_label_escaped(self):
        spec = self._make_spec(nodes=[
            DiagramNode(id="a", label='<script>alert("xss")</script>', type="container"),
        ])
        html = generate_c4_diagram(spec)
        assert "<script>" not in html.split("<style>")[0]  # not in body content
        assert "&lt;script&gt;" in html

    def test_script_in_title_escaped(self):
        spec = self._make_spec(title='<img src=x onerror="alert(1)">')
        html = generate_c4_diagram(spec)
        # Title appears in both <title> and .diagram-title div
        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html

    def test_script_in_description_escaped(self):
        spec = self._make_spec(nodes=[
            DiagramNode(
                id="a", label="Safe", type="container",
                description='<script>document.cookie</script>',
            ),
        ])
        html = generate_c4_diagram(spec)
        assert "<script>document.cookie</script>" not in html

    def test_script_in_edge_label_escaped(self):
        spec = self._make_spec(
            nodes=[
                DiagramNode(id="a", label="A", type="container"),
                DiagramNode(id="b", label="B", type="system"),
            ],
            edges=[DiagramEdge(source="a", target="b", label='<img onerror="alert(1)">')],
        )
        html = generate_c4_diagram(spec)
        assert 'onerror="alert(1)"' not in html

    def test_html_in_node_id_escaped(self):
        spec = self._make_spec(nodes=[
            DiagramNode(id='"><script>x</script>', label="Safe", type="container"),
        ])
        html = generate_c4_diagram(spec)
        assert '"><script>x</script>' not in html

    def test_spec_description_escaped(self):
        spec = self._make_spec(description='<b onmouseover="alert(1)">hover me</b>')
        html = generate_c4_diagram(spec)
        assert 'onmouseover="alert(1)"' not in html
