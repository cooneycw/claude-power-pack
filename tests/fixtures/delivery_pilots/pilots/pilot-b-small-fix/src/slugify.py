"""Turn a title into a URL slug."""

import re


def slugify(title):
    """Lowercase, collapse runs of non-alphanumerics to one hyphen, trim hyphens."""
    out = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return out.strip()
