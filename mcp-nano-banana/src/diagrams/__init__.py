"""Diagram generators for the Nano-Banana MCP server."""

from diagrams.architecture import generate_architecture_diagram
from diagrams.c4 import generate_c4_diagram
from diagrams.flowchart import generate_flowchart_diagram
from diagrams.sequence import generate_sequence_diagram
from diagrams.orgchart import generate_orgchart_diagram
from diagrams.timeline import generate_timeline_diagram
from diagrams.mindmap import generate_mindmap_diagram
from diagrams.base import DIAGRAM_TYPES, DiagramSpec, DiagramNode, DiagramEdge
from diagrams.validate import validate_diagram, score_diagram_density
from diagrams.split import auto_split_diagram, split_save_paths, cluster_nodes

__all__ = [
    "generate_architecture_diagram",
    "generate_c4_diagram",
    "generate_flowchart_diagram",
    "generate_sequence_diagram",
    "generate_orgchart_diagram",
    "generate_timeline_diagram",
    "generate_mindmap_diagram",
    "validate_diagram",
    "score_diagram_density",
    "auto_split_diagram",
    "split_save_paths",
    "cluster_nodes",
    "DIAGRAM_TYPES",
    "DiagramSpec",
    "DiagramNode",
    "DiagramEdge",
]
