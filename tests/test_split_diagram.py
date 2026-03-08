"""Tests for the auto_split_diagram module in nano-banana."""

import pytest
from diagrams.base import DiagramEdge, DiagramNode, DiagramSpec
from diagrams.split import (
    auto_split_diagram,
    build_detail,
    build_summary,
    cluster_nodes,
    split_save_paths,
)

# -- Fixtures ----------------------------------------------------------------


def _make_spec(
    node_count: int,
    node_type: str = "default",
    chain_edges: bool = True,
    title: str = "Test Diagram",
) -> DiagramSpec:
    """Build a DiagramSpec with N nodes and optional chain edges."""
    nodes = [
        DiagramNode(id=f"n{i}", label=f"Node {i}", type=node_type)
        for i in range(node_count)
    ]
    edges = []
    if chain_edges and node_count > 1:
        edges = [
            DiagramEdge(source=f"n{i}", target=f"n{i+1}")
            for i in range(node_count - 1)
        ]
    return DiagramSpec(title=title, nodes=nodes, edges=edges)


def _make_c4_spec() -> DiagramSpec:
    """Build a C4-style spec with multiple node types (>15 nodes)."""
    nodes = [
        DiagramNode(id="user1", label="Admin", type="person"),
        DiagramNode(id="user2", label="End User", type="person"),
        DiagramNode(id="ext1", label="Email Service", type="system"),
        DiagramNode(id="ext2", label="Payment Gateway", type="system"),
        DiagramNode(id="ext3", label="Auth Provider", type="system"),
        DiagramNode(id="web", label="Web App", type="container", description="React"),
        DiagramNode(id="api", label="API Server", type="container", description="FastAPI"),
        DiagramNode(id="worker", label="Worker", type="container", description="Celery"),
        DiagramNode(id="db", label="Database", type="container", description="PostgreSQL"),
        DiagramNode(id="cache", label="Cache", type="container", description="Redis"),
        DiagramNode(id="auth", label="Auth Module", type="component"),
        DiagramNode(id="billing", label="Billing Module", type="component"),
        DiagramNode(id="notif", label="Notification Module", type="component"),
        DiagramNode(id="search", label="Search Module", type="component"),
        DiagramNode(id="reports", label="Reports Module", type="component"),
        DiagramNode(id="audit", label="Audit Module", type="component"),
    ]
    edges = [
        DiagramEdge(source="user1", target="web", label="Manages"),
        DiagramEdge(source="user2", target="web", label="Uses"),
        DiagramEdge(source="web", target="api", label="REST API"),
        DiagramEdge(source="api", target="db", label="SQL"),
        DiagramEdge(source="api", target="cache", label="Read/Write"),
        DiagramEdge(source="api", target="ext1", label="SMTP"),
        DiagramEdge(source="api", target="ext2", label="Payment API"),
        DiagramEdge(source="api", target="ext3", label="OAuth"),
        DiagramEdge(source="worker", target="db", label="Background jobs"),
        DiagramEdge(source="auth", target="ext3", label="Validates tokens"),
        DiagramEdge(source="billing", target="ext2", label="Charges"),
        DiagramEdge(source="notif", target="ext1", label="Sends emails"),
    ]
    return DiagramSpec(
        title="L2 Container - MyApp",
        nodes=nodes,
        edges=edges,
        description="System architecture",
    )


def _make_disconnected_spec() -> DiagramSpec:
    """Build a spec with multiple disconnected components."""
    nodes = [
        # Group 1: connected
        DiagramNode(id="a1", label="A1", type="default"),
        DiagramNode(id="a2", label="A2", type="default"),
        DiagramNode(id="a3", label="A3", type="default"),
        # Group 2: connected
        DiagramNode(id="b1", label="B1", type="primary"),
        DiagramNode(id="b2", label="B2", type="primary"),
        DiagramNode(id="b3", label="B3", type="primary"),
        DiagramNode(id="b4", label="B4", type="primary"),
        # Group 3: connected
        DiagramNode(id="c1", label="C1", type="secondary"),
        DiagramNode(id="c2", label="C2", type="secondary"),
        DiagramNode(id="c3", label="C3", type="secondary"),
        DiagramNode(id="c4", label="C4", type="secondary"),
        DiagramNode(id="c5", label="C5", type="secondary"),
        # Group 4: connected
        DiagramNode(id="d1", label="D1", type="accent"),
        DiagramNode(id="d2", label="D2", type="accent"),
        DiagramNode(id="d3", label="D3", type="accent"),
        DiagramNode(id="d4", label="D4", type="accent"),
        DiagramNode(id="d5", label="D5", type="accent"),
        DiagramNode(id="d6", label="D6", type="accent"),
    ]
    edges = [
        # Group 1
        DiagramEdge(source="a1", target="a2"),
        DiagramEdge(source="a2", target="a3"),
        # Group 2
        DiagramEdge(source="b1", target="b2"),
        DiagramEdge(source="b2", target="b3"),
        DiagramEdge(source="b3", target="b4"),
        # Group 3
        DiagramEdge(source="c1", target="c2"),
        DiagramEdge(source="c2", target="c3"),
        DiagramEdge(source="c3", target="c4"),
        DiagramEdge(source="c4", target="c5"),
        # Group 4
        DiagramEdge(source="d1", target="d2"),
        DiagramEdge(source="d2", target="d3"),
        DiagramEdge(source="d3", target="d4"),
        DiagramEdge(source="d4", target="d5"),
        DiagramEdge(source="d5", target="d6"),
    ]
    return DiagramSpec(
        title="Disconnected Graph",
        nodes=nodes,
        edges=edges,
    )


# -- cluster_nodes -----------------------------------------------------------


class TestClusterNodes:
    def test_c4_boundary_groups_by_type(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        # Should have clusters for person, system, container, component
        names = {c.name for c in clusters}
        assert "Actors" in names
        assert "External Systems" in names
        assert "Containers" in names
        assert "Components" in names

    def test_connectivity_finds_components(self):
        spec = _make_disconnected_spec()
        clusters = cluster_nodes(spec, strategy="connectivity")
        assert len(clusters) == 4  # 4 disconnected groups

    def test_connectivity_single_component(self):
        spec = _make_spec(5, chain_edges=True)
        clusters = cluster_nodes(spec, strategy="connectivity")
        assert len(clusters) == 1
        assert len(clusters[0].node_ids) == 5

    def test_type_group_strategy(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="type_group")
        types_found = {c.name for c in clusters}
        assert "Person" in types_found
        assert "System" in types_found
        assert "Container" in types_found
        assert "Component" in types_found

    def test_invalid_strategy_raises(self):
        spec = _make_spec(5)
        with pytest.raises(ValueError, match="Unknown clustering strategy"):
            cluster_nodes(spec, strategy="invalid_strategy")

    def test_all_nodes_accounted_for(self):
        spec = _make_c4_spec()
        for strategy in ("c4_boundary", "connectivity", "type_group"):
            clusters = cluster_nodes(spec, strategy=strategy)
            all_ids = set()
            for c in clusters:
                all_ids.update(c.node_ids)
            spec_ids = {n.id for n in spec.nodes}
            assert all_ids == spec_ids, f"Strategy {strategy} lost nodes"


# -- build_summary ----------------------------------------------------------


class TestBuildSummary:
    def test_summary_node_count(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        assert len(summary.nodes) == len(clusters)

    def test_summary_title_suffix(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        assert summary.title.endswith("(Summary)")

    def test_summary_nodes_have_cluster_ids(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        for node in summary.nodes:
            assert node.id.startswith("cluster-")

    def test_summary_edges_are_inter_cluster(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        # All edges should connect different cluster nodes
        for edge in summary.edges:
            assert edge.source != edge.target

    def test_summary_no_duplicate_edges(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        edge_pairs = [(e.source, e.target) for e in summary.edges]
        assert len(edge_pairs) == len(set(edge_pairs))

    def test_summary_description_shows_count(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        summary = build_summary(spec, clusters)
        for node in summary.nodes:
            assert "elements" in node.description


# -- build_detail ------------------------------------------------------------


class TestBuildDetail:
    def test_detail_contains_cluster_nodes(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        for idx, cluster in enumerate(clusters):
            detail = build_detail(spec, cluster, idx)
            detail_ids = {n.id for n in detail.nodes}
            for nid in cluster.node_ids:
                assert nid in detail_ids

    def test_detail_title_includes_cluster_name(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        for idx, cluster in enumerate(clusters):
            detail = build_detail(spec, cluster, idx)
            assert cluster.name in detail.title

    def test_detail_external_stubs_as_system(self):
        spec = _make_c4_spec()
        clusters = cluster_nodes(spec, strategy="c4_boundary")
        # Find the "Containers" cluster - it has edges to external systems
        container_cluster = next(c for c in clusters if c.name == "Containers")
        idx = clusters.index(container_cluster)
        detail = build_detail(spec, container_cluster, idx)

        # Should have stub nodes for external connections
        stub_nodes = [n for n in detail.nodes if "(external)" in n.label]
        assert len(stub_nodes) > 0
        for stub in stub_nodes:
            assert stub.type == "system"

    def test_detail_preserves_internal_edges(self):
        spec = _make_disconnected_spec()
        clusters = cluster_nodes(spec, strategy="connectivity")
        for idx, cluster in enumerate(clusters):
            detail = build_detail(spec, cluster, idx)
            cluster_ids = set(cluster.node_ids)
            for edge in detail.edges:
                # At least one endpoint must be in the cluster
                assert edge.source in cluster_ids or edge.target in cluster_ids


# -- auto_split_diagram ------------------------------------------------------


class TestAutoSplitDiagram:
    def test_no_split_when_small(self):
        spec = _make_spec(10)
        result = auto_split_diagram(spec, max_nodes_per_page=15)
        assert len(result) == 1
        assert result[0] is spec

    def test_split_when_large(self):
        spec = _make_c4_spec()  # 16 nodes
        result = auto_split_diagram(spec, max_nodes_per_page=15)
        assert len(result) > 1
        # First should be summary
        assert "(Summary)" in result[0].title

    def test_split_at_exact_threshold(self):
        spec = _make_spec(15)
        result = auto_split_diagram(spec, max_nodes_per_page=15)
        assert len(result) == 1  # <= threshold, no split

    def test_split_at_threshold_plus_one(self):
        spec = _make_c4_spec()
        result = auto_split_diagram(spec, max_nodes_per_page=15)
        assert len(result) > 1

    def test_custom_threshold(self):
        spec = _make_spec(6, chain_edges=False)
        # With chain_edges=False and all same type, only 1 cluster
        # so no split even though above threshold
        result = auto_split_diagram(spec, max_nodes_per_page=5, strategy="type_group")
        # Only one type group - can't split into multiple clusters
        assert len(result) == 1

    def test_all_nodes_preserved_across_details(self):
        spec = _make_c4_spec()
        result = auto_split_diagram(spec, max_nodes_per_page=10)
        if len(result) > 1:
            # Collect all nodes from detail specs (skip summary)
            detail_node_ids: set[str] = set()
            for detail in result[1:]:
                for node in detail.nodes:
                    # Exclude external stubs
                    if "(external)" not in node.label:
                        detail_node_ids.add(node.id)
            spec_ids = {n.id for n in spec.nodes}
            assert detail_node_ids == spec_ids

    def test_connectivity_strategy(self):
        spec = _make_disconnected_spec()
        result = auto_split_diagram(spec, max_nodes_per_page=5, strategy="connectivity")
        assert len(result) > 1
        # First is summary, rest are details (one per connected component)
        assert "(Summary)" in result[0].title
        # 4 disconnected groups -> summary + 4 details = 5
        assert len(result) == 5

    def test_single_cluster_no_split(self):
        spec = _make_spec(20, chain_edges=True)
        # All nodes same type and connected - connectivity produces 1 cluster
        result = auto_split_diagram(spec, max_nodes_per_page=15, strategy="connectivity")
        assert len(result) == 1

    def test_invalid_strategy_raises(self):
        spec = _make_spec(20)
        with pytest.raises(ValueError, match="Unknown clustering strategy"):
            auto_split_diagram(spec, max_nodes_per_page=10, strategy="bogus")


# -- split_save_paths --------------------------------------------------------


class TestSplitSavePaths:
    def test_single_file_no_split(self):
        paths = split_save_paths("docs/diagram.html", 1)
        assert paths == ["docs/diagram.html"]

    def test_split_naming_convention(self):
        paths = split_save_paths("docs/architecture/c4-l3-api-server.html", 3)
        assert len(paths) == 3
        assert paths[0] == "docs/architecture/c4-l3-api-server.html"
        assert paths[1] == "docs/architecture/c4-l3-api-server-detail-1.html"
        assert paths[2] == "docs/architecture/c4-l3-api-server-detail-2.html"

    def test_preserves_extension(self):
        paths = split_save_paths("output/diagram.htm", 2)
        assert paths[0].endswith(".htm")
        assert paths[1].endswith(".htm")

    def test_preserves_directory(self):
        paths = split_save_paths("/absolute/path/to/diagram.html", 3)
        for p in paths:
            assert p.startswith("/absolute/path/to/")

    def test_count_zero_or_one_returns_base(self):
        paths = split_save_paths("x.html", 0)
        assert paths == ["x.html"]
        paths = split_save_paths("x.html", 1)
        assert paths == ["x.html"]
