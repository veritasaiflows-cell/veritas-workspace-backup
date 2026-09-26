import re


def slugify(title, max_len=40):
    """Make a URL slug.

    Lowercase the title; every run of characters other than ASCII a-z and 0-9 becomes a
    single "-"; strip leading and trailing "-"; truncate to max_len characters, then strip
    any trailing "-" again. If the result is empty, return "untitled".
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = slug[:max_len].rstrip("-")
    return slug
