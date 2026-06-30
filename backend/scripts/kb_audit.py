"""
Knowledge-base content audit — $0, read-only, no Modal.

The RAG retriever is fine (M3/M4 context-precision ≈ 0.79); the scary
RAGAS faithfulness ≈ 0.04 is mostly a MEASUREMENT artifact (empathic CBT
replies make few citable claims), NOT broken retrieval. Before touching the
pipeline, this script answers the only question that would justify a real
change: "is the KB CONTENT healthy?" — per Qdrant store it reports:

  • point count
  • doc_role distribution
  • risk_allowed distribution
  • empty / very-short chunks (would retrieve as noise)
  • exact-duplicate rate (inflates a topic, wastes top-k slots)
  • content length: mean / p50 / p90

Run from backend/:
    python scripts/kb_audit.py
"""
from __future__ import annotations
import hashlib
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.core.config import settings           # noqa: E402
from app.services import qdrant_client as qd    # noqa: E402


def _pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "—"


def _scroll_all(cli, name, page=512):
    """Yield every payload in a collection (vectors not fetched)."""
    offset = None
    while True:
        points, offset = cli.scroll(
            collection_name=name, limit=page, offset=offset,
            with_payload=True, with_vectors=False)
        for p in points:
            yield dict(p.payload or {})
        if offset is None:
            break


def audit_collection(cli, name):
    print("\n" + "=" * 64)
    print(f" {name}")
    print("=" * 64)
    try:
        cli.get_collection(name)
    except Exception as e:
        print(f"   MISSING / unreadable: {e}")
        return

    roles, risks = Counter(), Counter()
    lengths, hashes = [], Counter()
    n = empty = short = 0
    for pl in _scroll_all(cli, name):
        n += 1
        content = (pl.get("content") or "").strip()
        roles[pl.get("doc_role") or "—"] += 1
        for r in (pl.get("risk_allowed") or ["—"]):
            risks[r] += 1
        if not content:
            empty += 1
            continue
        if len(content) < 80:
            short += 1
        lengths.append(len(content))
        hashes[hashlib.sha1(content.encode("utf-8")).hexdigest()] += 1

    if not n:
        print("   EMPTY collection (0 points).")
        return

    dups = sum(c - 1 for c in hashes.values() if c > 1)
    print(f"   points: {n}")
    print(f"   empty content:      {empty} ({_pct(empty, n)})")
    print(f"   very short (<80ch): {short} ({_pct(short, n)})")
    print(f"   exact duplicates:   {dups} ({_pct(dups, n)})")
    if lengths:
        lengths.sort()
        p = lambda q: lengths[min(len(lengths) - 1, int(q * len(lengths)))]
        print(f"   content length:     mean {int(statistics.mean(lengths))}  "
              f"p50 {p(.5)}  p90 {p(.9)}  max {lengths[-1]}")
    print(f"   doc_role:    {dict(roles)}")
    print(f"   risk_allowed:{dict(risks)}")

    flags = []
    if empty:
        flags.append(f"{empty} empty chunks (retrieve as noise — clean them)")
    if _pct(dups, n) != "—" and dups / n > 0.05:
        flags.append(f"{_pct(dups, n)} duplicates (waste top-k slots)")
    if lengths and statistics.mean(lengths) < 120:
        flags.append("chunks look very short (thin context — check chunking)")
    if flags:
        print("   ⚠  " + "\n   ⚠  ".join(flags))
    else:
        print("   ✓ content looks healthy")


def main():
    print("#" * 64)
    print("# KB CONTENT AUDIT  ($0 — read-only, no Modal)")
    print("#" * 64)
    cli = qd.get_qdrant()
    prefix = settings.rag_collection_prefix
    stores = [f"{prefix}__cbt_knowledge_base",
              f"{prefix}__response_template_base",
              f"{prefix}__safety_policy_base"]
    for name in stores:
        audit_collection(cli, name)
    print("\n" + "#" * 64)
    print("# Healthy retrieval + this audit clean ⇒ the low RAGAS faithfulness")
    print("# is a measurement artifact, not a content problem. Re-measure with")
    print("# grounding_nli(..., factual_only=True) for the real number.")
    print("#" * 64)


if __name__ == "__main__":
    main()
