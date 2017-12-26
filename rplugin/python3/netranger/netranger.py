import os
import fnmatch
from neovim.api.nvim import NvimError
from netranger.fs import FS, RClone
from netranger.util import log, VimIO, Shell
from netranger import default
from netranger.colortbl import colortbl
from netranger.ui import BookMarkUI, HelpUI
from netranger.rifle import Rifle
from enum import Enum
from collections import defaultdict


log('')


class Node(object):
    State = Enum('NodeState', 'NORMAL, PICKED, UNDEROP')
    ToggleOpRes = Enum('NodeToggleOpRes', 'INVALID, ON, OFF')

    def __init__(self, name, highlight, level=0):
        self.name = name
        self.set_highlight(highlight)
        self.level = level
        self.state = Node.State.NORMAL
        self.valid = True

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

    def reset_highlight(self):
        self.state = Node.State.NORMAL
        self.highlight = self.ori_highlight


class DirNode(EntryNode):
    def __init__(self, fullpath, name, ftype, level=0):
        self.expanded = False
        EntryNode.__init__(self, fullpath, name, ftype, level)


class NetRangerBuf(object):
    header_height = None

    @property
    def first_content_lineNo(self):
        if NetRangerBuf.header_height is None:
            i = 0
            sz = len(self.nodes)
            while i < sz:
                if not self.nodes[i].isHeader:
                    break
                i = i + 1
            NetRangerBuf.header_height = i
        if len(self.nodes) == NetRangerBuf.header_height:
            return NetRangerBuf.header_height - 1
        else:
            return NetRangerBuf.header_height

    @property
    def highlight_content(self):
        return [n.highlight_content for n in self.nodes]

    @property
    def plain_content(self):
        return [n.name for n in self.nodes]

    @property
    def curNode(self):
        return self.nodes[self.clineNo]

    @property
    def highlight_outdated(self):
        return 0 < len(self.highlight_outdated_nodes)

    def __init__(self, vim, wd, fs, rifle):
        self.vim = vim
        self.fs = fs

        self.wd = wd
        self.content_outdated = False
        self.highlight_outdated_nodes = set()
        self.expanded_dirs = set()

        self.vim.command('silent file N:{}'.format(os.path.basename(wd)))
        self.vim.command('lcd ' + wd)

        self.nodes = self.createNodes(self.wd)
        self.nodes.insert(0, Node(Shell.abbrevuser(wd), self.vim.vars['NETRHiCWD']))
        self.clineNo = self.first_content_lineNo
        self.nodes[self.clineNo].cursor_on()
        self.mtime = fs.mtime(wd)
        self.render()

    def createNodes(self, wd, level=0):
        nodes = []
        for f in self.fs.ls(wd):
            if self.shouldIgnore(f):
                continue
            node = self.createNode(wd, f, level)
            if node:
                nodes.append(node)
        return nodes

    def shouldIgnore(self, basename):
        for ig in self.vim.vars['NETRIgnore']:
            if fnmatch.fnmatch(basename, ig):
                return True
        return False

    def createNode(self, dirname, basename, level):
        fullpath = os.path.join(dirname, basename)
        if os.path.isdir(fullpath):
            return DirNode(fullpath, basename, self.fs.ftype(fullpath), level=level)
        else:
            return EntryNode(fullpath, basename, self.fs.ftype(fullpath), level=level)

    def refresh_nodes(self):
        new_mtime = self.fs.mtime(self.wd)
        if new_mtime > self.mtime:
            self.content_outdated = True
            self.mtime = self.fs.mtime(self.wd)
        for d in self.expanded_dirs:
            if not os.path.isdir(d.fullpath):
                continue
            if self.fs.mtime(d.fullpath):
                self.content_outdated = True
                break

        if not self.content_outdated:
            return
        oriNode = self.curNode

        self.content_outdated = False
        new_nodes = []
        fs_files = [set(self.fs.ls(self.wd))]
        for i in range(len(self.nodes)):
            curNode = self.nodes[i]
            if curNode.isHeader:
                new_nodes.append(curNode)
                continue

            prevNode = self.nodes[i-1]
            if curNode.level > prevNode.level:
                fs_files.append(set(self.fs.ls(prevNode.fullpath)))
            else:
                fs_files = fs_files[:curNode.level+1]

            if self.shouldIgnore(curNode.name) or curNode.name not in fs_files[-1]:
                continue

            new_nodes.append(curNode)
            if curNode.isDir and curNode.expanded:
                nextInd = self.next_lesseq_level_ind(i)
                old_names = set([n.name for n in self.nodes[i+1:nextInd+1]])
                for new_name in self.fs.ls(curNode.fullpath):
                    if self.shouldIgnore(new_name):
                        continue
                    if new_name not in old_names:
                        new_node = self.createNode(curNode.fullpath, new_name, curNode.level+1)
                        new_nodes.append(new_node)

        old_names = set([n.name for n in self.nodes])
        for new_name in self.fs.ls(self.wd):
            if self.shouldIgnore(new_name):
                continue
            if new_name not in old_names:
                new_node = self.createNode(self.wd, new_name, 0)
                new_nodes.append(new_node)

        self.nodes = self.sortNodes(new_nodes)
        self.render()
        self.setClineNoByNode(oriNode)

    def refresh_highlight(self):
        if not self.highlight_outdated:
            return
        lines = []
        for i, node in enumerate(self.nodes):
            if node in self.highlight_outdated_nodes:
                lines.append(i)
        self.refresh_lines(lines)
        self.highlight_outdated_nodes.clear()

    def sortNodes(self, nodes):
        header_nodes = []
        sortedNodes = []
        prefix =''
        prefixEndInd = [0]
        for i in range(len(nodes)):
            curNode = nodes[i]
            if curNode.isHeader:
                header_nodes.append(curNode)
                continue

            prevNode = nodes[i-1]
            if curNode.level > prevNode.level:
                prefix += '  {}'.format(prevNode.name)
                prefixEndInd.append(len(prefix))
            else:
                prefixEndInd = prefixEndInd[:curNode.level+1]
                prefix = prefix[:prefixEndInd[-1]]
            if curNode.isDir:
                sortedNodes.append(('{}  {}'.format(prefix, curNode.name), curNode))
            else:
                sortedNodes.append(('{} ~{}'.format(prefix, curNode.name), curNode))

        sortedNodes = sorted(sortedNodes, key=lambda x: x[0])
        sortedNodes = [node[1] for node in sortedNodes]

        return header_nodes + sortedNodes

    def render(self, plain=False):
        self.vim.command('setlocal modifiable')
        if plain:
            self.vim.current.buffer[:] = self.plain_content
        else:
            self.vim.current.buffer[:] = self.highlight_content
        self.vim.command('setlocal nomodifiable')
        self.vim.command('call cursor({}, 1)'.format(self.clineNo+1))

    def on_cursormoved(self):
        log('on_cursormoved')
        lineNo = self.vim.eval("line('.')") - 1
        self.setClineNo(lineNo)

    def setClineNoByName(self, name):
        for i, node in enumerate(self.nodes):
            if node.name == name:
                self.vim.command('call cursor({}, 1)'.format(i+1))
                break
        return False

    def setClineNoByNode(self, node):
        if node in self.nodes:
            self.vim.command('call cursor({}, 1)'.format(self.nodes.index(node)+1))
        else:
            self.vim.command('call cursor({}, 1)'.format(self.first_content_lineNo + 1))

    def setClineNo(self, newLineNo):
        if newLineNo == self.clineNo:
            # ensure clineNo is on
            self.nodes[newLineNo].cursor_on()
            self.refresh_lines([newLineNo])
            return

        oc = self.clineNo
        self.clineNo = newLineNo
        if oc < len(self.nodes):
            self.nodes[oc].cursor_off()
        self.nodes[newLineNo].cursor_on()
        self.refresh_lines([oc, newLineNo])

    def refresh_lines(self, lineNos):
        self.vim.command('setlocal modifiable')

        sz = min(len(self.nodes), len(self.vim.current.buffer))
        for i in lineNos:
            if i < sz:
                self.vim.current.buffer[i] = self.nodes[i].highlight_content
        self.vim.command('setlocal nomodifiable')

    def refresh_cur_line(self):
        self.refresh_lines([self.clineNo])

    def ToggleExpand(self):
        curNode = self.curNode
        if not curNode.isDir:
            return
        if curNode.expanded:
            self.expanded_dirs.remove(curNode)
            endInd = self.next_lesseq_level_ind(self.clineNo)
            self.nodes = self.nodes[:self.clineNo+1] + self.nodes[endInd:]
        else:
            self.expanded_dirs.add(curNode)
            newNodes = self.createNodes(self.curNode.fullpath, curNode.level+1)
            if len(newNodes)>0:
                self.nodes = self.nodes[:self.clineNo+1] + newNodes + self.nodes[self.clineNo+1:]
        curNode.expanded = not curNode.expanded
        self.render()

    def Save(self):
        vimBuf = self.vim.current.buffer
        if len(self.nodes) != len(vimBuf):
            VimIO.ErrorMsg('Edit mode can not add/delete files!')
            self.render()
            return

        oriNode = self.curNode
        # We need to rename subdirectory/subfiles first, so we rename from bottom nodes to top nodes.
        for i in range(len(vimBuf)-1, -1, -1):
            line = vimBuf[i].strip()
            if not self.nodes[i].isHeader and line != self.nodes[i].name:
                oripath = self.nodes[i].rename(line)
                self.fs.mv(oripath, self.nodes[i].fullpath)
        self.nodes = self.sortNodes(self.nodes)
        self.render()
        self.setClineNoByNode(oriNode)

    def Cut(self, nodes):
        for node in nodes:
            node.cut()
        self.highlight_outdated_nodes.update(nodes)

    def Copy(self, nodes):
        for node in nodes:
            node.copy()
        self.highlight_outdated_nodes.update(nodes)

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


class Netranger(object):
    @property
    def curBuf(self):
        return self.bufs[self.vim.current.buffer.number]

    @property
    def curNode(self):
        return self.curBuf.curNode

    @property
    def cwd(self):
        return self.curBuf.wd

    def __init__(self, vim):
        self.vim = vim
        self.inited = False
        self.bufs = {}
        self.wd2bufnum = {}
        VimIO.init(self.vim)

    def init(self):
        self.inited = True
        self.initVimVariables()
        self.initKeymaps()
        self.rclone = None
        self.bookmarkUI = None
        self.helpUI = None
        self.isEditing = False
        self.onuiquit = None
        self.onuiquitNumArgs = 0
        Shell.mkdir(default.variables['NETRRootDir'])
        self.rifle = Rifle(self.vim, self.vim.vars['NETRRifleFile'])
        self.fs = FS()
        self.pinnedRoots = set()
        self.lock = False
        ignore_pat = self.vim.vars['NETRIgnore']
        self.picked_nodes = defaultdict(set)
        self.cut_nodes, self.copied_nodes= defaultdict(set), defaultdict(set)

        if '.*' not in ignore_pat:
            ignore_pat.append('.*')
            self.vim.vars['NETRIgnore'] = ignore_pat

    def initVimVariables(self):
        for k,v in default.variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v

        for k,v in default.internal_variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v

    def initKeymaps(self):
        self.keymaps = {}
        self.keymap_doc = {}
        skip = []
        for k in self.vim.vars['NETRDefaultMapSkip']:
            if k[0]=='<' and k[-1]=='>':
                skip = [k.lower()]
        for fn, (keys, desc) in default.keymap.items():
            user_keys = self.vim.vars.get(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymaps[fn] = user_keys
            self.keymap_doc[fn] = (keys, desc)

    def map_keys(self):
        for fn, keys in self.keymaps.items():
            for k in keys:
                self.vim.command("nnoremap <buffer> {} :call _NETRInvokeMap('{}')<CR>".format(k, fn))

    def on_bufenter(self, bufnum):
        if bufnum in self.bufs:
            self.refresh_curbuf()
            if self.onuiquit is not None:
                # If not enough arguments are passed, ignore the pending onuituit, e.g. quit the bookmark go ui without pressing key to specify where to go.
                if len(self.vim.vars['NETRRegister']) == self.onuiquitNumArgs:
                    self.onuiquit(*self.vim.vars['NETRRegister'])
                self.onuiquit = None
                self.vim.vars['NETRRegister'] = []
                self.onuiquitNumArgs = 0
        else:
            bufname = self.vim.current.buffer.name
            if len(bufname)>0 and bufname[-1] == '~':
                bufname = os.path.expanduser('~')

            if not os.path.isdir(bufname):
                return

            if not self.inited:
                self.init()

            if self.buf_existed(bufname):
                self.show_existing_buf(bufname)
            else:
                self.gen_new_buf(bufname)

    def refresh_curbuf(self):
        curBuf = self.curBuf
        curBuf.refresh_nodes()
        curBuf.refresh_highlight()

    def show_existing_buf(self, bufname):
        ori_bufnum = self.vim.current.buffer.number
        existed_bufnum = self.wd2bufnum[bufname]
        self.vim.command('{}b'.format(existed_bufnum))
        self.setBufOption()
        buf = self.bufs[existed_bufnum]
        self.refresh_curbuf()
        if ori_bufnum not in self.bufs:
            self.vim.command('bwipeout {}'.format(ori_bufnum))
        self.vim.command('call cursor({},1)'.format(buf.clineNo+1))

    def gen_new_buf(self, bufname):
        bufnum = self.vim.current.buffer.number
        if(bufname.startswith(self.vim.vars['NETRCacheDir'])):
            self.bufs[bufnum] = NetRangerBuf(self.vim, os.path.abspath(bufname), self.rclone, self.rifle)
        else:
            self.bufs[bufnum] = NetRangerBuf(self.vim, os.path.abspath(bufname), self.fs, self.rifle)

        self.map_keys()
        self.wd2bufnum[bufname] = bufnum
        self.setBufOption()

    def buf_existed(self, wd):
        if wd not in self.wd2bufnum:
            return False

        bufnum = self.wd2bufnum[wd]
        try:
            buf = self.vim.buffers[bufnum]
            return buf.valid
        except KeyError:
            del self.wd2bufnum[wd]
            del self.bufs[bufnum]
            return False

    def setBufOption(self):
        self.vim.command('setlocal buftype=nofile')
        self.vim.command('setlocal filetype=netranger')
        self.vim.command('setlocal encoding=utf-8')
        self.vim.command('setlocal noswapfile')
        self.vim.command('setlocal nowrap')
        self.vim.command('setlocal foldmethod=manual')
        self.vim.command('setlocal foldcolumn=0')
        self.vim.command('setlocal nofoldenable')
        # self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal bufhidden=hide')
        self.vim.command('setlocal conceallevel=3')
        self.vim.command('set concealcursor=nvic')
        self.vim.command('setlocal nocursorline')

    def on_cursormoved(self, bufnum):
        if bufnum in self.bufs:
            if self.isEditing:
                return
            self.bufs[bufnum].on_cursormoved()

    def pend_onuiquit(self, fn, numArgs=0):
        self.onuiquit = fn
        self.onuiquitNumArgs = numArgs

    def NETROpen(self):
        curNode = self.curNode
        if curNode.isHeader:
            return

        fullpath = curNode.fullpath
        if curNode.isDir:
            self.vim.command('silent edit {}'.format(fullpath))
        else:
            if type(self.fs) is RClone:
                self.fs.download(fullpath)
            cmd = self.rifle.decide_open_cmd(fullpath)

            if cmd:
                Shell.spawn('{} {}'.format(cmd, fullpath))
            else:
                self.vim.command('{} {}'.format(self.vim.vars['NETROpenCmd'], fullpath))

    def NETRParentDir(self):
        cwd = self.curBuf.wd
        if cwd in self.pinnedRoots:
            return
        pdir = self.fs.parent_dir(cwd)
        parent_buf_existed = self.buf_existed(pdir)
        self.vim.command('silent edit {}'.format(pdir))
        if not parent_buf_existed:
            self.curBuf.setClineNoByName(os.path.basename(cwd))

    def NETRVimCD(self):
        curName = self.curNode.fullpath
        if os.path.isdir(curName):
            self.vim.command('lcd {}'.format(curName))
        else:
            self.vim.command('lcd {}'.format(os.path.dirname(curName)))

    def NETREdit(self):
        self.isEditing = True
        for fn, keys in self.keymaps.items():
            if fn == 'NETRSave':
                continue
            for k in keys:
                self.vim.command("nunmap <buffer> {}".format(k))
        self.curBuf.render(plain=True)
        self.vim.command('setlocal modifiable')
        self.vim.command('startinsert')

    def NETRToggleExpand(self):
        self.curBuf.ToggleExpand()

    def NETRSave(self):
        if not self.isEditing:
            return
        self.curBuf.Save()
        self.map_keys()
        self.isEditing = False
        self.vim.command('setlocal nomodifiable')

    def NETRTogglePinRoot(self):
        cwd = self.cwd
        if cwd in self.pinnedRoots:
            self.pinnedRoots.remove(cwd)
        else:
            self.pinnedRoots.add(cwd)

    def NETRToggleShowHidden(self):
        ignore_pat = self.vim.vars['NETRIgnore']
        if '.*' in ignore_pat:
            ignore_pat.remove('.*')
        else:
            ignore_pat.append('.*')
        self.vim.vars['NETRIgnore'] = ignore_pat
        for buf in self.bufs.values():
            buf.content_outdated = True
        self.curBuf.refresh_nodes()

    def invoke_map(self, fn):
        if hasattr(self, fn):
            getattr(self, fn)()

    def initBookMarkUI(self):
        if self.bookmarkUI is None:
            self.bookmarkUI = BookMarkUI(self.vim, self)

    def NETRBookmarkSet(self):
        self.initBookMarkUI()
        self.bookmarkUI.set(self.cwd)

    def NETRBookmarkGo(self):
        self.initBookMarkUI()
        self.bookmarkUI.go()

    def bookmarkgo_onuiquit(self, fullpath):
        # The redundant ifelse statement (same as in on_bufenter) is due to that on_bufenter is synchronous and hence neseted on_bufenter can't be handled.
        self.vim.command('silent edit {}'.format(fullpath))
        if self.buf_existed(fullpath):
            self.show_existing_buf(fullpath)
        else:
            self.gen_new_buf(fullpath)

    def NETRBookmarkEdit(self):
        self.initBookMarkUI()
        self.bookmarkUI.edit()

    def NETRHelp(self):
        if self.helpUI is None:
            self.helpUI = HelpUI(self.vim, self.keymap_doc)
        else:
            self.helpUI.show()

    def NETRTogglePick(self):
        curNode = self.curNode
        curBuf = self.curBuf
        res = curNode.toggle_pick()
        if res == Node.ToggleOpRes.ON:
            self.picked_nodes[curBuf].add(curNode)
        elif res == Node.ToggleOpRes.OFF:
            self.picked_nodes[curBuf].remove(curNode)
        self.curBuf.refresh_cur_line()

    def NETRCut(self):
        for buf, nodes in self.picked_nodes.items():
            buf.Cut(nodes)
            self.cut_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.curBuf.refresh_highlight()

    def NETRCutSingle(self):
        curBuf = self.curBuf
        curNode = self.curNode
        curBuf.Cut([curNode])
        self.cut_nodes[curBuf].add(curNode)
        curBuf.refresh_highlight()

    def NETRCopy(self):
        for buf, nodes in self.picked_nodes.items():
            buf.Copy(nodes)
            self.copied_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.curBuf.refresh_highlight()

    def NETRCopySingle(self):
        curBuf = self.curBuf
        curNode = self.curNode
        curBuf.Copy([curNode])
        self.copied_nodes[curBuf].add(curNode)
        curBuf.refresh_highlight()

    def NETRPaste(self):
        cwd = self.cwd
        alreday_moved = set()
        for buf, nodes in self.cut_nodes.items():
            wd = buf.wd
            # We need to reset highlight when mv fails.
            buf.highlight_outdated_nodes.update(nodes)
            while True:
                if wd in self.wd2bufnum:
                    self.bufs[self.wd2bufnum[wd]].content_outdated = True
                wd = os.path.dirname(wd)
                if len(wd) == 1:
                    break

            # We need to mv longer (deeper) file name first
            nodes = sorted(nodes, key=lambda n: n.fullpath, reverse=True)
            for node in nodes:
                node.reset_highlight()
                if node.fullpath not in alreday_moved:
                    try:
                        self.fs.mv(node.fullpath, cwd)
                    except Exception as e:
                        VimIO.ErrorMsg(e)
                    alreday_moved.add(node.fullpath)
        self.cut_nodes = defaultdict(set)

        for buf, nodes in self.copied_nodes.items():
            buf.highlight_outdated_nodes.update(nodes)
            for node in nodes:
                node.reset_highlight()
                try:
                    self.fs.cp(node.fullpath, cwd)
                except Exception as e:
                    VimIO.ErrorMsg(e)
        self.copied_nodes = defaultdict(set)
        self.curBuf.refresh_nodes()
        self.curBuf.refresh_highlight()

    def NETRDelete(self, force=False):
        for buf, nodes in self.picked_nodes.items():
            buf.content_outdated = True
            for node in nodes:
                self.fs.rm(node.fullpath, force)
        self.curBuf.refresh_nodes()
        self.picked_nodes = defaultdict(set)

    def NETRDeleteSingle(self, force=False):
        self.fs.rm(self.curNode.fullpath, force)
        self.curBuf.refresh_nodes()

    def NETRForceDelete(self):
        self.NETRDelete(force=True)

    def NETRForceDeleteSingle(self):
        self.NETRDeleteSingle(force=True)

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
            VimIO.ErrorMsg("There's no remote now. Run 'rclone config' in a terminal to setup remotes")
