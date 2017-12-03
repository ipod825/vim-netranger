import string
import os
from netranger.util import log

log('')


class UI(object):
    def map_key_reg(self, key, regval):
        self.vim.command("nnoremap <buffer> {} :let g:_NETRRegister='{}' <cr> :quit <cr>".format(key, regval))


class BookMarkUI(UI):
    def __init__(self, vim, netranger):
        self.valid_mark = string.ascii_lowercase + string.ascii_uppercase
        self.vim = vim
        self.netranger = netranger
        self.set_buf = None
        self.go_buf = None
        self.mark_dict = {}
        self.path_to_mark = None
        self.go_buf_out_dated = False

        # This is to avoid a bug that I can't solve.
        # If bookmark file is initially empty. The first time
        # 'm' (set) mapping is trigger, it won't quit the buffer
        # on user input..
        if not os.path.isfile(self.vim.vars['NETRBookmarkFile']):
            with open(self.vim.vars['NETRBookmarkFile'], 'w') as f:
                f.write('/:/')

        self.load_bookmarks()

    def load_bookmarks(self, *args):
        self.mark_dict = {}
        if os.path.isfile(self.vim.vars['NETRBookmarkFile']):
            with open(self.vim.vars['NETRBookmarkFile'], 'r') as f:
                for line in f:
                    kp = line.split(':')
                    if(len(kp)==2):
                        self.mark_dict[kp[0].strip()] = kp[1].strip()

    def init_set_buf(self):
        self.vim.command('belowright new')

        for ch in self.valid_mark:
            self.map_key_reg(ch, ch)

        self.set_buf = self.vim.current.buffer

        self.set_buf[:] = ['{}:{}'.format(k, p) for k,p in self.mark_dict.items()]
        self.set_buf_common_option()
        self.set_buf_out_dated = False

    def init_go_buf(self):
        self.vim.command('belowright split new')
        self.set_buf_common_option()
        self.vim.current.buffer[:] = ['{}:{}'.format(k, p) for k,p in self.mark_dict.items()]

        for k, path in self.mark_dict.items():
            self.map_key_reg(k, path)
        self.go_buf_out_dated = False

    def set_buf_common_option(self):
        self.vim.command('setlocal noswapfile')
        self.vim.command('setlocal foldmethod=manual')
        self.vim.command('setlocal foldcolumn=0')
        self.vim.command('setlocal nofoldenable')
        self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal buftype=nofile')
        self.vim.command('setlocal bufhidden=hide')

    def set(self, path):
        if self.set_buf is None or not self.set_buf.valid:
            self.init_set_buf()
        else:
            self.vim.command('belowright {}sb'.format(self.set_buf.number))
        self.path_to_mark = path
        self.netranger.pend_onuiquit(self._set)

    def _set(self, mark):
        if mark == '':
            return
        if mark not in self.valid_mark:
            self.vim.command('echo "Only a-zA-Z are valid mark!!"')
            return
        self.set_buf.options['modifiable'] = True
        if mark in self.mark_dict:
            for i, line in enumerate(self.set_buf):
                if len(line)>0 and line[0] == mark:
                    self.set_buf[i] = '{}:{}'.format(mark, self.path_to_mark)
                    break
        else:
            self.set_buf.append('{}:{}'.format(mark, self.path_to_mark))
        self.set_buf.options['modifiable'] = False
        self.mark_dict[mark] = self.path_to_mark
        self.go_buf_out_dated = True
        with open(self.vim.vars['NETRBookmarkFile'], 'w') as f:
            for k, p in self.mark_dict.items():
                f.write('{}:{}\n'.format(k,p))

    def go(self):
        if self.go_buf is None or not self.go_buf.valid or self.go_buf_out_dated:
            self.init_go_buf()
        else:
            self.vim.command('belowright {}sb'.format(self.go_buf.number))
        self.netranger.pend_onuiquit('set_cwd')

    def edit(self):
        self.vim.command('belowright split {}'.format(self.vim.vars['NETRBookmarkFile']))
        self.vim.command('setlocal bufhidden=wipe')
        self.go_buf_out_dated = True
        self.netranger.pend_onuiquit(self.load_bookmarks)
