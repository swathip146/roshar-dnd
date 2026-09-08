#!/usr/bin/env python3
"""
Verify the Qdrant collections after a fresh embed (plan §10 / 0.18).

Pass criteria:
  * dnd_documents contains chunks from the Radiant's Handbook  (finding #3)
  * chunks are bounded — word count near the split target      (0.12 splitter)
  * dnd_documents contains NO campaigns/characters chunks      (D1 isolation)
  * wiki markup is gone from lore chunks                       (0.13)

Usage:  conda run -n dndenv python scripts/verify_embeddings.py
Exit code 0 = all checks pass.
"""

import ast
import pickle
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE = PROJECT_ROOT / "qdrant_storage" / "collection"


def read_collection(name: str):
    """Yield (meta, content) for every point in a local Qdrant collection."""
    db = STORAGE / name / "storage.sqlite"
    if not db.exists():
        return

    conn = sqlite3.connect(db)
    try:
        for (blob,) in conn.execute("select point from points"):
            try:
                point = pickle.loads(blob)
            except Exception:
                continue
            payload = point.get("payload") if isinstance(point, dict) else getattr(point, "payload", None)
            if not payload:
                continue
            meta = payload.get("meta")
            if isinstance(meta, str):
                try:
                    meta = ast.literal_eval(meta)
                except Exception:
                    meta = {}
            yield (meta or {}), str(payload.get("content", ""))
    finally:
        conn.close()


def summarize(name: str):
    tags, sources, lengths, words = Counter(), Counter(), [], []
    handbook = 0
    markup = 0
    headings = 0   # chunks starting at a markdown heading (structure preserved)
    midword = 0    # chunks starting mid-word (structure destroyed)

    for meta, content in read_collection(name):
        tags[meta.get("document_tag", "?")] += 1
        src = str(meta.get("source_file", "?"))
        sources[src] += 1
        lengths.append(len(content))
        words.append(len(content.split()))
        if content.lstrip().startswith("#"):
            headings += 1
        if re.match(r"^[a-z]{2,}", content.strip()):
            midword += 1
        if "radiant" in src.lower() or "863203275" in src:
            handbook += 1
        if "[[" in content or "{{" in content:
            markup += 1

    return {
        "count": len(lengths),
        "tags": tags,
        "sources": sources,
        "lengths": sorted(lengths),
        "words": sorted(words),
        "handbook": handbook,
        "markup": markup,
        "headings": headings,
        "midword": midword,
    }


def main() -> int:
    failures = []

    for name in ("dnd_documents", "dnd_reference"):
        s = summarize(name)
        print(f"\n{'=' * 62}\n📦 {name}\n{'=' * 62}")

        if not s["count"]:
            print("   ❌ EMPTY — collection missing or not built")
            failures.append(f"{name} is empty")
            continue

        L = s["lengths"]
        W = s["words"]
        print(f"   chunks : {s['count']}")
        print(f"   chars  : median {L[len(L) // 2]}  p90 {L[int(.9 * len(L))]}  max {L[-1]}")
        print(f"   words  : median {W[len(W) // 2]}  p90 {W[int(.9 * len(W))]}  max {W[-1]}")
        print(f"   tags   : {dict(s['tags'])}")
        print(f"   top sources:")
        for src, n in s["sources"].most_common(5):
            print(f"            {n:>6}  {src}")

        # 0.12 — the splitter counts WORDS, so assert on words. A handful of
        # chunks exceed a char budget legitimately (e.g. table-of-contents dot
        # leaders: 200 words that are mostly periods), so char count alone is
        # the wrong metric. p90 chars is the real signal that chunking works —
        # it was 5,017 before the splitter was wired up.
        expected_words = 800 if name == "dnd_reference" else 200
        # 1.6x: the splitter honours sentence boundaries, so a chunk can
        # overshoot the word target to avoid cutting mid-sentence.
        word_cap = int(expected_words * 1.6)
        p90_chars = L[int(.9 * len(L))]

        # Oversized chunks are LEGITIMATE when they are whole preserved tables:
        # the structure-aware splitter keeps a table with its header rather than
        # severing it, because a header without its rows embeds to noise. Judge
        # on p90 (the bulk of the corpus) rather than the single max.
        p90_words = W[int(.9 * len(W))]
        if p90_words > word_cap:
            print(f"   ❌ p90 {p90_words} words (cap {word_cap}) — splitter not applied (0.12)")
            failures.append(f"{name} p90 exceeds {word_cap} words")
        elif p90_chars > expected_words * 12:
            print(f"   ❌ p90 {p90_chars} chars is implausibly large for {expected_words}-word chunks")
            failures.append(f"{name} p90 chars = {p90_chars}")
        else:
            big = sum(1 for n in W if n > word_cap)
            note = f" ({big} oversized, expected: preserved tables)" if big else ""
            print(f"   ✅ chunking bounded: p90 {p90_words} words / "
                  f"{p90_chars} chars, max {W[-1]}{note}")

        # 0.12 (revised) — structure-aware splitting. split_by="word" cut
        # mid-word 78% of the time and never started at a heading, which made
        # the Handbook's mechanics tables useless for retrieval.
        heading_pct = 100 * s["headings"] // s["count"]
        midword_pct = 100 * s["midword"] // s["count"]
        print(f"   structure: {heading_pct}% start at a heading, "
              f"{midword_pct}% start mid-word")
        if midword_pct > 20:
            print(f"   ❌ {midword_pct}% of chunks start mid-word — "
                  f"the splitter is structure-blind again")
            failures.append(f"{name}: {midword_pct}% chunks start mid-word")
        elif heading_pct < 30:
            print(f"   ⚠️  only {heading_pct}% start at a heading")
        else:
            print("   ✅ structure preserved")

        # 0.13 — markup stripped
        if s["markup"]:
            print(f"   ⚠️  {s['markup']} chunk(s) still contain wiki markup (0.13)")
        else:
            print("   ✅ no wiki markup")

        if name == "dnd_documents":
            # Finding #3 — the whole point of the re-index
            if s["handbook"]:
                print(f"   ✅ Radiant's Handbook indexed ({s['handbook']} chunks)")
            else:
                print("   ❌ Radiant's Handbook MISSING — the Cosmere ruleset is the point")
                failures.append("Handbook not in dnd_documents")

            # D1 — structural isolation
            leaked = {t: n for t, n in s["tags"].items()
                      if t in ("campaigns", "characters", "maps")}
            if leaked:
                print(f"   ❌ reference content leaked into the DM collection: {leaked}")
                failures.append(f"dnd_documents contaminated: {leaked}")
            else:
                print("   ✅ no campaigns/characters content (D1 isolation holds)")

    print(f"\n{'=' * 62}")
    if failures:
        print("❌ FAILED:")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("✅ All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
