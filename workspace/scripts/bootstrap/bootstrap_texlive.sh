#!/usr/bin/env bash
set -euo pipefail

# TeXLive Bootstrap Script for AMI-ORCHESTRATOR
# Downloads and installs minimal TeXLive in the .boot-linux environment ONLY
# This script ensures pdflatex and related tools are available without system-wide installation
# FORCE INSTALLS TO .boot-linux - NO FALLBACKS, NO .venv, ONLY .boot-linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

# Use a minimal texlive scheme to keep size reasonable
TEXLIVE_DIR="${VENV_DIR}/texlive"
INSTALLER_DIR="${TEXLIVE_DIR}/installer"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if running on Linux
if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This script only supports Linux. For other platforms, install TeXLive manually."
    exit 1
fi

log_info "Bootstrapping minimal TeXLive for PDF generation"

# Create texlive directory structure
mkdir -p "${INSTALLER_DIR}"

# Download the TeXLive installer
log_info "Downloading TeXLive installer..."
INSTALLER_URL="https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz"
INSTALLER_TARBALL="${INSTALLER_DIR}/install-tl-unx.tar.gz"

if command -v curl ; then
    curl -L -o "${INSTALLER_TARBALL}" "${INSTALLER_URL}"
elif command -v wget ; then
    wget -O "${INSTALLER_TARBALL}" "${INSTALLER_URL}"
else
    log_error "Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Extract the installer
log_info "Extracting TeXLive installer..."
cd "${INSTALLER_DIR}"
tar -xzf "${INSTALLER_TARBALL}"

# Find the installer directory (it has a date in the name)
INSTALLER_SUBDIR=$(find . -maxdepth 1 -type d -name "install-tl-*" 2>&1)
INSTALLER_SUBDIR="${INSTALLER_SUBDIR%%$'\n'*}"

if [[ -z "${INSTALLER_SUBDIR}" ]]; then
    log_error "Could not find installer directory"
    exit 1
fi

cd "${INSTALLER_SUBDIR}"

# Create a profile file for automated installation
mkdir -p "${TEXLIVE_DIR}/texmf"
cat > texlive.profile << EOF
selected_scheme scheme-minimal
TEXDIR ${TEXLIVE_DIR}/texmf
TEXMFCONFIG ${TEXLIVE_DIR}/texmf-config
TEXMFVAR ${TEXLIVE_DIR}/texmf-var
TEXMFHOME ${TEXLIVE_DIR}/texmf-home
TEXMFLOCAL ${TEXLIVE_DIR}/texmf-local
option_doc 0
option_src 0
binary_x86_64-linux 1
instopt_adjustpath 0
instopt_letter 0
tlpdbopt_autobackup 0
EOF

# Run the installer with environment variables to avoid system directories
export TEXLIVE_INSTALL_PREFIX="${TEXLIVE_DIR}"
export TEXDIR="${TEXLIVE_DIR}/texmf"
export TEXMFCONFIG="${TEXLIVE_DIR}/texmf-config"
export TEXMFVAR="${TEXLIVE_DIR}/texmf-var"
export TEXMFHOME="${TEXLIVE_DIR}/texmf-home"
export TEXMFLOCAL="${TEXLIVE_DIR}/texmf-local"

log_info "Installing minimal TeXLive (this may take several minutes)..."
./install-tl --profile=texlive.profile --no-gui --texdir="${TEXLIVE_DIR}/texmf"

# Install additional packages needed for PDF generation
BINARY_BASE_DIR="${TEXLIVE_DIR}/texmf/bin"
# Find tlmgr binary
TLMGR=""
for arch in x86_64-linux aarch64-linux; do
    if [[ -f "${BINARY_BASE_DIR}/${arch}/tlmgr" ]]; then
        TLMGR="${BINARY_BASE_DIR}/${arch}/tlmgr"
        break
    fi
done
if [[ -z "${TLMGR}" ]]; then
    for arch_dir in "${BINARY_BASE_DIR}"/*; do
        if [[ -d "$arch_dir" && -f "$arch_dir/tlmgr" ]]; then
            TLMGR="$arch_dir/tlmgr"
            break
        fi
    done
fi

if [[ -z "${TLMGR}" ]]; then
    log_error "Could not find tlmgr binary"
    exit 1
fi

log_info "Using tlmgr: ${TLMGR}"

# Track tlmgr block failures. Previously every block had its exit
# code masked unconditionally, so legit failures (network drop,
# sealed mirror, disk full) and stale package names alike disappeared
# from the bootstrap return code. The 8 stale-name errors in tom@
# tomohawkyo's install-20260505-162919.log went unnoticed for the
# same reason. Capture each block's rc, keep going so a single typo
# doesn't take out the whole TeX install, and report loud at the
# end so the operator (and the install log) sees what broke.
tlmgr_failures=()

run_tlmgr_block() {
    local label="$1"
    shift
    log_info "Installing ${label}..."
    if ! "${TLMGR}" install "$@"; then
        tlmgr_failures+=("${label}")
    fi
}

# --- Collections (broad package groups) ---
run_tlmgr_block "TeX collections" \
    collection-latex \
    collection-latexrecommended \
    collection-latexextra \
    collection-fontsrecommended \
    collection-mathscience

# --- Core engines and tools ---
run_tlmgr_block "TeX engines and tools" \
    latex-bin \
    xetex \
    luatex

# --- Fonts (needed for xelatex / pandoc output) ---
# Removed package names that CTAN no longer ships standalone (these
# triggered the "package not present in repository" spam in Tom's
# log without breaking anything functional):
#   - freefont       -> use gnu-freefont (kept below)
#   - sourcesanspro  -> rolled into source-pro / no standalone any more
#   - sourceserifpro -> ditto
run_tlmgr_block "fonts" \
    fontspec \
    unicode-math \
    montserrat \
    lato \
    noto \
    roboto \
    sourcecodepro \
    libertinus \
    libertinus-fonts \
    libertinus-otf \
    fira \
    firamath \
    firamath-otf \
    inter \
    cabin \
    opensans \
    raleway \
    inconsolata \
    dejavu \
    gnu-freefont \
    ec \
    cm-unicode \
    lm \
    lm-math

# --- Pandoc / document conversion essentials ---
# These packages are required by pandoc's default LaTeX template
# and commonly needed when converting markdown to PDF/DOCX.
# Removed:
#   - footnote  (does not exist as a standalone package; footmisc
#     covers the typical use case and is already in the list)
#   - longtable (ships with the `tools` collection / package, also
#     in the list as `tools`)
run_tlmgr_block "pandoc/document conversion packages" \
    amsmath \
    amscls \
    amsfonts \
    babel \
    babel-english \
    biblatex \
    biber \
    bookmark \
    booktabs \
    caption \
    csquotes \
    enumitem \
    etoolbox \
    fancyhdr \
    fancyvrb \
    float \
    footmisc \
    framed \
    geometry \
    grffile \
    hyperref \
    iftex \
    kvoptions \
    listings \
    mdframed \
    microtype \
    multirow \
    natbib \
    needspace \
    oberdiek \
    parskip \
    pgf \
    setspace \
    soul \
    subfig \
    subfigure \
    tcolorbox \
    textpos \
    titlesec \
    titling \
    tocloft \
    tools \
    trimspaces \
    ulem \
    upquote \
    url \
    xcolor \
    xkeyval \
    xurl

# --- Tables and lists ---
# Removed:
#   - array, tabularx (both ship with the `tools` package, already
#     pulled in by the pandoc/document block above)
run_tlmgr_block "table and list packages" \
    colortbl \
    ctable \
    makecell \
    multirow \
    tabulary \
    tabu \
    threeparttable \
    wrapfig \
    adjustbox

# --- Graphics and images ---
# Removed:
#   - graphicx (ships inside the `graphics` package, kept below)
run_tlmgr_block "graphics packages" \
    graphics \
    svg \
    svg-inkscape \
    epstopdf \
    epstopdf-pkg \
    pdflscape \
    pdfpages \
    tikz-cd \
    tikzfill

# --- Math and science ---
run_tlmgr_block "math/science packages" \
    mathtools \
    unicode-math \
    siunitx \
    physics \
    chemformula \
    mhchem \
    algorithms \
    algorithmicx \
    algorithm2e

# --- Code listings and verbatim ---
run_tlmgr_block "code/verbatim packages" \
    minted \
    fvextra \
    lineno

# --- Page layout and headers ---
run_tlmgr_block "layout packages" \
    lastpage \
    wallpaper \
    background \
    everypage \
    changepage

# --- Misc commonly needed ---
run_tlmgr_block "miscellaneous packages" \
    catchfile \
    environ \
    import \
    letltxmacro \
    luacode \
    pdftexcmds \
    selnolig \
    stringenc \
    unicode-data \
    xifthen \
    xindy \
    zref

log_info "Package installation complete"

# Create symlinks in venv/bin for the necessary binaries
log_info "Creating symlinks in ${VENV_DIR}/bin"

# Find the binary directory (it may vary by architecture)
BINARY_DIR=""
for dir in "${TEXLIVE_DIR}/texmf/bin/"*; do
    if [[ -d "$dir" && -f "$dir/pdflatex" ]]; then
        BINARY_DIR="$dir"
        break
    fi
done

if [[ -z "${BINARY_DIR}" ]]; then
    log_error "Could not find TeXLive binary directory with pdflatex"
    exit 1
fi

log_info "Found binaries in: ${BINARY_DIR}"

# Create symlinks for essential PDF generation and TeX tools
for binary in pdflatex xelatex lualatex latex kpsewhich mktexlsr \
              bibtex dvips makeindex tex luatex luahbtex \
              afm2tfm dvipdft gftodvi gftopk gftype mf mf-nowin mft \
              mkindex mkocp mkofm pktogf pktype teckit_compile xdvi xdvipdfmx xetex; do
    if [[ -f "${BINARY_DIR}/${binary}" ]]; then
        ln -sf "${BINARY_DIR}/${binary}" "${VENV_DIR}/bin/${binary}"
        log_info "Created symlink for ${binary}"
    fi
done

# Set up environment for TeXLive
export PATH="${BINARY_DIR}:${PATH}"
export TEXMFCNF="${TEXLIVE_DIR}/texmf/texmf.cnf"

# Verify installation
log_info "Verifying pdflatex installation"
if "${VENV_DIR}/bin/pdflatex" --version; then
    log_info "pdflatex installed successfully:"
    _pdflatexver="$("${VENV_DIR}/bin/pdflatex" --version 2>&1)"
    _pdflatexver="${_pdflatexver%%$'\n'*}"
    echo "  ${_pdflatexver}"
else
    log_error "pdflatex installation verification failed"
    exit 1
fi

# If any tlmgr block returned non-zero, fail the bootstrap loud here.
# pdflatex itself works (verified above) so the parent installer can
# decide to accept partial success via detect_path / version_cmd, but
# the upstream caller and the install log still see a clear signal -
# previously each tlmgr exit was masked outright and broken package
# names piled up across releases without anyone noticing.
if (( ${#tlmgr_failures[@]} > 0 )); then
    log_error "tlmgr returned non-zero for these blocks: ${tlmgr_failures[*]}"
    log_error "  Inspect ${TEXLIVE_DIR}/texmf/texmf-var/web2c/tlmgr.log"
    log_error "  pdflatex/xelatex are present and runnable; missing"
    log_error "  packages can be installed individually via:"
    log_error "    ${TLMGR} install <pkg-name>"
    exit 1
fi

# Clean up installer
rm -rf "${INSTALLER_DIR}"

log_info "TeXLive bootstrap complete!"
log_info "Installed components:"
log_info "  - pdflatex"
log_info "  - xelatex"
log_info "  - lualatex"
log_info "  - latex"
log_info "  - Binary: ${VENV_DIR}/bin/[engine-name]"
log_info ""
log_info "To use TeXLive PDF engines:"
    log_info "  1. Run: run pdflatex [args] (Engines auto-available)"
log_info "  2. Or use scripts directly that need PDF engines"
