from __future__ import absolute_import, print_function

import datetime
import fnmatch
import os
import re
from collections import defaultdict
from sys import platform

from netranger import default
from netranger.api import HasHooker, Hookers
from netranger.colortbl import colorhexstr2ind, colorname2ind
from netranger.config import file_sz_display_wid
from netranger.enum import Enum
from netranger.fs import FS, Rclone
from netranger.rifle import Rifle
from netranger.ui import AskUI, BookMarkUI, HelpUI, NewUI, SortUI
from netranger.util import Shell, c256
from netranger.Vim import (VimCurWinHeight, VimCurWinWidth, VimErrorMsg,
                           VimTimer, VimUserInput, VimVar, VimWarningMsg)

if platform == "win32":
    from os import getenv
else:
    import pwd
    import grp


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

    def re_stat(self, fs):
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

    def re_stat(self, fs=None):
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

        if HasHooker('node_highlight_content_l', 'node_highlight_content_r'):
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

    def __init__(self, fullpath, name, fs, level=0, buf=None):
        self.fullpath = fullpath
        self.buf = buf
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
        except FileNotFoundError:
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

    def __init__(self, controler, vim, wd, fs):
        self.controler = controler
        self.vim = vim
        self.wd = wd
        self.fs = fs

        self.content_outdated = False
        self.highlight_outdated_nodes = set()
        self.nodes_order_outdated = False

        self.vim.command('silent file N:{}'.format(os.path.basename(wd)))
        if VimVar('NETRAutochdir'):
            self.vim.command('lcd ' + wd)

        self.header_node = HeaderNode(wd)
        self.footer_node = FooterNode()
        self.nodes = self.nodes_plus_header_footer(
            self.create_nodes(self.wd, truncate_if_too_many_nodes=True))

        self.clineNo = 1
        self.nodes[self.clineNo].cursor_on()
        # In refresh_buf we need to check the mtime of all expanded nodes to
        # see if any content in the buffer is changed. Adding the HeaderNode
        # simply means we check the mtime of the wd everytime.
        self.expanded_nodes = set([self.header_node])
        self.winwidth = VimCurWinWidth()
        self.pseudo_header_lineNo = None
        self.pseudo_footer_lineNo = None
        self.is_editing = False
        self.visual_start_line = 0
        self.vim_buf_handel = self.vim.current.buffer
        self.render()

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
        self.vim.current.buffer[0] = self.header_node.highlight_content

    def set_footer_content(self):
        meta = ''
        cur_node = self.cur_node
        if not cur_node.is_INFO:
            cur_node.re_stat(self.fs)
            meta = ' {} {} {} {}'.format(cur_node.acl, cur_node.user,
                                         cur_node.group, cur_node.mtime)
        self.footer_node.name = meta.strip()
        self.vim.current.buffer[-1] = self.footer_node.highlight_content

    def set_pseudo_header_content(self, clineNo):
        # recover content for the last line occupied by pseudo header
        # ignore error when buffer no longer has the last line
        if self.pseudo_header_lineNo is not None:
            try:
                self.vim.current.buffer[
                    self.pseudo_header_lineNo] = self.nodes[
                        self.pseudo_header_lineNo].highlight_content
            except IndexError:
                pass

        # if first visible line is not the first line
        # we need to put header content on the first visible line
        first_visible_line = int(self.vim.eval('line("w0")')) - 1
        if first_visible_line > 0:
            # if current line is at the header we need to keep the current line
            # to be 2nd visible line
            if first_visible_line == clineNo:
                self.vim.command("normal! ")
                first_visible_line -= 1
            self.pseudo_header_lineNo = first_visible_line
            self.vim.current.buffer[
                first_visible_line] = self.header_node.highlight_content
        else:
            self.pseudo_header_lineNo = None

    def set_pseudo_footer_content(self, clineNo):
        # recover content for the last line occupied by pseudo footer
        # ignore error when buffer no longer has the last line
        if self.pseudo_footer_lineNo is not None:
            try:
                self.vim.current.buffer[
                    self.pseudo_footer_lineNo] = self.nodes[
                        self.pseudo_footer_lineNo].highlight_content
            except IndexError:
                pass

        # if last visible line is not the last line
        # we need to put footer content on the last visible line
        last_visible_line = int(self.vim.eval('line("w$")')) - 1
        if last_visible_line < int(self.vim.eval("line('$')")) - 1:
            # if current line is at the footer we need to keep the current line
            # to be penultimate visible line
            if last_visible_line == clineNo:
                self.vim.command("normal! ")
                last_visible_line += 1
            self.pseudo_footer_lineNo = last_visible_line
            self.vim.current.buffer[
                last_visible_line] = self.footer_node.highlight_content
        else:
            self.pseudo_footer_lineNo = None

    def create_nodes(self, wd, level=0, truncate_if_too_many_nodes=False):
        nodes = self.create_nodes_with_file_names(self.fs.ls(wd), wd, level,
                                                  truncate_if_too_many_nodes)
        return self.sort_nodes(nodes)

    def create_nodes_with_file_names(self,
                                     files,
                                     dirpath,
                                     level,
                                     truncate_if_too_many_nodes=False):
        if truncate_if_too_many_nodes:
            if len(files) > VimVar('NETRMaxFileNumToEagerlyDisplay'):
                files = files[:VimCurWinHeight() - 2]
                VimErrorMsg(
                    'Part of the files are not shown for efficiency. Press r'
                    'to show all of them\n')
            files = [f for f in files if not self.controler.should_ignore(f)]
            nodes = [self.create_node(dirpath, f, level) for f in files]
        else:
            files = [f for f in files if not self.controler.should_ignore(f)]
            if len(files) > VimVar('NETRMinFileNumToLoadInParallel'):
                nodes = []
                import concurrent
                from concurrent.futures import ThreadPoolExecutor
                from netranger.Vim import pbar
                with ThreadPoolExecutor(
                        max_workers=len(os.sched_getaffinity(0))) as executor:
                    futures = [
                        executor.submit(self.create_node, dirpath, f, level)
                        for f in files
                    ]
                    for future in pbar(
                            concurrent.futures.as_completed(futures),
                            total=len(files)):
                        nodes.append(future.result())
            else:
                nodes = [self.create_node(dirpath, f, level) for f in files]
        return nodes

    def create_node(self, dirname, basename, level):
        fullpath = os.path.join(dirname, basename)
        if os.path.isdir(fullpath):
            return DirNode(fullpath, basename, self.fs, level=level, buf=self)
        else:
            return EntryNode(fullpath,
                             basename,
                             self.fs,
                             level=level,
                             buf=self)

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
                ori_mtime = node.stat.st_mtime
                node.re_stat(self.fs)
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
            node.re_stat(self.fs)
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
        for hooker in Hookers['render_begin']:
            hooker(self)

        self.vim_buf_handel.options['modifiable'] = True
        if plain:
            self.vim_buf_handel[:] = self.plain_content
        else:
            self.vim_buf_handel[:] = self.highlight_content
        self.vim_buf_handel.options['modifiable'] = False
        if self.vim.current.buffer.number is self.vim_buf_handel.number:
            self.move_vim_cursor(self.clineNo)

        for hooker in Hookers['render_end']:
            hooker(self)

    def refresh_hi_if_winwidth_changed(self):
        if self.is_editing:
            return

        winwidth = VimCurWinWidth()
        if self.winwidth != winwidth:
            self.winwidth = winwidth
            self.refresh_lines_hi(range(len(self.nodes)))

    def on_cursormoved(self):
        """Remember the current line no.

        and refresh the highlight of the current line no.
        """
        clineNo = int(self.vim.eval("line('.')")) - 1

        # do not stay on footer
        if clineNo == len(self.nodes) - 1:
            self.vim.command('normal! k')
            clineNo -= 1

        self.set_clineno(clineNo)

    def on_cursormoved_post(self):
        self.vim.command("setlocal modifiable")
        self.set_header_content()
        self.set_footer_content()
        self.set_pseudo_header_content(self.clineNo)
        self.set_pseudo_footer_content(self.clineNo)
        self.vim.command("setlocal nomodifiable")

    def move_vim_cursor(self, lineNo):
        """Will trigger on_cursormoved."""
        self.vim.command('call cursor({},1)'.format(lineNo + 1))

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
        # nvim.current.buffer[i]=content
        # moves the cursor
        self.vim.command('call setline({},"{}")'.format(
            i + 1, self.nodes[i].highlight_content))

    def refresh_lines_hi(self, lineNos):
        self.vim.command('setlocal modifiable')

        sz = min(len(self.nodes), len(self.vim.current.buffer))
        for i in lineNos:
            if i < sz:
                self.vim_set_line(i, self.nodes[i].highlight_content)
        self.vim.command('setlocal nomodifiable')

    def refresh_clineNo(self):
        if self.clineNo == self.vim.eval("line('.')") - 1:
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
            self.expanded_nodes.add(cur_node)
            newNodes = self.create_nodes(self.cur_node.fullpath,
                                         cur_node.level + 1)
            if len(newNodes) > 0:
                self.nodes = self.nodes[:self.clineNo +
                                        1] + newNodes + self.nodes[
                                            self.clineNo + 1:]
        cur_node.expanded = not cur_node.expanded
        self.render()

    def edit(self):
        self.is_editing = True
        self.render(plain=True)
        self.vim.command('setlocal modifiable')
        self.vim.command('setlocal wrap')

    def save(self):
        """Rename the files according to current buffer content.

        Retur false if called but is_editing is false. Otherwise return
        true.
        """
        if not self.is_editing:
            return False
        self.is_editing = False

        vimBuf = self.vim.current.buffer
        if len(self.nodes) != len(vimBuf):
            VimErrorMsg('Edit mode can not add/delete files!')
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
        self.vim.command('setlocal nowrap')
        self.vim.command('setlocal nomodifiable')
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
        return self.bufs[self.vim.current.buffer.number]

    @property
    def cur_node(self):
        return self.cur_buf.cur_node

    @property
    def cwd(self):
        return self.cur_buf.wd

    def __init__(self, vim):
        self.vim = vim
        self.inited = False
        self.bufs = {}
        self.wd2bufnum = {}
        self.picked_nodes = defaultdict(set)
        self.num_fs_op = 0
        self.cut_nodes = defaultdict(set)
        self.copied_nodes = defaultdict(set)
        self.bookmarkUI = None
        self.helpUI = None
        self.sortUI = None
        self.askUI = None
        self.onuiquit = None
        self.newUI = None
        self.onuiquit_num_args = 0
        self.fs = FS()
        self.rclone = None

        self.init_vim_variables()
        self.init_keymaps()
        Shell.mkdir(default.variables['NETRRootDir'])
        self.rifle = Rifle(self.vim, VimVar('NETRRifleFile'))

        ignore_pat = list(VimVar('NETRIgnore'))
        if '.*' not in ignore_pat:
            ignore_pat.append('.*')
            self.vim.vars['NETRIgnore'] = ignore_pat
        self.ignore_pattern = re.compile('|'.join(
            fnmatch.translate(p) for p in ignore_pat))

        self.vim.vars['NETRemoteCacheDir'] = os.path.expanduser(
            VimVar('NETRemoteCacheDir'))

    def init_vim_variables(self):
        for k, v in default.variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v
        self.reset_default_colors()

        for k, v in default.internal_variables.items():
            if k not in self.vim.vars:
                self.vim.vars[k] = v

    def reset_default_colors(self):
        for name, color in VimVar('NETRColors').items():
            if name not in default.color:
                VimErrorMsg('netranger: {} is not a valid NETRColors key!')
                continue
            if type(color) is int and (color < 0 or color > 255):
                VimErrorMsg('netranger: Color value should be within 0~255')
                continue
            elif type(color) is str:
                if color[0] == '#':
                    color = colorhexstr2ind.get(color, None)
                else:
                    color = colorname2ind.get(color, None)
                if color is None:
                    VimErrorMsg('netranger: {} is not a valid color name!')
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
        self.keymaps = {}
        self.keymap_doc = {}
        skip = []
        for k in VimVar('NETRDefaultMapSkip'):
            skip.append(k.lower())
        for fn, (keys, desc) in default.keymap.items():
            user_keys = VimVar(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymaps[fn] = user_keys
            self.keymap_doc[fn] = (user_keys, desc)

    def map_keys(self):
        for fn, keys in self.keymaps.items():
            for k in keys:
                self.vim.command('nnoremap <nowait> <silent> <buffer> {} '
                                 ':exe ":call _NETRInvokeMap({})"<CR>'.format(
                                     k, "'" + fn + "'"))

        for k in self.keymaps['NETRTogglePick']:
            self.vim.command('vnoremap <nowait> <silent> <buffer> {} '
                             '<Esc>:exe ":call _NETRInvokeMap({})"<CR>'.format(
                                 k, "'NETRTogglePickVisual'"))

    def unmap_keys(self):
        for fn, keys in self.keymaps.items():
            if fn == 'NETRSave':
                continue
            for k in keys:
                self.vim.command("nunmap <silent> <buffer> {}".format(k))

        for k in self.keymaps['NETRTogglePick']:
            self.vim.command('vunmap <silent> <buffer> {}'.format(k))

    def register_keymap(self, keys_fns):
        mapped_keys = []
        for keys in self.keymaps.values():
            mapped_keys += keys
        mapped_keys = set(mapped_keys)

        for keys, fn in keys_fns:
            if type(keys) is str:
                keys = [keys]
            real_keys = []
            name = fn.__name__
            for key in keys:
                if key in mapped_keys:
                    VimErrorMsg(
                        "netranger: Fail to bind key {} to {} because it has "
                        "been mapped to other function.".format(key, name))
                    continue
                real_keys.append(key)
            self.keymaps[name] = real_keys
            assert not hasattr(
                self, name
            ), "Plugin of vim-netranger should not register a keymap with a "
            "function name already defined by vim-netranger."
            setattr(self, name, fn)

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
                if len(VimVar('NETRRegister')) == self.onuiquit_num_args:
                    self.onuiquit(*VimVar('NETRRegister'))
                self.onuiquit = None
                self.vim.vars['NETRRegister'] = []
                self.onuiquit_num_args = 0
        else:
            bufname = self.vim.current.buffer.name
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
        if VimVar('NETRAutochdir'):
            self.vim.command('lcd ' + cur_buf.wd)

    def show_existing_buf(self, bufname):
        ori_bufnum = self.vim.current.buffer.number
        existed_bufnum = self.wd2bufnum[bufname]
        self.vim.command('{}b'.format(existed_bufnum))
        self.set_buf_option()
        buf = self.bufs[existed_bufnum]
        self.refresh_curbuf()
        if ori_bufnum not in self.bufs:
            # wipe out the [No Name] temporary buffer
            self.vim.command('bwipeout {}'.format(ori_bufnum))
        buf.move_vim_cursor(buf.clineNo)

    def gen_new_buf(self, bufname):
        bufnum = self.vim.current.buffer.number
        if (bufname.startswith(VimVar('NETRemoteCacheDir'))):
            self.bufs[bufnum] = NetRangerBuf(self, self.vim,
                                             os.path.abspath(bufname),
                                             self.rclone)
        else:
            self.bufs[bufnum] = NetRangerBuf(self, self.vim,
                                             os.path.abspath(bufname), self.fs)

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
            buf = self.vim.buffers[bufnum]
            return buf.valid
        except KeyError:
            del self.wd2bufnum[wd]
            del self.bufs[bufnum]
            return False

    def set_buf_option(self):
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
        self.vim.command('setlocal nolist')

    def on_cursormoved(self, bufnum):
        """refresh buffer highlight when cursor is moved.

        @param bufnum: current buffer number
        """
        if bufnum in self.bufs and not self.bufs[bufnum].is_editing:
            self.bufs[bufnum].on_cursormoved()
            VimTimer(VimVar('NETRRedrawDelay'), '_NETROnCursorMovedPost',
                     self.on_cursormoved_post)

    def on_cursormoved_post(self):
        """Refresh header and footer content.
        This is a heavy task (compared to setting highlight when cursor moved).
        We alieviate its load by using timer.
        """
        bufnum = self.vim.current.buffer.number
        if bufnum in self.bufs:
            self.bufs[bufnum].on_cursormoved_post()

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
                open_cmd = VimVar('NETROpenCmd')

        fullpath = cur_node.fullpath
        if cur_node.is_DIR:
            if cur_node.size == '?' or cur_node.size == '':
                VimErrorMsg('Permission Denied: {}'.format(cur_node.name))
                return
            if use_rifle and rifle_cmd is not None:
                Shell.run_async(rifle_cmd.format('"{}"'.format(fullpath)))
            else:
                self.vim.command('silent {} {}'.format(open_cmd, fullpath))
                # Manually call on_bufenLer as old vim version might not
                # trigger BufEnter with the above command. It does not cause
                # too much overhead calling on_bufenter two times because most
                # of things are cached
                self.on_bufenter(self.vim.eval("winnr()"))
        else:
            if self.rclone is not None and self.is_remote_path(fullpath):
                self.rclone.ensure_downloaded(fullpath)

            if rifle_cmd is None:
                rifle_cmd = self.rifle.decide_open_cmd(fullpath)

            if use_rifle and rifle_cmd is not None:
                Shell.run_async(rifle_cmd.format('"{}"'.format(fullpath)))
            else:
                try:
                    self.vim.command('{} {}'.format(open_cmd, fullpath))
                except Exception as e:
                    err_msg = str(e)
                    if 'E325' not in err_msg:
                        VimErrorMsg(err_msg)

    def NETRefresh(self):
        cur_buf = self.cur_buf
        cur_buf.refresh_nodes(force_refreh=True)

    def NETRTabOpen(self):
        self.NETROpen('tabedit', use_rifle=False)

    def NETRTabBgOpen(self):
        self.NETROpen('tabedit', use_rifle=False)
        self.vim.command('tabprevious')

    def NETRBufOpen(self):
        self.NETROpen('edit', use_rifle=False)

    def NETRBufVSplitOpen(self):
        self.NETROpen(VimVar('NETRSplitOrientation') + ' vsplit',
                      use_rifle=False)

    def NETRBufHSplitOpen(self):
        self.NETROpen(VimVar('NETRSplitOrientation') + ' split',
                      use_rifle=False)

    def NETRBufPanelOpen(self):
        if self.cur_node.is_DIR:
            return

        if len(self.vim.current.tabpage.windows) == 1:
            self.NETROpen(VimVar('NETRSplitOrientation') + ' vsplit',
                          use_rifle=False)
            newsize = VimCurWinWidth() * VimVar('NETRPanelSize')
            self.vim.command('vertical resize {}'.format(newsize))
        else:
            fpath = self.cur_node.fullpath
            self.vim.command('wincmd l')
            self.vim.command('edit {}'.format(fpath))

    def NETRAskOpen(self):
        fullpath = self.cur_node.fullpath
        if self.askUI is None:
            self.askUI = AskUI(self.vim, self)
        self.askUI.ask(self.rifle.list_available_cmd(fullpath), fullpath)

    def NETRParentDir(self):
        """Real work is done in on_bufenter."""
        cur_buf = self.cur_buf
        cwd = cur_buf.wd
        pdir = self.fs.parent_dir(cwd)
        self.vim.command('silent edit {}'.format(pdir))
        # Manually call on_bufenter, see comments in NETROpen
        self.on_bufenter(self.vim.eval("winnr()"))
        cur_buf = self.cur_buf
        cur_buf.set_clineno_by_path(cwd)
        # Manually call on_cursormoved as synchronous on_bufenter block
        # on_cursormoved event handler, which should trigger by the previous
        # line.
        cur_buf.on_cursormoved()

    def NETRVimCD(self):
        curName = self.cur_node.fullpath
        if os.path.isdir(curName):
            self.vim.command('silent lcd {}'.format(curName))
        else:
            self.vim.command('silent lcd {}'.format(os.path.dirname(curName)))
        VimWarningMsg('Set pwd to {}'.format(self.vim.eval('getcwd()')))

    def NETRToggleExpand(self):
        self.cur_buf.toggle_expand()

    def NETRNew(self):
        if self.newUI is None:
            self.newUI = NewUI(self.vim)
        self.newUI.show()
        self.pend_onuiquit(self.new_onuiiquit, numArgs=1)

    def new_onuiiquit(self, opt):
        cwd = os.path.dirname(self.cur_node.fullpath)
        if opt == 'd':
            name = VimUserInput('New directory name')
            Shell.mkdir(os.path.join(cwd, name))
        elif opt == 'f':
            name = VimUserInput('New file name')
            Shell.touch(os.path.join(cwd, name))
        self.cur_buf.refresh_nodes()

    def NETREdit(self):
        self.unmap_keys()
        self.cur_buf.edit()

    def NETRSave(self):
        if self.cur_buf.save():
            self.map_keys()

    def NETRToggleShowHidden(self):
        """Change ignore pattern and mark all existing netranger buffers to be
        content_outdated so that their content will be updated when entered
        again."""
        ignore_pat = VimVar('NETRIgnore')
        if '.*' in ignore_pat:
            ignore_pat.remove('.*')
        else:
            ignore_pat.append('.*')
        self.vim.vars['NETRIgnore'] = ignore_pat

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
            self.bookmarkUI = BookMarkUI(self.vim, self)

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
        self.vim.command('silent edit {}'.format(fullpath))
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
        if self.sortUI is None:
            self.sortUI = SortUI(self.vim)
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
            self.helpUI = HelpUI(self.vim, self.keymap_doc)
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

    def NETRCancelPickCutCopy(self):
        self.reset_pick_cut_copy()
        self.cur_buf.refresh_highlight()

    def NETRTogglePick(self):
        """Funciton to Add or remove cur_node to/from picked_nodes.

        Also update the highlight of the current line.
        """
        if self.fs_busy():
            return
        cur_node = self.cur_node
        cur_buf = self.cur_buf
        res = cur_node.toggle_pick()
        if res == Node.ToggleOpRes.ON:
            self.picked_nodes[cur_buf].add(cur_node)
        elif res == Node.ToggleOpRes.OFF:
            self.picked_nodes[cur_buf].remove(cur_node)
        self.cur_buf.refresh_cur_line_hi()

    def NETRTogglePickVisual(self):
        if self.fs_busy():
            return
        self.vim.command('normal! gv')
        beg = int(self.vim.eval('line("\'<")')) - 1
        end = int(self.vim.eval('line("\'>")'))
        cur_buf = self.cur_buf
        for i in range(beg, end):
            node = cur_buf.nodes[i]
            res = node.toggle_pick()
            if res == Node.ToggleOpRes.ON:
                self.picked_nodes[cur_buf].add(node)
            else:
                self.picked_nodes[cur_buf].remove(node)
        cur_buf.refresh_lines_hi([i for i in range(beg, end)])
        self.vim.command('normal! V')

    def NETRCut(self):
        """Move picked_nodes to cut_nodes.

        All buffers containing picked nodes are marked as
        highlight_outdated so that their highlight will be updated when
        entered again.
        """
        if self.fs_busy():
            return
        for buf, nodes in self.picked_nodes.items():
            buf.cut(nodes)
            self.cut_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.cur_buf.refresh_highlight()

    def NETRCutSingle(self):
        if self.fs_busy():
            return
        cur_buf = self.cur_buf
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
        if self.fs_busy():
            return
        for buf, nodes in self.picked_nodes.items():
            buf.copy(nodes)
            self.copied_nodes[buf].update(nodes)
        self.picked_nodes = defaultdict(set)
        self.cur_buf.refresh_highlight()

    def NETRCopySingle(self):
        if self.fs_busy():
            return
        cur_buf = self.cur_buf
        cur_node = self.cur_node
        cur_node.copy()
        self.copied_nodes[cur_buf].add(cur_node)
        cur_buf.refresh_cur_line_hi()

    def fs_busy(self):
        if self.num_fs_op > 0:
            VimErrorMsg(
                'Previous operation that might change the view is not done'
                'yet. Try again later')
            return True
        else:
            return False

    def inc_num_fs_op(self):
        self.num_fs_op += 1

    def dec_num_fs_op(self):
        if self.vim.current.buffer.number in self.bufs:
            self.cur_buf.refresh_nodes(force_refreh=True, cheap_remote_ls=True)
        self.num_fs_op -= 1

    def _NETRPaste_cut_nodes(self):
        cwd = self.vim.eval('getcwd()')
        cwd_is_remote = self.is_remote_path(cwd)
        targets = []
        remote_targets = []

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
                    if cwd_is_remote or self.is_remote_path(buf.wd):
                        remote_targets.append(node.fullpath)
                    else:
                        targets.append(node.fullpath)
                    alreday_moved.add(node.fullpath)
            self.cut_nodes = defaultdict(set)
            if targets:
                self.inc_num_fs_op()
                self.fs.mv(targets, cwd, on_exit=lambda: self.dec_num_fs_op())
            if remote_targets:
                self.inc_num_fs_op()
                self.rclone.mv(targets,
                               cwd,
                               on_exit=lambda: self.dec_num_fs_op())

    def _NETRPaste_copied_nodes(self):
        cwd = self.vim.eval('getcwd()')
        cwd_is_remote = self.is_remote_path(cwd)
        targets = []
        remote_targets = []
        for buf, nodes in self.copied_nodes.items():
            buf.reset_hi(nodes)
            for node in nodes:
                if cwd_is_remote or self.is_remote_path(buf.wd):
                    remote_targets.append(node.fullpath)
                else:
                    targets.append(node.fullpath)
        self.copied_nodes = defaultdict(set)
        if targets:
            self.inc_num_fs_op()
            self.fs.cp(targets, cwd, on_exit=lambda: self.dec_num_fs_op())
        if remote_targets:
            self.inc_num_fs_op()
            self.rclone.cp(targets, cwd, on_exit=lambda: self.dec_num_fs_op())

    def NETRPaste(self):
        """Perform mv from cut_nodes or cp from copied_nodes to cwd.
        For each source (cut/copy) buffer, reset the highlight of the cut/
        copied nodes so that the highlight will be updated when entered again
        in refresh_curbuf
        """
        if self.fs_busy():
            return
        self._NETRPaste_copied_nodes()
        self._NETRPaste_cut_nodes()

    def NETRDelete(self, force=False):
        if self.fs_busy():
            return
        targets = []
        remote_targets = []
        for buf, nodes in self.picked_nodes.items():
            buf.content_outdated = True
            buf.reset_hi(nodes)
            if self.is_remote_path(buf.wd):
                remote_targets += [n.fullpath for n in nodes]
            else:
                targets += [n.fullpath for n in nodes]

        self.picked_nodes = defaultdict(set)

        if targets:
            self.inc_num_fs_op()
            self.fs.rm(targets, force, on_exit=lambda: self.dec_num_fs_op())
        if remote_targets:
            self.inc_num_fs_op()
            self.rclone.rm(remote_targets,
                           force,
                           on_exit=lambda: self.dec_num_fs_op())

    def NETRDeleteSingle(self, force=False):
        if self.fs_busy():
            return
        self.cur_buf.content_outdated = True
        self.inc_num_fs_op()
        self.cur_buf.fs.rm([self.cur_node.fullpath],
                           force,
                           on_exit=lambda: self.dec_num_fs_op())

    def NETRForceDelete(self):
        self.NETRDelete(force=True)

    def NETRForceDeleteSingle(self):
        self.NETRDeleteSingle(force=True)

    def is_remote_path(self, path):
        return path.startswith(VimVar('NETRemoteCacheDir'))

    def NETRemotePull(self):
        """Sync local so that the local content of the current directory will
        be the same as the remote content."""
        try:
            cur_buf = self.cur_buf
        except KeyError:
            VimErrorMsg('Not a netranger buffer')
            return

        if not self.is_remote_path(cur_buf.wd):
            VimErrorMsg('Not a remote directory')
        else:
            self.rclone.sync(cur_buf.wd, Rclone.SyncDirection.DOWN)
        cur_buf.refresh_nodes(force_refreh=True, cheap_remote_ls=True)

    def NETRemotePush(self):
        """Sync remote so that the remote content of the current directory will
        be the same as the local content."""
        try:
            cur_buf = self.cur_buf
        except KeyError:
            VimErrorMsg('Not a netranger buffer')
            return

        if not self.is_remote_path(cur_buf.wd):
            VimErrorMsg('Not a remote directory')
        else:
            self.rclone.sync(cur_buf.wd, Rclone.SyncDirection.UP)

    def NETRemoteList(self):
        if self.rclone is None:
            Rclone.valid_or_install(self.vim)
            self.rclone = Rclone(VimVar('NETRemoteCacheDir'),
                                 VimVar('NETRemoteRoots'))

        if self.rclone.has_remote:
            self.vim.command('tabe ' + VimVar('NETRemoteCacheDir'))
        else:
            VimErrorMsg(
                "There's no remote now. Run 'rclone config' in a terminal to "
                "setup remotes")
