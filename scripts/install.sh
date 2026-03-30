#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

[ -f "${REPO_DIR}/pyproject.toml" ] || error "pyproject.toml not found in ${REPO_DIR}"

PIP_FLAGS=()
if python3 -c "import ensurepip" 2>/dev/null; then
    PIP_FLAGS=(--break-system-packages)
fi

info "Installing clawteam from ${REPO_DIR} ..."
pip3 install -e "${REPO_DIR}" "${PIP_FLAGS[@]}"
info "Installed: $(clawteam --version)"

info "Installing skills ..."

SKILL_SRC_DIRS=(
    "${REPO_DIR}/skills/clawteam"
)

SKILL_TARGETS=(
    "${HOME}/.claude/skills"
    "${HOME}/.config/opencode/skills"
)

for target in "${SKILL_TARGETS[@]}"; do
    mkdir -p "$target"
done

for skill_dir in "${SKILL_SRC_DIRS[@]}"; do
    [ -d "$skill_dir" ] || { warn "Skipping $(basename "$skill_dir") (not found)"; continue; }

    skill_name="$(basename "$skill_dir")"
    for target in "${SKILL_TARGETS[@]}"; do
        dest="${target}/${skill_name}"
        rm -rf "$dest"
        cp -r "$skill_dir" "$dest"
        info "  ${skill_name} -> ${dest}"
    done
done

echo ""
info "Done."
