import os
import pickle
import shutil
import sys
from pathlib import Path


class FSServerException(Exception):
    pass


def mv(src, dst):
    try:
        shutil.move(src, dst)
    except Exception as e:
        return str(e)
    return ''


def cp(src, dst):
    try:
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, os.path.basename(src)))
        else:
            shutil.copy(src, dst)
    except Exception as e:
        return str(e)
    return ''


def cpas(src, dst):
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)
    except Exception as e:
        return str(e)
    return ''


def rm(src, dst=None):
    try:
        if os.path.isdir(src) and not Path(src).is_symlink():
            shutil.rmtree(src)
        else:
            os.remove(src)
    except Exception as e:
        return str(e)
    return ''


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg_file = sys.argv[2]
    with open(arg_file, 'rb') as f:
        args = pickle.load(f)

    err_msg = []
    fn = locals()[cmd]
    dst = args.get('dst', '')
    for src in args['src']:
        err_msg.append(fn(src, dst))

    err_msg = '\n'.join([e for e in err_msg if e])
    if err_msg:
        raise FSServerException(err_msg)
