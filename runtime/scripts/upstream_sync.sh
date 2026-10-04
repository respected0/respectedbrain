#!/bin/bash
set -eu
SCRIPT_DIR=${BASH_SOURCE[0]%/*}
exec bash "$SCRIPT_DIR/../../tools/upstream_sync.sh" "$@"
