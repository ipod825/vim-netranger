#!/bin/sh

TMPDIR="${TMPDIR:-/tmp}"
rm -rf $TMPDIR/netrangertest*

NVIM_LISTEN_ADDRESS=$TMPDIR/netrangertest nvim --headless 2> /dev/null &
NVIM_PID=$!
python3 test.py
kill $NVIM_PID

