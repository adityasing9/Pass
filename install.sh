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
    echo "Python 3 was not found. Attempting to install..."
    if command -v pkg &>/dev/null; then
        pkg update -y && pkg install python python-pip -y
        PY_CMD="python"
    elif command -v apt-get &>/dev/null && [ "$EUID" -eq 0 ]; then
        apt-get update && apt-get install -y python3 python3-pip
        PY_CMD="python3"
    else
        echo "Error: Please install Python 3 (e.g. 'pkg install python python-pip' or 'sudo apt install python3 python3-pip')."
        exit 1
    fi
fi

# Ensure pip is installed
if ! $PY_CMD -m pip --version &>/dev/null; then
    echo "pip is not installed. Bootstrapping pip..."
    $PY_CMD -m ensurepip --upgrade &>/dev/null || $PY_CMD -m ensurepip --default-pip &>/dev/null || true
    
    if ! $PY_CMD -m pip --version &>/dev/null; then
        if command -v pkg &>/dev/null; then
            echo "Installing python-pip via pkg..."
            pkg install python-pip -y
        elif command -v apt-get &>/dev/null; then
            echo "Installing python3-pip..."
            if [ "$EUID" -eq 0 ]; then
                apt-get update && apt-get install -y python3-pip
            else
                sudo apt-get update && sudo apt-get install -y python3-pip
            fi
        fi
    fi
fi

# On Termux, install pre-compiled cryptography binary to avoid compiling from source
if command -v pkg &>/dev/null; then
    echo "Optimizing dependencies for Termux..."
    pkg install python-cryptography -y &>/dev/null || true
fi

echo "Installing PASS directly from GitHub archive (no git clone required)..."
$PY_CMD -m pip install --upgrade --quiet "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip" || \
$PY_CMD -m pip install --upgrade --break-system-packages --quiet "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip"

echo ""
echo "=========================================="
echo "  PASS installed successfully!"
echo "=========================================="
echo "Run 'passx' from any terminal to get started."
echo ""
if command -v passx &>/dev/null; then
    passx version
fi
