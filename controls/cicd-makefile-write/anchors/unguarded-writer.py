"""Constructed alternative: generate content, then overwrite without a guard."""

from pathlib import Path

from lib.cicd.makefile import generate_makefile


def write_makefile(project_root, *, force=False, template_dir=None):
    target = Path(project_root) / 'Makefile'
    target.write_text(generate_makefile(project_root, template_dir=template_dir))
    return target
