#!/usr/bin/env bash
# PASS (passx) Linux & Android Termux One-Line Installer
set -e

echo "=========================================="
echo "  Installing PASS (passx)..."
echo "=========================================="

# Find python
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "Error: Python 3 was not found."
    echo "Please install Python 3 (e.g. 'sudo apt install python3 python3-pip' or 'pkg install python')."
    exit 1
fi

echo "Installing PASS directly from GitHub archive (no git clone required)..."
$PY_CMD -m pip install --upgrade --quiet "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip" || \
$PY_CMD -m pip install --upgrade --break-system-packages --quiet "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip"

echo ""
echo "PASS installed successfully!"
echo "Run 'passx' from any terminal to get started."
if command -v passx &>/dev/null; then
    passx version
fi
