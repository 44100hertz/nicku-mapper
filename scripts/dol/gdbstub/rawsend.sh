#!/usr/bin/env bash
# Send a command to the persistent raw client (FIFO), read the reply from log
DIR="$(cd "$(dirname "$0")" && pwd)"
timeout 5 bash -c "echo \"$*\" > $DIR/raw_cmd" 2>/dev/null
