from __future__ import absolute_import
import string
import os
from netranger.util import log
from netranger.Vim import VimVar
from netranger.Vim import VimWarningMsg

log('')


class UI(object):
    @property
    def position(self):
        return VimVar('NETRSplitOrientation')

    def __init__(self, vim):
        self.bufs = {}
        self.vim = vim

    def map_key_reg(self, key, regval):
        self.vim.command("nnoremap <nowait> <silent> <buffer> {} :let g:NETRRegister=['{}'] <cr> :quit <cr>".format(key, regval))

    def buf_valid(self, name='default'):
        return name in self.bufs and self.bufs[name].valid

    def del_buf(self, name):
        if name in self.bufs:
            del self.bufs[name]

    def show(self, name='default'):
        self.vim.command('{} {}sb'.format(self.position, self.bufs[name].number))

    def create_buf(self, content, mappings=None, name='default'):
        self.vim.command('{} new'.format(self.position))
        self.set_buf_common_option()
        new_buf = self.vim.current.buffer
        self.bufs[name] = new_buf

        if mappings is not None:
            for k, v in mappings:
                self.map_key_reg(k, v)

        new_buf.options['modifiable'] = True
        new_buf[:] = content
        new_buf.options['modifiable'] = False
        self.vim.command('quit')

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


class AskUI(UI):
    def __init__(self, vim, netranger):
        UI.__init__(self, vim)
        self.netranger = netranger
        self.options = None
        self.fullpath = None
        self.create_buf(content=[], mappings=[(chr(ind),chr(ind)) for ind in range(97,123)])

    def ask(self, content, fullpath):
        self.show()
        if len(content) > 26:
            VimWarningMsg('Ask only supports up to 26 commands.')
            content = content[:26]

        ind = 97
        self.options = content[:]
        self.options.append('vim')
        self.fullpath = fullpath
        for i, c in enumerate(content):
            content[i] = '{}. {}'.format(chr(ind), c)
            ind += 1
        content.append('{}. {}'.format(chr(ind), 'vim'))

        buf = self.bufs['default']
        buf.api.set_option('modifiable', True)
        buf[:] = content
        buf.api.set_option('modifiable', False)
        self.netranger.pend_onuiquit(self._ask, 1)

    def _ask(self, char):
        cmd = self.options[ord(char)-97]
        log(self.options)
        log(char, cmd, cmd=='vim')
        if cmd == 'vim':
            self.netranger.NETROpen(use_rifle=False)
        else:
            self.netranger.NETROpen(rifle_cmd=cmd)


def size(path):
    if os.path.isdir(path):
        return str(len(os.listdir(path))).rjust(18)
    else:
        return str(os.stat(path).st_size).rjust(18)


def ext_name(path):
    ind = path.rfind('.')
    if ind < 0:
        return ' '
    else:
        return path[ind+1:]


class SortUI(UI):
    sort_fns = {
        'a': lambda n: os.stat(n.fullpath).st_atime,
        'c': lambda n: os.stat(n.fullpath).st_ctime,
        'd': lambda n: '',
        'e': lambda n: ext_name(n.name),
        'm': lambda n: os.stat(n.fullpath).st_ctime,
        's': lambda n: size(n.fullpath),
    }

    sort_fn_ch = 'd'
    reverse = False

    @classmethod
    def select_sort_fn(cls, ch):
        SortUI.sort_fn_ch = ch

    @classmethod
    def get_sort_fn(cls):
        return SortUI.sort_fns[SortUI.sort_fn_ch]

    def __init__(self, vim):
        UI.__init__(self, vim)
        sort_opts = ['atime', 'ctime', 'default', 'extension', 'mtime', 'size']
        content = ['{}  {}'.format(s[0], s) for s in sort_opts]
        content.insert(0, 'Type keys for sorting option. Use captial letter for reverse (small to large) order')
        mappings = [(k[0],k[0]) for k in sort_opts] + [(k[0].upper(), k[0].upper()) for k in sort_opts]
        self.create_buf(content=content, mappings=mappings)


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
        if not os.path.isfile(VimVar('NETRBookmarkFile')):
            with open(VimVar('NETRBookmarkFile'), 'w') as f:
                f.write('/:/')

        self.load_bookmarks()

    def load_bookmarks(self):
        self.mark_dict = {}
        if os.path.isfile(VimVar('NETRBookmarkFile')):
            with open(VimVar('NETRBookmarkFile'), 'r') as f:
                for line in f:
                    kp = line.split(':')
                    if(len(kp)==2):
                        self.mark_dict[kp[0].strip()] = kp[1].strip()

    def set(self, path):
        if not self.buf_valid('set'):
            self.create_buf(mappings=zip(self.valid_mark, self.valid_mark),
                            content=['{}:{}'.format(k, p) for k,p in self.mark_dict.items()],
                            name='set')
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
        with open(VimVar('NETRBookmarkFile'), 'w') as f:
            for k, p in self.mark_dict.items():
                f.write('{}:{}\n'.format(k,p))

    def go(self):
        if not self.buf_valid('go'):
            self.create_buf(mappings=self.mark_dict.items(),
                            content=['{}:{}'.format(k, p) for k,p in self.mark_dict.items()],
                            name='go')
        self.show('go')
        self.netranger.pend_onuiquit(self.netranger.bookmarkgo_onuiquit, 1)

    def edit(self):
        self.vim.command('belowright split {}'.format(VimVar('NETRBookmarkFile')))
        self.vim.command('setlocal bufhidden=wipe')
        self.del_buf('set')
        self.del_buf('go')
        self.netranger.pend_onuiquit(self.load_bookmarks)


class ParentUI(UI):
    def __init__(self, vim, height):
        UI.__init__(self, vim)
        self.height = height
        self.create_buf([])

    def set_content(self, acl, content):
        buf = self.bufs['default']
        buf.api.set_option('modifiable', True)
        buf[:] = [acl] + content
        buf.api.set_option('modifiable', False)
