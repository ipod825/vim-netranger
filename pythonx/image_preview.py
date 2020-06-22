import sys
import time

import ueberzug.lib.v0 as ueberzug

if __name__ == '__main__':
    with ueberzug.Canvas() as c:
        path = sys.argv[1]
        total_width = int(sys.argv[2])
        preview_width = int(sys.argv[3])

        ratio = preview_width / total_width

        beg = (total_width - preview_width) * ratio
        width = preview_width * ratio
        canvas = c.create_placement('',
                                    x=beg,
                                    y=0,
                                    width=width,
                                    scaler=ueberzug.ScalerOption.CONTAIN.value)
        canvas.path = path

        canvas.visibility = ueberzug.Visibility.VISIBLE
        while True:
            time.sleep(3600)
