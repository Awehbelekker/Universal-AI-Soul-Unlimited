"""Family library ingest, search, and privacy."""

from __future__ import annotations

import pytest

from core.library import store as lib


@pytest.fixture()
def tmp_library(monkeypatch, tmp_path):
    monkeypatch.setattr(lib, "LIBRARY_DIR", tmp_path)
    return tmp_path


def test_ingest_txt_and_search(tmp_library):
    text = (
        "The purple zebra invented quantum porridge in chapter three. "
        "Later the zebra shared the recipe with the family."
    ).encode("utf-8")
    result = lib.ingest_bytes(
        text,
        filename="zebra.md",
        title="Purple Zebra Tales",
        member_id="richard_",
        visibility="family",
    )
    assert result["ok"], result
    assert result["doc"]["chunk_count"] >= 1

    found = lib.search("quantum porridge", member_id="richard_", limit=4)
    assert found["ok"]
    assert found["hits"], found
    assert "porridge" in found["hits"][0]["text"].lower()


def test_private_doc_hidden_from_other_member(tmp_library):
    payload = b"Secret diary of the moon garden and silver ferns."
    result = lib.ingest_bytes(
        payload,
        filename="diary.txt",
        title="Moon Diary",
        member_id="richard_",
        visibility="private",
    )
    assert result["ok"]
    doc_id = result["doc"]["id"]

    richard = lib.list_docs("richard_")
    assert any(d["id"] == doc_id for d in richard["docs"])

    sibling = lib.list_docs("sam_")
    assert not any(d["id"] == doc_id for d in sibling["docs"])

    # Primary can see private for household admin
    primary = lib.list_docs("primary")
    assert any(d["id"] == doc_id for d in primary["docs"])


def test_library_intent_summarize(tmp_library):
    lib.ingest_bytes(
        b"Habits compound. Tiny changes add up over years of practice.",
        filename="habits.txt",
        title="Atomic Habits",
        member_id="primary",
        visibility="family",
    )
    intent = lib.library_intent("Summarize Atomic Habits", "primary")
    assert intent is not None
    assert not intent.get("empty")
    assert intent.get("hits")


def test_parenting_tags_boost_support_intent(tmp_library):
    lib.ingest_bytes(
        b"When a child melts down, stay calm, name the feeling, and offer a choice.",
        filename="parenting.txt",
        title="Calm Parenting Guide",
        member_id="primary",
        visibility="family",
        tags=["parenting", "support"],
    )
    lib.ingest_bytes(
        b"Quantum porridge recipe for space explorers.",
        filename="other.txt",
        title="Space Cookbook",
        member_id="primary",
        visibility="family",
        tags=["general"],
    )
    intent = lib.library_intent("How do I support my child during a meltdown?", "primary")
    assert intent is not None
    assert intent.get("support")
    assert intent.get("hits")
    assert any("Calm" in str(h.get("title") or "") for h in intent["hits"])


def test_update_tags(tmp_library):
    result = lib.ingest_bytes(
        b"Bedtime stories help kids wind down.",
        filename="bed.txt",
        title="Night Stories",
        member_id="primary",
        tags=["story"],
    )
    doc_id = result["doc"]["id"]
    updated = lib.update_doc(doc_id, "primary", tags=["bedtime", "kids", "parenting"])
    assert updated["ok"]
    assert set(updated["doc"]["tags"]) == {"bedtime", "kids", "parenting"}


def test_delete_owner_only(tmp_library):
    result = lib.ingest_bytes(
        b"Shared picnic notes for Sunday lunch.",
        filename="picnic.txt",
        title="Picnic Notes",
        member_id="richard_",
        visibility="family",
    )
    doc_id = result["doc"]["id"]
    denied = lib.delete_doc(doc_id, "sam_")
    assert not denied["ok"]
    ok = lib.delete_doc(doc_id, "richard_")
    assert ok["ok"]
    assert lib.get_doc(doc_id) is None
