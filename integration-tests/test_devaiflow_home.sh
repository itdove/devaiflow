#!/bin/bash
TEMP_DIR="/tmp/test-devaiflow-home-$$"
export DEVAIFLOW_HOME="$TEMP_DIR"
mkdir -p "$DEVAIFLOW_HOME"
echo "=== Testing daf init with DEVAIFLOW_HOME ==="
echo "DEVAIFLOW_HOME=$DEVAIFLOW_HOME"
echo ""
daf init 2>&1 | head -10
echo ""
echo "=== Checking if config was created ==="
if [ -f "$DEVAIFLOW_HOME/config.json" ]; then
    echo "✓ config.json created at $DEVAIFLOW_HOME/config.json"
else
    echo "✗ config.json NOT created"
    ls -la "$DEVAIFLOW_HOME/"
fi
rm -rf "$TEMP_DIR"
