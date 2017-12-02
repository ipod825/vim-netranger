import os
import fnmatch
from neovim.api.nvim import NvimError
import string
from netranger.fs import FS, RClone
from netranger.util import log, VimErrorMsg
from netranger import default
from netranger.colortbl import colortbl
from enum import Enum

log('')


class Node(object):
    State = Enum('NodeState', 'NORMAL, PICKED, UNDEROP')
    ToggleOpRes = Enum('NodeToggleOpRes', 'INVALID, ON, OFF')

    def __init__(self, name, highlight, level=0):
        self.name = name
        self.set_highlight(highlight)
        self.level = level
        self.state = Node.State.NORMAL

    def set_highlight(self, highlight, cursor_on=False):
        if type(highlight) is str:
            highlight = colortbl[highlight]
        if cursor_on:
            self.highlight = '[38;5;{};7'.format(highlight)
        else:
            self.highlight = '[38;5;{}'.format(highlight)

    @property
    def highlight_content(self):
        return '{}m{}{}'.format(self.highlight, ' '*(self.level*2), self.name)

    @property
    def isDir(self):
        return type(self) is DirNode

    @property
    def isHeader(self):
        return type(self) is Node

    def cursor_on(self):
        pass

    def cursor_off(self):
        pass

    def toggle_pick(self):
        return Node.ToggleOpRes.INVALID


class EntryNode(Node):
    def __init__(self, fullpath, name, ftype, level=0):
        self.fullpath = fullpath
        highlight = default.color[ftype]
        Node.__init__(self, name, highlight, level=level)
        self.ori_highlight = self.highlight

    def cursor_on(self):
        hiArr = self.highlight.split(';')
        if len(hiArr) == 3:
            hiArr.append('7')
            self.highlight = ';'.join(hiArr)

    def cursor_off(self):
        hiArr = self.highlight.split(';')
        if len(hiArr) == 4:
            hiArr = hiArr[:-1]
            self.highlight = ';'.join(hiArr)

    def rename(self, name):
        ori = self.fullpath
        self.fullpath = os.path.join(os.path.dirname(self.fullpath), name)
        self.name = name
        return ori

    def toggle_pick(self):
        if self.state == Node.State.NORMAL:
            self.state = Node.State.PICKED
            self.set_highlight(default.color['pick'], cursor_on=True)
            return Node.ToggleOpRes.ON
        elif self.state == Node.State.PICKED:
            self.state = Node.State.NORMAL
            self.highlight = self.ori_highlight
            return Node.ToggleOpRes.OFF
        else:
            return Node.ToggleOpRes.INVALID

    def cut(self):
        if self.state == Node.State.UNDEROP:
            return
        self.state = Node.State.UNDEROP
        self.set_highlight(default.color['cut'])

    def copy(self):
        if self.state == Node.State.UNDEROP:
            return
        self.state = Node.State.UNDEROP
        self.set_highlight(default.color['copy'])

    def reset_state(self):
        self.state = Node.State.NORMAL
        self.highlight = self.ori_highlight


class DirNode(EntryNode):
    def __init__(self, fullpath, name, ftype, level=0):
        self.expanded = False
        EntryNode.__init__(self, fullpath, name, ftype, level)


class Page(object):
    def __init__(self, vim, cwd, fs, prevcwd=None):
        self.vim = vim
        self.cwd = cwd
        self.fs = fs
        self.nodes = self.createNodes(cwd)
        self.nodes.insert(0, Node(self.cwd, self.vim.vars['NETRHiCWD']))
        self.initClineNo(prevcwd)
        self.nodes[self.clineNo].cursor_on()

    def createNodes(self, cwd, level=0):
        nodes = []
        for f in self.fs.ls(cwd):
            shouldIgnore = False
            for ig in self.vim.vars['NETRIgnore']:
                if fnmatch.fnmatch(f, ig):
                    shouldIgnore = True
                    break
            if not shouldIgnore:
                fullpath = os.path.join(cwd, f)
                if os.path.isdir(fullpath):
                    nodes.append(DirNode(fullpath, f, self.fs.ftype(fullpath), level=level))
                else:
                    nodes.append(EntryNode(fullpath, f, self.fs.ftype(fullpath), level=level))
        return nodes

    def initClineNo(self, prevcwd=None):
        self.clineNo = 0
        if prevcwd is not None:
            prevcwd = os.path.basename(prevcwd)
            for i, node in enumerate(self.nodes):
                if node.name == prevcwd:
                    self.clineNo = i
                    break
        else:
            for i, node in enumerate(self.nodes):
                if not node.isHeader:
                    self.clineNo = i
                    break

    def refresh_lines(self, lineNos):
        self.vim.command('setlocal modifiable')

        self.nodes[self.clineNo].cursor_on()
        if type(lineNos) is list:
            for l in lineNos:
                self.vim.current.buffer[l] = self.nodes[l].highlight_content
        else:
            self.vim.current.buffer[lineNos] = self.nodes[lineNos].highlight_content
        self.vim.command('setlocal nomodifiable')

    def setClineNo(self, newLineNo):
        if newLineNo == self.clineNo:
            return

        oc = self.clineNo
        self.nodes[oc].cursor_off()
        self.clineNo = newLineNo
        self.refresh_lines([oc, newLineNo])

    @property
    def curNode(self):
        return self.nodes[self.clineNo]

    @property
    def highlight_content(self):
        return [n.highlight_content for n in self.nodes]

    @property
    def plain_content(self):
        return [n.name for n in self.nodes]

    def find_next_ind(self, ind, pred):
        beg_node = self.nodes[ind]
        ind += 1
        sz = len(self.nodes)
        while ind < sz:
            if pred(beg_node, self.nodes[ind]):
                break
            ind += 1
        return ind

    def next_lesseq_level_ind(self, begInd):
        return self.find_next_ind(begInd, lambda beg, new: new.level<=beg.level)

    def next_lesseq_level_name_ind(self, begInd):
        return self.find_next_ind(begInd, lambda beg, new: new.level<=beg.level and new.name<=beg.name)

    def toggle_expand(self):
        curNode = self.curNode
        if not curNode.isDir:
            return
        if curNode.expanded:
            endInd = self.next_lesseq_level_ind(self.clineNo)
            self.nodes = self.nodes[:self.clineNo+1] + self.nodes[endInd:]
        else:
            newNodes = self.createNodes(self.curNode.fullpath, curNode.level+1)
            if len(newNodes)>0:
                self.nodes = self.nodes[:self.clineNo+1] + newNodes + self.nodes[self.clineNo+1:]
        curNode.expanded = not curNode.expanded

    def rename_nodes_from_content(self):
        curBuf = self.vim.current.buffer
        if len(self.nodes) != len(curBuf):
            curBuf[:] = self.highlight_content
            return False
        else:
            log('fuck')
            log('node#: {}'.format(len(self.nodes)))
            for i, line in enumerate(curBuf):
                line = line.strip()
                if not self.nodes[i].isHeader and line != self.nodes[i].name:
                    oripath = self.nodes[i].rename(line)
                    self.fs.mv(oripath, self.nodes[i].fullpath)
            log('node#: {}'.format(len(self.nodes)))
            curBuf[:] = self.highlight_content
            return True


class NetRangerBuf(object):
    def __init__(self, vim, keymaps, cwd, fs):
        self.vim = vim
        self.fs = fs
        self.keymaps = keymaps

        self.pages = {}
        self.picked_lines = []
        self.cut_lines, self.copy_lines = [], []
        self.cut_path, self.copy_path = [], []
        self.render_lock = False
        self.pinnedRoot = None
        self.source_page_wd = None
        self.isEditing = False

        if self.vim.vars['NETRTabAutoToFirst']:
            self.vim.command('tabmove 0')

        self.cwd = None
        self.setBufOption()
        self.map_keys()
        self.set_cwd(cwd)

    def map_keys(self):
        for fn, keys in self.keymaps.items():
            for k in keys:
                self.vim.command("nnoremap <buffer> {} :call NETRInvokeMap('{}')<CR>".format(k, fn))

    def setBufOption(self):
        self.vim.command('setlocal filetype=netranger')
        self.vim.command('setlocal encoding=utf-8')
        self.vim.command('setlocal noswapfile')
        self.vim.command('setlocal nowrap')
        self.vim.command('setlocal foldmethod=manual')
        self.vim.command('setlocal foldcolumn=0')
        self.vim.command('setlocal nofoldenable')
        self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal bufhidden=wipe')
        self.vim.command('setlocal conceallevel=3')
        self.vim.command('set concealcursor=nvic')
        self.vim.command('setlocal nocursorline')

    def render(self):
        self.render_lock = True
        self.vim.command('setlocal modifiable')

        self.vim.current.buffer[:] = self.curPage.highlight_content
        self.vim.command('call cursor({}, 1)'.format(self.curPage.clineNo+1))

        self.vim.command('setlocal nomodifiable')
        self.render_lock = False

    @property
    def curPage(self):
        return self.pages[self.cwd]

    @property
    def curNode(self):
        return self.curPage.curNode

    def set_cwd(self, cwd, isParentOfPrev=False):
        log('set_cwd')
        self.finalizeCutCopy()

        if cwd not in self.pages:
            if isParentOfPrev:
                page = Page(self.vim, cwd, self.fs, prevcwd=self.cwd)
            else:
                page = Page(self.vim, cwd, self.fs)
            self.pages[cwd] = page

        self.cwd = cwd
        self.set_buf_name(cwd)
        self.render()
        self.vim.command('cd '+cwd)

    def set_buf_name(self, cwd):
        succ = False
        ind = 0
        while not succ:
            try:
                if ind == 0:
                    affix = ''
                else:
                    affix = '-'+str(ind)
                self.vim.command('silent file N:{}{}'.format(
                    os.path.basename(cwd), affix))
                succ = True
            except NvimError:
                ind = ind + 1

    def refresh_page(self):
        self.pages[self.cwd] = Page(self.vim, self.cwd, self.fs)
        self.render()

    def on_cursormoved(self):
        if self.isEditing:
            return
        if self.render_lock:
            return
        lineNo = self.vim.eval("line('.')") - 1
        self.curPage.setClineNo(lineNo)

    def NETROpen(self):
        if self.curNode.isHeader:
            return
        fullpath = self.curNode.fullpath
        if self.curNode.isDir:
            self.set_cwd(fullpath)
        else:
            if type(self.fs) is RClone:
                self.fs.download(fullpath)
            self.vim.command('tab drop {}'.format(fullpath))

    def NETRParentDir(self):
        log('ParentDir')
        if self.cwd == self.pinnedRoot:
            return
        pdir = self.fs.parent_dir(self.cwd)
        self.set_cwd(pdir, isParentOfPrev=True)

    def NETRVimCD(self):
        curName = self.curNode.fullpath
        if os.path.isdir(curName):
            self.vim.command('cd {}'.format(curName))
        else:
            self.vim.command('cd {}'.format(os.path.dirname(curName)))

    def NETRToggleExpand(self):
        self.curPage.toggle_expand()
        self.render()

    def NETREdit(self):
        self.isEditing = True
        self.vim.command('startinsert')
        for fn, keys in self.keymaps.items():
            if fn == 'NETRSave':
                continue
            for k in keys:
                self.vim.command("nunmap <buffer> {}".format(k))
        self.vim.command('setlocal modifiable')
        self.vim.current.buffer[:] = self.curPage.plain_content
        self.vim.command('echo "Start editing mode."')

    def NETRSave(self):
        if not self.isEditing:
            return
        succ = self.curPage.rename_nodes_from_content()
        self.refresh_page()
        self.map_keys()
        self.isEditing = False
        self.vim.command('setlocal nomodifiable')
        if not succ:
            VimErrorMsg(self.vim, 'Edit mode can not add/delete files!')

    def NETRTogglePinRoot(self):
        if self.pinnedRoot is not None:
            self.pinnedRoot = None
        else:
            self.pinnedRoot = self.cwd

    def NETRBookmarkSet(self):
        if self.bookmark is None:
            self.bookmark = BookMarkBuf(self.vim)
        self.bookmark.set(self.cwd)

    def NETRTogglePick(self):
        res = self.curNode.toggle_pick()
        if res == Node.ToggleOpRes.ON:
            self.picked_lines.append(self.curPage.clineNo)
        elif res == Node.ToggleOpRes.OFF:
            self.picked_lines.remove(self.curPage.clineNo)
        self.curPage.refresh_lines(self.curPage.clineNo)

    def _cutcopy(self, op, oplines):
        if self.source_page_wd is not None:
            VimErrorMsg(self.vim, 'Paste before {} again!'.format(op))
            return

        for l in self.picked_lines:
            getattr(self.curPage.nodes[l], op)()
        oplines += self.picked_lines

        self.picked_lines = []
        self.curPage.refresh_lines(self.picked_lines + oplines)

    def NETRCut(self):
        self._cutcopy('cut', self.cut_lines)

    def NETRCopy(self):
        self._cutcopy('copy', self.copy_lines)

    def finalizeCutCopy(self):
        log('finalizeCutCopy')
        if self.cwd is None:
            return

        for i in self.picked_lines:
            self.curPage.nodes[i].reset_state()
        self.curPage.refresh_lines(self.picked_lines + self.copy_lines)
        self.picked_lines = []

        for i in self.cut_lines:
            self.cut_path.append(self.curPage.nodes[i].fullpath)
        for i in self.copy_lines:
            self.copy_path.append(self.curPage.nodes[i].fullpath)

        if len(self.cut_lines)>0 or len(self.copy_lines)>0:
            self.source_page_wd = self.cwd

        self.cut_lines = []
        self.copy_lines = []

    def NETRPaste(self):
        if len(self.copy_path)<len(self.copy_lines) or len(self.cut_path)< len(self.cut_lines):
            self.finalizeCutCopy()

        try:
            for path in self.cut_path:
                self.fs.mv(path, self.cwd)

            for path in self.copy_path:
                self.fs.cp(path, self.cwd)
        except Exception as e:
            VimErrorMsg(self.vim, e)

        self.cut_path = []
        self.copy_path = []
        self.cut_lines = []
        self.copy_lines = []
        if self.source_page_wd is not None:
            del self.pages[self.source_page_wd]
        self.source_page_wd = None
        self.refresh_page()
        self.render()

    def NETRDelete(self):
        for i in self.picked_lines:
            self.fs.rm(self.curPage.nodes[i].fullpath)
        self.picked_lines = []
        self.refresh_page()
        self.render()

    def NETRDeleteSingle(self):
        self.picked_lines.append(self.curPage.clineNo)
        self.NETRDelete()

    def NETRForceDelete(self):
        for i in self.picked_lines:
            self.fs.rmf(self.curPage.nodes[i].fullpath)
        self.picked_lines = []
        self.refresh_page()
        self.render()

    def NETRForceDeleteSingle(self):
        self.picked_lines.append(self.curPage.clineNo)
        self.NETRForceDelete()

    def NETRUndo(self):
        pass

    def NETRCutSingle(self):
        self.picked_lines.append(self.curPage.clineNo)
        self.NETRCut()

    def NETRCopySingle(self):
        self.picked_lines.append(self.curPage.clineNo)
        self.NETRCopy()


class BookMarkBuf(object):
    def __init__(self, vim):
        self.valid_mark = string.ascii_lowercase + string.ascii_uppercase
        self.vim = vim
        self.set_buf = None
        self.bookmarks = {}
        self.path_to_mark = None
        if os.path.isfile(self.vim.vars['NETRBookmark']):
            with open(self.vim.vars['NETRBookmark'], 'r') as f:
                for line in f:
                    kp = line.split(':')
                    if(len(kp)==2):
                        self.bookmarks[kp[0].strip()] = kp[1].strip()

    def on_vimleavepre(self):
        # if self.bookmarks:
        with open(self.vim.vars['NETRBookmark'], 'w+') as f:
            f.writelines(['{}:{}\n'.format(k, p) for k,p in self.bookmarks.items()])

    def set(self, path):
        if self.set_buf is None or not self.set_buf.valid:
            self.init_set_buf()
        else:
            self.vim.command('belowright {}sb'.format(self.set_buf.number))
        self.path_to_mark = path

    def init_set_buf(self):
        self.vim.command('belowright new')

        for ch in self.valid_mark:
            self.vim.command('nnoremap <buffer> {} :quit<cr>:call _NETRBookmarkSet("{}") <cr>'.format(ch, ch))

        self.set_buf = self.vim.current.buffer

        self.set_buf[:] = ['{}:{}'.format(k, p) for k,p in self.bookmarks.items()]
        self.set_buf_common_option()

    def _set(self, mark):
        if mark not in self.valid_mark:
            self.vim.command('echo "Only a-zA-Z are valid mark!!"')
            return
        self.set_buf.options['modifiable'] = True
        if mark in self.bookmarks:
            for i, line in enumerate(self.set_buf):
                if len(line)>0 and line[0] == mark:
                    self.set_buf[i] = '{}:{}'.format(mark, self.path_to_mark)
                    break
        else:
            self.set_buf.append('{}:{}'.format(mark, self.path_to_mark))
        self.set_buf.options['modifiable'] = False
        self.bookmarks[mark] = self.path_to_mark

    def set_buf_common_option(self):
        self.vim.command('setlocal noswapfile')
        self.vim.command('setlocal foldmethod=manual')
        self.vim.command('setlocal foldcolumn=0')
        self.vim.command('setlocal nofoldenable')
        self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal buftype=nofile')
        self.vim.command('setlocal bufhidden=hide')

    def go(self):
        self.vim.command('belowright split new')
        self.set_buf_common_option()
        self.vim.current.buffer[:] = ['{}:{}'.format(k, p) for k,p in self.bookmarks.items()]

        for k, path in self.bookmarks.items():
            self.vim.command('nnoremap <buffer> {} :q<cr>:NETRCD {}<cr>'.format(k, path))


class Netranger(object):
    def __init__(self, vim):
        self.vim = vim
        self.inited = False
        self.bufs = {}

    def init(self):
        self.inited = True
        self.initVimVariables()
        self.initKeymaps()
        self.rclone = None
        self.bookmark = None
        self.isEditing = False

    def initVimVariables(self):
        for k,v in default.variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v

    def initKeymaps(self):
        self.keymaps = {}
        skip = [k.lower() for k in self.vim.vars['NETRDefaultMapSkip']]
        for fn, keys in default.keymap.items():
            user_keys = self.vim.vars.get(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymaps[fn] = user_keys

    def on_bufenter(self, bufnum):
        if bufnum not in self.bufs:

            if not self.inited:
                self.init()

            buf = self.vim.current.buffer
            bufname = buf.name
            if len(bufname)>0 and bufname[-1] == '~':
                bufname = os.path.expanduser('~')
            if(os.path.isdir(bufname)):
                self.vim.command('setlocal buftype=nofile')

                if(bufname.startswith(self.vim.vars['NETRCacheDir'])):
                    self.bufs[bufnum] = NetRangerBuf(self.vim, self.keymaps, os.path.abspath(bufname), self.rclone)
                else:
                    self.bufs[bufnum] = NetRangerBuf(self.vim, self.keymaps, os.path.abspath(bufname), FS())

    def on_cursormoved(self, bufnum):
        if bufnum in self.bufs:
            self.bufs[bufnum].on_cursormoved()

    @property
    def curBuf(self):
        return self.bufs[self.vim.current.buffer.number]

    @property
    def curPage(self):
        return self.curBuf.curPage

    @property
    def curNode(self):
        return self.curPage.curNode

    @property
    def isInNETRBuf(self):
        return self.vim.current.buffer.number in self.bufs

    def invoke_map(self, fn):
        log('invoke_map', fn)
        getattr(self.curBuf, fn)()

    def _NETRBookmarkSet(self, mark):
        self.bookmark._set(mark)

    def NETRBookmarkGo(self):
        if self.bookmark is None:
            self.bookmark = BookMarkBuf(self.vim)
        self.bookmark.go()

    def valid_rclone_or_install(self):
        if self.rclone is not None:
            return
        RClone.valid_or_install(self.vim)

        self.vim.vars['NETRCacheDir'] = os.path.expanduser(self.vim.vars['NETRCacheDir'])
        self.rclone = RClone(self.vim.vars['NETRCacheDir'])

    def listremotes(self):
        self.valid_rclone_or_install()
        if self.rclone.has_remote:
            self.vim.command('tabe ' + self.vim.vars['NETRCacheDir'])
        else:
            self.vim.command("There's no remote now. Run 'rclone config' in a terminal to setup remotes")

    def cd(self, dst):
        if not self.isInNETRBuf:
            self.vim.command('Only applicable in a netranger buffer.')
        else:
            if dst=='~':
                DST = os.path.expanduser('~')
            else:
                DST = os.path.abspath(dst)
            if not os.path.isdir(DST):
                self.vim.command('echo "Error: {} is not a directory"'.format(dst))
            else:
                self.curBuf.set_cwd(DST)
