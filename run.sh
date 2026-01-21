#!/bin/bash
# Run Fingerprint App with uv virtual environment

cd "$(dirname "$0")"

# Check if running as root (needed for USB access)
if [ "$EUID" -ne 0 ]; then
    echo "USB access requires root. Re-running with sudo..."
    exec sudo -E "$0" "$@"
fi

# Set library paths for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
fi

# Run with uv
exec uv run python app/main.py "$@"
