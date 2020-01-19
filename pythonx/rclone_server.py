import os
import pickle
import subprocess
import sys
from subprocess import PIPE

import fs_server


class FSServerException(Exception):
    pass


def mv(args, err_msg):
    cp(args, err_msg)
    rm(args, err_msg)


def cp(args, err_msg):
    process = []
    rdst = args['rdst']
    dst = args['dst']
    need_local_cp = dst != rdst

    for rsrc in args['rsrc']:
        p = subprocess.Popen('rclone copyto --tpslimit=10 "{}" "{}"'.format(
            rsrc, os.path.join(rdst, os.path.basename(rsrc))),
                             shell=True,
                             stdout=PIPE,
                             stderr=PIPE)
        process.append(p)

    for src, p in zip(args['src'], process):
        p.wait()
        err = p.stderr.read().decode('utf8')
        if err:
            err_msg.append(err)
        elif need_local_cp:
            err_msg.append(fs_server.cp(src, dst))


def rm(args, err_msg):
    process = []
    for src, rsrc in zip(args['src'], args['rsrc']):
        cmd = 'purge' if os.path.isdir(src) else 'delete'
        p = subprocess.Popen('rclone "{}" "{}"'.format(cmd, rsrc),
                             shell=True,
                             stdout=PIPE,
                             stderr=PIPE)
        process.append(p)

    for src, rsrc, p in zip(args['src'], args['rsrc'], process):
        p.wait()
        err = p.stderr.read().decode('utf8')
        if err:
            err_msg.append(err)
        elif src != rsrc:
            err_msg.append(fs_server.rm(src))


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg_file = sys.argv[2]
    with open(arg_file, 'rb') as f:
        args = pickle.load(f)

    err_msg = []
    fn = locals()[cmd]
    fn(args, err_msg)

    err_msg = '\n'.join([e for e in err_msg if e])
    if err_msg:
        raise FSServerException(err_msg)
