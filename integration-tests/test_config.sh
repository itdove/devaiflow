#!/bin/bash
TEMP_DIR="/tmp/test-config-check-$$"
export DEVAIFLOW_HOME="$TEMP_DIR"
mkdir -p "$DEVAIFLOW_HOME"
daf init > /dev/null 2>&1
python3 configure_test_prompts.py
echo "=== Prompts Configuration ==="
cat "$DEVAIFLOW_HOME/config.json" | python3 -m json.tool | grep -A 20 '"prompts"'
rm -rf "$TEMP_DIR"
