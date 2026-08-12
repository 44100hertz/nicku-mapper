#!/usr/bin/env bash
# Persistent raw GDB-protocol session: ONE connection, driven via FIFO.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export RAWLOG="$DIR/raw.log"
rm -f raw_cmd raw.log raw.pid
mkfifo raw_cmd
echo "[$(date +%T)] starting raw client..." > raw.log

nohup python3 -u gdbraw.py repl < raw_cmd >> raw.log 2>&1 &
echo $! > raw.pid

for i in $(seq 1 60); do
  if [ -r raw_cmd ]; then break; fi
  sleep 0.5
done
exec 3>raw_cmd
echo "[$(date +%T)] FIFO open" >> raw.log
wait
