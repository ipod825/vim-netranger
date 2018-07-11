from __future__ import absolute_import
from __future__ import print_function
import os
import fnmatch
import datetime
from netranger.fs import FS, Rclone
from netranger.util import log, Shell, c256
from netranger import default
from netranger.colortbl import colortbl
from netranger.ui import BookMarkUI, HelpUI, SortUI, AskUI
from netranger.rifle import Rifle
from netranger.Vim import VimVar, VimErrorMsg, VimCurWinWidth, pbar
from netranger.enum import Enum
from collections import defaultdict
from netranger.config import file_sz_display_wid
from netranger.hooker import Hookers, has_hooker

from sys import platform
if platform == "win32":
    from os import getenv
else:
    import pwd
    import grp


log('')


class Node(object):
    """
    General node. Inherited by header nodes or entry nodes.
    """
    State = Enum('NodeState', 'NORMAL, PICKED, UNDEROP')
    ToggleOpRes = Enum('NodeToggleOpRes', 'INVALID, ON, OFF')

    def __init__(self, fullpath, name, highlight, level=0):
        self.fullpath = fullpath
        self.name = name
        self.set_highlight(highlight)
        self.level = level
        self.state = Node.State.NORMAL
        self.is_cursor_on = False

    def set_highlight(self, highlight):
        if type(highlight) is str:
            highlight = colortbl[highlight]
        self.highlight = highlight

    @property
    def highlight_content(self):
        return c256(self.name, self.highlight, self.is_cursor_on)

    @property
    def isDir(self):
        return False

    @property
    def isHeader(self):
        return False

    def cursor_on(self):
        self.is_cursor_on = True

    def cursor_off(self):
        self.is_cursor_on = False

    def toggle_pick(self):
        return Node.ToggleOpRes.INVALID


class CWDNode(Node):
    def __init__(self, fullpath):
        super(CWDNode, self).__init__(fullpath, Shell.abbrevuser(fullpath), default.color['cwd'], level=0)
        self.re_stat()

    def re_stat(self, fs=None):
        self.stat = os.stat(self.fullpath)

    @property
    def highlight_content(self):
        return c256(self.name, self.highlight, False)

    @property
    def isHeader(self):
        return True


class EntryNode(Node):
    """
    Content node.
    """
    def abbrev_name(self, width):
        if self.linkto is not None:
            name = self.name + ' -> ' + self.linkto
        else:
            name = self.name

        sz = len(name)
        if width >= sz:
            return name.ljust(width)

        width -= 1
        ext_beg = name.rfind('.')
        if ext_beg > 0:
            return '{}~{}'.format(name[:width - (sz-ext_beg)], name[ext_beg:])
        else:
            return name[:width]+'~'

    @property
    def highlight_content(self):
        width = VimCurWinWidth()
        levelPad = '  '*self.level
        size_info = self.size.rjust(file_sz_display_wid+1)

        left = levelPad
        right = size_info

        def c(msg):
            return c256(msg, self.highlight, self.is_cursor_on)

        if has_hooker('node_highlight_content_l', 'node_highlight_content_r'):
            left_extra = ''
            left_extra_len = 0
            for hooker in Hookers['node_highlight_content_l']:
                l_s, l_h = hooker(self)
                left_extra_len += len(l_s)
                left_extra += c256(l_s, l_h, False)

            right_extra = ''
            right_extra_len = 0
            for hooker in Hookers['node_highlight_content_r']:
                r_s, r_h = hooker(self)
                right_extra_len += len(r_s)
                right_extra += c256(r_s, r_h, False)

            return c(left) +\
                left_extra +\
                c(self.abbrev_name(width-len(left)-len(right)-left_extra_len-right_extra_len)) +\
                c(right) +\
                right_extra
        else:
            return c('{}{}{}'.format(left, self.abbrev_name(width-len(left)-len(right)), right))

    def __init__(self, fullpath, name, fs, level=0):
        self.fullpath = fullpath
        self.re_stat(fs)
        highlight = self.decide_hi()
        super(EntryNode, self).__init__(fullpath, name, highlight, level=level)
        self.ori_highlight = self.highlight

    def re_stat(self, fs):
        self.linkto = None
        if os.path.islink(self.fullpath):
            self.linkto = os.readlink(self.fullpath)

        try:
            self.stat = os.stat(self.fullpath)
        except IOError:
            assert self.linkto is not None
            self.stat = None

        if self.stat:
            try:
                self.size = fs.size_str(self.fullpath, self.stat)
            except PermissionError:
                self.size = '?'

            self.acl = fs.acl_str(self.stat)
            try:
                if platform == "win32":
                    self.user = getenv("USERNAME")
                    self.group = getenv("USERDOMAIN")
                else:
                    self.user = pwd.getpwuid(self.stat.st_uid)[0]
                    self.group = grp.getgrgid(self.stat.st_gid)[0]
            except KeyError:
                self.user = self.stat.st_uid
                self.group = self.stat.st_gid
        else:
            self.size = ''
            self.acl = ''
            self.user = ''
            self.group = ''

    def decide_hi(self):
        if self.linkto is not None:
            if self.stat is None:
                return default.color['brokenlink']
            else:
                return default.color['link']
        elif self.acl[0] == 'd':
            return default.color['dir']
        elif os.access(self.fullpath, os.X_OK):
            return default.color['exe']
        else:
            return default.color['file']

    def rename(self, name):
        ori = self.fullpath
        dirname = os.path.dirname(self.fullpath)
        self.fullpath = os.path.join(dirname, name)
        self.name = name
        return ori

    def change_dirname(self, oridirname, dirname):
        self.fullpath = os.path.join(dirname, self.fullpath[len(oridirname)+1:])

    def toggle_pick(self):
        if self.state == Node.State.NORMAL:
            self.state = Node.State.PICKED
            self.set_highlight(default.color['pick'])
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
    """
    Content node for directory.
    """
    def __init__(self, fullpath, name, fs, level=0):
        self.expanded = False
        super(DirNode, self).__init__(fullpath, name, fs, level)

    @property
    def isDir(self):
        return True


class NetRangerBuf(object):
    """
    Main (mvc) model/view. Each netranger buffer corresponds to a directory and keeps a list of file/directory nodes and display them in a vim buffer.
    """
    header_height = None

    @property
    def first_content_lineNo(self):
        """
        Return the height of header (or minus 1 if the content is empty).
        """
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
        self.nodes_order_outdated = False

        self.vim.command('silent file N:{}'.format(os.path.basename(wd)))
        self.vim.command('lcd ' + wd)

        self.nodes = [CWDNode(wd)] + self.createNodes(self.wd)
        self.clineNo = self.first_content_lineNo
        self.nodes[self.clineNo].cursor_on()
        # In refresh_buf we need to check the mtime of all expanded nodes to see if any content in the buffer is changed. Adding the CWDNode simply means we check the mtime of the wd everytime.
        self.expanded_nodes = set([self.nodes[0]])
        self.winwidth = VimCurWinWidth()
        self.temp_header_line = 0
        self.is_editing = False
        self.render()

    def abbrevcwd(self, width):
        res = self.wd.replace(Shell.userhome, '~')
        if len(res) <= width:
            return res.ljust(width)

        sp = res.split('/')
        szm1 = len(sp) - 1
        total = 2*(szm1) + len(sp[-1])
        for i in range(szm1, -1, -1):
            if total + len(sp[i]) - 1 > width:
                for j in range(i+1):
                    try:
                        sp[j] = sp[j][0]
                    except IndexError:
                        pass
                return '/'.join(sp).ljust(width)
            else:
                total += len(sp[i]) - 1

    def set_header_content(self):
        meta = ''
        curNode = self.curNode
        if not curNode.isHeader:
            curNode.re_stat(self.fs)
            mtime = str(datetime.datetime.fromtimestamp(curNode.stat.st_mtime))[:19]
            meta =' {} {} {} {}'.format(curNode.user, curNode.group, mtime, curNode.acl)
        left = self.abbrevcwd(self.winwidth-len(meta)-1)
        self.vim.command("setlocal modifiable")
        self.nodes[0].name = '{} {}'.format(left, meta).strip()
        self.vim.current.buffer[0] = self.nodes[0].highlight_content
        self.vim.command("setlocal nomodifiable")

    def createNodes(self, wd, level=0):
        nodes = []
        files = self.fs.ls(wd)
        for f in pbar(files):
            if self.shouldIgnore(f):
                continue
            node = self.createNode(wd, f, level)
            nodes.append(node)
        return self.sortNodes(nodes)

    def shouldIgnore(self, basename):
        for ig in VimVar('NETRIgnore'):
            if fnmatch.fnmatch(basename, ig):
                return True
        return False

    def createNode(self, dirname, basename, level):
        fullpath = os.path.join(dirname, basename)
        if os.path.isdir(fullpath):
            return DirNode(fullpath, basename, self.fs, level=level)
        else:
            return EntryNode(fullpath, basename, self.fs, level=level)

    def creat_nodes_if_not_exist(self, nodes, dirpath, level, cheap_remote_ls):
        old_paths = set([node.fullpath for node in nodes if not node.isHeader])
        new_paths = set([os.path.join(dirpath, name) for name in self.fs.ls(dirpath, cheap_remote_ls)])
        new_nodes = []
        for path in new_paths.difference(old_paths):
            name = os.path.basename(path)
            if self.shouldIgnore(name):
                continue
            new_nodes.append(self.createNode(dirpath, name, level+1))
        return new_nodes

    def refresh_nodes(self, cheap_remote_ls=False):
        """
        1. Check the mtime of wd or any expanded subdir changed. If so, set content_outdated true, which could also be set manually (e.g. NETRToggleShowHidden).
        2. For each file/directory in the file system, including those in expanded directories, if no current node corresponds to it, add a new node to the node list so that it will be visible next time.
        3. For each current node, including nodes in expanded directories, if no files/directories corresponds to it or it should be ignore, remove it from the node list so that it will be invisible next time.
        """
        for node in self.expanded_nodes:
            if os.access(node.fullpath, os.R_OK):
                ori_mtime = node.stat.st_mtime
                node.re_stat(self.fs)
                new_mtime = node.stat.st_mtime
                if new_mtime > ori_mtime:
                    self.content_outdated = True

        if not self.content_outdated:
            return

        oriNode = self.curNode

        self.content_outdated = False

        # create nodes corresponding to new files
        new_nodes = self.creat_nodes_if_not_exist(self.nodes, self.wd, -1, cheap_remote_ls)
        fs_files = [set(self.fs.ls(self.wd, cheap_remote_ls))]
        nextValidInd = -1
        for i in range(len(self.nodes)):
            if i<nextValidInd:
                continue

            curNode = self.nodes[i]
            if curNode.isHeader:
                new_nodes.append(curNode)
                continue

            # When the first child of a parent node (directory) is
            # encountered, we push the "context" including the list
            # of existing  files in the parent directory.
            # When curNode is no more a decendent of prevNode,
            # We should reset the "context" to the corresponding parent
            # node.
            prevNode = self.nodes[i-1]
            if curNode.level > prevNode.level and os.path:
                fs_files.append(set(self.fs.ls(prevNode.fullpath, cheap_remote_ls)))
            else:
                fs_files = fs_files[:curNode.level+1]

            # The children of an invalid node will all be invalid
            # Hence, we will start with the next valid node
            if self.shouldIgnore(curNode.name) or curNode.name not in fs_files[-1]:
                nextValidInd = self.next_lesseq_level_ind(i)
                continue

            # create nodes corresponding to new files in expanded directories
            new_nodes.append(curNode)
            if curNode.isDir and curNode.expanded:
                nextInd = self.next_lesseq_level_ind(i)
                new_nodes += self.creat_nodes_if_not_exist(self.nodes[i+1:nextInd+1], curNode.fullpath, curNode.level, cheap_remote_ls)

        self.nodes = self.sortNodes(new_nodes)
        self.render()
        self.setClineNoByNode(oriNode)

    def reverse_sorted_nodes(self, nodes):
        rev = []
        prevLevel = -1
        curInd = 0
        for node in nodes:
            if node.level <= prevLevel:
                for i, n in enumerate(rev):
                    if n.level == node.level:
                        rev.insert(i, node)
                        curInd = i + 1
                        break
            else:
                rev.insert(curInd, node)
                curInd += 1

            prevLevel = node.level
        return rev

    def Sort_prep(self):
        self.nodes_order_outdated = True
        self.lastNodeId = self.nodes[self.clineNo]

    def Sort(self):
        if not self.nodes_order_outdated:
            return
        self.nodes_order_outdated = False
        for i in range(self.header_height, len(self.nodes)):
            self.nodes[i].re_stat(self.fs)
        self.nodes = self.sortNodes(self.nodes)
        self.render()
        self.setClineNoByNode(self.lastNodeId)

    def sortNodes(self, nodes):
        """
        Sort the nodes by their path and SortUI.sort_fn. Information of ancestor are accumulated for subnodes as prefix. To sort directories before files, ' '(ascii 32) is put into the prefix for directories and '~' (ascii 127) is put into the prefix for files. An additional ' ' is put before ' ' or '~' to handle tricky case like 'dir, dir/z, dir2', without which will results in 'dir, dir2, dir/z'.
        """
        sort_fn = SortUI.get_sort_fn()
        reverse = SortUI.reverse
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
                # curNode must be a DirNode, hence the same as in the folloing "curNode.isDir" case
                prefix += '  {}{}'.format(sort_fn(prevNode), prevNode.name)
                prefixEndInd.append(len(prefix))
            else:
                prefixEndInd = prefixEndInd[:curNode.level+1]
                prefix = prefix[:prefixEndInd[-1]]
            if curNode.isDir:
                sortedNodes.append(('{}  {}{}'.format(prefix, sort_fn(curNode), curNode.name), curNode))
            else:
                sortedNodes.append(('{} ~{}{}'.format(prefix, sort_fn(curNode), curNode.name), curNode))

        sortedNodes = sorted(sortedNodes, key=lambda x: x[0])
        sortedNodes = [node[1] for node in sortedNodes]
        if reverse:
            sortedNodes = self.reverse_sorted_nodes(sortedNodes)

        return header_nodes + sortedNodes

    def render(self, plain=False):
        self.vim.command('setlocal modifiable')
        if plain:
            self.vim.current.buffer[:] = self.plain_content
        else:
            self.vim.current.buffer[:] = self.highlight_content
        self.vim.command('setlocal nomodifiable')
        self.moveVimCursor(self.clineNo)
        self.winwidth = VimCurWinWidth()

    def render_if_winwidth_changed(self):
        if self.winwidth != VimCurWinWidth():
            self.render()

    def on_cursormoved(self):
        """
        Remember the current line no. and refresh the highlight of the current line no.
        """
        if self.is_editing:
            return
        lineNo = int(self.vim.eval("line('.')")) - 1
        self.setClineNo(lineNo)
        self.set_header_content()
        self.vim.command("setlocal modifiable")

        # Afer the number of nodes decrease (e.g. toggle show hidden), temp_header_line
        # might exceeds total number of line. In such case, reset it to 0.
        if self.temp_header_line >= len(self.nodes):
            self.temp_header_line = 0

        self.vim.current.buffer[self.temp_header_line] = self.nodes[self.temp_header_line].highlight_content
        first_visible_line = int(self.vim.eval('line("w0")'))-1
        if first_visible_line > 0:
            if first_visible_line == int(self.vim.eval("line('.')")) - 1:
                # keep current line to be 2nd line if current line is 1st line
                self.vim.command("normal! ")
                first_visible_line -= 1
            self.temp_header_line = first_visible_line
            self.vim.current.buffer[first_visible_line] = self.nodes[0].highlight_content
        self.vim.command("setlocal nomodifiable")

    def moveVimCursor(self, lineNo):
        """
        Will trigger on_cursormoved
        """
        self.vim.command('call cursor({},1)'.format(lineNo+1))

    def setClineNoByPath(self, path):
        """ Real work is done in on_cursormoved. Eventually call setClineNo. """
        for i in range(self.header_height, len(self.nodes)):
            if self.nodes[i].fullpath == path:
                self.moveVimCursor(i)
                break

    def setClineNoByNode(self, node):
        """ Real work is done in on_cursormoved. Eventually call setClineNo. """
        if node in self.nodes:
            self.moveVimCursor(self.nodes.index(node))
        else:
            self.moveVimCursor(self.first_content_lineNo)

    def setClineNo(self, newLineNo):
        """
        Turn on newLineNo and turn off self.clineNo.
        """
        if newLineNo == self.clineNo:
            self.nodes[newLineNo].cursor_on()
            self.refresh_lines_hi([newLineNo])
            return

        oc = self.clineNo
        self.clineNo = newLineNo
        if oc < len(self.nodes):
            self.nodes[oc].cursor_off()
        self.nodes[newLineNo].cursor_on()
        self.refresh_lines_hi([oc, newLineNo])

    def refresh_lines_hi(self, lineNos):
        self.vim.command('setlocal modifiable')

        sz = min(len(self.nodes), len(self.vim.current.buffer))
        for i in lineNos:
            if i < sz:
                self.vim.current.buffer[i] = self.nodes[i].highlight_content
        self.vim.command('setlocal nomodifiable')

    def refresh_clineNo(self):
        if self.clineNo == self.vim.eval("line('.')") - 1:
            return

    def refresh_highlight(self):
        """
        Refresh the highlight of nodes in highlight_outdated_nodes. Rather expensive, so consider use refresh_line_hi or refresh_cur_line_hi if possible.
        """
        if not self.highlight_outdated:
            return
        lines = []
        for i, node in enumerate(self.nodes):
            if node in self.highlight_outdated_nodes:
                lines.append(i)
        self.refresh_lines_hi(lines)
        self.highlight_outdated_nodes.clear()

    def refresh_cur_line_hi(self):
        self.refresh_lines_hi([self.clineNo])

    def ToggleExpand(self):
        """
        Create subnodes for the target directory. Also record the mtime of the target directory so that we can refresh the buffer content (refresh_nodes) if the subdirectory is changed.
        """
        curNode = self.curNode
        if not curNode.isDir:
            return
        if curNode.expanded:
            self.expanded_nodes.remove(curNode)
            endInd = self.next_lesseq_level_ind(self.clineNo)
            self.nodes = self.nodes[:self.clineNo+1] + self.nodes[endInd:]
        else:
            self.expanded_nodes.add(curNode)
            newNodes = self.createNodes(self.curNode.fullpath, curNode.level+1)
            if len(newNodes)>0:
                self.nodes = self.nodes[:self.clineNo+1] + newNodes + self.nodes[self.clineNo+1:]
        curNode.expanded = not curNode.expanded
        self.render()

    def Edit(self):
        self.is_editing = True
        self.render(plain=True)
        self.vim.command('setlocal modifiable')
        self.vim.command('setlocal wrap')

    def Save(self):
        """
        Rename the files according to current buffer content.
        Retur false if called but is_editing is false. Otherwise return true.
        """
        if not self.is_editing:
            return False
        self.is_editing = False

        vimBuf = self.vim.current.buffer
        if len(self.nodes) != len(vimBuf):
            VimErrorMsg('Edit mode can not add/delete files!')
            self.render()
            return True

        oriNode = self.curNode

        change = {}
        i = 0
        for i in range(len(vimBuf)):
            line = vimBuf[i].strip()
            if not self.nodes[i].isHeader and line != self.nodes[i].name:

                # change name of the i'th node
                oripath = self.nodes[i].rename(line)
                change[oripath] = self.nodes[i].fullpath

                # change dirname of subnodes
                endInd = self.next_lesseq_level_ind(begInd=i)
                for j in range(i+1, endInd):
                    self.nodes[j].change_dirname(oripath, self.nodes[i].fullpath)

        # apply the changes
        for oripath, fullpath in change.items():
            self.fs.rename(oripath, fullpath)

        self.nodes = self.sortNodes(self.nodes)
        self.render()
        self.setClineNoByNode(oriNode)
        self.vim.command('setlocal nowrap')
        self.vim.command('setlocal nomodifiable')
        return True

    def Cut(self, nodes):
        for node in nodes:
            node.cut()
        self.highlight_outdated_nodes.update(nodes)

    def Copy(self, nodes):
        for node in nodes:
            node.copy()
        self.highlight_outdated_nodes.update(nodes)

    def find_next_ind(self, nodes, ind, pred):
        beg_node = nodes[ind]
        ind += 1
        sz = len(self.nodes)
        while ind < sz:
            if pred(beg_node, nodes[ind]):
                break
            ind += 1
        return ind

    def next_lesseq_level_ind(self, begInd, nodes=None):
        if nodes is None:
            nodes = self.nodes
        return self.find_next_ind(nodes, begInd, lambda beg, new: new.level<=beg.level)


class Netranger(object):
    """
    Main  (mvc) controler. Main functions are:
    1. on_bufenter: create / update netr buffers
    2. invoke_map: invoke one of NETR* function on user key press
    """
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
        self.pinnedRoots = set()
        self.picked_nodes = defaultdict(set)
        self.cut_nodes, self.copied_nodes= defaultdict(set), defaultdict(set)
        self.bookmarkUI = None
        self.helpUI = None
        self.sortUI = None
        self.askUI = None
        self.onuiquit = None
        self.onuiquitNumArgs = 0
        self.fs = FS()
        self.rclone = None

        self.initVimVariables()
        self.initKeymaps()
        Shell.mkdir(default.variables['NETRRootDir'])
        self.rifle = Rifle(self.vim, VimVar('NETRRifleFile'))
        ignore_pat = list(VimVar('NETRIgnore'))
        self.vim.vars['NETRemoteCacheDir'] = os.path.expanduser(VimVar('NETRemoteCacheDir'))
        if '.*' not in ignore_pat:
            ignore_pat.append('.*')
            self.vim.vars['NETRIgnore'] = ignore_pat

    def initVimVariables(self):
        for k, v in default.variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v
        self.reset_default_colors()

        for k,v in default.internal_variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v

    def reset_default_colors(self):
        for name, color in VimVar('NETRColors').items():
            if name not in default.color:
                VimErrorMsg('netranger: {} is not a valid NETRColors key!')
                continue
            if type(color) is int and (color<0 or color>255):
                VimErrorMsg('netranger: Color value should be within 0~255')
                continue
            elif type(color) is str and color not in colortbl:
                VimErrorMsg('netranger: {} is not a valid color name!')
                continue

            default.color[name] = color

    def initKeymaps(self):
        """
        Add key mappings to NETR* functions for netranger buffers. Override or skip some default mappings on user demand.
        """
        self.keymaps = {}
        self.keymap_doc = {}
        skip = []
        for k in VimVar('NETRDefaultMapSkip'):
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
                self.vim.command('nnoremap <nowait> <silent> <buffer> {} :exe ":call _NETRInvokeMap({})"<CR>'.format(k, "'" + fn + "'"))

    def on_bufenter(self, bufnum):
        """
        There are four cases on bufenter:
        1. The buffer is not a netranger buffer: do nothing
        2. The buffer is a existing netranger buffer: refresh buffer content (e.g. directory content changed else where) and call any pending onuiquit functions
        3. The buffer is a [No Name] temporary buffer and the buffer name is a directory. Then we either create a new netranger buffer or bring up an existing netranger buffer
        """
        if bufnum in self.bufs:
            self.refresh_curbuf()
            if self.onuiquit is not None:
                # If not enough arguments are passed, ignore the pending onuituit, e.g. quit the bookmark go ui without pressing key to specify where to go.
                if len(VimVar('NETRRegister')) == self.onuiquitNumArgs:
                    self.onuiquit(*VimVar('NETRRegister'))
                self.onuiquit = None
                self.vim.vars['NETRRegister'] = []
                self.onuiquitNumArgs = 0
        else:
            bufname = self.vim.current.buffer.name
            if len(bufname)>0 and bufname[-1] == '~':
                bufname = os.path.expanduser('~')
            if not os.path.isdir(bufname):
                return

            bufname = os.path.abspath(bufname)
            if self.buf_existed(bufname):
                self.show_existing_buf(bufname)
            else:
                self.gen_new_buf(bufname)

    def refresh_curbuf(self):
        curBuf = self.curBuf
        # manually turn off highlight of current linen as synchronous on_bufenter block on_cursormoved event handler
        curBuf.curNode.cursor_off()
        curBuf.refresh_nodes()
        curBuf.refresh_highlight()
        curBuf.Sort()
        curBuf.render_if_winwidth_changed()
        # ensure pwd is correct
        self.vim.command('lcd ' + curBuf.wd)

    def show_existing_buf(self, bufname):
        ori_bufnum = self.vim.current.buffer.number
        existed_bufnum = self.wd2bufnum[bufname]
        self.vim.command('{}b'.format(existed_bufnum))
        self.setBufOption()
        buf = self.bufs[existed_bufnum]
        self.refresh_curbuf()
        if ori_bufnum not in self.bufs:
            # wipe out the [No Name] temporary buffer
            self.vim.command('bwipeout {}'.format(ori_bufnum))
        buf.moveVimCursor(buf.clineNo)

    def gen_new_buf(self, bufname):
        bufnum = self.vim.current.buffer.number
        if(bufname.startswith(VimVar('NETRemoteCacheDir'))):
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
        self.vim.command('setlocal nobuflisted')
        self.vim.command('setlocal nospell')
        self.vim.command('setlocal bufhidden=hide')
        self.vim.command('setlocal conceallevel=3')
        self.vim.command('set concealcursor=nvic')
        self.vim.command('setlocal nocursorline')

    def on_cursormoved(self, bufnum):
        """
        refresh buffer highlight when cursor is moved.
        @param bufnum: current buffer number
        """
        if bufnum in self.bufs:
            self.bufs[bufnum].on_cursormoved()

    def pend_onuiquit(self, fn, numArgs=0):
        """
        Can be called by any UI. Used for waiting for user input in some UI and then defer what to do when the UI window is quit and the netranger buffer gain focus again. Function arguments are passed as a list via vim variable g:'NETRRegister'.
        @param fn: function to be executed
        @param numArgs: number of args expected to see in g:'NETRRegister'. When exectuing fn, if numArgs do not match, fn will not be executed. (e.g. User press no keys in BookMarkGo UI but simply quit the UI)
        """
        self.onuiquit = fn
        self.onuiquitNumArgs = numArgs

    def NETROpen(self, open_cmd=None, rifle_cmd=None, use_rifle=True):
        """
        The real work for opening directories is handled in on_bufenter. For openning files, we check if there's rifle rule to open the file. Otherwise, open it in vim.
        """
        curNode = self.curNode
        if curNode.isHeader:
            return

        if open_cmd is None:
            if curNode.isDir:
                open_cmd = 'edit'
            else:
                open_cmd = VimVar('NETROpenCmd')

        fullpath = curNode.fullpath
        if curNode.isDir:
            if curNode.size == '?' or curNode.size == '':
                VimErrorMsg('Permission Denied: {}'.format(curNode.name))
                return
            self.vim.command('silent {} {}'.format(open_cmd, fullpath))
            # manually call on_bufenter as vim might not trigger BufEnter with the above command
            self.on_bufenter(self.vim.eval("winnr()"))
        else:
            if self.rclone is not None and self.isRemotePath(fullpath):
                self.rclone.ensure_downloaded(fullpath)

            if rifle_cmd is None:
                rifle_cmd = self.rifle.decide_open_cmd(fullpath)

            if use_rifle and rifle_cmd is not None:
                Shell.run_async(rifle_cmd.format(fullpath))
            else:
                try:
                    self.vim.command('{} {}'.format(open_cmd, fullpath))
                except Exception as e:
                    err_msg = str(e)
                    if 'E325' not in err_msg:
                        VimErrorMsg(err_msg)

    def NETRefresh(self):
        clineNo = self.curBuf.clineNo
        self.gen_new_buf(self.curBuf.wd)
        self.curBuf.moveVimCursor(clineNo)

    def NETRTabOpen(self):
        self.NETROpen('tabedit', use_rifle=False)

    def NETRTabBgOpen(self):
        self.NETROpen('tabedit', use_rifle=False)
        self.vim.command('tabprevious')

    def NETRBufOpen(self):
        self.NETROpen('edit', use_rifle=False)

    def NETRBufVSplitOpen(self):
        self.NETROpen(VimVar('NETRSplitOrientation') + ' vsplit', use_rifle=False)

    def NETRBufHSplitOpen(self):
        self.NETROpen(VimVar('NETRSplitOrientation') + ' split', use_rifle=False)

    def NETRBufPanelOpen(self):
        if self.curNode.isDir:
            return

        if len(self.vim.current.tabpage.windows) == 1:
            self.NETROpen(VimVar('NETRSplitOrientation') + ' vsplit', use_rifle=False)
            newsize = VimCurWinWidth()*VimVar('NETRPanelSize')
            self.vim.command('vertical resize {}'.format(newsize))
        else:
            fpath = self.curNode.fullpath
            self.vim.command('wincmd l')
            self.vim.command('edit {}'.format(fpath))

    def NETRAskOpen(self):
        fullpath = self.curNode.fullpath
        if self.askUI is None:
            self.askUI = AskUI(self.vim, self)
        self.askUI.ask(self.rifle.list_available_cmd(fullpath), fullpath)

    def NETRParentDir(self):
        """ Real work is done in on_bufenter """
        curBuf = self.curBuf
        cwd = curBuf.wd
        if cwd in self.pinnedRoots:
            return
        pdir = self.fs.parent_dir(cwd)
        self.vim.command('silent edit {}'.format(pdir))
        # manually call on_bufenter as vim might not trigger BufEnter with the above command
        self.on_bufenter(self.vim.eval("winnr()"))
        curBuf = self.curBuf
        curBuf.setClineNoByPath(cwd)
        # manually call on_cursormoved as synchronous on_bufenter block on_cursormoved event handler
        curBuf.on_cursormoved()

    def NETRVimCD(self):
        curName = self.curNode.fullpath
        if os.path.isdir(curName):
            self.vim.command('silent lcd {}'.format(curName))
        else:
            self.vim.command('silent lcd {}'.format(os.path.dirname(curName)))

    def NETRToggleExpand(self):
        self.curBuf.ToggleExpand()

    def NETREdit(self):
        for fn, keys in self.keymaps.items():
            if fn == 'NETRSave':
                continue
            for k in keys:
                self.vim.command("nunmap <silent> <buffer> {}".format(k))
        self.curBuf.Edit()

    def NETRSave(self):
        if self.curBuf.Save():
            self.map_keys()

    def NETRTogglePinRoot(self):
        cwd = self.cwd
        if cwd in self.pinnedRoots:
            self.pinnedRoots.remove(cwd)
        else:
            self.pinnedRoots.add(cwd)

    def NETRToggleShowHidden(self):
        """
        Change ignore pattern and mark all existing netranger buffers to be content_outdated so that their content will be updated when entered again.
        """
        ignore_pat = VimVar('NETRIgnore')
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
        self.vim.command('silent edit {}'.format(fullpath))
        # manually do the same thing like in on_bufenter as synchronous on_bufenter block (nested) on_bufenter event handler
        if self.buf_existed(fullpath):
            self.show_existing_buf(fullpath)
        else:
            self.gen_new_buf(fullpath)

    def NETRBookmarkEdit(self):
        self.initBookMarkUI()
        self.bookmarkUI.edit()

    def NETRSort(self):
        if self.sortUI is None:
            self.sortUI = SortUI(self.vim)
        self.sortUI.show()
        self.pend_onuiquit(self.sort_onuiiquit, numArgs=1)

    def sort_onuiiquit(self, opt):
        SortUI.reverse = opt.isupper()
        SortUI.select_sort_fn(opt.lower())
        for buf in self.bufs.values():
            buf.Sort_prep()
        self.curBuf.Sort()

    def NETRHelp(self):
        if self.helpUI is None:
            self.helpUI = HelpUI(self.vim, self.keymap_doc)
        self.helpUI.show()

    def NETRTogglePick(self):
        """
        Funciton to Add or remove curNode to/from picked_nodes. Also update the highlight of the current line.
        """
        curNode = self.curNode
        curBuf = self.curBuf
        res = curNode.toggle_pick()
        if res == Node.ToggleOpRes.ON:
            self.picked_nodes[curBuf].add(curNode)
        elif res == Node.ToggleOpRes.OFF:
            self.picked_nodes[curBuf].remove(curNode)
        self.curBuf.refresh_cur_line_hi()

    def NETRCut(self):
        """
        Move picked_nodes to cut_nodes. All buffers containing picked nodes are marked as highlight_outdated so that their highlight will be updated when entered again.
        """
        for buf, nodes in self.picked_nodes.items():
            buf.Cut(nodes)
            self.cut_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.curBuf.refresh_highlight()

    def NETRCutSingle(self):
        curBuf = self.curBuf
        curNode = self.curNode
        curNode.cut()
        self.cut_nodes[curBuf].add(curNode)
        curBuf.refresh_cur_line_hi()

    def NETRCopy(self):
        """
        Move picked_nodes to copied_nodes. All buffers containing picked nodes are marked as highlight_outdated so that their highlight will be updated when entered again.
        """
        for buf, nodes in self.picked_nodes.items():
            buf.Copy(nodes)
            self.copied_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.curBuf.refresh_highlight()

    def NETRCopySingle(self):
        curBuf = self.curBuf
        curNode = self.curNode
        curNode.copy()
        self.copied_nodes[curBuf].add(curNode)
        curBuf.refresh_cur_line_hi()

    def NETRPaste(self):
        """
        Perform mv from cut_nodes or cp from copied_nodes to cwd. For each source (cut/copy) buffer, reset the highlight of the cut/copied nodes and mark the buffer as highlight_outdated so that the highlight will be updated when entered again.
        """
        cwd = self.vim.eval('getcwd()')
        cwd_is_remote = self.isRemotePath(cwd)
        alreday_moved = set()
        for buf, nodes in self.cut_nodes.items():
            # TODO do we really need to update buf.highlight_outdated here?
            buf.highlight_outdated_nodes.update(nodes)

            # For all ancestor directories of the source directory,
            # It's possible that their content contains the cutted
            # entry (by expansion). Hence we also mark them as content_outdated
            wd = buf.wd
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
                    fs = self.rclone if cwd_is_remote else buf.fs
                    fs.mv(node.fullpath, cwd)
                    alreday_moved.add(node.fullpath)

        for buf, nodes in self.copied_nodes.items():
            buf.highlight_outdated_nodes.update(nodes)
            for node in nodes:
                node.reset_highlight()
                fs = self.rclone if cwd_is_remote else buf.fs
                fs.cp(node.fullpath, cwd)

        self.cut_nodes = defaultdict(set)
        self.copied_nodes = defaultdict(set)
        self.curBuf.refresh_nodes(cheap_remote_ls=True)
        self.curBuf.refresh_highlight()

    def NETRDelete(self, force=False):
        for buf, nodes in self.picked_nodes.items():
            buf.content_outdated = True
            for node in nodes:
                buf.fs.rm(node.fullpath, force)
        curBuf = self.curBuf
        clineNo = curBuf.clineNo
        curBuf.refresh_nodes(cheap_remote_ls=True)
        curBuf.moveVimCursor(clineNo)
        self.picked_nodes = defaultdict(set)

    def NETRDeleteSingle(self, force=False):
        curBuf = self.curBuf
        curBuf.fs.rm(self.curNode.fullpath, force)
        curBuf.refresh_nodes(cheap_remote_ls=True)
        curBuf.moveVimCursor(curBuf.clineNo)

    def NETRForceDelete(self):
        self.NETRDelete(force=True)

    def NETRForceDeleteSingle(self):
        self.NETRDeleteSingle(force=True)

    def isRemotePath(self, path):
        return path.startswith(VimVar('NETRemoteCacheDir'))

    def NETRemotePull(self):
        """
        Sync local so that the local content of the current directory will be the same as the remote content.
        """
        try:
            curBuf = self.curBuf
        except KeyError:
            VimErrorMsg('Not a netranger buffer')
            return

        if not self.isRemotePath(curBuf.wd):
            VimErrorMsg('Not a remote directory')
        else:
            self.rclone.sync(curBuf.wd, Rclone.SyncDirection.DOWN)
        curBuf.refresh_nodes(cheap_remote_ls=True)

    def NETRemotePush(self):
        """
        Sync remote so that the remote content of the current directory will be the same as the local content.
        """
        try:
            curBuf = self.curBuf
        except KeyError:
            VimErrorMsg('Not a netranger buffer')
            return

        if not self.isRemotePath(curBuf.wd):
            VimErrorMsg('Not a remote directory')
        else:
            self.rclone.sync(curBuf.wd, Rclone.SyncDirection.UP)

    def NETRemoteList(self):
        if self.rclone is None:
            Rclone.valid_or_install(self.vim)
            self.rclone = Rclone(VimVar('NETRemoteCacheDir'), VimVar('NETRemoteRoots'))

        if self.rclone.has_remote:
            self.vim.command('tabe ' + VimVar('NETRemoteCacheDir'))
        else:
            VimErrorMsg("There's no remote now. Run 'rclone config' in a terminal to setup remotes")
