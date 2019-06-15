import os
import shutil
import sys


class FSServerException(Exception):
    pass


if __name__ == "__main__":
    cmd = sys.argv[1]
    err_msg = ''
    if cmd == 'mv':
        dst = sys.argv[-1]
        for src in sys.argv[2:-1]:
            try:
                shutil.move(src, dst)
            except Exception as e:
                err_msg += str(e) + '\n'
    elif cmd == 'cp':
        dst = sys.argv[-1]
        for src in sys.argv[2:-1]:
            try:
                if os.path.isdir(src):
                    shutil.copytree(src,
                                    os.path.join(dst, os.path.basename(src)))
                else:
                    shutil.copy(src, dst)
            except Exception as e:
                err_msg += str(e) + '\n'
    elif cmd == 'rm':
        for f in sys.argv[2:]:
            try:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)
            except Exception as e:
                err_msg += str(e) + '\n'
    if err_msg:
        raise FSServerException(err_msg)
