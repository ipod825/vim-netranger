import re
import tempfile
from pathlib import Path

from netranger import Vim, util
from netranger.shell import Shell
from netranger.thirdparty.pymagic import magic


class view(object):
    def __init__(self):
        self.tempfile_cache = {}

    def __call__(self, path, total_width, preview_width):
        self.path = path
        self.total_width = total_width
        self.preview_width = preview_width
        self.preview_close_on_tableave = False

        try:
            self.mime_type = magic.from_file(path).lower()
        except Exception:
            self.mime_type = ''
        if re.search('image', self.mime_type):
            self.view_image()
            self.preview_close_on_tableave = True
        elif re.search('pdf', self.mime_type):
            self.view_pdf()
            self.preview_close_on_tableave = True
        elif re.search('text|data$|empty', self.mime_type):
            self.view_plaintext()
        else:
            self.view_mime()

        return self.preview_close_on_tableave

    def view_plaintext(self):
        bak_shortmess = Vim.options['shortmess']
        Vim.options['shortmess'] = 'A'
        Vim.command(f'silent edit {self.path}')
        Vim.options['shortmess'] = bak_shortmess
        Vim.current.window.options['foldenable'] = False

    def view_mime(self):
        Vim.command('setlocal buftype=nofile')
        Vim.command('setlocal noswapfile')
        Vim.command('setlocal nobuflisted')
        Vim.command('setlocal bufhidden=wipe')
        Vim.current.buffer[:] = [self.path, self.mime_type]
        Vim.command('setlocal nomodifiable')

    def view_image(self):
        try:
            Vim.AsyncRun(f'{util.GenNetRangerScriptCmd("image_preview")}\
                            {self.path} {self.total_width} {self.preview_width}',
                         term=True,
                         termopencmd='')
            Vim.command('setlocal nocursorline')
        except Exception:
            self.view_mime()

    def view_pdf(self):
        if not Shell.isinPATH('pdftoppm'):
            self.view_mime()
        else:
            if self.path not in self.tempfile_cache:
                fname = tempfile.mkstemp()[1]
                Shell.touch(fname)
                self.tempfile_cache[self.path] = fname
                Shell.run(
                    f'pdftoppm -png -f 1 -singlefile {self.path} {fname}')
            self.path = self.tempfile_cache[self.path] + '.png'
            self.view_image()
