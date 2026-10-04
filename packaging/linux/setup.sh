#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
package="$script_dir/RespectedBrain"
: "${HOME:?HOME is required}"
: "${RESPECTED_APP_DIR:=$HOME/.local/lib/respectedbrain}"
export RESPECTED_APP_DIR
exec "$package/respectedbrain" setup --platform posix --package "$package" "$@"
