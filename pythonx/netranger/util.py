import os
import sys


def GenNetRangerScriptCmd(script):
    python = sys.executable
    if os.name == 'nt':
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'..\\{script}.py')
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'../{script}.py')
    return f'{python} {path}'
