#!/usr/bin/env bash
# setup_env.sh - bootstrap a Python virtual environment with uv and install project requirements
#
# Usage: ./setup_env.sh [VENV_DIR] [--force]
#        VENV_DIR  Optional virtual environment directory name (default: .venv-${HOSTNAME})
#        --force   Recreate the VENV_DIR directory if it already exists.
#
# Prerequisites:
#   • bash (or compatible shell)
#   • curl or brew (for optional uv installation)
#   • macOS/Linux (adjust paths for Windows if needed)
#
# Notes:
#   • Google Chrome is assumed to already be installed – no Playwright browser installation step is included.
#   • After the script finishes, activate the environment with:
#         source <VENV_DIR>/bin/activate
#
set -euo pipefail

# Parse arguments
VENV_DIR=""
FORCE=""

for arg in "$@"; do
  case $arg in
    --force)
      FORCE="--force"
      ;;
    *)
      if [[ -z "$VENV_DIR" ]]; then
        VENV_DIR="$arg"
      fi
      ;;
  esac
done

# Set default VENV_DIR if not provided
if [[ -z "$VENV_DIR" ]]; then
  VENV_DIR=".venv-${HOSTNAME}"
fi

# -------- Helper functions --------
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$1"; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$1"; }

# -------- Ensure uv --------
if ! command_exists uv; then
  warn "uv not found. Installing..."
  if command_exists brew; then
    brew install uv
  else
    curl -LsSf https://astral.sh/uv/install | sh
  fi
else
  info "uv is already installed."
fi

# -------- Create / recreate venv --------
if [[ -d "$VENV_DIR" ]]; then
  if [[ "$FORCE" == "--force" ]]; then
    warn "Removing existing $VENV_DIR because --force was supplied."
    rm -rf "$VENV_DIR"
  else
    info "$VENV_DIR already exists. Skipping creation — use --force to recreate."
  fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtual environment in $VENV_DIR ..."
  uv venv "$VENV_DIR"
fi

# -------- Install dependencies --------
info "Installing dependencies from requirements.txt ..."
uv pip install --python "$VENV_DIR/bin/python" -r requirements.txt

info "Setup complete. Activate the environment with:"
printf '\n    source %s/bin/activate\n\n' "$VENV_DIR" 