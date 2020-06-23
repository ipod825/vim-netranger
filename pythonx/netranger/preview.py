import re

from netranger import Vim, util
from netranger.thirdparty.pymagic import magic


class view(object):
    def __init__(self, path, total_width, preview_width):
        self.path = path
        self.total_width = total_width
        self.preview_width = preview_width
        self.preview_close_on_tableave = False

        try:
            self.mime_type = magic.from_file(path)
        except Exception:
            self.mime_type = ''
        if re.search('image', self.mime_type):
            self.view_image()
            self.preview_close_on_tableave = True
        elif re.search('text|data$|empty', self.mime_type):
            self.view_plaintext()
        else:
            self.view_mime()

    def view_plaintext(self):
        bak_shortmess = Vim.options['shortmess']
        Vim.options['shortmess'] = 'A'
        Vim.command(f'edit {self.path}')
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
