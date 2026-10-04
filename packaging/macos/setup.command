#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
package="$script_dir/RespectedBrain.app"
: "${HOME:?HOME is required}"
: "${RESPECTED_APP_DIR:=$HOME/Applications/RespectedBrain.app}"
export RESPECTED_APP_DIR
exec "$package/Contents/MacOS/respectedbrain" setup --platform posix --package "$package" "$@"
