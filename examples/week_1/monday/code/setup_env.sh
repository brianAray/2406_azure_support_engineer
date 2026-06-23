#!/usr/bin/env bash
# setup_env.sh - Automates system package updates and Python development environment installation.
# Designed for Ubuntu on WSL2.

# Exit immediately if a command exits with a non-zero status,
# treat unset variables as an error, and catch failures in pipelines.
set -euo pipefail

# Define simple text colors for logging (avoiding emojis completely)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;6m' # No Color
NC_BOLD='\033[1m'

log_info() {
    echo -e "[INFO] $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# 1. Verify OS environment (must be Linux/Ubuntu)
log_info "Verifying execution environment..."
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    log_error "This script is designed to run inside Ubuntu/Linux. Current OS: $OSTYPE"
    exit 1
fi

if [ ! -f /etc/debian_version ]; then
    log_warn "This script was built and tested for Debian/Ubuntu distributions. Running on other distros might fail."
fi

# 2. Update local package repository indices
log_info "Updating system package repositories (requires sudo)..."
if ! sudo apt-get update; then
    log_error "Failed to update package repositories. Please check internet connectivity."
    exit 1
fi

# 3. Install Python 3, Pip, and Venv utilities
log_info "Installing Python3, Pip, Virtual Environment tools, and Build Essentials..."
PACKAGES=(
    "python3"
    "python3-pip"
    "python3-venv"
    "build-essential"
)

# Run non-interactive apt-get install
if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"; then
    log_error "Failed to install required packages. Inspect package manager errors."
    exit 1
fi
log_success "Core environment packages installed successfully."

# 4. Set up python virtual environment in user home directory (or current directory)
VENV_DIR="./.wsl_venv"
log_info "Initializing Python virtual environment at ${VENV_DIR}..."

# Clean up existing venv directory if present
if [ -d "$VENV_DIR" ]; then
    log_warn "Existing virtual environment directory '${VENV_DIR}' detected. Recreating..."
    rm -rf "$VENV_DIR"
fi

if ! python3 -m venv "$VENV_DIR"; then
    log_error "Failed to create Python virtual environment."
    exit 1
fi
log_success "Virtual environment initialized."

# 5. Bootstrap and upgrade pip in virtual environment
log_info "Upgrading pip inside virtual environment..."
# Run command inside virtual environment without permanently changing shell state
if ! "$VENV_DIR/bin/pip" install --upgrade pip; then
    log_error "Failed to upgrade pip inside the virtual environment."
    exit 1
fi
log_success "Pip upgraded successfully."

log_success "System environment setup completed successfully."
log_info "To activate the environment manually, run: source $VENV_DIR/bin/activate"
