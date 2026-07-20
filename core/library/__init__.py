"""Family document library — PC-local ingest, search, and catalog."""

from core.library.store import (
    LIBRARY_DIR,
    delete_doc,
    format_hits_for_prompt,
    get_doc,
    ingest_bytes,
    list_docs,
    library_intent,
    normalize_tags,
    search,
    update_doc,
    visible_to,
)

__all__ = [
    "LIBRARY_DIR",
    "delete_doc",
    "format_hits_for_prompt",
    "get_doc",
    "ingest_bytes",
    "list_docs",
    "library_intent",
    "normalize_tags",
    "search",
    "update_doc",
    "visible_to",
]
