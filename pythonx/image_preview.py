import glob
import itertools
import os
import sys
import time

import ueberzug.lib.v0 as ueberzug

if __name__ == '__main__':
    with ueberzug.Canvas() as c:
        path = sys.argv[1]
        total_width = int(sys.argv[2])
        preview_width = int(sys.argv[3])

        beg = (total_width - preview_width)
        width = preview_width
        canvas = c.create_placement('',
                                    x=beg,
                                    y=0,
                                    width=width,
                                    scaler=ueberzug.ScalerOption.CONTAIN.value)
        if os.path.isdir(path):
            for i in itertools.cycle(sorted(glob.glob(f'{path}/*'))):
                canvas.path = i
                canvas.visibility = ueberzug.Visibility.VISIBLE
                time.sleep(0.2)
        else:
            canvas.path = path
            canvas.visibility = ueberzug.Visibility.VISIBLE
            while True:
                time.sleep(3600)
