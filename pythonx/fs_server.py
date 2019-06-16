import os
import shutil
import sys


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


def rm(src):
    try:
        if os.path.isdir(src):
            shutil.rmtree(src)
        else:
            os.remove(src)
    except Exception as e:
        return str(e)
    return ''


if __name__ == "__main__":
    cmd = sys.argv[1]
    err_msg = []
    if cmd == 'mv':
        dst = sys.argv[-1]
        for src in sys.argv[2:-1]:
            err_msg.append(mv(src, dst))
    elif cmd == 'cp':
        dst = sys.argv[-1]
        for src in sys.argv[2:-1]:
            err_msg.append(cp(src, dst))
    elif cmd == 'rm':
        for src in sys.argv[2:]:
            err_msg.append(rm(src))
    err_msg = '\n'.join([e for e in err_msg if e])
    if err_msg:
        raise FSServerException(err_msg)
