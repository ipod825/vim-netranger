#!/bin/sh

NETRANGER_SESSION=netrangertest

rm -rf $TMPDIR/netrangertest*

tmux kill-session -t $NETRANGER_SESSION
tmux new-session -d -t $NETRANGER_SESSION
tmux send-keys -t $NETRANGER_SESSION "NVIM_LISTEN_ADDRESS=$TMPDIR/netrangertest nvim" C-m
sleep 1
python3 test.py &&  tmux send-keys -t $NETRANGER_SESSION :q C-m && tmux kill-session -t $NETRANGER_SESSION
