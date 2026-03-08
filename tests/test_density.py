"""Tests for the score_diagram_density function in nano-banana."""

from diagrams.validate import score_diagram_density


class TestDensityThresholds:
    """Test density status thresholds at default 1920x1080 viewport.

    With default params (avg_node_width=200, avg_node_height=100):
        usable_area = 1920 * 1080 * 0.65 = 1,347,840
        node_area   = 200 * 100 * 1.5    = 30,000
        capacity    = int(1,347,840 / 30,000) = 44

    Thresholds (density = node_count / capacity):
        <= 0.8: ok
        0.8-1.0: warning
        1.0-1.5: overflow
        > 1.5: critical
    """

    def test_small_diagram_ok(self):
        """5 nodes at 1920x1080 -> status: ok (density ~0.11)."""
        result = score_diagram_density(node_count=5, edge_count=4)
        assert result["status"] == "ok"
        assert result["suggestion"] is None
        assert result["node_count"] == 5
        assert result["edge_count"] == 4

    def test_medium_diagram_ok(self):
        """20 nodes at 1920x1080 -> still ok (density ~0.45)."""
        result = score_diagram_density(node_count=20, edge_count=19)
        assert result["status"] == "ok"

    def test_near_capacity_warning(self):
        """36 nodes -> warning (density ~0.82, just above 0.8 threshold)."""
        result = score_diagram_density(node_count=36, edge_count=35)
        assert result["status"] == "warning"
        assert result["suggestion"] is not None

    def test_at_capacity_warning(self):
        """44 nodes -> warning (density = 1.0, at capacity but <= 1.0)."""
        result = score_diagram_density(node_count=44, edge_count=43)
        assert result["status"] == "warning"

    def test_overflow(self):
        """50 nodes -> overflow (density ~1.14)."""
        result = score_diagram_density(node_count=50, edge_count=49)
        assert result["status"] == "overflow"
        assert "split" in result["suggestion"].lower()

    def test_critical(self):
        """70 nodes -> critical (density ~1.59)."""
        result = score_diagram_density(node_count=70, edge_count=69)
        assert result["status"] == "critical"
        assert "must split" in result["suggestion"].lower()


class TestDensityReturnStructure:
    def test_all_keys_present(self):
        result = score_diagram_density(node_count=10, edge_count=9)
        assert "density" in result
        assert "capacity" in result
        assert "node_count" in result
        assert "edge_count" in result
        assert "status" in result
        assert "suggestion" in result

    def test_density_is_rounded(self):
        result = score_diagram_density(node_count=10, edge_count=9)
        # density should be a float rounded to 2 decimal places
        density_str = str(result["density"])
        if "." in density_str:
            assert len(density_str.split(".")[1]) <= 2

    def test_capacity_is_int(self):
        result = score_diagram_density(node_count=5, edge_count=4)
        assert isinstance(result["capacity"], int)


class TestDensityCustomViewport:
    def test_smaller_viewport_reduces_capacity(self):
        default = score_diagram_density(node_count=10, edge_count=9)
        small = score_diagram_density(node_count=10, edge_count=9, width=800, height=600)
        assert small["capacity"] < default["capacity"]
        assert small["density"] > default["density"]

    def test_larger_viewport_increases_capacity(self):
        default = score_diagram_density(node_count=10, edge_count=9)
        large = score_diagram_density(node_count=10, edge_count=9, width=3840, height=2160)
        assert large["capacity"] > default["capacity"]
        assert large["density"] < default["density"]


class TestDensityEdgeCases:
    def test_zero_nodes(self):
        result = score_diagram_density(node_count=0, edge_count=0)
        assert result["status"] == "ok"
        assert result["density"] == 0.0

    def test_one_node(self):
        result = score_diagram_density(node_count=1, edge_count=0)
        assert result["status"] == "ok"

    def test_custom_node_size(self):
        """Larger nodes reduce capacity."""
        result = score_diagram_density(
            node_count=10, edge_count=9,
            avg_node_width=400, avg_node_height=200,
        )
        default = score_diagram_density(node_count=10, edge_count=9)
        assert result["capacity"] < default["capacity"]
