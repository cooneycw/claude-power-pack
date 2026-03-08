"""Auto-split large diagrams into summary + detail sub-diagrams.

When a diagram has too many nodes to render legibly at 1920x1080, this module
splits it into a summary diagram (showing clusters as single nodes) and detail
diagrams (one per cluster with full node detail).

Clustering strategies:
  - c4_boundary: Group by C4 node type (person, system, container, etc.)
  - connectivity: Group by connected components in the edge graph
  - type_group: Group by generic node type (default, primary, secondary, ...)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from diagrams.base import DiagramEdge, DiagramNode, DiagramSpec


@dataclass
class Cluster:
    """A group of related nodes within a diagram."""

    name: str
    node_ids: list[str] = field(default_factory=list)


# -- Clustering strategies ---------------------------------------------------


def _cluster_c4_boundary(spec: DiagramSpec) -> list[Cluster]:
    """Group nodes by their C4 type (person, system, container, etc.)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for node in spec.nodes:
        groups[node.type].append(node.id)

    label_map = {
        "person": "Actors",
        "system": "External Systems",
        "system-focus": "System Boundary",
        "container": "Containers",
        "component": "Components",
        "code": "Code",
    }

    clusters: list[Cluster] = []
    for ntype, ids in groups.items():
        name = label_map.get(ntype, ntype.replace("-", " ").title())
        clusters.append(Cluster(name=name, node_ids=ids))
    return clusters


def _cluster_connectivity(spec: DiagramSpec) -> list[Cluster]:
    """Group nodes by connected components (graph traversal)."""
    adj: dict[str, set[str]] = defaultdict(set)
    all_ids = {n.id for n in spec.nodes}

    for edge in spec.edges:
        if edge.source in all_ids and edge.target in all_ids:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)

    visited: set[str] = set()
    clusters: list[Cluster] = []
    idx = 0

    for node in spec.nodes:
        if node.id in visited:
            continue
        # BFS to find connected component
        component: list[str] = []
        queue = [node.id]
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            component.append(nid)
            for neighbor in adj.get(nid, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        idx += 1
        clusters.append(Cluster(name=f"Group {idx}", node_ids=component))

    return clusters


def _cluster_type_group(spec: DiagramSpec) -> list[Cluster]:
    """Group nodes by their generic type field."""
    groups: dict[str, list[str]] = defaultdict(list)
    for node in spec.nodes:
        groups[node.type].append(node.id)

    return [
        Cluster(name=ntype.replace("-", " ").title(), node_ids=ids)
        for ntype, ids in groups.items()
    ]


_STRATEGIES = {
    "c4_boundary": _cluster_c4_boundary,
    "connectivity": _cluster_connectivity,
    "type_group": _cluster_type_group,
}


# -- Core split logic --------------------------------------------------------


def cluster_nodes(
    spec: DiagramSpec,
    strategy: str = "c4_boundary",
) -> list[Cluster]:
    """Partition nodes into clusters using the given strategy.

    Args:
        spec: The diagram spec to cluster.
        strategy: One of 'c4_boundary', 'connectivity', 'type_group'.

    Returns:
        List of Cluster objects, each containing a name and list of node IDs.

    Raises:
        ValueError: If the strategy name is not recognized.
    """
    fn = _STRATEGIES.get(strategy)
    if fn is None:
        valid = ", ".join(sorted(_STRATEGIES))
        raise ValueError(f"Unknown clustering strategy '{strategy}'. Valid: {valid}")
    return fn(spec)


def build_summary(spec: DiagramSpec, clusters: list[Cluster]) -> DiagramSpec:
    """Build a summary diagram where each cluster becomes a single node.

    Inter-cluster edges are preserved (collapsed to cluster-level connections).
    The summary inherits the original spec's title with a ' (Summary)' suffix.
    """
    # Map node IDs to their cluster index
    node_to_cluster: dict[str, int] = {}
    for idx, cluster in enumerate(clusters):
        for nid in cluster.node_ids:
            node_to_cluster[nid] = idx

    # Build lookup for original nodes
    nodes_by_id: dict[str, DiagramNode] = {n.id: n for n in spec.nodes}

    # Create summary nodes (one per cluster)
    summary_nodes: list[DiagramNode] = []
    for idx, cluster in enumerate(clusters):
        # Use the dominant type from the cluster's nodes
        type_counts: dict[str, int] = defaultdict(int)
        for nid in cluster.node_ids:
            orig = nodes_by_id.get(nid)
            if orig:
                type_counts[orig.type] += 1
        dominant_type = max(type_counts, key=type_counts.get) if type_counts else "default"

        summary_nodes.append(DiagramNode(
            id=f"cluster-{idx}",
            label=cluster.name,
            type=dominant_type,
            description=f"{len(cluster.node_ids)} elements",
        ))

    # Collapse edges to cluster-level (deduplicate)
    seen_edges: set[tuple[str, str]] = set()
    summary_edges: list[DiagramEdge] = []
    for edge in spec.edges:
        src_cluster = node_to_cluster.get(edge.source)
        tgt_cluster = node_to_cluster.get(edge.target)
        if src_cluster is None or tgt_cluster is None:
            continue
        if src_cluster == tgt_cluster:
            continue  # Internal edge, skip in summary
        key = (f"cluster-{src_cluster}", f"cluster-{tgt_cluster}")
        if key in seen_edges:
            continue
        seen_edges.add(key)
        summary_edges.append(DiagramEdge(
            source=key[0],
            target=key[1],
            label="",
            style="solid",
        ))

    return DiagramSpec(
        title=f"{spec.title} (Summary)",
        nodes=summary_nodes,
        edges=summary_edges,
        description=spec.description,
    )


def build_detail(
    spec: DiagramSpec,
    cluster: Cluster,
    cluster_index: int,
) -> DiagramSpec:
    """Build a detail diagram for a single cluster.

    Includes all nodes in the cluster plus edges between them. External
    connections (edges to nodes outside the cluster) are represented as
    stub nodes with type 'system' so the viewer sees the boundary.
    """
    cluster_ids = set(cluster.node_ids)
    nodes_by_id: dict[str, DiagramNode] = {n.id: n for n in spec.nodes}

    # Collect nodes in this cluster
    detail_nodes: list[DiagramNode] = [
        nodes_by_id[nid] for nid in cluster.node_ids if nid in nodes_by_id
    ]

    # Collect edges and identify external stubs
    detail_edges: list[DiagramEdge] = []
    external_stubs: dict[str, DiagramNode] = {}

    for edge in spec.edges:
        src_in = edge.source in cluster_ids
        tgt_in = edge.target in cluster_ids

        if src_in and tgt_in:
            detail_edges.append(edge)
        elif src_in and not tgt_in:
            # External target - create stub if not already present
            if edge.target not in external_stubs:
                orig = nodes_by_id.get(edge.target)
                stub_label = orig.label if orig else edge.target
                external_stubs[edge.target] = DiagramNode(
                    id=edge.target,
                    label=f"{stub_label} (external)",
                    type="system",
                    description="",
                )
            detail_edges.append(edge)
        elif not src_in and tgt_in:
            # External source - create stub if not already present
            if edge.source not in external_stubs:
                orig = nodes_by_id.get(edge.source)
                stub_label = orig.label if orig else edge.source
                external_stubs[edge.source] = DiagramNode(
                    id=edge.source,
                    label=f"{stub_label} (external)",
                    type="system",
                    description="",
                )
            detail_edges.append(edge)

    all_nodes = detail_nodes + list(external_stubs.values())

    return DiagramSpec(
        title=f"{spec.title} - {cluster.name}",
        nodes=all_nodes,
        edges=detail_edges,
        description=f"Detail view: {cluster.name}",
    )


def auto_split_diagram(
    spec: DiagramSpec,
    max_nodes_per_page: int = 15,
    strategy: str = "c4_boundary",
) -> list[DiagramSpec]:
    """Split a large diagram into summary + detail specs.

    If the diagram has fewer nodes than ``max_nodes_per_page``, returns it
    unchanged as a single-element list.

    Otherwise, clusters the nodes using the given strategy, then produces:
      - A summary diagram with one node per cluster
      - A detail diagram for each cluster

    Args:
        spec: The original DiagramSpec to split.
        max_nodes_per_page: Maximum nodes before triggering a split.
        strategy: Clustering strategy - 'c4_boundary', 'connectivity', or 'type_group'.

    Returns:
        List of DiagramSpec objects. First element is the summary (if split),
        followed by detail specs. Returns ``[spec]`` if no split is needed.
    """
    if len(spec.nodes) <= max_nodes_per_page:
        return [spec]

    clusters = cluster_nodes(spec, strategy)

    # If clustering produces only one cluster, no benefit in splitting
    if len(clusters) <= 1:
        return [spec]

    summary = build_summary(spec, clusters)
    details = [
        build_detail(spec, cluster, idx)
        for idx, cluster in enumerate(clusters)
    ]
    return [summary] + details


def split_save_paths(base_path: str, count: int) -> list[str]:
    """Generate file paths for split diagram output.

    Given a base path like 'docs/architecture/c4-l3-api-server.html',
    produces:
      - 'docs/architecture/c4-l3-api-server.html'           (summary)
      - 'docs/architecture/c4-l3-api-server-detail-1.html'  (detail 1)
      - 'docs/architecture/c4-l3-api-server-detail-2.html'  (detail 2)
      - ...

    Args:
        base_path: The original file path (before splitting).
        count: Total number of specs (1 summary + N details).

    Returns:
        List of file path strings, one per spec.
    """
    if count <= 1:
        return [base_path]

    p = PurePosixPath(base_path)
    stem = p.stem
    suffix = p.suffix

    paths = [base_path]  # summary keeps original name
    for i in range(1, count):
        paths.append(str(p.with_name(f"{stem}-detail-{i}{suffix}")))
    return paths
