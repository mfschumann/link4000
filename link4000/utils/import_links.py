"""Link import utilities for Link4000."""

import json
import os
from typing import Optional

from link4000.data.link_store import LinkStore
from link4000.models.link import Link


def _detect_schema(data: dict | list) -> str:
    """Detect whether the input data uses 'legacy' or 'current' schema.

    Args:
        data: Parsed JSON data (dict or list)

    Returns:
        'legacy' if data uses keywords instead of tags, 'current' otherwise
    """
    if isinstance(data, list):
        return "legacy"
    links = data.get("links", [])
    if not links:
        return "current"
    first_link = links[0]
    if "keywords" in first_link:
        return "legacy"
    return "current"


def do_import(
    source_path: str, override: bool = False
) -> tuple[int, int, int, Optional[str]]:
    """Import links from a JSON file into the configured links.json.

    Args:
        source_path: Path to the source JSON file
        override: If True, overwrite existing links with the same URL

    Returns:
        Tuple of (added, skipped, updated, error_message).
        error_message is None on success, or a string describing the error.
    """
    source_path = os.path.expanduser(source_path)

    if not os.path.exists(source_path):
        return 0, 0, 0, f"File not found: {source_path}"

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return 0, 0, 0, f"Invalid JSON in {source_path}: {e}"

    schema = _detect_schema(data)

    if schema == "legacy":
        if not isinstance(data, list):
            return 0, 0, 0, f"Expected a list for legacy schema, got {type(data)}"
        links_data = data
    else:
        links_data = data.get("links", [])

    if not links_data:
        return 0, 0, 0, None

    if schema == "legacy":
        links: list[Link] = [Link.from_legacy_dict(d) for d in links_data]
    else:
        links = [Link.from_dict(d) for d in links_data]

    store = LinkStore()
    added, skipped, updated = store.import_links(links, override=override)

    return added, skipped, updated, None
