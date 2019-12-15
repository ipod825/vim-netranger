from __future__ import absolute_import, print_function

import datetime
import fnmatch
import os
import re
from collections import defaultdict
from sys import platform

from netranger import Vim, default
from netranger.api import NETRApi
from netranger.colortbl import colorhexstr2ind, colorname2ind
from netranger.config import file_sz_display_wid
from netranger.enum import Enum
from netranger.fs import FSTarget, LocalFS, Rclone
from netranger.rifle import Rifle
from netranger.shell import Shell
from netranger.thirdparty.wcwidth.wcwidth import wcswidth
from netranger.ui import AskUI, BookMarkUI, HelpUI, NewUI, PreviewUI, SortUI

if platform == "win32":
    from os import getenv
else:
    import pwd
    import grp


def c256(msg, c, background):
    if background:
        return '[38;5;{};7m{}[0m'.format(c, msg)
    else:
        return '[38;5;{}m{}[0m'.format(c, msg)


class Node(object):
    """General node.

    Inherited by header nodes or entry nodes.
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
        self.highlight = highlight

    @property
    def highlight_content(self):
        return c256(self.name, self.highlight, self.is_cursor_on)

    @property
    def is_DIR(self):
        return False

    @property
    def is_INFO(self):
        return False

    def cursor_on(self):
        self.is_cursor_on = True

    def cursor_off(self):
        self.is_cursor_on = False

    def toggle_pick(self):
        return Node.ToggleOpRes.INVALID

    def re_stat(self):
        pass


class FooterNode(Node):
    def __init__(self):
        super(FooterNode, self).__init__("METAINFO", "METAINFO",
                                         default.color['footer'])

    @property
    def is_INFO(self):
        return True


class HeaderNode(Node):
    def __init__(self, fullpath):
        super(HeaderNode, self).__init__(fullpath,
                                         Shell.abbrevuser(fullpath),
                                         default.color['cwd'],
                                         level=0)
        self.re_stat()

    def re_stat(self):
        self.stat = os.stat(self.fullpath)

    @property
    def highlight_content(self):
        return c256(self.name, self.highlight, False)

    @property
    def is_INFO(self):
        return True


class EntryNode(Node):
    """Content node."""

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
            return '{}~{}'.format(name[:width - (sz - ext_beg)],
                                  name[ext_beg:])
        else:
            return name[:width] + '~'

    @property
    def highlight_content(self):
        width = self.buf.winwidth
        levelPad = '  ' * self.level
        size_info = self.size.rjust(file_sz_display_wid + 1)

        left = levelPad
        right = size_info

        def c(msg):
            return c256(msg, self.highlight, self.is_cursor_on)

        if NETRApi.HasHooker('node_highlight_content_l',
                             'node_highlight_content_r'):
            left_extra = ''
            left_extra_len = 0
            for hooker in NETRApi.Hookers['node_highlight_content_l']:
                l_s, l_h = hooker(self)
                left_extra_len += wcswidth(l_s)
                left_extra += c256(l_s, l_h, False)

            right_extra = ''
            right_extra_len = 0
            for hooker in NETRApi.Hookers['node_highlight_content_r']:
                r_s, r_h = hooker(self)
                right_extra_len += wcswidth(r_s)
                right_extra += c256(r_s, r_h, False)

            # Calling c and concatenation multiple times is rather expensive.
            # Hence we avoid it if possible.
            if left_extra_len or right_extra_len:
                return c(left) + left_extra + c(
                    self.abbrev_name(width - len(left) - len(right) -
                                     left_extra_len -
                                     right_extra_len)) + c(right) + right_extra

        return c('{}{}{}'.format(
            left, self.abbrev_name(width - len(left) - len(right)), right))

    @property
    def mtime(self):
        if self.stat:
            return str(datetime.datetime.fromtimestamp(
                self.stat.st_mtime))[:19]
        else:
            return ''

    def __init__(self, fullpath, name, level=0, buf=None):
        self.fullpath = fullpath
        self.buf = buf
        self.re_stat(lazy=Vim.Var('NETRLazyLoadStat'))
        highlight = self.decide_hi()
        super(EntryNode, self).__init__(fullpath, name, highlight, level=level)
        self.ori_highlight = self.highlight

    def re_stat(self, lazy=False):
        self.linkto = None
        if os.path.islink(self.fullpath):
            try:
                self.linkto = os.readlink(self.fullpath)
            except PermissionError:  # added eyal
                self.stat = None
            except FileNotFoundError:
                self.stat = None
        if not lazy:
            try:
                self.stat = os.stat(self.fullpath)
            except PermissionError:  # added eyal
                self.stat = None
            except FileNotFoundError:
                self.stat = None
        else:
            self.stat = None

        if self.stat:
            try:
                self.size = LocalFS.size_str(self.fullpath, self.stat)
            except PermissionError:
                self.size = '?'

            self.acl = LocalFS.acl_str(self.stat)
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
            if os.path.exists(self.fullpath):
                return default.color['link']
            else:
                return default.color['brokenlink']
        elif self.is_DIR:
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
        self.fullpath = os.path.join(dirname,
                                     self.fullpath[len(oridirname) + 1:])

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

    def reset_hi(self):
        self.state = Node.State.NORMAL
        self.highlight = self.ori_highlight


class DirNode(EntryNode):
    """Content node for directory."""

    def __init__(self, *args, **kwargs):
        self.expanded = False
        super(DirNode, self).__init__(*args, **kwargs)

    @property
    def is_DIR(self):
        return True


class NetRangerBuf(object):
    """Main (mvc) model/view.

    Each netranger buffer corresponds to a directory and keeps a list of
    file/directory nodes and display them in a vim buffer.
    """

    @property
    def highlight_content(self):
        return [n.highlight_content for n in self.nodes]

    @property
    def plain_content(self):
        return [n.name for n in self.nodes]

    @property
    def cur_node(self):
        return self.nodes[self.clineNo]

    @property
    def highlight_outdated(self):
        return 0 < len(self.highlight_outdated_nodes)

    def nodes_plus_header_footer(self, nodes):
        return [self.header_node] + nodes + [self.footer_node]

    def __init__(self, controler, wd, fs):
        self.controler = controler
        self.wd = wd
        self.last_vim_pwd = self.wd
        self.fs = fs
        self.num_fs_op = 0
        self.pending_on_cursormoved_post = 0
        self.last_on_curosormoved_lineNo = -1

        self.content_outdated = False
        self.highlight_outdated_nodes = set()
        self.nodes_order_outdated = False

        if Vim.Var('NETRAutochdir'):
            Vim.command('lcd ' + wd)

        self.header_node = HeaderNode(wd)
        self.footer_node = FooterNode()
        self.nodes = self.nodes_plus_header_footer(self.create_nodes(self.wd))

        self.clineNo = 1
        self.nodes[self.clineNo].cursor_on()
        # In refresh_buf we need to check the mtime of all expanded nodes to
        # see if any content in the buffer is changed. Adding the HeaderNode
        # simply means we check the mtime of the wd everytime.
        self.expanded_nodes = set([self.header_node])
        self.winwidth = Vim.CurWinWidth()
        self.pseudo_header_lineNo = None
        self.pseudo_footer_lineNo = None
        self.is_editing = False
        self.visual_start_line = 0
        self.vim_buf_handel = Vim.current.buffer
        self.render()

    def fs_busy(self, echo=True):
        if self.num_fs_op > 0:
            if echo:
                Vim.ErrorMsg(
                    'Previous operation that might change the view is not done'
                    ' yet. Try again later')
            return True
        else:
            return False

    def inc_num_fs_op(self):
        self.num_fs_op += 1

    def dec_num_fs_op(self):
        self.num_fs_op -= 1

    def abbrev_cwd(self, width):
        res = self.wd.replace(Shell.userhome, '~')
        if len(res) <= width:
            return res.ljust(width)

        sp = res.split('/')
        szm1 = len(sp) - 1
        total = 2 * (szm1) + len(sp[-1])
        for i in range(szm1, -1, -1):
            if total + len(sp[i]) - 1 > width:
                for j in range(i + 1):
                    try:
                        sp[j] = sp[j][0]
                    except IndexError:
                        pass
                return '/'.join(sp).ljust(width)
            else:
                total += len(sp[i]) - 1

    def set_header_content(self):
        self.header_node.name = self.abbrev_cwd(self.winwidth).strip()
        Vim.current.buffer[0] = self.header_node.highlight_content

    def set_footer_content(self):
        meta = ''
        cur_node = self.cur_node
        if not cur_node.is_INFO:
            cur_node.re_stat()
            meta = ' {} {} {} {}'.format(cur_node.acl, cur_node.user,
                                         cur_node.group, cur_node.mtime)
        self.footer_node.name = meta.strip()
        Vim.current.buffer[-1] = self.footer_node.highlight_content

    def set_pseudo_header_content(self, clineNo):
        # recover content for the last line occupied by pseudo header
        # ignore error when buffer no longer has the last line
        if self.pseudo_header_lineNo is not None:
            try:
                Vim.current.buffer[self.pseudo_header_lineNo] = self.nodes[
                    self.pseudo_header_lineNo].highlight_content
            except IndexError:
                pass

        # if first visible line is not the first line
        # we need to put header content on the first visible line
        first_visible_line = int(Vim.eval('line("w0")')) - 1
        if first_visible_line > 0:
            # if current line is at the header we need to keep the current line
            # to be 2nd visible line
            if first_visible_line == clineNo:
                Vim.command("normal! ")
                first_visible_line -= 1
            self.pseudo_header_lineNo = first_visible_line
            Vim.current.buffer[
                first_visible_line] = self.header_node.highlight_content
        else:
            self.pseudo_header_lineNo = None

    def set_pseudo_footer_content(self, clineNo):
        # recover content for the last line occupied by pseudo footer
        # ignore error when buffer no longer has the last line
        if self.pseudo_footer_lineNo is not None:
            try:
                Vim.current.buffer[self.pseudo_footer_lineNo] = self.nodes[
                    self.pseudo_footer_lineNo].highlight_content
            except IndexError:
                pass

        # if last visible line is not the last line
        # we need to put footer content on the last visible line
        last_visible_line = int(Vim.eval('line("w$")')) - 1
        if last_visible_line < int(Vim.eval("line('$')")) - 1:
            # if current line is at the footer we need to keep the current line
            # to be penultimate visible line
            if last_visible_line == clineNo:
                Vim.command("normal! ")
                last_visible_line += 1
            self.pseudo_footer_lineNo = last_visible_line
            Vim.current.buffer[
                last_visible_line] = self.footer_node.highlight_content
        else:
            self.pseudo_footer_lineNo = None

    def create_nodes(self, wd, level=0):
        nodes = self.create_nodes_with_file_names(self.fs.ls(wd), wd, level)
        return self.sort_nodes(nodes)

    def create_nodes_with_file_names(self, files, dirpath, level):
        files = [f for f in files if not self.controler.should_ignore(f)]
        return [self.create_node(dirpath, f, level) for f in files]

    def create_node(self, dirname, basename, level):
        fullpath = os.path.join(dirname, basename)
        if os.path.isdir(fullpath):
            return DirNode(fullpath, basename, level=level, buf=self)
        else:
            return EntryNode(fullpath, basename, level=level, buf=self)

    def creat_nodes_if_not_exist(self, nodes, dirpath, level, cheap_remote_ls):
        old_paths = set([node.fullpath for node in nodes if not node.is_INFO])
        new_paths = set([
            os.path.join(dirpath, name)
            for name in self.fs.ls(dirpath, cheap_remote_ls)
        ])
        file_names = [
            os.path.basename(path) for path in new_paths.difference(old_paths)
        ]
        return self.create_nodes_with_file_names(file_names, dirpath,
                                                 level + 1)

    def refresh_nodes(self, force_refreh=False, cheap_remote_ls=False):
        """
        1. Check the mtime of wd or any expanded subdir changed. If so, set
           content_outdated true, which could also be set manually (e.g.
           NETRToggleShowHidden).
        2. For each file/directory in the file system, including those in
           expanded directories, if no current node corresponds to it, add
           a new node to the node list so that it will be visible next time.
        3. For each current node, including nodes in expanded directories, if
           condition: no files/directories corresponds to it or it should be
           ignore, remove it from the node list so that it will be invisible
           next time.
        """
        for node in self.expanded_nodes:
            if os.access(node.fullpath, os.R_OK):
                ori_mtime = node.stat.st_mtime if node.stat else -1
                node.re_stat()
                new_mtime = node.stat.st_mtime
                if new_mtime > ori_mtime:
                    self.content_outdated = True

        if not self.content_outdated and not force_refreh:
            return

        self.content_outdated = False

        # create nodes corresponding to new files
        new_nodes = self.creat_nodes_if_not_exist(self.nodes, self.wd, -1,
                                                  cheap_remote_ls)
        fs_files = [set(self.fs.ls(self.wd, cheap_remote_ls))]
        nextValidInd = -1
        for i in range(len(self.nodes)):
            if i < nextValidInd:
                continue

            cur_node = self.nodes[i]
            if cur_node.is_INFO:
                new_nodes.append(cur_node)
                continue

            # When the first child of a parent node (directory) is
            # encountered, we push the "context" including the list
            # of existing  files in the parent directory.
            # When cur_node is no more a decendent of prevNode,
            # We should reset the "context" to the corresponding parent
            # node.
            prevNode = self.nodes[i - 1]
            if cur_node.level > prevNode.level and os.path:
                fs_files.append(
                    set(self.fs.ls(prevNode.fullpath, cheap_remote_ls)))
            else:
                fs_files = fs_files[:cur_node.level + 1]

            # The children of an invalid node will all be invalid
            # Hence, we will start with the next valid node
            if self.controler.should_ignore(
                    cur_node.name) or cur_node.name not in fs_files[-1]:
                nextValidInd = self.next_lesseq_level_ind(i)
                continue

            # create nodes corresponding to new files in expanded directories
            new_nodes.append(cur_node)
            if cur_node.is_DIR and cur_node.expanded:
                nextInd = self.next_lesseq_level_ind(i)
                new_nodes += self.creat_nodes_if_not_exist(
                    self.nodes[i + 1:nextInd + 1], cur_node.fullpath,
                    cur_node.level, cheap_remote_ls)

        oriNode = self.cur_node
        ori_clineNo = self.clineNo
        self.nodes = self.nodes_plus_header_footer(self.sort_nodes(new_nodes))
        self.render()
        self.set_clineno_by_node(oriNode, ori_clineNo)

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

    def sort_prep(self):
        self.nodes_order_outdated = True
        self.lastNodeId = self.nodes[self.clineNo]

    def sort(self):
        if not self.nodes_order_outdated:
            return
        self.nodes_order_outdated = False
        for node in self.nodes:
            node.re_stat()
        self.nodes = self.nodes_plus_header_footer(self.sort_nodes(self.nodes))
        self.render()
        self.set_clineno_by_node(self.lastNodeId)

    def sort_nodes(self, nodes):
        """Sort the nodes by their path and SortUI.sort_fn.

        Information of ancestor are accumulated for subnodes as prefix.
        To sort directories before files, ' '(ascii 32) is put into the
        prefix for directories and '~' (ascii 127) is put into the
        prefix for files. An additional ' ' is put before ' ' or '~' to
        handle tricky case like 'dir, dir/z, dir2', without which will
        results in 'dir, dir2, dir/z'.
        """
        sort_fn = SortUI.get_sort_fn()
        reverse = SortUI.reverse
        sortedNodes = []
        prefix = ''
        prefixEndInd = [0]
        for i in range(len(nodes)):
            cur_node = nodes[i]
            if cur_node.is_INFO:
                continue

            prevNode = nodes[i - 1]
            if cur_node.level > prevNode.level:
                # cur_node must be a DirNode, hence the same as in the folloing
                # "cur_node.is_DIR" case
                prefix += '  {}{}'.format(sort_fn(prevNode), prevNode.name)
                prefixEndInd.append(len(prefix))
            else:
                prefixEndInd = prefixEndInd[:cur_node.level + 1]
                prefix = prefix[:prefixEndInd[-1]]
            if cur_node.is_DIR:
                sortedNodes.append(
                    ('{}  {}{}'.format(prefix, sort_fn(cur_node),
                                       cur_node.name), cur_node))
            else:
                sortedNodes.append(
                    ('{} ~{}{}'.format(prefix, sort_fn(cur_node),
                                       cur_node.name), cur_node))

        sortedNodes = sorted(sortedNodes, key=lambda x: x[0])
        sortedNodes = [node[1] for node in sortedNodes]
        if reverse:
            sortedNodes = self.reverse_sorted_nodes(sortedNodes)

        return sortedNodes

    def render(self, plain=False):
        for hooker in NETRApi.Hookers['render_begin']:
            hooker(self)

        self.vim_buf_handel.options['modifiable'] = True
        if plain:
            self.vim_buf_handel[:] = self.plain_content
        else:
            self.vim_buf_handel[:] = self.highlight_content
        self.vim_buf_handel.options['modifiable'] = False
        if Vim.current.buffer.number is self.vim_buf_handel.number:
            self.move_vim_cursor(self.clineNo)

        for hooker in NETRApi.Hookers['render_end']:
            hooker(self)

    def refresh_hi_if_winwidth_changed(self):
        if self.is_editing:
            return

        winwidth = Vim.CurWinWidth()
        if self.winwidth != winwidth:
            self.winwidth = winwidth
            self.refresh_lines_hi(range(len(self.nodes)))

    def on_cursormoved(self):
        """Remember the current line no.

        and refresh the highlight of the current line no.
        """
        clineNo = int(Vim.eval("line('.')")) - 1

        # do not stay on footer
        if clineNo == len(self.nodes) - 1:
            Vim.command('normal! k')
            clineNo -= 1

        self.set_clineno(clineNo)

        # Avoid throttling by avoiding rerender the buffer (in
        # on_cursormoved_post) for each call of on_cursormoved (e.g. when the
        # user press j and don't let go).
        self.pending_on_cursormoved_post += 1

    def on_cursormoved_post(self):
        self.pending_on_cursormoved_post -= 1
        if self.pending_on_cursormoved_post > 0:
            return

        # The line self.vim_set_line... below triggers on_cursormoved event,
        # which in term triggers on_cursormoved_post. This test is to avoid
        # such call loop.
        if self.clineNo == self.last_on_curosormoved_lineNo:
            return
        self.last_on_curosormoved_lineNo = self.clineNo

        # Avoid rerender if this buffer is not the current vim buffer.
        if self.vim_buf_handel.number != Vim.current.buffer.number\
                or self.is_editing:
            return

        Vim.command("setlocal modifiable")
        self.set_header_content()
        self.set_footer_content()

        # set_footer_content re_stat the node, now we refresh the current
        # node to update the size information
        self.vim_set_line(self.clineNo,
                          self.nodes[self.clineNo].highlight_content)

        self.set_pseudo_header_content(self.clineNo)
        self.set_pseudo_footer_content(self.clineNo)
        Vim.command("setlocal nomodifiable")

    def move_vim_cursor(self, lineNo):
        """Will trigger on_cursormoved."""
        Vim.command('call cursor({},1)'.format(lineNo + 1))

    def set_clineno_by_path(self, path):
        """Real work is done in on_cursormoved.

        Eventually call set_clineno.
        """
        for ind, node in enumerate(self.nodes):
            if node.fullpath == path:
                self.move_vim_cursor(ind)
                break

    def set_clineno_by_node(self, node, ori_clineNo=0):
        """Real work is done in on_cursormoved.

        Eventually call set_clineno.
        """
        if node in self.nodes:
            self.move_vim_cursor(self.nodes.index(node))
        else:
            self.move_vim_cursor(ori_clineNo)

    def set_clineno(self, newLineNo):
        """Turn on newLineNo and turn off self.clineNo."""
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

    def vim_set_line(self, i, content):
        # This is a work-abound for the fact that
        # nVim.current.buffer[i]=content
        # moves the cursor
        Vim.command('call setline({},"{}")'.format(i + 1, content))

    def refresh_lines_hi(self, lineNos):
        Vim.command('setlocal modifiable')

        sz = min(len(self.nodes), len(Vim.current.buffer))
        for i in lineNos:
            if i < sz:
                self.vim_set_line(i, self.nodes[i].highlight_content)
        Vim.command('setlocal nomodifiable')

    def refresh_clineNo(self):
        if self.clineNo == Vim.eval("line('.')") - 1:
            return

    def refresh_highlight(self):
        """Refresh the highlight of nodes in highlight_outdated_nodes.

        Rather expensive, so consider use refresh_line_hi or
        refresh_cur_line_hi if possible.
        """
        if not self.highlight_outdated:
            return
        lines = []
        # TODO This is expensive but called frequently, can we do better?
        for i, node in enumerate(self.nodes):
            if node in self.highlight_outdated_nodes:
                lines.append(i)
        self.refresh_lines_hi(lines)
        self.highlight_outdated_nodes.clear()

    def refresh_cur_line_hi(self):
        self.refresh_lines_hi([self.clineNo])

    def VimCD(self):
        target_dir = self.cur_node.fullpath
        if not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        Vim.command('silent cd {}'.format(target_dir))
        self.last_vim_pwd = target_dir

    def toggle_expand(self):
        """Create subnodes for the target directory.

        Also record the mtime of the target directory so that we can
        refresh the buffer content (refresh_nodes) if the subdirectory
        is changed.
        """
        cur_node = self.cur_node
        if not cur_node.is_DIR:
            return
        if cur_node.expanded:
            self.expanded_nodes.remove(cur_node)
            endInd = self.next_lesseq_level_ind(self.clineNo)
            self.nodes = self.nodes[:self.clineNo + 1] + self.nodes[endInd:]
        else:
            try:
                newNodes = self.create_nodes(self.cur_node.fullpath,
                                             cur_node.level + 1)
            except PermissionError:
                Vim.ErrorMsg('Permission Denied: {}'.format(cur_node.name))
                return
            self.expanded_nodes.add(cur_node)
            if len(newNodes) > 0:
                self.nodes = self.nodes[:self.clineNo +
                                        1] + newNodes + self.nodes[
                                            self.clineNo + 1:]
        cur_node.expanded = not cur_node.expanded
        self.render()

    def edit(self):
        self.is_editing = True
        self.render(plain=True)
        Vim.command('setlocal modifiable')

    def save(self):
        """Rename the files according to current buffer content.

        Retur false if called but is_editing is false. Otherwise return
        true.
        """
        if not self.is_editing:
            return False
        self.is_editing = False

        vimBuf = Vim.current.buffer
        if len(self.nodes) != len(vimBuf):
            Vim.ErrorMsg('Edit mode can not add/delete files!')
            self.render()
            return True

        oriNode = self.cur_node

        change = {}
        i = 0
        for i in range(len(vimBuf)):
            line = vimBuf[i].strip()
            if not self.nodes[i].is_INFO and line != self.nodes[i].name:

                # change name of the i'th node
                oripath = self.nodes[i].rename(line)
                change[oripath] = self.nodes[i].fullpath

                # change dirname of subnodes
                endInd = self.next_lesseq_level_ind(begInd=i)
                for j in range(i + 1, endInd):
                    self.nodes[j].change_dirname(oripath,
                                                 self.nodes[i].fullpath)

        # apply the changes
        for oripath, fullpath in change.items():
            self.fs.rename(oripath, fullpath)

        self.nodes = [self.header_node] + self.sort_nodes(
            self.nodes) + [self.footer_node]
        self.render()
        self.set_clineno_by_node(oriNode)
        Vim.command('setlocal nomodifiable')
        return True

    def cut(self, nodes):
        for node in nodes:
            node.cut()
        self.highlight_outdated_nodes.update(nodes)

    def copy(self, nodes):
        for node in nodes:
            node.copy()
        self.highlight_outdated_nodes.update(nodes)

    def reset_hi(self, nodes):
        for node in nodes:
            node.reset_hi()
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
        return self.find_next_ind(
            nodes, begInd, lambda beg, new: new.level <= beg.level)


class Netranger(object):
    """Main  (mvc) controler.

    Main functions are:
    1. on_bufenter: create / update netr buffers
    2. invoke_map: invoke one of NETR* function on user key press
    """

    @property
    def cur_buf(self):
        return self.bufs[Vim.current.buffer.number]

    @property
    def cur_buf_is_remote(self):
        return self.cur_buf.fs is Rclone

    @property
    def cur_node(self):
        return self.cur_buf.cur_node

    @property
    def cwd(self):
        return self.cur_buf.wd

    def __init__(self):
        self.inited = False
        self.bufs = {}
        self.wd2bufnum = {}
        self.picked_nodes = defaultdict(set)
        self.cut_nodes = defaultdict(set)
        self.copied_nodes = defaultdict(set)
        self.bookmarkUI = None
        self.helpUI = None
        self.sortUI = None
        self.askUI = None
        self.onuiquit = None
        self.newUI = None
        self.previewUI = None
        self.onuiquit_num_args = 0

        self.init_vim_variables()
        self.init_keymaps()

        Rclone.init(Vim.Var('NETRemoteCacheDir'), Vim.Var('NETRemoteRoots'))
        Shell.mkdir(default.variables['NETRRootDir'])
        self.rifle = Rifle(Vim.Var('NETRRifleFile'))

        ignore_pat = list(Vim.Var('NETRIgnore'))
        if '.*' not in ignore_pat:
            ignore_pat.append('.*')
            Vim.vars['NETRIgnore'] = ignore_pat
        self.ignore_pattern = re.compile('|'.join(
            fnmatch.translate(p) for p in ignore_pat))

        Vim.vars['NETRemoteCacheDir'] = os.path.expanduser(
            Vim.Var('NETRemoteCacheDir'))

    def init_vim_variables(self):
        for k, v in default.variables.items():
            if k not in Vim.vars:
                Vim.vars[k] = v
        self.reset_default_colors()

        for k, v in default.internal_variables.items():
            if k not in Vim.vars:
                Vim.vars[k] = v

    def reset_default_colors(self):
        for name, color in Vim.Var('NETRColors').items():
            if name not in default.color:
                Vim.ErrorMsg('netranger: {} is not a valid NETRColors key!')
                continue
            if type(color) is int and (color < 0 or color > 255):
                Vim.ErrorMsg('netranger: Color value should be within 0~255')
                continue
            elif type(color) is str:
                if color[0] == '#':
                    color = colorhexstr2ind.get(color, None)
                else:
                    color = colorname2ind.get(color, None)
                if color is None:
                    Vim.ErrorMsg('netranger: {} is not a valid color name!')
                    continue

            default.color[name] = color

        for key, value in default.color.items():
            if type(value) is str:
                default.color[key] = colorname2ind[value]

    def should_ignore(self, basename):
        if self.ignore_pattern.match(basename) and self.ignore_pattern:
            return True
        return False

    def init_keymaps(self):
        """Add key mappings to NETR* functions for netranger buffers.

        Override or skip some default mappings on user demand.
        """
        self.keymap_doc = {}
        self.key2fn = {}
        self.visual_key2fn = {}
        skip = []
        for k in Vim.Var('NETRDefaultMapSkip'):
            skip.append(k.lower())
        for fn, (keys, desc) in default.keymap.items():
            user_keys = Vim.Var(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymap_doc[fn] = (keys, desc)
            for key in user_keys:
                self.key2fn[key] = getattr(self, fn)

        skip = []
        for k in Vim.Var('NETRDefaultVisualMapSkip'):
            skip.append(k.lower())
        for fn, (keys, desc) in default.visual_keymap.items():
            user_keys = Vim.Var(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymap_doc[fn] = (keys, desc)
            for key in user_keys:
                self.visual_key2fn[key] = getattr(self, fn)

    def map_keys(self):
        def literal(key):
            if key[0] == '<':
                escape_key = '<lt>' + key[1:]
            else:
                escape_key = key
            return escape_key

        for key in self.key2fn:
            Vim.command("nnoremap <nowait> <silent> <buffer> {} "
                        ':py3 ranger.key2fn[\"{}\"]()<cr>'.format(
                            key, literal(key)))
        for key in self.visual_key2fn:
            Vim.command("vnoremap <nowait> <silent> <buffer> {} "
                        ':py3 ranger.visual_key2fn[\"{}\"]()<cr>'.format(
                            key, literal(key)))

    def unmap_keys(self):
        for key, fn in self.key2fn.items():
            if fn.__name__ == 'NETRSave':
                continue
            Vim.command("nunmap <silent> <buffer> {}".format(key))

        for key, fn in self.visual_key2fn.items():
            Vim.command("vunmap <silent> <buffer> {}".format(key))

    def map(self, key, fn, check=False):
        if check and key in self.key2fn:
            Vim.ErrorMsg("netranger: Fail to bind key {} to {} because it has "
                         "been mapped to other {}.".format(
                             key, fn.__name__, self.key2fn[key].__name__))
        self.key2fn[key] = fn

    def on_winenter(self, bufnum):
        # deal with window width changed
        if bufnum in self.bufs:
            self.cur_buf.refresh_hi_if_winwidth_changed()

    def on_bufenter(self, bufnum):
        """There are four cases on bufenter:

        1. The buffer is not a netranger buffer: do nothing
        2. The buffer is a existing netranger buffer: refresh buffer content
           (e.g. directory content changed else where) and call any pending
           onuiquit functions
        3. The buffer is a [No Name] temporary buffer and the buffer name is a
           directory. Then we either create a new netranger buffer or bring up
           an existing netranger buffer
        """
        if bufnum in self.bufs:
            self.refresh_curbuf()
            if self.onuiquit is not None:
                # If not enough arguments are passed, ignore the pending
                # onuituit, e.g. quit the bookmark go ui without pressing
                # key to specify where to go.
                if len(Vim.Var('NETRRegister')) == self.onuiquit_num_args:
                    self.onuiquit(*Vim.Var('NETRRegister'))
                self.onuiquit = None
                Vim.vars['NETRRegister'] = []
                self.onuiquit_num_args = 0
        else:
            bufname = Vim.current.buffer.name
            if len(bufname) > 0 and bufname[-1] == '~':
                bufname = os.path.expanduser('~')
            if not os.path.isdir(bufname):
                return
            if os.path.islink(bufname):
                bufname = os.path.join(os.path.dirname(bufname),
                                       os.readlink(bufname))
            bufname = os.path.abspath(bufname)

            if self.buf_existed(bufname):
                self.show_existing_buf(bufname)
            else:
                self.gen_new_buf(bufname)

    def refresh_curbuf(self):
        cur_buf = self.cur_buf
        # manually turn off highlight of current linen as synchronous
        # on_bufenter block on_cursormoved event handler
        cur_buf.cur_node.cursor_off()

        # deal with content changed, e.g., file operation outside
        cur_buf.refresh_nodes()

        # deal with highlight changed, e.g., pick, copy hi dismiss because of
        # paste
        cur_buf.refresh_highlight()

        # ensure pwd is correct
        if Vim.Var('NETRAutochdir'):
            Vim.command('lcd ' + cur_buf.last_vim_pwd)

    def show_existing_buf(self, bufname):
        ori_bufnum = Vim.current.buffer.number
        existed_bufnum = self.wd2bufnum[bufname]
        Vim.command('{}b'.format(existed_bufnum))
        self.set_buf_option()
        buf = self.bufs[existed_bufnum]
        self.refresh_curbuf()

        # Check window width in case the window was closed in a different
        # width
        buf.refresh_hi_if_winwidth_changed()

        if ori_bufnum not in self.bufs:
            # wipe out the [No Name] temporary buffer
            Vim.command('bwipeout {}'.format(ori_bufnum))
        buf.move_vim_cursor(buf.clineNo)

    def gen_new_buf(self, bufname):
        bufnum = Vim.current.buffer.number
        if (bufname.startswith(Vim.Var('NETRemoteCacheDir'))):
            self.bufs[bufnum] = NetRangerBuf(self, os.path.abspath(bufname),
                                             Rclone)
        else:
            self.bufs[bufnum] = NetRangerBuf(self, os.path.abspath(bufname),
                                             LocalFS)
        Vim.command('silent file N:{}'.format(bufname))

        self.map_keys()
        self.wd2bufnum[bufname] = bufnum
        self.set_buf_option()

    def buf_existed(self, wd):
        """ Check if there's an existing NETRangerBuf.
        This avoids reinitializing a NETRangerBuf when the corresponding vim
        buffer is wipeout and later reentered.
        """
        if wd not in self.wd2bufnum:
            return False

        bufnum = self.wd2bufnum[wd]
        try:
            buf = Vim.buffers[bufnum]
            return buf.valid
        except KeyError:
            del self.wd2bufnum[wd]
            del self.bufs[bufnum]
            return False

    def set_buf_option(self):
        Vim.command('setlocal buftype=nofile')
        Vim.command('setlocal filetype=netranger')
        Vim.command('setlocal encoding=utf-8')
        Vim.command('setlocal noswapfile')
        Vim.command('setlocal nowrap')
        Vim.command('setlocal foldmethod=manual')
        Vim.command('setlocal foldcolumn=0')
        Vim.command('setlocal nofoldenable')
        Vim.command('setlocal nobuflisted')
        Vim.command('setlocal nospell')
        Vim.command('setlocal bufhidden=hide')
        Vim.command('setlocal conceallevel=3')
        Vim.command('set concealcursor=nvic')
        Vim.command('setlocal nocursorline')
        Vim.command('setlocal nolist')

    def on_cursormoved(self, bufnum):
        """refresh buffer highlight when cursor is moved.

        @param bufnum: current buffer number
        """
        # if bufnum in self.bufs and not self.bufs[bufnum].is_editing:
        if not self.bufs[bufnum].is_editing:
            self.bufs[bufnum].on_cursormoved()
            Vim.Timer(Vim.Var('NETRRedrawDelay'), '_NETROnCursorMovedPost',
                      self.on_cursormoved_post, bufnum)

    def on_cursormoved_post(self, bufnum):
        """Refresh header and footer content.
        re_stat is a heavy task (compared to setting highlight when cursor
        moved). To avoid unnecessary calling of re_stat (e.g. when the user
        keep pressing j just to move down and don't care the stat information
        ), we delay re_stat in on_cursormoved by using timer and avoid
        re_stat throttling using a trick documented in NETRangerBuf.
        on_cursormoved_post.
        """
        self.bufs[bufnum].on_cursormoved_post()
        if self.previewUI and Vim.current.buffer.number in self.bufs:
            self.previewUI.set_content(self.cur_node.fullpath)

    def pend_onuiquit(self, fn, numArgs=0):
        """Called by UIs to perform actions after reentering netranger buffer.
        Used for waiting for user input in some UI and then defer what to do
        when the UI window is quit and the netranger buffer gain focus again.
        Function arguments are passed as a list via vim variable g:'
        NETRRegister'.

        @param fn: function to be executed
        @param numArgs: number of args expected to see in g:'NETRRegister'.
                        When exectuing fn, if numArgs do not match, fn will not
                        be executed. (e.g. User press no keys in BookMarkGo UI
                        but simply quit the UI)
        """
        self.onuiquit = fn
        self.onuiquit_num_args = numArgs

    def NETROpen(self, open_cmd=None, rifle_cmd=None, use_rifle=True):
        """The real work for opening directories is handled in on_bufenter.

        For openning files, we check if there's rifle rule to open the
        file. Otherwise, open it in vim.
        """
        cur_node = self.cur_node
        if cur_node.is_INFO:
            return

        if open_cmd is None:
            if cur_node.is_DIR:
                open_cmd = 'edit'
            else:
                open_cmd = Vim.Var('NETROpenCmd')

        fullpath = cur_node.fullpath
        if cur_node.is_DIR:
            if not os.access(cur_node.fullpath, os.X_OK):
                Vim.ErrorMsg('Permission Denied: {}'.format(cur_node.name))
                return
            if use_rifle and rifle_cmd is not None:
                Shell.run_async(rifle_cmd.format('"{}"'.format(fullpath)))
            else:
                Vim.command('silent {} {}'.format(open_cmd, fullpath))
                # Manually call on_bufenLer as old vim version might not
                # trigger BufEnter with the above command. It does not cause
                # too much overhead calling on_bufenter two times because most
                # of things are cached
                self.on_bufenter(Vim.eval("winnr()"))
        else:
            if self.cur_buf_is_remote:
                Rclone.ensure_downloaded(fullpath)

            if rifle_cmd is None:
                rifle_cmd = self.rifle.decide_open_cmd(fullpath)

            if use_rifle and rifle_cmd is not None:
                Shell.run_async(rifle_cmd.format('"{}"'.format(fullpath)))
            else:
                try:
                    Vim.command('{} {}'.format(open_cmd, fullpath))
                except Exception as e:
                    err_msg = str(e)
                    if 'E325' not in err_msg:
                        Vim.ErrorMsg(err_msg)

    def NETRefresh(self):
        cur_buf = self.cur_buf
        cur_buf.refresh_nodes(force_refreh=True)

    def NETRTabOpen(self):
        self.NETROpen('tabedit', use_rifle=False)

    def NETRTabBgOpen(self):
        self.NETROpen('tabedit', use_rifle=False)
        Vim.command('tabprevious')

    def NETRBufOpen(self):
        self.NETROpen('edit', use_rifle=False)

    def NETRBufVSplitOpen(self):
        self.NETROpen(Vim.Var('NETRSplitOrientation') + ' vsplit',
                      use_rifle=False)

    def NETRBufHSplitOpen(self):
        self.NETROpen(Vim.Var('NETRSplitOrientation') + ' split',
                      use_rifle=False)

    def NETRBufPanelOpen(self):
        if self.cur_node.is_DIR:
            return

        if len(Vim.current.tabpage.windows) == 1:
            self.NETROpen(Vim.Var('NETRSplitOrientation') + ' vsplit',
                          use_rifle=False)
            newsize = Vim.CurWinWidth() * Vim.Var('NETRPanelSize')
            Vim.command('vertical resize {}'.format(newsize))
        else:
            fpath = self.cur_node.fullpath
            Vim.command('wincmd l')
            Vim.command('edit {}'.format(fpath))

    def NETRAskOpen(self):
        fullpath = self.cur_node.fullpath
        if self.askUI is None:
            self.askUI = AskUI(self)
        self.askUI.ask(self.rifle.list_available_cmd(fullpath), fullpath)

    def NETRTogglePreview(self):
        if self.previewUI is None:
            self.previewUI = PreviewUI()
        self.previewUI.close_or_show(self.cur_node.fullpath)

    def NETRParentDir(self):
        """Real work is done in on_bufenter."""
        cur_buf = self.cur_buf
        cwd = cur_buf.wd
        pdir = LocalFS.parent_dir(cwd)
        Vim.command('silent edit {}'.format(pdir))
        # Manually call on_bufenter, see comments in NETROpen
        self.on_bufenter(Vim.eval("winnr()"))
        cur_buf = self.cur_buf
        cur_buf.set_clineno_by_path(cwd)
        # Manually call on_cursormoved as synchronous on_bufenter block
        # on_cursormoved event handler, which should trigger by the previous
        # line.
        self.on_cursormoved(Vim.current.buffer.number)

    def NETRVimCD(self):
        self.cur_buf.VimCD()
        Vim.WarningMsg('Set pwd to {}'.format(Vim.eval('getcwd()')))

    def NETRToggleExpand(self):
        self.cur_buf.toggle_expand()

    def NETRNew(self):
        if self.cur_buf.fs_busy():
            return
        if self.newUI is None:
            self.newUI = NewUI()
        self.newUI.show()
        self.pend_onuiquit(self.new_onuiiquit, numArgs=1)

    def new_onuiiquit(self, opt):
        cur_buf = self.cur_buf
        if opt == 'd':
            name = Vim.UserInput('New directory name')
            cur_buf.fs.mkdir(os.path.join(cur_buf.last_vim_pwd, name))
        elif opt == 'f':
            name = Vim.UserInput('New file name')
            cur_buf.fs.touch(os.path.join(cur_buf.last_vim_pwd, name))
        self.cur_buf.refresh_nodes()

    def NETREdit(self):
        if self.cur_buf.fs_busy():
            return
        self.unmap_keys()
        self.cur_buf.edit()

    def NETRSave(self):
        if self.cur_buf.save():
            self.map_keys()

    def NETRToggleShowHidden(self):
        """Change ignore pattern and mark all existing netranger buffers to be
        content_outdated so that their content will be updated when entered
        again."""
        ignore_pat = Vim.Var('NETRIgnore')
        if '.*' in ignore_pat:
            ignore_pat.remove('.*')
        else:
            ignore_pat.append('.*')
        Vim.vars['NETRIgnore'] = ignore_pat

        # When ignore_pat is empty, the compiled pattern matches everything.
        # However, what we want is to ignore nothing in such case. Hence we add
        # a pattern that will never be matched.
        ignore_pat = [fnmatch.translate(p) for p in ignore_pat]
        if len(ignore_pat) == 0:
            ignore_pat = ['$^']

        self.ignore_pattern = re.compile('|'.join(ignore_pat))
        for buf in self.bufs.values():
            buf.content_outdated = True
        self.cur_buf.refresh_nodes(force_refreh=True)

    def invoke_map(self, fn):
        if hasattr(self, fn):
            getattr(self, fn)()

    def init_bookmark_ui(self):
        if self.bookmarkUI is None:
            self.bookmarkUI = BookMarkUI(self)

    def NETRBookmarkSet(self):
        self.init_bookmark_ui()
        self.bookmarkUI.set(self.cwd)

    def NETRBookmarkGo(self):
        self.init_bookmark_ui()
        self.bookmarkUI.go()

    def bookmarkgo_onuiquit(self, fullpath):
        # The following ls ensure that the directory exists on some remote file
        # system
        Shell.ls(fullpath)
        Vim.command('silent edit {}'.format(fullpath))
        # Manually perform part of on_bufenter as synchronous
        # on_bufenter block (nested) on_bufenter event handler
        if self.buf_existed(fullpath):
            self.show_existing_buf(fullpath)
        else:
            self.gen_new_buf(fullpath)

    def NETRBookmarkEdit(self):
        self.init_bookmark_ui()
        self.bookmarkUI.edit()

    def NETRSort(self):
        if self.cur_buf.fs_busy():
            return
        if self.sortUI is None:
            self.sortUI = SortUI()
        self.sortUI.show()
        self.pend_onuiquit(self.sort_onuiiquit, numArgs=1)

    def sort_onuiiquit(self, opt):
        SortUI.reverse = opt.isupper()
        SortUI.select_sort_fn(opt.lower())
        for buf in self.bufs.values():
            buf.sort_prep()
        self.cur_buf.sort()

    def NETRHelp(self):
        if self.helpUI is None:
            self.helpUI = HelpUI(self.keymap_doc)
        self.helpUI.show()

    def reset_pick_cut_copy(self):
        for buf, nodes in self.cut_nodes.items():
            buf.reset_hi(nodes)
        for buf, nodes in self.copied_nodes.items():
            buf.reset_hi(nodes)
        for buf, nodes in self.picked_nodes.items():
            buf.reset_hi(nodes)
        self.picked_nodes = defaultdict(set)
        self.cut_nodes = defaultdict(set)
        self.copied_nodes = defaultdict(set)

    def inc_num_fs_op(self, bufs):
        """Increase number of filesystem operation for buffers.
        The mechanisms of filesystem operation locking are as follows:
        1. The general guideline is that after operation, if the content (but
        1not highlight) of the buffer will change, the buffer should be locked.
        2. When a buffer contains nodes under deletion, the buffer should be
        locked.
        3. When performing paste operation on a buffer, the buffer should be
        locked. The source buffers for cut nodes should also be locked.
        However, The source buffers for copied nodes need not be locked as
        only highlight will change.
        4. When a buffer is locked, NETRTogglePick/NETRDeleteSingle/NETRPaste
        are forbidden, i.e. operation that will change content of the buffer.
        5. Note that NETRCut/NETRCopy/NETRDelete get their sources from
        picked_nodes, so they are not forbidden though you still can't pick
        nodes and then perform cut/copy/delete in the current buffer (as
        NETRTogglePick is forbidden in the current buffer)
        5. To lock a buffer, we increase it's num_fs_op by 1.
        6. To unlock a buffer, we decrease it's num_fs_op by 1.
        7. A buffer is considered as locked if its num_fs_op>0.
        """
        for buf in bufs:
            buf.inc_num_fs_op()

    def dec_num_fs_op(self, bufs):
        """Decrease number of filesystem operation for buffers.
        See inc_num_fs_op.
        """

        for buf in bufs:
            buf.dec_num_fs_op()

        if Vim.current.buffer.number in self.bufs:
            cur_buf = self.cur_buf
            if not cur_buf.fs_busy(echo=False):
                cur_buf.refresh_nodes(force_refreh=True, cheap_remote_ls=True)

    def NETRCancelPickCutCopy(self):
        self.reset_pick_cut_copy()
        self.cur_buf.refresh_highlight()

    def NETRTogglePick(self):
        """Funciton to Add or remove cur_node to/from picked_nodes.

        Also update the highlight of the current line.
        """
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        cur_node = self.cur_node
        res = cur_node.toggle_pick()
        if res == Node.ToggleOpRes.ON:
            self.picked_nodes[cur_buf].add(cur_node)
        elif res == Node.ToggleOpRes.OFF:
            self.picked_nodes[cur_buf].remove(cur_node)
        self.cur_buf.refresh_cur_line_hi()

    def NETRTogglePickVisual(self):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        Vim.command('normal! gv')
        beg = int(Vim.eval('line("\'<")')) - 1
        end = int(Vim.eval('line("\'>")'))
        for i in range(beg, end):
            node = cur_buf.nodes[i]
            res = node.toggle_pick()
            if res == Node.ToggleOpRes.ON:
                self.picked_nodes[cur_buf].add(node)
            else:
                self.picked_nodes[cur_buf].remove(node)
        cur_buf.refresh_lines_hi([i for i in range(beg, end)])
        Vim.command('normal! V')

    def NETRCut(self):
        """Move picked_nodes to cut_nodes.

        All buffers containing picked nodes are marked as
        highlight_outdated so that their highlight will be updated when
        entered again.
        """
        for buf, nodes in self.picked_nodes.items():
            buf.cut(nodes)
            self.cut_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.cur_buf.refresh_highlight()

    def NETRCutSingle(self):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        cur_node = self.cur_node
        cur_node.cut()
        self.cut_nodes[cur_buf].add(cur_node)
        cur_buf.refresh_cur_line_hi()

    def NETRCopy(self):
        """Move picked_nodes to copied_nodes.

        All buffers containing picked nodes are marked as
        highlight_outdated so that their highlight will be updated when
        entered again.
        """
        for buf, nodes in self.picked_nodes.items():
            buf.copy(nodes)
            self.copied_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.cur_buf.refresh_highlight()

    def NETRCopySingle(self):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        cur_node = self.cur_node
        cur_node.copy()
        self.copied_nodes[cur_buf].add(cur_node)
        cur_buf.refresh_cur_line_hi()

    def _NETRPaste_cut_nodes(self, busy_bufs):
        cwd = Vim.eval('getcwd()')
        fsfilter = FSTarget(cwd)

        alreday_moved = set()
        for buf, nodes in self.cut_nodes.items():
            buf.reset_hi(nodes)

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
                if node.fullpath not in alreday_moved:
                    fsfilter.append(node.fullpath)
                    alreday_moved.add(node.fullpath)

            self.cut_nodes = defaultdict(set)

            fsfilter.mv(cwd,
                        on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                        on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def _NETRPaste_copied_nodes(self, busy_bufs):
        cwd = Vim.eval('getcwd()')
        fsfilter = FSTarget(cwd)

        for buf, nodes in self.copied_nodes.items():
            buf.reset_hi(nodes)
            for node in nodes:
                fsfilter.append(node.fullpath)

        self.copied_nodes = defaultdict(set)
        fsfilter.cp(cwd,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def NETRPaste(self):
        """Perform mv from cut_nodes or cp from copied_nodes to cwd.
        For each source (cut/copy) buffer, reset the highlight of the cut/
        copied nodes so that the highlight will be updated when entered again
        in refresh_curbuf
        """
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return

        # Set locked bufs. See comments in inc_num_fs_op.
        cut_busy_bufs = list(self.cut_nodes.keys()) + [cur_buf]
        copy_busy_bufs = [cur_buf]

        Vim.WarningMsg('Paste to {}'.format(Vim.eval('getcwd()')))
        self._NETRPaste_copied_nodes(copy_busy_bufs)
        self._NETRPaste_cut_nodes(cut_busy_bufs)

    def NETRDelete(self, force=False):
        fsfilter = FSTarget('')

        for buf, nodes in self.picked_nodes.items():
            buf.content_outdated = True
            buf.reset_hi(nodes)
            fsfilter.extend([n.fullpath for n in nodes], hint=buf.wd)

        # Set locked bufs. See comments in inc_num_fs_op.
        busy_bufs = list(self.picked_nodes.keys())
        self.picked_nodes = defaultdict(set)

        fsfilter.rm(force,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def NETRDeleteSingle(self, force=False):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        fsfilter = FSTarget('')

        cur_buf.content_outdated = True
        fsfilter.append(self.cur_node.fullpath)
        busy_bufs = [cur_buf]

        fsfilter.rm(force,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def NETRForceDelete(self):
        self.NETRDelete(force=True)

    def NETRForceDeleteSingle(self):
        self.NETRDeleteSingle(force=True)

    def NETRemotePull(self):
        """Sync local so that the local content of the current directory will
        be the same as the remote content."""
        try:
            cur_buf = self.cur_buf
        except KeyError:
            Vim.ErrorMsg('Not a netranger buffer')
            return

        if not self.cur_buf_is_remote:
            Vim.ErrorMsg('Not a remote directory')
        else:
            Rclone.sync(cur_buf.wd, Rclone.SyncDirection.DOWN)
        cur_buf.refresh_nodes(force_refreh=True, cheap_remote_ls=True)

    def NETRemotePush(self):
        """Sync remote so that the remote content of the current directory will
        be the same as the local content."""
        try:
            cur_buf = self.cur_buf
        except KeyError:
            Vim.ErrorMsg('Not a netranger buffer')
            return

        if not self.cur_buf_is_remote:
            Vim.ErrorMsg('Not a remote directory')
        else:
            Rclone.sync(cur_buf.wd, Rclone.SyncDirection.UP)

    def NETRemoteList(self):
        Rclone.valid_or_install()

        if Rclone.has_remote:
            Vim.command('tabe ' + Vim.Var('NETRemoteCacheDir'))
        else:
            Vim.ErrorMsg(
                "There's no remote now. Run 'rclone config' in a terminal to "
                "setup remotes")
