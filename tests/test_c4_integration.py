"""Integration tests for C4 diagram generation in nano-banana."""

from diagrams.base import DiagramEdge, DiagramNode, DiagramSpec
from diagrams.c4 import generate_c4_diagram


def _sample_l1_spec() -> DiagramSpec:
    """L1 System Context spec with actors, focus system, and external systems."""
    return DiagramSpec(
        title="Intake Platform - System Context",
        description="L1 System Context diagram",
        nodes=[
            DiagramNode(id="user", label="Project Manager", type="person",
                        description="Manages project intake"),
            DiagramNode(id="intake", label="Intake Platform", type="system-focus",
                        description="Python / FastAPI"),
            DiagramNode(id="teams", label="Microsoft Teams", type="system",
                        description="Communication platform"),
            DiagramNode(id="aws", label="AWS Services", type="system",
                        description="Cloud infrastructure"),
        ],
        edges=[
            DiagramEdge(source="user", target="intake", label="submits projects"),
            DiagramEdge(source="intake", target="teams", label="joins meetings"),
            DiagramEdge(source="intake", target="aws", label="stores data"),
        ],
    )


def _sample_l2_spec() -> DiagramSpec:
    """L2 Container spec with containers inside the system boundary."""
    return DiagramSpec(
        title="Intake Platform - Containers",
        description="L2 Container diagram",
        nodes=[
            DiagramNode(id="user", label="Project Manager", type="person"),
            DiagramNode(id="api", label="API Gateway", type="container",
                        description="Python / FastAPI"),
            DiagramNode(id="agent", label="LangGraph Agent", type="container",
                        description="Python / LangGraph"),
            DiagramNode(id="db", label="PostgreSQL", type="container",
                        description="PostgreSQL 16"),
            DiagramNode(id="cache", label="Redis", type="container",
                        description="Redis 7"),
        ],
        edges=[
            DiagramEdge(source="user", target="api", label="HTTP/REST"),
            DiagramEdge(source="api", target="agent", label="orchestrates"),
            DiagramEdge(source="agent", target="db", label="reads/writes"),
            DiagramEdge(source="agent", target="cache", label="session state"),
        ],
    )


def _sample_l3_spec() -> DiagramSpec:
    """L3 Component spec with components inside a container."""
    return DiagramSpec(
        title="LangGraph Agent - Components",
        description="L3 Component diagram",
        nodes=[
            DiagramNode(id="router", label="Intent Router", type="component",
                        description="Classifies user intent"),
            DiagramNode(id="interview", label="Interview Engine", type="component",
                        description="Structured questioning"),
            DiagramNode(id="review", label="Risk Reviewer", type="component",
                        description="Privacy + model risk"),
            DiagramNode(id="scribe", label="Meeting Scribe", type="component",
                        description="Minutes + summaries"),
        ],
        edges=[
            DiagramEdge(source="router", target="interview", label="routes to"),
            DiagramEdge(source="router", target="review", label="routes to"),
            DiagramEdge(source="router", target="scribe", label="routes to"),
        ],
    )


class TestC4HtmlStructure:
    """Test the HTML structure of generated C4 diagrams."""

    def test_returns_valid_html(self):
        html = generate_c4_diagram(_sample_l1_spec())
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_title_in_output(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "Intake Platform - System Context" in html

    def test_description_in_output(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "L1 System Context diagram" in html

    def test_all_nodes_rendered(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        for node in spec.nodes:
            assert node.label in html

    def test_all_edges_rendered(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        for edge in spec.edges:
            if edge.label:
                assert edge.label in html

    def test_person_node_has_svg_icon(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "c4-person" in html
        assert "<svg" in html

    def test_technology_labels_rendered(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "Python / FastAPI" in html
        assert "Communication platform" in html

    def test_css_embedded(self):
        html = generate_c4_diagram(_sample_l1_spec())
        assert "<style>" in html
        assert "c4-node" in html
        assert "c4-label" in html


class TestC4NodeTypes:
    """Test that different node types render correctly."""

    def test_person_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="p", label="User", type="person")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="person"' in html
        assert "c4-person" in html

    def test_system_focus_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="s", label="My System", type="system-focus")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="system-focus"' in html

    def test_container_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="c", label="API", type="container")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="container"' in html

    def test_component_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="comp", label="Router", type="component")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="component"' in html

    def test_code_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="cd", label="Class", type="code")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="code"' in html

    def test_external_system_type_rendering(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="ext", label="External", type="system")],
        )
        html = generate_c4_diagram(spec)
        assert 'data-type="system"' in html


class TestC4BoundarySections:
    """Test that nodes are grouped into boundary sections by type."""

    def test_bounded_section_for_containers(self):
        spec = _sample_l2_spec()
        html = generate_c4_diagram(spec)
        assert "c4-section-bounded" in html
        assert "Containers" in html

    def test_open_section_for_actors(self):
        spec = _sample_l2_spec()
        html = generate_c4_diagram(spec)
        assert "c4-section-open" in html
        assert "Actors" in html

    def test_components_get_boundary(self):
        spec = _sample_l3_spec()
        html = generate_c4_diagram(spec)
        assert "Components" in html
        assert "c4-section-bounded" in html


class TestC4EdgeRendering:
    """Test edge/relationship rendering."""

    def test_relationships_panel_exists(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "Relationships" in html
        assert "c4-edges-panel" in html

    def test_no_edges_no_panel(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[DiagramNode(id="a", label="Solo", type="container")],
            edges=[],
        )
        html = generate_c4_diagram(spec)
        # CSS always defines .c4-edges-panel, but the div element should not be in the body
        assert 'class="c4-edges-panel"' not in html

    def test_dashed_edge_style(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[
                DiagramNode(id="a", label="A", type="container"),
                DiagramNode(id="b", label="B", type="system"),
            ],
            edges=[DiagramEdge(source="a", target="b", label="async", style="dashed")],
        )
        html = generate_c4_diagram(spec)
        assert "stroke-dasharray" in html

    def test_dotted_edge_style(self):
        spec = DiagramSpec(
            title="Test",
            nodes=[
                DiagramNode(id="a", label="A", type="container"),
                DiagramNode(id="b", label="B", type="system"),
            ],
            edges=[DiagramEdge(source="a", target="b", label="optional", style="dotted")],
        )
        html = generate_c4_diagram(spec)
        assert "stroke-dasharray" in html


class TestC4CustomViewport:
    """Test custom width/height parameters."""

    def test_custom_dimensions_in_css(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec, width=3840, height=2160)
        assert "3840px" in html
        assert "2160px" in html

    def test_default_dimensions(self):
        spec = _sample_l1_spec()
        html = generate_c4_diagram(spec)
        assert "1920px" in html
        assert "1080px" in html


class TestC4EmptyAndMinimal:
    """Test edge cases with empty or minimal specs."""

    def test_empty_nodes(self):
        spec = DiagramSpec(title="Empty", nodes=[], edges=[])
        html = generate_c4_diagram(spec)
        assert "<!DOCTYPE html>" in html
        assert "Empty" in html

    def test_single_node(self):
        spec = DiagramSpec(
            title="Minimal",
            nodes=[DiagramNode(id="only", label="Only Node", type="container")],
        )
        html = generate_c4_diagram(spec)
        assert "Only Node" in html

    def test_no_description(self):
        spec = DiagramSpec(
            title="No Desc",
            nodes=[DiagramNode(id="a", label="A", type="container")],
        )
        html = generate_c4_diagram(spec)
        assert "C4 Architecture Diagram" in html  # default subtitle
