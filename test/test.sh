#!/bin/sh

NETRANGER_SESSION=netrangertest

rm -rf /tmp/netrangertest*

tmux new-session -d -s $NETRANGER_SESSION
tmux send-keys -t $NETRANGER_SESSION "NVIM_LISTEN_ADDRESS=/tmp/netrangertest nvim" C-m
sleep 1
python3 test.py
tmux send-keys -t $NETRANGER_SESSION :q C-m
tmux kill-session -t $NETRANGER_SESSION
