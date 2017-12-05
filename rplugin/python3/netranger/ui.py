import string
import os
from netranger.util import log

log('')


class UI(object):
    def __init__(self, vim):
        self.bufs = {}
        self.vim = vim

    def map_key_reg(self, key, regval):
        self.vim.command("nnoremap <buffer> {} :let g:_NETRRegister=['{}'] <cr> :quit <cr>".format(key, regval))

    def buf_valid(self, name='default'):
        return name in self.bufs and self.bufs[name].valid

    def del_buf(self, name):
        if name in self.bufs:
            del self.bufs[name]

    def show(self, name='default'):
        self.vim.command('belowright {}sb'.format(self.bufs[name].number))

    def create_buf(self, content, mappings=None, name='default'):
        self.vim.command('belowright new')
        self.set_buf_common_option()
        new_buf = self.vim.current.buffer
        self.bufs[name] = new_buf

        if mappings is not None:
            for k, v in mappings:
                self.map_key_reg(k, v)

        new_buf.options['modifiable'] = True
        new_buf[:] = content
        new_buf.options['modifiable'] = False

    def set_buf_common_option(self, modifiable=False):
        self.vim.command('setlocal noswapfile')
        self.vim.command('setlocal foldmethod=manual')
        self.vim.command('setlocal foldcolumn=0')
        self.vim.command('setlocal nofoldenable')
        self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal buftype=nofile')
        self.vim.command('setlocal bufhidden=hide')
        self.vim.command('setlocal nomodifiable')


class HelpUI(UI):
    def __init__(self, vim, keymap_doc):
        UI.__init__(self, vim)

        self.create_buf(content=['{:<25} {:<10} {}'.format(fn, ','.join(keys), desc) for fn, (keys, desc) in keymap_doc.items()])


class BookMarkUI(UI):
    def __init__(self, vim, netranger):
        UI.__init__(self, vim)
        self.valid_mark = string.ascii_lowercase + string.ascii_uppercase
        self.netranger = netranger
        self.mark_dict = {}
        self.path_to_mark = None

        # This is to avoid a bug that I can't solve.
        # If bookmark file is initially empty. The first time
        # 'm' (set) mapping is trigger, it won't quit the buffer
        # on user input..
        if not os.path.isfile(self.vim.vars['NETRBookmarkFile']):
            with open(self.vim.vars['NETRBookmarkFile'], 'w') as f:
                f.write('/:/')

        self.load_bookmarks()

    def load_bookmarks(self):
        self.mark_dict = {}
        if os.path.isfile(self.vim.vars['NETRBookmarkFile']):
            with open(self.vim.vars['NETRBookmarkFile'], 'r') as f:
                for line in f:
                    kp = line.split(':')
                    if(len(kp)==2):
                        self.mark_dict[kp[0].strip()] = kp[1].strip()

    def set(self, path):
        if not self.buf_valid('set'):
            self.create_buf(mappings=zip(self.valid_mark, self.valid_mark),
                            content=['{}:{}'.format(k, p) for k,p in self.mark_dict.items()],
                            name='set')
        else:
            self.show('set')
        self.path_to_mark = path
        self.netranger.pend_onuiquit(self._set, 1)

    def _set(self, mark):
        if mark == '':
            return
        if mark not in self.valid_mark:
            self.vim.command('echo "Only a-zA-Z are valid mark!!"')
            return
        set_buf = self.bufs['set']
        set_buf.options['modifiable'] = True

        if mark in self.mark_dict:
            for i, line in enumerate(set_buf):
                if len(line)>0 and line[0] == mark:
                    set_buf[i] = '{}:{}'.format(mark, self.path_to_mark)
                    break
        elif self.path_to_mark in self.mark_dict.values():
            for i, line in enumerate(set_buf):
                if len(line)>0 and line[2:] == self.path_to_mark:
                    set_buf[i] = '{}:{}'.format(mark, self.path_to_mark)
                    break
        else:
            set_buf.append('{}:{}'.format(mark, self.path_to_mark))
        set_buf.options['modifiable'] = False
        self.mark_dict[mark] = self.path_to_mark
        self.del_buf('go')
        with open(self.vim.vars['NETRBookmarkFile'], 'w') as f:
            for k, p in self.mark_dict.items():
                f.write('{}:{}\n'.format(k,p))

    def go(self):
        if not self.buf_valid('go'):
            self.create_buf(mappings=self.mark_dict.items(),
                            content=['{}:{}'.format(k, p) for k,p in self.mark_dict.items()],
                            name='go')
        else:
            self.show('go')
        self.netranger.pend_onuiquit('set_cwd', 1)

    def edit(self):
        self.vim.command('belowright split {}'.format(self.vim.vars['NETRBookmarkFile']))
        self.vim.command('setlocal bufhidden=wipe')
        self.del_buf('set')
        self.del_buf('go')
        self.netranger.pend_onuiquit(self.load_bookmarks)
