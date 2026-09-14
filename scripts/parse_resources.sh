#!/usr/bin/env bash
#
# parse_resources.sh — Parse every document in resources/ into parsed_data/
# using the pkgwiki-parse parser (Docling-based, with table/asset extraction).
#
# Plan reference: docs/REBUILD_PLAN_V5.md
#   Runs AFTER  0.12-0.15 (chunker/markup/metadata/filter fixes)
#   Runs BEFORE 2.9-2.10  (Stormlight rules JSON authoring)
#   Feeds       0.18      (fresh embed into Qdrant)
#
# Output layout, one slug dir per source document:
#   parsed_data/<slug>/docling.md    <- markdown text (what gets embedded)
#   parsed_data/<slug>/tagged.md     <- markdown with structure tags
#   parsed_data/<slug>/meta.json     <- parser metadata
#   parsed_data/<slug>/assets/       <- extracted images/tables
#   parsed_data/<slug>/source.json   <- provenance we add (original path + tags)
#
# Usage:
#   ./scripts/parse_resources.sh                 # parse everything (skips done)
#   ./scripts/parse_resources.sh --force         # re-parse even if output exists
#   ./scripts/parse_resources.sh --captioning    # enable VLM captioning (needs an LLM endpoint)
#   ./scripts/parse_resources.sh --only rules    # only resources/rules/**
#   ./scripts/parse_resources.sh --dry-run       # list what would be parsed
#   ./scripts/parse_resources.sh -j 4            # 4 parallel workers
#
set -uo pipefail

PROJECT_ROOT="/Users/scj/Documents/Projects/AI/DnD_new/roshar-dnd/roshar-dnd"
RESOURCES="${PROJECT_ROOT}/resources"
OUT_ROOT="${PROJECT_ROOT}/parsed_data"
PARSER_PROJECT="/Users/scj/Documents/Projects/AI/pkg-wiki-cli"
LOG_DIR="${PROJECT_ROOT}/logs"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/parse_resources_${STAMP}.log"

FORCE=0
CAPTIONING=0
DRY_RUN=0
JOBS=1
ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)      FORCE=1; shift ;;
    --captioning) CAPTIONING=1; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --only)       ONLY="${2:-}"; shift 2 ;;
    -j|--jobs)    JOBS="${2:-1}"; shift 2 ;;
    -h|--help)    sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

mkdir -p "$LOG_DIR" "$OUT_ROOT"

# Docling downloads its layout/table models from HuggingFace on first use, which
# the sandbox proxy blocks (403 Forbidden -> every PDF fails). The models are
# already cached locally, so force offline resolution against that cache.
# Verified: without these, PDFs fail; with them, they parse.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

# Dual output: console + log file (mirrors config/logging_config.py convention)
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"; }

log "============================================================"
log "📚 Parsing resources → parsed_data"
log "   source : ${RESOURCES}${ONLY:+/$ONLY}"
log "   output : ${OUT_ROOT}"
log "   parser : pkgwiki-parse (${PARSER_PROJECT})"
log "   force=${FORCE} captioning=${CAPTIONING} jobs=${JOBS} dry_run=${DRY_RUN}"
log "   log    : ${LOG_FILE}"
log "============================================================"

# --- preflight ---------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  log "❌ 'uv' not found on PATH. Install uv or add it to PATH."; exit 1
fi
if [[ ! -d "$RESOURCES" ]]; then
  log "❌ Resources dir not found: $RESOURCES"; exit 1
fi
if [[ ! -d "$PARSER_PROJECT" ]]; then
  log "❌ Parser project not found: $PARSER_PROJECT"; exit 1
fi
if [[ $DRY_RUN -eq 0 ]]; then
  log "🔎 Checking parser is runnable..."
  if ! uv run --project "$PARSER_PROJECT" pkgwiki-parse --help >/dev/null 2>&1; then
    log "❌ 'pkgwiki-parse' failed to launch. Try:"
    log "     uv run --project $PARSER_PROJECT pkgwiki-parse --help"
    exit 1
  fi
  log "✅ Parser OK"
fi

# --- collect files -----------------------------------------------------------
SEARCH_ROOT="$RESOURCES"
[[ -n "$ONLY" ]] && SEARCH_ROOT="${RESOURCES}/${ONLY}"
if [[ ! -d "$SEARCH_ROOT" ]]; then
  log "❌ --only path not found: $SEARCH_ROOT"; exit 1
fi

FILE_LIST="$(mktemp)"
trap 'rm -f "$FILE_LIST"' EXIT
# Parser-supported types. .textClipping/.DS_Store deliberately excluded.
find "$SEARCH_ROOT" -type f \
  \( -iname '*.pdf'  -o -iname '*.pptx' -o -iname '*.docx' \
  -o -iname '*.xlsx' -o -iname '*.key'  -o -iname '*.json' \
  -o -iname '*.md'   -o -iname '*.txt' \) \
  ! -name '.*' | sort > "$FILE_LIST"

TOTAL=$(wc -l < "$FILE_LIST" | tr -d ' ')
log "📄 Found ${TOTAL} parseable file(s)"
if [[ "$TOTAL" -eq 0 ]]; then log "⚠️  Nothing to do."; exit 0; fi

# --- slug helper: mirror the parser's naming so we can detect prior runs ------
slugify() {
  basename "$1" | sed 's/\.[^.]*$//' \
    | tr '[:upper:]' '[:lower:]' \
    | sed -e 's/[^a-z0-9]\+/-/g' -e 's/^-//' -e 's/-$//'
}

# --- worker ------------------------------------------------------------------
parse_one() {
  local src="$1" idx="$2" total="$3"
  local rel slug out tag_dir
  rel="${src#"$RESOURCES"/}"
  slug="$(slugify "$src")"
  out="${OUT_ROOT}/${slug}"
  # folder_tags: the resources/ subdirectory chain (rules, lore, campaigns, ...)
  tag_dir="$(dirname "$rel")"; [[ "$tag_dir" == "." ]] && tag_dir="root"

  if [[ -f "${out}/docling.md" && $FORCE -eq 0 ]]; then
    log "[${idx}/${total}] ⏭  skip (exists): ${rel}"
    return 0
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "[${idx}/${total}] 🔍 would parse: ${rel} → parsed_data/${slug}/"
    return 0
  fi

  log "[${idx}/${total}] ⚙️  ${rel}  [tags: ${tag_dir}]"
  local args=(--output-dir "$out")
  [[ $CAPTIONING -eq 1 ]] && args+=(--captioning)

  local start; start=$(date +%s)
  if uv run --project "$PARSER_PROJECT" pkgwiki-parse "$src" "${args[@]}" >>"$LOG_FILE" 2>&1; then
    local dur=$(( $(date +%s) - start ))
    if [[ -f "${out}/docling.md" ]]; then
      local chars; chars=$(wc -c < "${out}/docling.md" | tr -d ' ')
      # Provenance sidecar — carries folder tags through to the embedder so
      # document_tag/source_file metadata survives (plan items 0.14, 0.15).
      cat > "${out}/source.json" <<JSON
{
  "source_file": "$(basename "$src")",
  "source_path": "${rel}",
  "folder_tags": ["${tag_dir//\//\", \"}"],
  "document_tag": "$(echo "$tag_dir" | cut -d/ -f1)",
  "parsed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "parser": "pkgwiki-parse"
}
JSON
      log "[${idx}/${total}] ✅ ${slug} (${chars} chars, ${dur}s)"
    else
      log "[${idx}/${total}] ⚠️  ${slug}: exited 0 but no docling.md — check log"
      return 1
    fi
  else
    log "[${idx}/${total}] ❌ FAILED: ${rel} (see ${LOG_FILE})"
    return 1
  fi
}
export -f parse_one slugify log
export RESOURCES OUT_ROOT PARSER_PROJECT LOG_FILE FORCE CAPTIONING DRY_RUN
export HF_HUB_OFFLINE TRANSFORMERS_OFFLINE HF_HOME

# --- run ---------------------------------------------------------------------
RUN_START=$(date +%s)
FAILED=0

if [[ "$JOBS" -gt 1 ]]; then
  log "🚀 Parsing with ${JOBS} parallel workers..."
  i=0
  while IFS= read -r f; do
    i=$((i+1))
    while [[ "$(jobs -rp | wc -l)" -ge "$JOBS" ]]; do wait -n 2>/dev/null || sleep 0.3; done
    parse_one "$f" "$i" "$TOTAL" &
  done < "$FILE_LIST"
  wait
else
  i=0
  while IFS= read -r f; do
    i=$((i+1))
    parse_one "$f" "$i" "$TOTAL" || FAILED=$((FAILED+1))
  done < "$FILE_LIST"
fi

# --- summary -----------------------------------------------------------------
ELAPSED=$(( $(date +%s) - RUN_START ))
PARSED=$(find "$OUT_ROOT" -name docling.md -type f 2>/dev/null | wc -l | tr -d ' ')

log "============================================================"
log "🏁 Done in ${ELAPSED}s"
log "   slug dirs with docling.md : ${PARSED}"
log "   source files considered   : ${TOTAL}"
[[ "$FAILED" -gt 0 ]] && log "   ⚠️  failures this run     : ${FAILED}"
log "   log: ${LOG_FILE}"

# Loud check for the file that motivated this whole exercise (plan finding #3)
HANDBOOK=$(find "$OUT_ROOT" -maxdepth 1 -type d \
  \( -iname '*radiant*' -o -iname '*863203275*' \) 2>/dev/null | head -1)
if [[ -n "$HANDBOOK" && -f "${HANDBOOK}/docling.md" ]]; then
  log "   ✅ Radiant's Handbook parsed: $(basename "$HANDBOOK") ($(wc -c < "${HANDBOOK}/docling.md" | tr -d ' ') chars)"
else
  log "   ❌ Radiant's Handbook NOT parsed — the Cosmere ruleset is the point of this run."
fi

log ""
log "Next: embed into Qdrant (plan 0.18). Back up first — the clear is irreversible:"
log "   cp -r qdrant_storage qdrant_storage.bak"
log "   conda run -n dndenv python generators/batch_qdrant_indexer.py"
log "   (root folder: parsed_data | collection: dnd_documents | clear existing: y)"
log "⚠️  Ensure DocumentSplitter is wired up first (plan 0.12) or chunks stay unbounded."
log "============================================================"

[[ "$FAILED" -gt 0 ]] && exit 1
exit 0
