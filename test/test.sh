#!/bin/sh

TMPDIR="${TMPDIR:-/tmp}"
LISTEN_ADDRESS=$TMPDIR/netrangertest
rm -rf $LISTEN_ADDRESS

xterm -e "NVIM_LISTEN_ADDRESS=$LISTEN_ADDRESS nvim -u ./test_init.vim" &
sleep 1
python test.py --listen_address $LISTEN_ADDRESS
