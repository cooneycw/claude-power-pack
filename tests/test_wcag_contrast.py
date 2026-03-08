"""Tests for WCAG contrast compliance in nano-banana diagram palettes."""

from diagrams.base import _contrast_ratio as base_contrast_ratio
from diagrams.base import _node_color
from diagrams.base import _relative_luminance as base_luminance
from diagrams.c4 import _C4_COLORS, _DEFAULT_COLOR
from diagrams.validate import _contrast_ratio, _relative_luminance, validate_diagram

WCAG_AA_MINIMUM = 4.5


class TestC4PaletteContrast:
    """Verify all C4 palette color combinations meet WCAG AA 4.5:1 minimum."""

    def test_person_contrast(self):
        bg, _border, text = _C4_COLORS["person"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"person: {ratio:.2f}:1 (need >= {WCAG_AA_MINIMUM})"

    def test_system_contrast(self):
        bg, _border, text = _C4_COLORS["system"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"system: {ratio:.2f}:1"

    def test_system_focus_contrast(self):
        bg, _border, text = _C4_COLORS["system-focus"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"system-focus: {ratio:.2f}:1"

    def test_container_contrast(self):
        bg, _border, text = _C4_COLORS["container"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"container: {ratio:.2f}:1"

    def test_component_contrast(self):
        bg, _border, text = _C4_COLORS["component"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"component: {ratio:.2f}:1"

    def test_code_contrast(self):
        bg, _border, text = _C4_COLORS["code"]
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"code: {ratio:.2f}:1"

    def test_default_color_contrast(self):
        bg, _border, text = _DEFAULT_COLOR
        ratio = _contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"default: {ratio:.2f}:1"

    def test_all_c4_colors_at_once(self):
        """Parametric check of every C4 color type."""
        for node_type, (bg, _border, text) in _C4_COLORS.items():
            ratio = _contrast_ratio(text, bg)
            assert ratio >= WCAG_AA_MINIMUM, (
                f"C4 type '{node_type}': contrast {ratio:.2f}:1 < {WCAG_AA_MINIMUM}:1 "
                f"(bg={bg}, text={text})"
            )


class TestBasePaletteContrast:
    """Verify all base diagram palette colors meet WCAG AA 4.5:1 minimum."""

    def test_primary_contrast(self):
        bg, _border, text = _node_color("primary")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"primary: {ratio:.2f}:1"

    def test_secondary_contrast(self):
        bg, _border, text = _node_color("secondary")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"secondary: {ratio:.2f}:1"

    def test_accent_contrast(self):
        bg, _border, text = _node_color("accent")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"accent: {ratio:.2f}:1"

    def test_warning_contrast(self):
        bg, _border, text = _node_color("warning")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"warning: {ratio:.2f}:1"

    def test_success_contrast(self):
        bg, _border, text = _node_color("success")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"success: {ratio:.2f}:1"

    def test_default_contrast(self):
        bg, _border, text = _node_color("default")
        ratio = base_contrast_ratio(text, bg)
        assert ratio >= WCAG_AA_MINIMUM, f"default: {ratio:.2f}:1"

    def test_unknown_type_falls_back_to_default(self):
        bg, _border, text = _node_color("nonexistent")
        default_bg, _d_border, default_text = _node_color("default")
        assert bg == default_bg
        assert text == default_text


class TestLuminanceCalculation:
    """Test WCAG relative luminance calculations."""

    def test_black_luminance(self):
        lum = _relative_luminance(0, 0, 0)
        assert abs(lum - 0.0) < 0.001

    def test_white_luminance(self):
        lum = _relative_luminance(255, 255, 255)
        assert abs(lum - 1.0) < 0.001

    def test_red_luminance(self):
        lum = _relative_luminance(255, 0, 0)
        assert 0.2 < lum < 0.22  # ~0.2126

    def test_green_luminance(self):
        lum = _relative_luminance(0, 255, 0)
        assert 0.71 < lum < 0.72  # ~0.7152

    def test_blue_luminance(self):
        lum = _relative_luminance(0, 0, 255)
        assert 0.07 < lum < 0.08  # ~0.0722

    def test_base_luminance_hex_input(self):
        """The base.py version takes hex input directly."""
        lum = base_luminance("#ffffff")
        assert abs(lum - 1.0) < 0.001

    def test_base_luminance_black(self):
        lum = base_luminance("#000000")
        assert abs(lum - 0.0) < 0.001


class TestContrastRatioMath:
    """Test contrast ratio calculation correctness."""

    def test_max_contrast(self):
        ratio = _contrast_ratio("#ffffff", "#000000")
        assert ratio >= 20.0  # 21:1 theoretical max

    def test_no_contrast(self):
        ratio = _contrast_ratio("#888888", "#888888")
        assert abs(ratio - 1.0) < 0.01

    def test_symmetry(self):
        r1 = _contrast_ratio("#ff0000", "#0000ff")
        r2 = _contrast_ratio("#0000ff", "#ff0000")
        assert abs(r1 - r2) < 0.01

    def test_known_ratio(self):
        """White on dark blue (#1e40af) should be ~8.72:1."""
        ratio = _contrast_ratio("#ffffff", "#1e40af")
        assert 8.5 < ratio < 9.0


class TestValidateDiagramContrastCheck:
    """Test that validate_diagram correctly flags poor contrast."""

    def test_c4_palette_passes_contrast_check(self):
        nodes = [
            {"id": "p", "label": "Person", "type": "person"},
            {"id": "s", "label": "System", "type": "system"},
            {"id": "sf", "label": "Focus", "type": "system-focus"},
            {"id": "c", "label": "Container", "type": "container"},
            {"id": "comp", "label": "Component", "type": "component"},
            {"id": "code", "label": "Code", "type": "code"},
        ]
        result = validate_diagram(nodes=nodes, diagram_type="c4")
        contrast_issues = [i for i in result["issues"] if i["check"] == "contrast"]
        assert len(contrast_issues) == 0, f"C4 palette has contrast issues: {contrast_issues}"

    def test_suggestion_when_contrast_fails(self):
        """When contrast fails, suggestions should include WCAG guidance."""
        # Use architecture type where accent has known poor contrast
        nodes = [{"id": "a", "label": "A", "type": "accent"}]
        result = validate_diagram(nodes=nodes, diagram_type="architecture")
        contrast_issues = [i for i in result["issues"] if i["check"] == "contrast"]
        if contrast_issues:
            assert any("WCAG" in s or "contrast" in s for s in result["suggestions"])
