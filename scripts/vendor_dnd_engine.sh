#!/usr/bin/env bash
#
# vendor_dnd_engine.sh — pin external/dnd_engine reproducibly (plan 4).
#
# THE PROBLEM: external/dnd_engine is an untracked nested git clone. `git
# ls-files external/` returns 0, so a fresh clone of this repo gets NO engine at
# all, and nothing pins the version. The build is not reproducible.
#
# THE COMMIT WE DEPEND ON: 2160564 (2025-08-22, "Merge pull request #8 from
# furlat/eventbus"). Upstream is effectively dormant — 24 stars, one author,
# 129 of 221 commits in May 2025 and one since — so pinning is not a limitation,
# it is the point. See plan §4 for the absorb-and-delete recommendation.
#
# Usage:
#   ./scripts/vendor_dnd_engine.sh          # clone/checkout the pinned commit
#   ./scripts/vendor_dnd_engine.sh --check  # verify what is present
set -uo pipefail

REPO="https://github.com/furlat/dnd_engine.git"
PINNED_COMMIT="2160564fa809210c10d267f4c39c9a447a0f8c40"
TARGET="$(cd "$(dirname "$0")/.." && pwd)/external/dnd_engine"

if [[ "${1:-}" == "--check" ]]; then
  if [[ ! -d "$TARGET/.git" ]]; then
    echo "❌ $TARGET is not a git clone — run without --check to vendor it"
    exit 1
  fi
  actual=$(git -C "$TARGET" rev-parse HEAD)
  if [[ "$actual" == "$PINNED_COMMIT" ]]; then
    echo "✅ dnd_engine at pinned commit ${PINNED_COMMIT:0:7}"
  else
    echo "⚠️  dnd_engine is at ${actual:0:7}, expected ${PINNED_COMMIT:0:7}"
    echo "    Run without --check to reset to the pinned commit."
    exit 1
  fi
  dirty=$(git -C "$TARGET" status --porcelain | wc -l | tr -d ' ')
  [[ "$dirty" == "0" ]] && echo "✅ no local modifications" \
                        || echo "⚠️  $dirty locally modified file(s)"
  exit 0
fi

if [[ -d "$TARGET/.git" ]]; then
  echo "📦 dnd_engine present; resetting to pinned commit..."
  git -C "$TARGET" fetch --quiet origin || echo "⚠️  fetch failed (offline?)"
else
  echo "📦 Cloning dnd_engine..."
  mkdir -p "$(dirname "$TARGET")"
  git clone --quiet "$REPO" "$TARGET" || { echo "❌ clone failed"; exit 1; }
fi

git -C "$TARGET" checkout --quiet "$PINNED_COMMIT" \
  && echo "✅ dnd_engine pinned at ${PINNED_COMMIT:0:7}" \
  || { echo "❌ could not check out $PINNED_COMMIT"; exit 1; }

echo
echo "Note: this engine has 3 ad-hoc example scripts and no test suite for"
echo "~15k LOC. It is covered by OUR tests at the DnDEngineWrapper seam"
echo "(tests/combat/test_real_engine_combat.py). See plan section 4."
