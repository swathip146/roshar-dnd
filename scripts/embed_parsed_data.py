#!/usr/bin/env python3
"""
Embed parsed_data/ into Qdrant — two collections (plan D1).

Reads the markdown produced by scripts/parse_resources.sh and writes embeddings
to two separate collections, because the DM and the campaign generator have
opposite needs:

  dnd_documents  <- rules/ + lore/ + current_campaign/   (DM at play)
                    small precise chunks (~200 words)
  dnd_reference  <- campaigns/ + characters/             (campaign generator)
                    large arc-sized chunks (~800 words)

Separate collections rather than payload filters: cross-contamination becomes
structurally impossible instead of depending on every query path remembering to
filter (and the current filter implementation is a silent no-op — plan 0.15).

Plan items: 0.12 (splitter), 0.13 (markup), 0.14 (metadata), 0.18 (fresh embed).

Usage:
    conda run -n dndenv python scripts/embed_parsed_data.py            # both
    conda run -n dndenv python scripts/embed_parsed_data.py --dry-run  # counts only
    conda run -n dndenv python scripts/embed_parsed_data.py --only dnd_documents
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Docling/HF model downloads are proxy-blocked; use the local cache.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from haystack import Document  # noqa: E402

from config.logging_config import get_logger  # noqa: E402
from generators.batch_qdrant_indexer import (  # noqa: E402
    clean_wiki_markup,
    setup_qdrant_store,
    store_in_qdrant,
)

logger = get_logger(__name__)

PARSED_DATA = PROJECT_ROOT / "parsed_data"

# document_tag -> collection. Tags come from the resources/ subdirectory and are
# recorded in each slug dir's source.json by parse_resources.sh.
COLLECTIONS = {
    "dnd_documents": {
        "tags": {"rules", "lore", "current_campaign"},
        "split_length": 200,
        "split_overlap": 30,
        "purpose": "DM at play — small precise chunks",
    },
    "dnd_reference": {
        "tags": {"campaigns", "characters", "maps"},
        "split_length": 800,
        "split_overlap": 80,
        "purpose": "campaign generator — large arc-sized chunks",
    },
}


def load_parsed_documents():
    """Yield (document_tag, Document) for every parsed slug dir."""
    if not PARSED_DATA.exists():
        logger.error(f"❌ {PARSED_DATA} not found — run scripts/parse_resources.sh first")
        return

    for slug_dir in sorted(PARSED_DATA.iterdir()):
        if not slug_dir.is_dir():
            continue

        md = slug_dir / "docling.md"
        if not md.exists():
            logger.warning(f"⚠️  {slug_dir.name}: no docling.md, skipping")
            continue

        # Provenance sidecar written by parse_resources.sh (plan 0.14)
        meta = {"source_file": slug_dir.name, "document_tag": "unknown"}
        sidecar = slug_dir / "source.json"
        if sidecar.exists():
            try:
                meta.update(json.loads(sidecar.read_text()))
            except Exception as e:
                logger.warning(f"⚠️  {slug_dir.name}: bad source.json ({e})")

        try:
            content = md.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️  {slug_dir.name}: unreadable ({e})")
            continue

        if not content.strip():
            logger.warning(f"⚠️  {slug_dir.name}: empty, skipping")
            continue

        meta.setdefault("slug", slug_dir.name)
        yield meta.get("document_tag", "unknown"), Document(content=content, meta=meta)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report routing, embed nothing")
    ap.add_argument("--only", choices=sorted(COLLECTIONS), help="build one collection")
    ap.add_argument("--keep-existing", action="store_true",
                    help="append instead of clearing (default clears for a fresh embed)")
    args = ap.parse_args()

    targets = [args.only] if args.only else list(COLLECTIONS)

    # Route every parsed document to its collection
    buckets = {name: [] for name in COLLECTIONS}
    unrouted = []
    for tag, doc in load_parsed_documents():
        for name, cfg in COLLECTIONS.items():
            if tag in cfg["tags"]:
                buckets[name].append(doc)
                break
        else:
            unrouted.append((tag, doc.meta.get("slug")))

    logger.info("=" * 66)
    logger.info("📊 Routing plan (D1: two collections)")
    for name, cfg in COLLECTIONS.items():
        logger.info(f"   {name:<15} {len(buckets[name]):>4} docs  "
                    f"split={cfg['split_length']}w  — {cfg['purpose']}")
    if unrouted:
        logger.warning(f"   ⚠️  {len(unrouted)} document(s) matched no collection:")
        for tag, slug in unrouted[:10]:
            logger.warning(f"        tag={tag!r} slug={slug}")
    logger.info("=" * 66)

    if args.dry_run:
        logger.info("🔍 Dry run — nothing embedded.")
        return 0

    failures = 0
    for name in targets:
        docs = buckets[name]
        if not docs:
            logger.warning(f"⚠️  {name}: no documents, skipping")
            continue

        cfg = COLLECTIONS[name]
        logger.info(f"\n🚀 Building {name} ({len(docs)} docs)...")
        try:
            store = setup_qdrant_store(
                collection_name=name,
                embedding_dim=1024,
                storage_path=str(PROJECT_ROOT / "qdrant_storage"),
                clear_existing=not args.keep_existing,
            )
            store_in_qdrant(
                docs, store,
                split_length=cfg["split_length"],
                split_overlap=cfg["split_overlap"],
            )
            logger.info(f"✅ {name} complete")
        except Exception as e:
            # Local Qdrant permits only one client per storage folder, so a
            # second collection in the same process hits a lock. Release the
            # first store and retry once.
            if "already accessed by another instance" in str(e):
                logger.warning(f"⚠️  {name}: Qdrant lock held; releasing and retrying")
                try:
                    del store
                except Exception:
                    pass
                import gc
                gc.collect()
                try:
                    store = setup_qdrant_store(
                        collection_name=name,
                        embedding_dim=1024,
                        storage_path=str(PROJECT_ROOT / "qdrant_storage"),
                        clear_existing=not args.keep_existing,
                    )
                    store_in_qdrant(
                        docs, store,
                        split_length=cfg["split_length"],
                        split_overlap=cfg["split_overlap"],
                    )
                    logger.info(f"✅ {name} complete (after retry)")
                    continue
                except Exception as retry_error:
                    logger.error(
                        f"❌ {name} failed after retry: {retry_error}\n"
                        f"   Workaround: run one collection per process —\n"
                        f"   python scripts/embed_parsed_data.py --only {name}"
                    )
                    failures += 1
                    continue
            logger.error(f"❌ {name} failed: {e}")
            failures += 1

    logger.info("\nVerify with: python scripts/verify_embeddings.py")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
