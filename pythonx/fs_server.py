import os
import shutil
import sys


class FSServerException(Exception):
    pass


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == 'mv':
        pass
    elif cmd == 'cp':
        pass
    elif cmd == 'rm':
        err_msg = ''
        for f in sys.argv[2:]:
            try:
                if os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    os.remove(f)
            except Exception as e:
                err_msg += str(e) + '\n'
        if err_msg:
            raise FSServerException(err_msg)
