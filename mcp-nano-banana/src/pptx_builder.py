"""PowerPoint slide builder — creates PPTX files with embedded diagrams and content."""

from __future__ import annotations

import base64
import io
import logging

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

logger = logging.getLogger(__name__)

# Standard 16:9 widescreen dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def create_presentation(
    title: str,
    slides: list[dict],
    author: str = "Nano-Banana",
) -> bytes:
    """Create a PowerPoint presentation from slide definitions.

    Args:
        title: Presentation title (used for title slide).
        slides: List of slide dicts, each with:
            - layout: "title", "content", "diagram", "two-column", "blank"
            - title: Slide title
            - subtitle: Optional subtitle
            - content: Text content (bullet points separated by newlines)
            - image_base64: Base64-encoded PNG image to embed
            - notes: Speaker notes
        author: Author metadata.

    Returns:
        PPTX file as bytes.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # Set core properties
    prs.core_properties.author = author
    prs.core_properties.title = title

    for slide_def in slides:
        layout = slide_def.get("layout", "content")
        if layout == "title":
            _add_title_slide(prs, slide_def)
        elif layout == "diagram":
            _add_diagram_slide(prs, slide_def)
        elif layout == "two-column":
            _add_two_column_slide(prs, slide_def)
        elif layout == "blank":
            _add_blank_slide(prs, slide_def)
        else:
            _add_content_slide(prs, slide_def)

    # Save to bytes
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _add_title_slide(prs: Presentation, slide_def: dict) -> None:
    """Add a title slide with dark background."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    _set_slide_bg(slide, RGBColor(0x0F, 0x17, 0x2A))

    # Title
    _add_textbox(
        slide,
        slide_def.get("title", ""),
        left=Inches(1), top=Inches(2.5), width=Inches(11.333), height=Inches(1.5),
        font_size=Pt(44), font_color=RGBColor(0xF8, 0xFA, 0xFC),
        bold=True, alignment=PP_ALIGN.CENTER,
    )

    # Subtitle
    if slide_def.get("subtitle"):
        _add_textbox(
            slide,
            slide_def["subtitle"],
            left=Inches(1), top=Inches(4.2), width=Inches(11.333), height=Inches(1),
            font_size=Pt(20), font_color=RGBColor(0x94, 0xA3, 0xB8),
            alignment=PP_ALIGN.CENTER,
        )

    _add_notes(slide, slide_def)


def _add_content_slide(prs: Presentation, slide_def: dict) -> None:
    """Add a content slide with title and bullet points."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide, RGBColor(0x1E, 0x29, 0x3B))

    # Title bar
    _add_textbox(
        slide,
        slide_def.get("title", ""),
        left=Inches(0.8), top=Inches(0.5), width=Inches(11.733), height=Inches(0.9),
        font_size=Pt(32), font_color=RGBColor(0xF8, 0xFA, 0xFC),
        bold=True,
    )

    # Content
    content = slide_def.get("content", "")
    if content:
        _add_textbox(
            slide,
            content,
            left=Inches(1), top=Inches(1.8), width=Inches(11.333), height=Inches(5),
            font_size=Pt(18), font_color=RGBColor(0xE2, 0xE8, 0xF0),
        )

    _add_notes(slide, slide_def)


def _add_diagram_slide(prs: Presentation, slide_def: dict) -> None:
    """Add a slide with an embedded diagram image."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide, RGBColor(0x0F, 0x17, 0x2A))

    # Title (smaller for diagram slides)
    if slide_def.get("title"):
        _add_textbox(
            slide,
            slide_def["title"],
            left=Inches(0.5), top=Inches(0.3), width=Inches(12.333), height=Inches(0.7),
            font_size=Pt(24), font_color=RGBColor(0xF8, 0xFA, 0xFC),
            bold=True,
        )

    # Embed image
    image_b64 = slide_def.get("image_base64", "")
    if image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
            img_stream = io.BytesIO(img_bytes)
            # Full-width diagram below title
            slide.shapes.add_picture(
                img_stream,
                left=Inches(0.3),
                top=Inches(1.2),
                width=Inches(12.733),
                height=Inches(5.8),
            )
        except Exception as e:
            logger.warning(f"Failed to embed diagram image: {e}")
            _add_textbox(
                slide,
                f"[Diagram image could not be embedded: {e}]",
                left=Inches(1), top=Inches(3), width=Inches(11.333), height=Inches(1),
                font_size=Pt(16), font_color=RGBColor(0xEF, 0x44, 0x44),
            )

    _add_notes(slide, slide_def)


def _add_two_column_slide(prs: Presentation, slide_def: dict) -> None:
    """Add a two-column layout slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide, RGBColor(0x1E, 0x29, 0x3B))

    # Title
    _add_textbox(
        slide,
        slide_def.get("title", ""),
        left=Inches(0.8), top=Inches(0.5), width=Inches(11.733), height=Inches(0.9),
        font_size=Pt(32), font_color=RGBColor(0xF8, 0xFA, 0xFC),
        bold=True,
    )

    # Left column
    left_content = slide_def.get("left_content", slide_def.get("content", ""))
    _add_textbox(
        slide,
        left_content,
        left=Inches(0.8), top=Inches(1.8), width=Inches(5.5), height=Inches(5),
        font_size=Pt(16), font_color=RGBColor(0xE2, 0xE8, 0xF0),
    )

    # Right column
    right_content = slide_def.get("right_content", "")
    if right_content:
        _add_textbox(
            slide,
            right_content,
            left=Inches(7), top=Inches(1.8), width=Inches(5.5), height=Inches(5),
            font_size=Pt(16), font_color=RGBColor(0xE2, 0xE8, 0xF0),
        )

    _add_notes(slide, slide_def)


def _add_blank_slide(prs: Presentation, slide_def: dict) -> None:
    """Add a blank slide (dark background only)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide, RGBColor(0x0F, 0x17, 0x2A))
    _add_notes(slide, slide_def)


def _set_slide_bg(slide, color: RGBColor) -> None:
    """Set slide background to a solid color."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(
    slide,
    text: str,
    left,
    top,
    width,
    height,
    font_size=Pt(18),
    font_color=RGBColor(0xE2, 0xE8, 0xF0),
    bold: bool = False,
    alignment=PP_ALIGN.LEFT,
) -> None:
    """Add a text box to a slide."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size = None

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line.lstrip("- ")
        p.alignment = alignment
        p.font.size = font_size
        p.font.color.rgb = font_color
        p.font.bold = bold

        # Add bullet for lines starting with -
        if line.strip().startswith("-"):
            p.level = 0


def _add_notes(slide, slide_def: dict) -> None:
    """Add speaker notes to a slide."""
    notes = slide_def.get("notes", "")
    if notes:
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = notes
