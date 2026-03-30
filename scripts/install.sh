#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

INSTALL_DIR="${HOME}/.local/clawteam"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${INSTALL_DIR}/venv"
SYMLINK_FILE="${BIN_DIR}/clawteam"
MCP_SYMLINK="${BIN_DIR}/clawteam-mcp"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RELEASE_VERSION="${1:-}"
RELEASE_URL=""

if [ -n "${RELEASE_VERSION}" ]; then
    RELEASE_URL="https://github.com/re2zero/cliteam/releases/download/${RELEASE_VERSION}/clawteam-${RELEASE_VERSION#v}-py3-none-any.whl"
fi

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       ClawTeam Installer              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

command -v python3 >/dev/null 2>&1 || error "python3 not found. Please install python3 (>=3.10)."

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 10 ]; }; then
    error "Python >= 3.10 required, found ${PY_VERSION}"
fi

if ! python3 -c "import venv" 2>/dev/null; then
    info "Installing python3-venv ..."
    sudo apt-get install -y python3-venv 2>/dev/null || \
        sudo dnf install -y python3-venv 2>/dev/null || \
        error "Failed to install python3-venv. Please install it manually."
fi

mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

if [ -d "${VENV_DIR}" ]; then
    info "Removing old virtual environment ..."
    rm -rf "${VENV_DIR}"
fi

info "Creating virtual environment at ${VENV_DIR} ..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

info "Upgrading pip ..."
pip install --upgrade pip -q

if [ -n "${RELEASE_URL}" ]; then
    info "Installing clawteam ${RELEASE_VERSION} from GitHub Release ..."
    pip install "${RELEASE_URL}"
else
    if [ -f "${REPO_DIR}/pyproject.toml" ]; then
        info "Installing clawteam from source (${REPO_DIR}) ..."
        pip install -e "${REPO_DIR}"
    else
        error "No pyproject.toml found. Run from repo root or specify version: ./install.sh v0.2.1"
    fi
fi

ln -sf "${VENV_DIR}/bin/clawteam" "${SYMLINK_FILE}"
ln -sf "${VENV_DIR}/bin/clawteam-mcp" "${MCP_SYMLINK}" 2>/dev/null || true

deactivate

echo ""

if [ -f "${SYMLINK_FILE}" ]; then
    CLAWTEAM_VERSION=$("${VENV_DIR}/bin/python" -c "import clawteam; print(clawteam.__version__)" 2>/dev/null || echo "unknown")
    info "clawteam ${CLAWTEAM_VERSION} installed successfully!"
    echo ""
    info "Commands available:"
    echo "  clawteam      -> ${SYMLINK_FILE}"
    echo "  clawteam-mcp  -> ${MCP_SYMLINK}"
    echo ""

    case ":${PATH}:" in
        *":${BIN_DIR}:"*)
            info "PATH already includes ${BIN_DIR}, you're good to go."
            ;;
        *)
            warn "Add ${BIN_DIR} to your PATH:"
            echo ""
            echo -e "  ${CYAN}echo 'export PATH=\"${BIN_DIR}:\$PATH\"' >> ~/.bashrc${NC}"
            echo -e "  ${CYAN}source ~/.bashrc${NC}"
            echo ""
            echo "  Or for zsh:"
            echo -e "  ${CYAN}echo 'export PATH=\"${BIN_DIR}:\$PATH\"' >> ~/.zshrc${NC}"
            echo -e "  ${CYAN}source ~/.zshrc${NC}"
            ;;
    esac
else
    error "Installation failed: clawteam command not found."
fi

echo ""
info "Done."
