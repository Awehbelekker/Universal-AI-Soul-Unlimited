"""
PC-local family document library.

Stores catalog metadata + chunked text under data/library/.
Keyword retrieval (no embeddings) for v1 — good enough for grounded ask/summarize.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
LIBRARY_DIR = ROOT / "data" / "library"
_lock = threading.Lock()

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 150
_MAX_BYTES = 12 * 1024 * 1024  # 12 MB

_ALLOWED_EXT = frozenset({".txt", ".md", ".markdown", ".pdf"})

_ALLOWED_TAGS = frozenset(
    {"parenting", "bedtime", "support", "kids", "general", "story"}
)

_LIBRARY_INTENT_RE = re.compile(
    r"\b("
    r"summarize|summary|summarise|"
    r"from (?:the |my |our )?(?:book|document|doc|pdf|library|file)|"
    r"in (?:the |my |our )?(?:book|library|document)|"
    r"(?:read|tell me) (?:(?:me |us )?)?(?:about |from )?(?:the |this |my )?(?:book|document|chapter)|"
    r"what does (?:the |my |this )?(?:book|document|doc) (?:say|mean)|"
    r"library|chapter\s+\d+"
    r")\b",
    re.I,
)

_SUPPORT_INTENT_RE = re.compile(
    r"\b("
    r"how (?:do|can|should) i support|"
    r"how to support|"
    r"parenting (?:advice|help|tip)|"
    r"help (?:my |our )?(?:child|kid|son|daughter|teen)|"
    r"what (?:does|do) (?:our |the |my )?parenting|"
    r"bedtime (?:routine|help|advice)|"
    r"support (?:my |our )?(?:child|kid|partner|family)"
    r")\b",
    re.I,
)

_STOP = frozenset(
    "a an the and or but if in on at to for of is are was were be been "
    "this that these those it its with from by as into about over after "
    "before between under again further then once here there when where "
    "why how all each few more most other some such no nor not only own "
    "same so than too very can will just don should now what which who "
    "whom your you me my our we they them their".split()
)


def _ensure_dir() -> Path:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return LIBRARY_DIR


def _meta_path(doc_id: str) -> Path:
    return _ensure_dir() / f"{doc_id}.meta.json"


def _chunks_path(doc_id: str) -> Path:
    return _ensure_dir() / f"{doc_id}.chunks.jsonl"


def _safe_title(title: str, filename: str) -> str:
    t = (title or "").strip()
    if t:
        return t[:160]
    stem = Path(filename or "document").stem.strip() or "Untitled"
    return stem[:160]


def normalize_tags(tags: Any) -> List[str]:
    """Normalize tag list to allowed lowercase labels."""
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = re.split(r"[,;\s]+", tags)
    elif isinstance(tags, (list, tuple, set)):
        raw = [str(t) for t in tags]
    else:
        return []
    out: List[str] = []
    for t in raw:
        key = re.sub(r"[^a-z0-9_-]", "", t.strip().lower())
        if key in _ALLOWED_TAGS and key not in out:
            out.append(key)
    return out[:8]


def _extract_text(data: bytes, filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise ValueError(
            f"Unsupported type “{ext or 'unknown'}”. Use .txt, .md, or .pdf."
        )
    if ext in (".txt", ".md", ".markdown"):
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    # PDF
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError(
            "PDF support needs pypdf. Install with: pip install pypdf"
        ) from exc
    import io

    reader = PdfReader(io.BytesIO(data))
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("Could not extract text from this PDF (it may be scanned/image-only).")
    return text


def _chunk_text(text: str) -> List[str]:
    cleaned = re.sub(r"\r\n?", "\n", text or "").strip()
    if not cleaned:
        return []
    # Prefer paragraph boundaries when possible
    paras = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in paras:
        if len(para) > _CHUNK_SIZE:
            if buf:
                chunks.append(buf.strip())
                buf = ""
            start = 0
            while start < len(para):
                end = min(len(para), start + _CHUNK_SIZE)
                chunks.append(para[start:end].strip())
                if end >= len(para):
                    break
                start = max(end - _CHUNK_OVERLAP, start + 1)
            continue
        if buf and len(buf) + 2 + len(para) > _CHUNK_SIZE:
            chunks.append(buf.strip())
            # overlap: keep tail of previous
            buf = buf[-_CHUNK_OVERLAP:] + "\n\n" + para if _CHUNK_OVERLAP else para
        else:
            buf = (buf + "\n\n" + para).strip() if buf else para
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def _tokens(text: str) -> List[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9']{3,}", (text or "").lower())
        if t not in _STOP
    ]


def visible_to(meta: Dict[str, Any], member_id: str) -> bool:
    """Whether member_id may see this document."""
    vis = (meta.get("visibility") or "family").strip().lower()
    owner = (meta.get("member_id") or "primary").strip() or "primary"
    mid = (member_id or "primary").strip() or "primary"
    if vis == "private":
        return mid == owner or mid == "primary"
    return True  # family


def ingest_bytes(
    data: bytes,
    *,
    filename: str = "document.txt",
    title: str = "",
    member_id: str = "primary",
    visibility: str = "family",
    tags: Any = None,
) -> Dict[str, Any]:
    """Ingest raw file bytes into the library. Returns meta + stats."""
    if not data:
        return {"ok": False, "error": "empty file"}
    if len(data) > _MAX_BYTES:
        return {
            "ok": False,
            "error": f"File too large (max {_MAX_BYTES // (1024 * 1024)} MB)",
        }
    vis = (visibility or "family").strip().lower()
    if vis not in ("family", "private"):
        vis = "family"
    mid = (member_id or "primary").strip() or "primary"
    tag_list = normalize_tags(tags)
    try:
        text = _extract_text(data, filename)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"extract failed: {exc}"}

    chunks = _chunk_text(text)
    if not chunks:
        return {"ok": False, "error": "No readable text found in file"}

    doc_id = uuid.uuid4().hex[:12]
    meta = {
        "id": doc_id,
        "title": _safe_title(title, filename),
        "filename": Path(filename or "document.txt").name[:160],
        "member_id": mid,
        "visibility": vis,
        "tags": tag_list,
        "created_at": time.time(),
        "char_count": len(text),
        "chunk_count": len(chunks),
        "ext": Path(filename or "").suffix.lower() or ".txt",
    }

    with _lock:
        _ensure_dir()
        _meta_path(doc_id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with _chunks_path(doc_id).open("w", encoding="utf-8") as fh:
            for i, chunk in enumerate(chunks):
                fh.write(
                    json.dumps(
                        {"i": i, "text": chunk, "doc_id": doc_id},
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    return {
        "ok": True,
        "doc": meta,
        "preview": chunks[0][:240],
    }


def update_doc(
    doc_id: str,
    member_id: str = "primary",
    *,
    tags: Any = None,
    title: Optional[str] = None,
    visibility: Optional[str] = None,
) -> Dict[str, Any]:
    """Update catalog fields (tags / title / visibility)."""
    mid = (member_id or "primary").strip() or "primary"
    meta = get_doc(doc_id)
    if not meta:
        return {"ok": False, "error": "not found"}
    owner = (meta.get("member_id") or "primary").strip()
    if mid != owner and mid != "primary":
        return {"ok": False, "error": "not allowed to update this document"}
    if tags is not None:
        meta["tags"] = normalize_tags(tags)
    if title is not None and str(title).strip():
        meta["title"] = str(title).strip()[:160]
    if visibility is not None:
        vis = str(visibility).strip().lower()
        if vis in ("family", "private"):
            meta["visibility"] = vis
    with _lock:
        _meta_path(doc_id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"ok": True, "doc": meta}


def get_doc(doc_id: str) -> Optional[Dict[str, Any]]:
    path = _meta_path(doc_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_docs(member_id: str = "primary") -> Dict[str, Any]:
    mid = (member_id or "primary").strip() or "primary"
    docs: List[Dict[str, Any]] = []
    with _lock:
        _ensure_dir()
        for path in sorted(LIBRARY_DIR.glob("*.meta.json")):
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(meta, dict) or not meta.get("id"):
                continue
            if visible_to(meta, mid):
                docs.append(meta)
    docs.sort(key=lambda d: float(d.get("created_at") or 0), reverse=True)
    return {"ok": True, "docs": docs, "count": len(docs)}


def delete_doc(doc_id: str, member_id: str = "primary") -> Dict[str, Any]:
    mid = (member_id or "primary").strip() or "primary"
    meta = get_doc(doc_id)
    if not meta:
        return {"ok": False, "error": "not found"}
    owner = (meta.get("member_id") or "primary").strip()
    # Owner or primary can delete
    if mid != owner and mid != "primary":
        return {"ok": False, "error": "not allowed to delete this document"}
    with _lock:
        for p in (_meta_path(doc_id), _chunks_path(doc_id)):
            try:
                if p.is_file():
                    p.unlink()
            except OSError as exc:
                return {"ok": False, "error": str(exc)}
    return {"ok": True, "deleted": doc_id}


def _load_chunks(doc_id: str) -> List[Dict[str, Any]]:
    path = _chunks_path(doc_id)
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row.get("text"):
                out.append(row)
    except Exception:
        return []
    return out


def search(
    query: str,
    member_id: str = "primary",
    *,
    limit: int = 6,
    doc_id: Optional[str] = None,
    prefer_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Keyword overlap search across visible documents."""
    q = (query or "").strip()
    if not q:
        return {"ok": True, "hits": [], "query": q}
    mid = (member_id or "primary").strip() or "primary"
    q_tokens = _tokens(q)
    prefer = set(normalize_tags(prefer_tags or []))
    catalog = list_docs(mid).get("docs") or []
    if doc_id:
        catalog = [d for d in catalog if d.get("id") == doc_id]

    scored: List[Dict[str, Any]] = []
    for meta in catalog:
        did = meta.get("id")
        if not did:
            continue
        title = str(meta.get("title") or "")
        title_l = title.lower()
        doc_tags = set(normalize_tags(meta.get("tags") or []))
        title_boost = 0
        if title_l and title_l in q.lower():
            title_boost = 8
        elif any(t in title_l for t in q_tokens[:6]):
            title_boost = 3
        tag_boost = 5 if prefer and (doc_tags & prefer) else 0

        for row in _load_chunks(str(did)):
            text = str(row.get("text") or "")
            c_tokens = set(_tokens(text))
            if not q_tokens:
                overlap = 0
            else:
                overlap = sum(1 for t in q_tokens if t in c_tokens)
            # phrase bonus
            phrase = 2 if len(q) > 8 and q.lower() in text.lower() else 0
            score = overlap + title_boost + phrase + tag_boost
            if score <= 0 and not title_boost and not tag_boost:
                continue
            scored.append(
                {
                    "score": score,
                    "doc_id": did,
                    "title": title,
                    "chunk_index": row.get("i"),
                    "text": text,
                    "visibility": meta.get("visibility"),
                    "tags": sorted(doc_tags),
                }
            )

    scored.sort(key=lambda h: (-int(h["score"]), str(h.get("title") or "")))
    # If summarize-style query with a matched title but weak chunk scores,
    # fall back to first chunks of the best-matching doc.
    hits = scored[: max(1, min(int(limit or 6), 12))]
    if not hits and catalog:
        # Prefer title substring match, else tagged parenting docs, else recent
        best = None
        ql = q.lower()
        for meta in catalog:
            t = str(meta.get("title") or "").lower()
            if t and (t in ql or any(w in t for w in q_tokens[:4])):
                best = meta
                break
        if best is None and prefer:
            for meta in catalog:
                if set(normalize_tags(meta.get("tags") or [])) & prefer:
                    best = meta
                    break
        if best is None and (
            "summar" in ql
            or "library" in ql
            or "book" in ql
            or "chapter" in ql
            or "support" in ql
            or "parent" in ql
        ):
            best = catalog[0]
        if best:
            chunks = _load_chunks(str(best["id"]))[: max(1, min(int(limit or 6), 8))]
            hits = [
                {
                    "score": 1,
                    "doc_id": best["id"],
                    "title": best.get("title"),
                    "chunk_index": c.get("i"),
                    "text": c.get("text"),
                    "visibility": best.get("visibility"),
                    "tags": normalize_tags(best.get("tags") or []),
                }
                for c in chunks
            ]

    return {"ok": True, "hits": hits, "query": q, "count": len(hits)}


def library_intent(message: str, member_id: str = "primary") -> Optional[Dict[str, Any]]:
    """Detect ask/summarize/support-about-library intent; return search payload or None."""
    text = (message or "").strip()
    if not text or len(text) < 4:
        return None
    mid = (member_id or "primary").strip() or "primary"
    catalog = list_docs(mid).get("docs") or []
    support = bool(_SUPPORT_INTENT_RE.search(text))
    libraryish = bool(_LIBRARY_INTENT_RE.search(text))
    if not catalog:
        if support or libraryish:
            return {
                "query": text,
                "empty": True,
                "hits": [],
                "support": support,
                "prefer_tags": ["parenting", "support"] if support else [],
            }
        return None

    title_hit = None
    low = text.lower()
    for meta in catalog:
        title = str(meta.get("title") or "").strip()
        if len(title) >= 3 and title.lower() in low:
            title_hit = meta
            break

    prefer_tags: List[str] = []
    if support:
        prefer_tags = ["parenting", "support", "kids", "bedtime"]

    if title_hit or libraryish or support:
        result = search(
            text,
            mid,
            limit=6,
            doc_id=title_hit.get("id") if title_hit else None,
            prefer_tags=prefer_tags or None,
        )
        return {
            "query": text,
            "empty": False,
            "doc_id": title_hit.get("id") if title_hit else None,
            "title": title_hit.get("title") if title_hit else None,
            "hits": result.get("hits") or [],
            "support": support,
            "prefer_tags": prefer_tags,
        }
    return None


def format_hits_for_prompt(hits: List[Dict[str, Any]], *, max_chars: int = 3500) -> str:
    """Format retrieved chunks for chat system prompt."""
    if not hits:
        return ""
    parts: List[str] = []
    used = 0
    for h in hits:
        title = h.get("title") or "Document"
        idx = h.get("chunk_index")
        body = (h.get("text") or "").strip()
        if not body:
            continue
        block = f"[{title} · chunk {idx}]\n{body}"
        if used + len(block) > max_chars:
            remain = max_chars - used - 40
            if remain > 80:
                parts.append(block[:remain] + "…")
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)
