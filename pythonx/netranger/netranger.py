from __future__ import absolute_import, print_function

import datetime
import fnmatch
import os
import re
from collections import defaultdict
from sys import platform

from netranger import Vim, default, preview
from netranger.api import NETRApi
from netranger.colortbl import colorhexstr2ind, colorind2hexstr, colorname2ind
from netranger.config import elipsis_note, file_sz_display_wid
from netranger.enum import Enum
from netranger.fs import FSTarget, LocalFS, Rclone
from netranger.rifle import Rifle
from netranger.shell import Shell
from netranger.ui import AskUI, HelpUI, NewUI, SortUI

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
        self.vim_hi_group = 'NETR' + highlight
        self.highlight = default.color[highlight]

    @property
    def highlight_content(self):
        return Vim.ColorMsg(self.name, self.highlight, self.is_cursor_on)

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
        super(FooterNode, self).__init__("", "", 'footer')

    @property
    def is_INFO(self):
        return True


class HeaderNode(Node):
    def __init__(self, fullpath):
        super(HeaderNode, self).__init__(fullpath,
                                         Shell.abbrevuser(fullpath),
                                         'cwd',
                                         level=0)
        self.re_stat()

    def re_stat(self):
        self.stat = os.stat(self.fullpath)

    @property
    def highlight_content(self):
        return Vim.ColorMsg(self.name, self.highlight, False)

    @property
    def is_INFO(self):
        return True


class EntryNode(Node):
    """Content node."""
    def abbrev_name(self, width):
        """ Return abbreviation of self.name such that it fits into `width`
        (terminal) columns.
        """
        if self.linkto is not None:
            name = self.name + ' -> ' + self.linkto
        else:
            name = self.name

        sz = Vim.strwidth(name)

        if width >= sz:
            # Conceptually, we should add (width - sz) spaces to meet the
            # desired width.  (sz-len(name)) compensates for extra columns
            # occupied by wide-characters.
            return name.ljust(width - (sz - len(name)))
        else:
            ext_beg = name.rfind('.')
            if ext_beg > 0:
                name, ext = name[:ext_beg], elipsis_note + name[ext_beg:]
                sz = Vim.strwidth(name)
            else:
                ext = elipsis_note

            if sz == len(name):
                abbrev_name = name[:width - len(ext)]
            else:
                abbrev_name = self._bisect_trunc(name, width - len(ext))

            return f'{abbrev_name}{ext}'

    def _bisect_trunc(self, s, w):
        """
        Using bisection to find the longest substring that is of width less or
        equal to w.
        """
        from itertools import accumulate
        length = list(accumulate([Vim.strwidth(c) for c in s]))
        if w < length[0]:
            return elipsis_note * w

        left = 0
        right = len(s) - 1
        while left < right:
            middle = left + (right - left) // 2 + 1
            if length[middle] == w:
                # Partial s is of lenth w, return such substring
                return s[:middle + 1]
            elif length[middle] > w:
                right = middle - 1
            else:
                left = middle

        # No substring of s is of exactly width w, pad left spaces with elipsis_note
        return s[:left + 1] + elipsis_note * (w - length[left])

    @property
    def highlight_content(self):
        width = self.buf.winwidth
        level_pad = '  ' * self.level
        size_info = self.size.rjust(file_sz_display_wid + 1)

        left = level_pad
        right = size_info

        def c(msg):
            return Vim.ColorMsg(msg, self.highlight, self.is_cursor_on)

        if NETRApi.HasHooker('node_highlight_content_l',
                             'node_highlight_content_r'):
            left_extra = ''
            left_extra_len = 0
            for hooker in NETRApi.Hookers['node_highlight_content_l']:
                l_s, l_h = hooker(self)
                left_extra_len += Vim.strwidth(l_s)
                left_extra += Vim.ColorMsg(l_s, l_h, False)

            right_extra = ''
            right_extra_len = 0
            for hooker in NETRApi.Hookers['node_highlight_content_r']:
                r_s, r_h = hooker(self)
                right_extra_len += Vim.strwidth(r_s)
                right_extra += Vim.ColorMsg(r_s, r_h, False)

            # Calling c and concatenation multiple times is rather expensive.
            # Hence we avoid it if possible.
            if left_extra_len or right_extra_len:
                return c(left) + left_extra + c(
                    self.abbrev_name(width - len(left) - len(right) -
                                     left_extra_len -
                                     right_extra_len)) + c(right) + right_extra

        return c(
            f'{left}{self.abbrev_name(width - len(left) - len(right))}{right}')

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
        self.ori_highlight = highlight

    def re_stat(self, lazy=False):
        self.linkto = None
        if os.path.islink(self.fullpath):
            try:
                self.linkto = os.readlink(self.fullpath)
            except (OSError, FileNotFoundError, PermissionError):
                pass

        if not lazy:
            try:
                self.stat = os.stat(self.fullpath)
            except (OSError, FileNotFoundError, PermissionError):
                self.stat = None
        else:
            self.stat = None

        if self.stat:
            try:
                self.size = LocalFS.size_str(self.fullpath, self.stat)
            except (OSError, FileNotFoundError, PermissionError):
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
                return 'link'
            else:
                return 'brokenlink'
        elif self.is_DIR:
            return 'dir'
        elif os.access(self.fullpath, os.X_OK):
            return 'exe'
        else:
            return 'file'

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
            self.set_highlight('pick')
            return Node.ToggleOpRes.ON
        elif self.state == Node.State.PICKED:
            self.state = Node.State.NORMAL
            self.set_highlight(self.ori_highlight)
            return Node.ToggleOpRes.OFF
        else:
            return Node.ToggleOpRes.INVALID

    def cut(self):
        if self.state == Node.State.UNDEROP:
            return
        self.state = Node.State.UNDEROP
        self.set_highlight('cut')

    def copy(self):
        if self.state == Node.State.UNDEROP:
            return
        self.state = Node.State.UNDEROP
        self.set_highlight('copy')

    def reset_highlight(self):
        self.state = Node.State.NORMAL
        self.set_highlight(self.ori_highlight)


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
        return self.nodes[self.clineno]

    @property
    def non_info_nodes(self):
        return self.nodes[1:-1]

    @property
    def is_remote(self):
        return self.fs.is_remote

    def ensure_remote_downloaded(self):
        self.fs.ensure_remote_downloaded(self.cur_node.fullpath)

    def nodes_plus_header_footer(self, nodes):
        return [self._header_node] + nodes + [self._footer_node]

    def __init__(self, controler, wd, fs):
        self._controler = controler
        self.wd = wd
        self.last_vim_pwd = self.wd
        self.fs = fs
        self._num_fs_op = 0
        self._pending_on_cursormoved_post = 0
        self._last_on_curosormoved_lineno = -1

        self.content_outdated = False
        self._highlight_outdated = False
        self._sort_outdated = False

        if Vim.Var('NETRAutochdir'):
            Vim.command('lcd ' + wd)

        self._header_node = HeaderNode(wd)
        self._footer_node = FooterNode()
        self.nodes = self.nodes_plus_header_footer(self.create_nodes(self.wd))

        self.clineno = 1
        self.nodes[self.clineno].cursor_on()
        # For lazy redraw in update_nodes_and_redraw, we detect the mtime
        # change of the working directory and all expanded subdirectories.
        self._expanded_nodes = set([self._header_node])
        self._pseudo_header_lineno = None
        self._pseudo_footer_lineno = None

        self.winwidth = Vim.CurWinWidth()
        self.is_editing = False
        self._vim_buf_handle = Vim.current.buffer
        self._redraw()

    def fs_busy(self, echo=True):
        """
        Return True if num_fs_op>0. See Netranger.inc_num_fs_op.
        """
        if self._num_fs_op > 0:
            if echo:
                Vim.ErrorMsg(
                    'Previous operation that might change the view is not done'
                    ' yet. Try again later')
            return True
        else:
            return False

    def inc_num_fs_op(self):
        """ Increase  num_fs_op by 1. See Netranger.inc_num_fs_op. """
        self._num_fs_op += 1

    def dec_num_fs_op(self):
        """ Decrease  num_fs_op by 1. See Netranger.inc_num_fs_op. """
        self._num_fs_op -= 1

    def abbrev_cwd(self, width):
        """ Return the shortend name for header that fits the width. """
        res = self.wd.replace(Shell.userhome, '~')
        if len(res) <= width:
            return res.ljust(width)

        sp = res.split('/')
        szm1 = len(sp) - 1
        total = 2 * (szm1) + len(sp[-1])
        for i in range(szm1 - 1, -1, -1):
            if total + len(sp[i]) - 1 > width:
                for j in range(i + 1):
                    # [:1] ensures that we get at most the first character of
                    # sp[j] if it's not empty.
                    sp[j] = sp[j][:1]
                return '/'.join(sp).ljust(width)
            else:
                total += len(sp[i]) - 1

    def redraw_header_content(self):
        self._header_node.name = self.abbrev_cwd(self.winwidth).strip()
        self._vim_buf_handle[0] = self._header_node.highlight_content

    def redraw_footer_content(self):
        """ Set the buffer's last line to the footer node's content. """
        meta = ''
        cur_node = self.cur_node
        if not cur_node.is_INFO:
            cur_node.re_stat()
            meta = f' {cur_node.acl} {cur_node.user} {cur_node.group} {cur_node.mtime}'
        self._footer_node.name = meta.strip()
        self._vim_buf_handle[-1] = self._footer_node.highlight_content

    def redraw_pedueo_header_footer(self):
        # Recover content for the last line occupied by pseudo header/footer
        # ignore error when buffer no longer has the first/last line
        if self._pseudo_header_lineno is not None:
            try:
                self._vim_buf_handle[self._pseudo_header_lineno] = self.nodes[
                    self._pseudo_header_lineno].highlight_content
            except IndexError:
                pass

        if self._pseudo_footer_lineno is not None:
            try:
                self._vim_buf_handle[self._pseudo_footer_lineno] = self.nodes[
                    self._pseudo_footer_lineno].highlight_content
            except IndexError:
                pass

        # if current line is at the header/footer we need to keep the current
        # line to be the 2nd/penultimate visible line
        first_visible_line = int(Vim.eval('line("w0")')) - 1
        if first_visible_line > 0 and first_visible_line == self.clineno:
            Vim.command("normal! ")
            first_visible_line -= 1

        last_visible_line = int(Vim.eval('line("w$")')) - 1
        if last_visible_line < len(self._vim_buf_handle
                                   ) - 1 and last_visible_line == self.clineno:
            Vim.command("normal! ")
            last_visible_line += 1
            first_visible_line += 1

        # Set the pseudo header/footer
        if first_visible_line > 0:
            self._pseudo_header_lineno = first_visible_line
            self._vim_buf_handle[
                first_visible_line] = self._header_node.highlight_content
        else:
            self._pseudo_header_lineno = None

        if last_visible_line < len(self._vim_buf_handle) - 1:
            self._pseudo_footer_lineno = last_visible_line
            self._vim_buf_handle[
                last_visible_line] = self._footer_node.highlight_content
        else:
            self._pseudo_footer_lineno = None

    def create_nodes(self, wd, level=0):
        nodes = self._create_nodes_with_file_names(self.fs.ls(wd), wd, level)
        return self.sort_nodes(nodes)

    def _create_nodes_with_file_names(self, files, dirpath, level):
        """ Return the nodes for given filenames. """
        files = [f for f in files if not self._controler.should_ignore(f)]
        return [self.create_node(dirpath, f, level) for f in files]

    def create_node(self, dirname, basename, level):
        """ Return the node for the given filename. """
        fullpath = os.path.join(dirname, basename)
        if os.path.isdir(fullpath):
            return DirNode(fullpath, basename, level=level, buf=self)
        else:
            return EntryNode(fullpath, basename, level=level, buf=self)

    def _create_nodes_if_not_exist(self, nodes, dirpath, level,
                                   cheap_remote_ls):
        """ Return missing nodes in dirpath that is not in input nodes. """
        old_paths = set([node.fullpath for node in nodes])
        new_paths = set([
            os.path.join(dirpath, name)
            for name in self.fs.ls(dirpath, cheap_remote_ls)
        ])
        file_names = [
            os.path.basename(path) for path in new_paths.difference(old_paths)
        ]
        return self._create_nodes_with_file_names(file_names, dirpath, level)

    def _sync_nodes_from_fs(self, wd, nodes, level, cheap_remote_ls):
        res = self._create_nodes_if_not_exist(self.nodes, wd, level,
                                              cheap_remote_ls)

        fs_files = set(self.fs.ls(wd, cheap_remote_ls))
        ind = 0
        sz = len(nodes)
        while ind < sz:
            cur_node = nodes[ind]

            # The children of an invalid node will all be invalid
            # Hence, we will start with the next valid node
            if self._controler.should_ignore(
                    cur_node.name) or cur_node.name not in fs_files:
                ind = self.next_lesseq_level_ind(ind, nodes=nodes)
                continue

            res.append(cur_node)
            # Recursively update expanded subnodes
            if cur_node.is_DIR and cur_node.expanded:
                next_ind = self.find_next_ind(
                    nodes, ind + 1, lambda beg, new: new.level < beg.level)
                res += self._sync_nodes_from_fs(cur_node.fullpath,
                                                nodes[ind + 1:next_ind],
                                                level + 1, cheap_remote_ls)
                ind = next_ind
                continue

            ind += 1

        return res

    def update_nodes_and_redraw(self,
                                force_redraw=False,
                                cheap_remote_ls=False):
        """ Update the nodes to reflect the filesystem change.

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
        for node in self._expanded_nodes:
            if os.access(node.fullpath, os.R_OK):
                ori_mtime = node.stat.st_mtime if node.stat else -1
                node.re_stat()
                new_mtime = node.stat.st_mtime
                if new_mtime > ori_mtime:
                    self.content_outdated = True

        if not self.content_outdated and not force_redraw:
            return

        self.content_outdated = False

        new_nodes = self._sync_nodes_from_fs(self.wd, self.non_info_nodes, 0,
                                             cheap_remote_ls)

        ori_node = self.cur_node
        ori_clineno = self.clineno
        self.nodes = self.nodes_plus_header_footer(self.sort_nodes(new_nodes))
        self._redraw()
        self.set_clineno_by_node(ori_node, ori_clineno)

    def reverse_sorted_nodes(self, nodes):
        """ Reverse the sorted nodes with regard to their levels. """
        rev = []
        prev_level = -1
        cur_ind = 0
        for node in nodes:
            if node.level <= prev_level:
                for i, n in enumerate(rev):
                    if n.level == node.level:
                        rev.insert(i, node)
                        cur_ind = i + 1
                        break
            else:
                rev.insert(cur_ind, node)
                cur_ind += 1

            prev_level = node.level
        return rev

    def _sort_prep(self):
        """ Mark the buffer as sort outdated so that it will be sorted when
        entered again. """
        self._sort_outdated = True
        self._last_node_id = self.nodes[self.clineno]

    def sort(self):
        """ Sort the nodes. """
        if not self._sort_outdated:
            return
        self._sort_outdated = False
        for node in self.nodes:
            node.re_stat()
        self.nodes = self.nodes_plus_header_footer(
            self.sort_nodes(self.non_info_nodes))
        self._redraw()
        self.set_clineno_by_node(self._last_node_id)

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
        sorted_nodes = []
        prefix = ''
        prefix_end_ind = [0]
        for i in range(len(nodes)):
            cur_node = nodes[i]

            prev_node = nodes[i - 1]
            if cur_node.level > prev_node.level:
                # cur_node must be a DirNode, hence the same as in the folloing
                # "cur_node.is_DIR" case
                prefix += f'  {sort_fn(prev_node)}{prev_node.name}'
                prefix_end_ind.append(len(prefix))
            else:
                prefix_end_ind = prefix_end_ind[:cur_node.level + 1]
                prefix = prefix[:prefix_end_ind[-1]]
            if cur_node.is_DIR:
                sorted_nodes.append(
                    (f'{prefix}  {sort_fn(cur_node)}{cur_node.name}',
                     cur_node))
            else:
                sorted_nodes.append(
                    (f'{prefix} ~{sort_fn(cur_node)}{cur_node.name}',
                     cur_node))

        sorted_nodes = sorted(sorted_nodes, key=lambda x: x[0])
        sorted_nodes = [node[1] for node in sorted_nodes]
        if reverse:
            sorted_nodes = self.reverse_sorted_nodes(sorted_nodes)

        return sorted_nodes

    def _redraw(self, plain=False):
        """ Redraw the buffer.
        Note that we delegate the job for rendering the forground highlight of
        the cursor line to on_cursormoved by calling _move_vim_cursor.
        """
        for hooker in NETRApi.Hookers['render_begin']:
            hooker(self)

        with self.SetBufferApiGuard():
            if plain:
                self._vim_buf_handle[:] = self.plain_content
            else:
                self._vim_buf_handle[:] = self.highlight_content
        if self._vim_buf_handle.number is self._vim_buf_handle.number:
            self._move_vim_cursor(self.clineno)

        for hooker in NETRApi.Hookers['render_end']:
            hooker(self)

    def _move_vim_cursor(self, lineno):
        """ Will trigger on_cursormoved through CursorMoved autocmd. """
        Vim.command(f'call cursor({lineno + 1},1)')

    def on_cursormoved(self):
        """ Handle for CursorMoved autocmd.

        1. Make the node in the previous cursor line background highlight.
        2. Make the node in the current cursor line foreground highlight.
        3. Set cline_no to the current cursor line.
        4. Enforce throttling by avoiding calling on_cursormoved_post
        frequently. See on_cursormoved_post for details.
        """
        new_lineno = int(Vim.eval("line('.')")) - 1

        # Do not stay on footer
        if new_lineno == len(self.nodes) - 1:
            Vim.command('normal! k')
            new_lineno -= 1

        if new_lineno == self.clineno:
            self.nodes[new_lineno].cursor_on()
            self.redraw_lines([new_lineno])
        else:
            oc = self.clineno
            self.clineno = new_lineno
            if oc < len(self.nodes):
                self.nodes[oc].cursor_off()
            self.nodes[new_lineno].cursor_on()
            self.redraw_lines([oc, new_lineno])
        self._pending_on_cursormoved_post += 1

    def on_cursormoved_post(self):
        """ Run heavy-duty tasks for CursorMoved autocmd. Each
        on_cursormoved_post is delayed by some time, if during this time, more
        CursorMoved event happens, only the last event will be served. """
        self._pending_on_cursormoved_post -= 1
        if self._pending_on_cursormoved_post > 0:
            return

        # The line self.vim_set_line... below triggers on_cursormoved event,
        # which in term triggers on_cursormoved_post. This test is to avoid
        # such call loop.
        if self.clineno == self._last_on_curosormoved_lineno:
            return
        self._last_on_curosormoved_lineno = self.clineno

        # Avoid rerender if the current vim buffer is not the same as
        # self._vim_buf_handle.
        if self._vim_buf_handle.number != Vim.current.buffer.number\
                or self.is_editing:
            return

        if self._controler._is_previewing:
            self.preview_on()

        with self.SetBufferApiGuard():
            self.redraw_header_content()
            self.redraw_footer_content()
            self.redraw_pedueo_header_footer()
            self._vim_buf_handle[self.clineno] = self.nodes[
                self.clineno].highlight_content

    def set_clineno_by_lineno(self, lineno):
        """ Set cursor line by number. """
        self._move_vim_cursor(lineno)

    def set_clineno_by_path(self, path):
        """ Set cursor line by full path. """
        for ind, node in enumerate(self.nodes):
            if node.fullpath == path:
                self._move_vim_cursor(ind)
                break

    def set_clineno_by_node(self, node, ori_clineno=0):
        """ Set cursor line by node reference. """
        if node in self.nodes:
            index = self.nodes.index(node)
            self._move_vim_cursor(index)
            self.clineno = index
        else:
            ori_clineno = min(ori_clineno, len(Vim.current.buffer) - 1)
            self._move_vim_cursor(ori_clineno)
            self.clineno = ori_clineno

    def SetBufferApiGuard(self):
        """ Context for setting buffer content.
        1. Set/restore modifiable
        2. vim.buffer[...] = ... api might moves cursor of all windows
           displaying the buffer. We prevent this by save/restore all the
           window cursor position.
        """
        class G(object):
            def __enter__(g):
                self._vim_buf_handle.options['modifiable'] = True
                g.win_cursor = []
                for w in Vim.windows:
                    if w.buffer == self._vim_buf_handle:
                        g.win_cursor.append((w, w.cursor))
                return g

            def __exit__(g, type, value, traceback):
                for w, c in g.win_cursor:
                    w.cursor = (min(c[0], len(self._vim_buf_handle) - 1), c[1])
                self._vim_buf_handle.options['modifiable'] = False

        return G()

    def redraw_lines(self, linenos):
        """ Redraw the highlight of nodes by line numbers. """
        sz = min(len(self.nodes), len(self._vim_buf_handle))

        with self.SetBufferApiGuard():
            for i in linenos:
                if i < sz:
                    self._vim_buf_handle[i] = self.nodes[i].highlight_content

    def redraw_if_winwidth_changed(self, force=False):
        """ Redraw the buffer highlight if the window widhth changed. """

        if self.is_editing and not force:
            return

        winwidth = Vim.CurWinWidth()
        if self.winwidth != winwidth:
            # print('hi', self.wd, 'real: ', winwidth, 'saved: ', self.winwidth)
            self.winwidth = winwidth

            with self.SetBufferApiGuard():
                self.redraw_header_content()
                for i, node in enumerate(self.nodes):
                    self._vim_buf_handle[i] = node.highlight_content
                self.redraw_pedueo_header_footer()

    def reset_highlight(self, nodes):
        """ Reset the highlight of the nodes and add them to
        highlight_outdated_nodes to redraw when the buffer is entered again.
        """
        for node in nodes:
            node.reset_highlight()
        self._highlight_outdated = True

    def redraw_if_highlight_outdated(self):
        """ Redraw the highlight of nodes in highlight_outdated_nodes.
        """
        if self._highlight_outdated:
            with self.SetBufferApiGuard():
                self._vim_buf_handle[:] = self.highlight_content
            self._highlight_outdated = False

    def redraw_cur_line(self):
        """ Redraw the highlight of the current node. """
        self.redraw_lines([self.clineno])

    def VimCD(self):
        """ Perform :cd. """
        target_dir = self.cur_node.fullpath
        if not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        Vim.command(f'silent lcd {target_dir}')
        self.last_vim_pwd = target_dir

    def _record_previewee(self, bufnr, winid):
        Vim.current.window.vars['netranger_last_previewee'] = [
            self.cur_node.is_DIR, bufnr, winid
        ]

    def _close_last_previewee(self):
        info = Vim.WindowVar('netranger_last_previewee', [])
        if len(info) == 0:
            return

        is_DIR, bufnr, winid = info
        win_nr = int(Vim.eval(f'win_id2win({winid})'))
        if win_nr == 0:
            return

        if is_DIR:
            Vim.command(f'{win_nr}hide')
        else:
            if Vim.eval(f'getbufvar({bufnr}, "&buftype")') == 'terminal':
                Vim.command(f'bwipeout! {bufnr}')
            elif Vim.eval(f'getbufvar({bufnr}, "&modified")') == '1':
                Vim.command(f'{win_nr}hide')
            elif len(Vim.eval(f'win_findbuf({bufnr})')) > 1:
                Vim.command(f'{win_nr}hide')
            else:
                Vim.command(f'bwipeout! {bufnr}')

    def preview_on(self):
        """ Turn preview panel on. """
        if Vim.WindowVar('netranger_is_previewee', False):
            return

        if Vim.eval('get(g:, "NETRCustomNopreview",{->0})()') != '0':
            return

        previewer_win = Vim.current.window
        Vim.current.window.vars['netranger_is_previewer'] = True
        self._close_last_previewee()

        cur_node = self.cur_node

        total_width = Vim.CurWinWidth()
        preview_width = int(total_width * Vim.Var('NETRPreviewSize') / 2)
        preview_close_on_tableave = False

        if cur_node.is_INFO:
            self.redraw_if_winwidth_changed()
            return
        elif cur_node.is_DIR:
            with self._controler.DisableOnWinEnter():
                if not os.access(cur_node.fullpath, os.X_OK):
                    Vim.ErrorMsg(f'Permission Denied: {cur_node.name}')
                    return
                Vim.command(
                    f'rightbelow vert {preview_width} vsplit {cur_node.fullpath}'
                )
            self._controler.cur_buf.redraw_if_winwidth_changed(force=True)
        else:
            with self._controler.DisableOnWinEnter():
                Vim.command(f'rightbelow vert {preview_width} new')
            preview_close_on_tableave = self._controler.preview(
                cur_node.fullpath, total_width, preview_width)

        with self._controler.DisableOnWinEnter():
            Vim.current.window.vars['netranger_is_previewee'] = True
            previewee_bufnr = Vim.eval('bufnr()')
            previewee_winid = Vim.eval('win_getid()')

            Vim.current.window = previewer_win
            if preview_close_on_tableave:
                Vim.command('augroup NETRPREVIEW')
                Vim.command(f'autocmd TabLeave <buffer> ++once \
                    py3 ranger._bufs[{self._vim_buf_handle.number}]._close_last_previewee()'
                            )
                Vim.command('augroup END')
            else:
                Vim.command('silent! autocmd! NETRPREVIEW TabLeave <buffer>')
            self._record_previewee(previewee_bufnr, previewee_winid)

        # Update the previewer window width. Note that it is not done above as
        # DisableOnWinEnter prevent this from happening through
        # autocmd.
        self.redraw_if_winwidth_changed()
        cur_width = Vim.CurWinWidth()
        for w in Vim.current.tabpage.windows:
            if 'netranger_is_previewer' in w.vars:
                w.width = cur_width

    def preview_off(self):
        """ Turn preview panel off. """
        self._close_last_previewee()
        self.redraw_if_winwidth_changed()

    def _expand_node(self, node, level):
        if not node.is_DIR:
            return []

        try:
            node.expanded = True
            self._expanded_nodes.add(node)
            if level == 1:
                return self.create_nodes(node.fullpath, node.level + 1)
            else:
                res = []
                for n in self.create_nodes(node.fullpath, node.level + 1):
                    res += [n] + self._expand_node(n, level - 1)
                return res
        except PermissionError:
            Vim.ErrorMsg(f'Permission Denied. Not Expanding: {node.name}')
            return []

    def toggle_expand(self, maxlevel=1):
        """Create subnodes for the target directory.

        Also record the mtime of the target directory so that we can
        redraw in update_nodes_and_redraw if the subdirectory is changed.
        """
        cur_node = self.cur_node
        if not cur_node.is_DIR:
            return
        if cur_node.expanded:
            end_ind = self.next_lesseq_level_ind(self.clineno)
            for i in range(self.clineno, end_ind):
                if self.nodes[i].is_DIR and self.nodes[i].expanded:
                    self._expanded_nodes.remove(self.nodes[i])
            self._controler.remove_pick_cut_copy(
                self, self.nodes[self.clineno + 1:end_ind])
            del self.nodes[self.clineno + 1:end_ind]
            cur_node.expanded = False
        else:
            self.nodes[self.clineno + 1:self.clineno + 1] = self._expand_node(
                self.cur_node, maxlevel)
        self._redraw()

    def edit(self):
        """ Enter edit mode. """
        self.is_editing = True
        self._redraw(plain=True)
        for i, node in enumerate(self.nodes):
            Vim.command(f'call matchaddpos("{node.vim_hi_group}", [{i+1}])')
        Vim.command('setlocal buftype=acwrite')
        Vim.command('setlocal modifiable')
        Vim.command('let old_undolevels = &undolevels')
        Vim.command('set undolevels=-1')
        Vim.command('exe "normal a \<BS>\<Esc>"')
        Vim.command('let &undolevels = old_undolevels')
        Vim.command('unlet old_undolevels')

    def save(self):
        """Rename the files according to current buffer content.

        Retur false if called but is_editing is false. Otherwise return
        true.
        """
        if not self.is_editing:
            return False
        self.is_editing = False

        Vim.command(f'call clearmatches()')

        vim_buf = self._vim_buf_handle
        if len(self.nodes) != len(vim_buf):
            Vim.ErrorMsg('Edit mode can not add/delete files!')
            self._redraw()
            return True

        ori_node = self.cur_node

        change = {}
        i = 0
        for i in range(len(vim_buf)):
            line = vim_buf[i].strip()
            if not self.nodes[i].is_INFO and line != self.nodes[i].name:

                # change name of the i'th node
                oripath = self.nodes[i].rename(line)
                change[oripath] = self.nodes[i].fullpath

                # change dirname of subnodes
                end_ind = self.next_lesseq_level_ind(beg_ind=i)
                for j in range(i + 1, end_ind):
                    self.nodes[j].change_dirname(oripath,
                                                 self.nodes[i].fullpath)

        # apply the changes
        for oripath, fullpath in change.items():
            self.fs.rename(oripath, fullpath)

        self.nodes = self.nodes_plus_header_footer(
            self.sort_nodes(self.non_info_nodes))
        self._redraw()
        self.set_clineno_by_node(ori_node)
        Vim.command('setlocal nomodifiable')
        Vim.command('setlocal buftype=nofile')
        return True

    def cut(self, nodes):
        """ Update the highlight of picked nodes to cut. """
        for node in nodes:
            node.cut()
        self._highlight_outdated = True

    def copy(self, nodes):
        """ Update the highlight of picked nodes to copy. """
        for node in nodes:
            node.copy()
        self._highlight_outdated = True

    def find_next_ind(self, nodes, ind, pred):
        """ Return the index of first next node that satisfies pred. """
        beg_node = nodes[ind]
        ind += 1
        sz = len(nodes)
        while ind < sz:
            if pred(beg_node, nodes[ind]):
                break
            ind += 1
        return ind

    def next_lesseq_level_ind(self, beg_ind, nodes=None):
        """ Return the index of the next node with less or equal indent. """
        if nodes is None:
            nodes = self.nodes
        return self.find_next_ind(nodes, beg_ind,
                                  lambda beg, new: new.level <= beg.level)

    def find_prev_ind(self, nodes, ind, pred):
        """ Return the index of first previous node that satisfies pred. """
        beg_node = nodes[ind]
        ind -= 1
        while ind > -1:
            if pred(beg_node, nodes[ind]):
                break
            ind -= 1
        return ind

    def prev_lesseq_level_ind(self, beg_ind, nodes=None):
        """ Return the index of the previous node with less or equal indent. """
        if nodes is None:
            nodes = self.nodes
        return self.find_prev_ind(nodes, beg_ind,
                                  lambda beg, new: new.level <= beg.level)


class Netranger(object):
    """ Main (mvc) controler.

    Autodmc handles:
    1. BufEnter: on_bufenter. create/update NetRangerBuf.
    2. CursorMoved: on_cursormoved. update node highlighting and some othe stuff.
    """
    def generate_and_ret_buf(self):
        bufname = Vim.current.buffer.name
        if len(bufname) > 0 and bufname[-1] == '~':
            bufname = os.path.expanduser('~')
        if not os.path.isdir(bufname):
            return
        if os.path.islink(bufname):
            bufname = os.path.join(os.path.dirname(bufname),
                                   os.readlink(bufname))
        bufname = os.path.abspath(bufname)

        # if self.buf_existed(bufname):
            # self._bufs[Vim.current.buffer.number] =  self._wd2bufnum[bufname]
        # else:
        self.gen_new_buf(bufname)

        return self._bufs[Vim.current.buffer.number]


        

    @property
    def cur_buf(self):
        if Vim.current.buffer.number in self._bufs:
            return self._bufs[Vim.current.buffer.number]
        else:
            return self.generate_and_ret_buf()

    @property
    def cur_node(self):
        return self.cur_buf.cur_node

    @property
    def cwd(self):
        return self.cur_buf.wd

    def __init__(self):
        self.init_vim_variables()
        self.init_keymaps()

        self._sudo = False
        self._bufs = {}
        self._wd2bufnum = {}
        self._picked_nodes = defaultdict(set)
        self._cut_nodes = defaultdict(set)
        self._copied_nodes = defaultdict(set)
        self._helpUI = None
        self._sortUI = None
        self._askUI = None
        self._onuiquit = None
        self._newUI = None
        self._onuiquit_num_args = 0
        self._NetRangerBuf_init_winwidth = -1
        self._is_previewing = Vim.Var("NETRPreviewDefaultOn")
        self.preview = preview.Previewer()
        self._disable_on_winenter = False
        self._cur_search_buf = None
        self._last_search_pattern = None

        Rclone.init(Vim.Var('NETRemoteCacheDir'), Vim.Var('NETRemoteRoots'))
        Shell.mkdir(default.variables['NETRRootDir'])
        self._rifle = Rifle(Vim.Var('NETRRifleFile'))

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
        """ Set the color table for nodes in a NetRangerBuf. """
        for name, color in Vim.Var('NETRColors').items():
            if name not in default.color:
                Vim.ErrorMsg(
                    f'netranger: {name} is not a valid NETRColors key!')
                continue
            if type(color) is int and (color < 0 or color > 255):
                Vim.ErrorMsg(
                    f'netranger: {name}:{color} value is not within 0~255')
                continue
            elif type(color) is str:
                if color[0] == '#':
                    color, ocolor = colorhexstr2ind.get(color, None), color
                else:
                    color, ocolor = colorname2ind.get(color, None), color
                if color is None:
                    Vim.ErrorMsg(
                        f'netranger: {name}:{ocolor} is not a valid color!')
                    continue

            default.color[name] = color

        for key, value in default.color.items():
            if type(value) is str:
                default.color[key] = colorname2ind[value]
        Vim.SetVar('_NETRSavedColors', [(n, colorind2hexstr[c], c)
                                        for n, c in default.color.items()])

        # True color support for gui/termguicolors
        if Vim.gui_compaitable:

            def hex_to_code(s):
                s = s.lstrip('#')
                return ';'.join(
                    tuple(str(int(s[i:i + 2], 16)) for i in range(0, 6, 2)))

            for name, color in Vim.Var('NETRGuiColors').items():
                if name not in default.color:
                    Vim.ErrorMsg(
                        f'netranger: {name} is not a valid NETRGuiColors key!')
                    continue
                default.color[name] = color

            for key, value in default.color.items():
                if type(value) is int:
                    default.color[key] = colorind2hexstr[value]

            Vim.SetVar('_NETRSavedGuiColors',
                       [(n, c, hex_to_code(c))
                        for n, c in default.color.items()])

            for key, value in default.color.items():
                default.color[key] = hex_to_code(value)

    def should_ignore(self, basename):
        """ Return True if basename should not be displayed in a NetRangerBuf. """
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
            skip.append(k)
        for fn, (keys, desc) in default.keymap.items():
            user_keys = Vim.Var(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymap_doc[fn] = (user_keys, desc)
            for key in user_keys:
                self.key2fn[key] = getattr(self, fn)

        skip = []
        for k in Vim.Var('NETRDefaultVisualMapSkip'):
            skip.append(k)
        for fn, (keys, desc) in default.visual_keymap.items():
            user_keys = Vim.Var(fn, [])
            user_keys += [k for k in keys if k not in skip]
            self.keymap_doc[fn] = (keys, desc)
            for key in user_keys:
                self.visual_key2fn[key] = getattr(self, fn)

    def map_keys(self):
        """ Map keys for a NetRangerBuf. """
        def literal(key):
            if key[0] == '<':
                escape_key = '<lt>' + key[1:]
            else:
                escape_key = key
            return escape_key

        for key in self.key2fn:
            Vim.command(f'nnoremap <nowait> <silent> <buffer> {key} '
                        f':py3 ranger.key2fn[\"{literal(key)}\"]()<cr>')
        for key in self.visual_key2fn:
            Vim.command(f'vnoremap <nowait> <silent> <buffer> {key} '
                        f':py3 ranger.visual_key2fn[\"{literal(key)}\"]()<cr>')

    def unmap_keys(self):
        """ Clear the key mappings in a NetRangerBuf (for edit mode). """
        for key, fn in self.key2fn.items():
            Vim.command(f'nunmap <silent> <buffer> {key}')

        for key, fn in self.visual_key2fn.items():
            Vim.command(f'vunmap <silent> <buffer> {key}')

    def map(self, key, fn, check=False):
        """ Enables user to map custom key mapping in a NetRangerBuf. """
        if check and key in self.key2fn:
            Vim.ErrorMsg("netranger: Fail to bind key {} to {} because it has "
                         "been mapped to other {}.".format(
                             key, fn.__name__, self.key2fn[key].__name__))
        self.key2fn[key] = fn

    def DisableOnWinEnter(self):
        """ Context for disabling on_winenter handler.
        Useful to save unnecessary redraw_if_winwidth_changed call.
        """
        class C(object):
            def __enter__(c):
                self._disable_on_winenter = True
                return c

            def __exit__(c, type, value, traceback):
                self._disable_on_winenter = False

        return C()

    def on_winenter(self, bufnum):
        """ Handle for WinEnter autocmd. """
        if self._disable_on_winenter:
            return
        if bufnum in self._bufs:
            self.cur_buf.redraw_if_winwidth_changed()

    def on_bufenter(self, bufnum):
        """ Handle for BufferError autocmd.

        Two possible cases:
        1. The buffer is an existing netranger buffer (but not wiped out):
        redraw buffer content (e.g. directory content changed else where) and
        call any pending onuiquit functions.
        2. The buffer is a [No Name] temporary buffer and the buffer name is a
           directory. Then we either create a new netranger buffer or bring up
           an existing netranger buffer (which was wiped out).
        """
        if bufnum in self._bufs:
            self.update_curbuf()
            self.cur_buf.redraw_if_winwidth_changed()
            if self._onuiquit is not None:
                # If not enough arguments are passed, ignore the pending
                # onuituit, e.g. quit the sort go ui without pressing key to
                # specify sort criterian.
                if len(Vim.Var('NETRRegister')) == self._onuiquit_num_args:
                    self._onuiquit(*Vim.Var('NETRRegister'))
                self._onuiquit = None
                Vim.vars['NETRRegister'] = []
                self._onuiquit_num_args = 0
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

    def update_curbuf(self):
        """ Update an existing NetRangerBuf's nodes and highlight. """
        cur_buf = self.cur_buf

        # deal with content changed, e.g., file operation outside
        cur_buf.update_nodes_and_redraw()

        # deal with highlight changed, e.g., pick, copy hi dismiss because of
        # paste
        cur_buf.redraw_if_highlight_outdated()

        # ensure pwd is correct
        if Vim.Var('NETRAutochdir'):
            Vim.command('lcd ' + cur_buf.last_vim_pwd)

    def show_existing_buf(self, bufname):
        """ Show an existing NETRangerBuf. """
        ori_bufnum = Vim.current.buffer.number
        existed_bufnum = self._wd2bufnum[bufname]
        Vim.command(f'{existed_bufnum}b')
        self.set_buf_option()
        buf = self._bufs[existed_bufnum]
        self.update_curbuf()

        # Check window width in case the window was closed in a different
        # width
        buf.redraw_if_winwidth_changed()

        if ori_bufnum not in self._bufs:
            # wipe out the [No Name] temporary buffer
            Vim.command(f'bwipeout {ori_bufnum}')
        buf.set_clineno_by_lineno(buf.clineno)

    def gen_new_buf(self, bufname):
        """ Generate a new NETRangerBuf. """
        bufnum = Vim.current.buffer.number
        if (bufname.startswith(Vim.Var('NETRemoteCacheDir'))):
            self._bufs[bufnum] = NetRangerBuf(self, os.path.abspath(bufname),
                                              Rclone)
        else:
            fullpath = os.path.abspath(bufname)
            if not os.access(fullpath, os.X_OK):
                Vim.ErrorMsg('Permission Denied')
                Vim.command('quit')
                return
            self._bufs[bufnum] = NetRangerBuf(self, os.path.abspath(bufname),
                                              LocalFS)
        # This shouldn't be necessary. However, without this, there is a bug in
        # neovim with preview
        Vim.command(f'silent file {bufname}')

        self.map_keys()
        self._wd2bufnum[bufname] = bufnum
        self.set_buf_option()

    def buf_existed(self, wd):
        """ Check if there's an existing NETRangerBuf.
        This avoids reinitializing a NETRangerBuf when the corresponding vim
        buffer is wipeout and later reentered.
        """
        if wd not in self._wd2bufnum:
            return False

        bufnum = self._wd2bufnum[wd]
        try:
            buf = Vim.buffers[bufnum]
            return buf.valid
        except KeyError:
            del self._wd2bufnum[wd]
            del self._bufs[bufnum]
            return False

    def set_buf_option(self):
        """ Set common option for the current buffer. """
        Vim.command('setlocal buftype=nofile')
        Vim.command('setlocal filetype=netranger')
        Vim.command('setlocal encoding=utf-8')
        Vim.command('setlocal noswapfile')
        Vim.command('setlocal nowrap')
        Vim.command('setlocal foldmethod=manual')
        Vim.command('setlocal foldcolumn=0')
        Vim.command('setlocal scrolloff=0')
        Vim.command('setlocal sidescrolloff=0')
        Vim.command('setlocal nofoldenable')
        Vim.command('setlocal nobuflisted')
        Vim.command('setlocal nospell')
        Vim.command('setlocal bufhidden=hide')
        Vim.command('setlocal conceallevel=3')
        Vim.command('setlocal concealcursor=nvc')
        Vim.command('setlocal nocursorline')
        Vim.command('setlocal nolist')

    def on_cursormoved(self, bufnum):
        """ Handle for CursorMoved.
        Only switch the cursor line foreground highlight. All hevay-duty tasks
        are performed in on_cursormoved_post. This makes on_cursormoved runs
        faster for e.g., when the user keep pressing j just to move down.

        @param bufnum: current buffer number
        """
        if not self._bufs[bufnum].is_editing:
            if Vim.eval('mode()') == 'V':
                return
            self._bufs[bufnum].on_cursormoved()
            Vim.Timer(Vim.Var('NETRPreviewDelay'), self.on_cursormoved_post,
                      'ranger.on_cursormoved_post', bufnum)

    def on_cursormoved_post(self, bufnum):
        """ Perform heavy-duty tasks for CursorMoved autocmd.

        We put all heavy-duty but not time-urgent tasks that we want to perform
        on CursorMoved over a node here. The heavy tasks might not even be
        executed thanks to the throttling trick applied in
        NetRangerBuf.on_cursormoved_post.
        """
        self._bufs[bufnum].on_cursormoved_post()

    def pend_onuiquit(self, fn, num_args=0):
        """ Called by UIs to perform actions after reentering netranger buffer.
        Used for waiting for user input in some UI and then defer what to do
        when the UI window is quit and the netranger buffer gain focus again.
        Function arguments are passed as a list via vim variable
        g:'NETRRegister'.

        @param fn: function to be executed
        @param num_args: number of args expected to see in g:'NETRRegister'.
        When exectuing fn, if num_args do not match, fn will not be executed
        which deals with the case for e.g., when user press no keys in
        Sort UI but simply quit the UI)
        """
        self._onuiquit = fn
        self._onuiquit_num_args = num_args

    def _rifle_print_error(self, job_id, err_msg):
        if Vim.Var('NETRRifleDisplayError'):
            Vim.ErrorMsg(err_msg)

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
                Vim.ErrorMsg(f'Permission Denied: {cur_node.name}')
                return
            if use_rifle and rifle_cmd is not None:
                Vim.AsyncRun(rifle_cmd.format(f'"{fullpath}"'),
                             on_stderr=self._rifle_print_error)
            else:
                with self.KeepPreviewState():
                    Vim.command(f'silent {open_cmd} {fullpath}')
        else:
            self.cur_buf.ensure_remote_downloaded()

            if rifle_cmd is None:
                rifle_cmd = self._rifle.decide_open_cmd(fullpath)

            if use_rifle and rifle_cmd is not None:
                Vim.AsyncRun(rifle_cmd.format(f'"{fullpath}"'),
                             on_stderr=self._rifle_print_error)
            else:
                try:
                    Vim.command(f'{open_cmd} {fullpath}')
                    if NETRApi.HasHooker('NETROpenCmd_end'):
                        for hooker in NETRApi.Hookers['NETROpenCmd_end']:
                            hooker(self)
                except Exception as e:
                    err_msg = str(e)
                    if 'E325' not in err_msg:
                        Vim.ErrorMsg(err_msg)

    def NETRedraw(self):
        """ Force redraw the current buffer. """
        cur_buf = self.cur_buf
        cur_buf.update_nodes_and_redraw(force_redraw=True)
        cur_buf.redraw_if_winwidth_changed()

    def NETRTabOpen(self):
        """ Open the current node in a new tab """
        self.NETROpen('tabedit', use_rifle=False)

    def NETRTabBgOpen(self):
        """ Open the current node in a new tab, staying in the current tab.
        """
        self.NETROpen('tabedit', use_rifle=False)
        Vim.command('tabprevious')

    def NETRBufOpen(self):
        """ Open the current node in the current buffer.  """
        self.NETROpen('edit', use_rifle=False)

    def NETRBufVSplitOpen(self):
        """ Open the current node in a vertical split.  """
        self.NETROpen(Vim.Var('NETRSplitOrientation') + ' vsplit',
                      use_rifle=False)

    def NETRBufHSplitOpen(self):
        """ Open the current node in a horizontal split.  """
        self.NETROpen(Vim.Var('NETRSplitOrientation') + ' split',
                      use_rifle=False)

    def NETRBufPanelOpen(self):
        """ Open the current node on the right with the current node serving as
        a panel.
        """
        if self.cur_node.is_DIR:
            with self.KeepPreviewState():
                self.NETRBufOpen()
            return

        if not self._is_previewing:
            self.NETRTogglePreview()
        Vim.command('wincmd l')

    def NETRAskOpen(self):
        """ Show the AskUI. """
        fullpath = self.cur_node.fullpath
        if self._askUI is None:
            self._askUI = AskUI(self)
        self._askUI.ask(self._rifle.list_available_cmd(fullpath), fullpath)

    def NETRTogglePreview(self):
        """ Toggle preview panel. """
        self._is_previewing = not self._is_previewing
        if self._is_previewing:
            self.cur_buf.preview_on()
            Vim.WarningMsg('Preview on')
        else:
            self.cur_buf.preview_off()
            Vim.WarningMsg('Preview off')

    def KeepPreviewState(self):
        """ Context to keep the preview panel on. """
        class C(object):
            def __enter__(cself):
                return cself

            def __exit__(cself, type, value, traceback):
                if self._is_previewing:
                    self.cur_buf.preview_on()

        return C()

    def NETRParentDir(self):
        """ View the parent directory.
        The real work is done in on_bufenter.
        """
        cdir = self.cur_buf.wd
        pdir = LocalFS.parent_dir(cdir)
        if pdir == cdir:
            return

        # On neovim, the command py3 vim.command('/') doesn't work.
        if pdir == '/':
            pdir += '..'

        with self.KeepPreviewState():
            Vim.command(f'silent edit {pdir}')
            self.cur_buf.set_clineno_by_path(cdir)

    def NETRGoPrevSibling(self):
        """ Move the cursor to the previous node with same indent. """
        cur_buf = self.cur_buf
        cur_buf.set_clineno_by_lineno(
            cur_buf.prev_lesseq_level_ind(cur_buf.clineno))

    def NETRGoNextSibling(self):
        """ Move the cursor to the next node with same indent. """
        cur_buf = self.cur_buf
        cur_buf.set_clineno_by_lineno(
            cur_buf.next_lesseq_level_ind(cur_buf.clineno))

    def NETRVimCD(self):
        """ :cd to the current node. """
        self.cur_buf.VimCD()
        Vim.WarningMsg(f'Set pwd to {Vim.eval("getcwd()")}')

    def NETRToggleExpand(self):
        """ Expand the current node. """
        if self.cur_buf.fs_busy():
            return
        if int(Vim.eval('foldclosed(".")')) > -1:
            Vim.command('normal! za')
        else:
            self.cur_buf.toggle_expand()

    def NETRToggleExpandRec(self):
        """ Expand the current node recursively. """
        if self.cur_buf.fs_busy():
            return
        self.cur_buf.toggle_expand(
            maxlevel=Vim.current.window.options['foldnestmax'])

    def NETRNew(self):
        """ Show the NewUI. """
        if self.cur_buf.fs_busy():
            return
        if self._newUI is None:
            self._newUI = NewUI()
        self._newUI.show()
        self.pend_onuiquit(self.new_onuiiquit, num_args=1)

    def new_onuiiquit(self, opt):
        """ The quit callback for the NewUI. """
        cur_buf = self.cur_buf
        if opt == 'd':
            name = Vim.UserInput('New directory name')
            cur_buf.fs.mkdir(os.path.join(cur_buf.last_vim_pwd, name))
        elif opt == 'f':
            name = Vim.UserInput('New file name')
            cur_buf.fs.touch(os.path.join(cur_buf.last_vim_pwd, name))
        self.cur_buf.update_nodes_and_redraw()

    def NETREdit(self):
        """ Enter edit mode. """
        cur_buf = self.cur_buf
        if not os.access(cur_buf.wd, os.W_OK):
            Vim.ErrorMsg('Permission Denied')
            return
        if cur_buf.fs_busy():
            return
        self.unmap_keys()
        cur_buf.edit()

    def NETRSave(self):
        """ Save from edit mode. """
        cur_buf = self.cur_buf
        ori_line = Vim.eval('line(".")')
        if cur_buf.save():
            self.map_keys()
            if self._is_previewing and Vim.eval('line(".")') == ori_line:
                cur_buf.preview_on()

    def NETRToggleShowHidden(self):
        """
        Change ignore pattern and mark all existing netranger buffers to be
        content_outdated so that they will be redraw.
        """
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
        for buf in self._bufs.values():
            buf.content_outdated = True
        self.cur_buf.update_nodes_and_redraw(force_redraw=True)

    def NETRToggleSudo(self):
        """ Toggle sudo for paste/rm operations. """
        self._sudo = not self._sudo
        Vim.WarningMsg(f'Sudo is turned {["off","on"][self._sudo]}.')

    def invoke_map(self, fn):
        if hasattr(self, fn):
            getattr(self, fn)()

    def NETRSort(self):
        """ Show the SortUI. """
        if self.cur_buf.fs_busy():
            return
        if self._sortUI is None:
            self._sortUI = SortUI()
        self._sortUI.show()
        self.pend_onuiquit(self.sort_onuiiquit, num_args=1)

    def sort_onuiiquit(self, opt):
        """ The quit callback for the SortUI. """
        SortUI.reverse = opt.isupper()
        SortUI.select_sort_fn(opt.lower())
        for buf in self._bufs.values():
            buf._sort_prep()
        self.cur_buf.sort()

    def NETRHelp(self):
        """ Show the HelpUI. """
        if self._helpUI is None:
            self._helpUI = HelpUI(self.keymap_doc)
        self._helpUI.show()

    def inc_num_fs_op(self, bufs):
        """ Increase number of filesystem operation for buffers.
        The mechanisms of filesystem operation locking are as follows:
        1. The general guideline is that after operation, if the content (but
        not highlight) of the buffer will change, the buffer should be locked.
        2. By 1, when a buffer contains nodes under deletion, the buffer should
        be locked.
        3. By 1, when performing paste operation on a buffer, the buffer should
        be locked. The source buffers for cut nodes should also be locked.
        However, The source buffers for copied nodes need not be locked as only
        highlight will change.
        4. When a buffer is locked, NETRTogglePick/NETRDeleteSingle/NETRPaste
        are forbidden, i.e. operations that will change content of the buffer.
        5. Note that NETRCut/NETRCopy/NETRDelete get their sources from
        picked_nodes, so they are not forbidden though you still can't pick
        nodes and then perform cut/copy/delete in the current buffer (as
        NETRTogglePick is forbidden in the current buffer)
        6. To lock a buffer, we increase it's _num_fs_op by 1.
        7. To unlock a buffer, we decrease it's _num_fs_op by 1.
        8. A buffer is considered as locked if its _num_fs_op>0.
        """
        for buf in bufs:
            buf.inc_num_fs_op()

    def dec_num_fs_op(self, bufs):
        """ Decrease number of filesystem operation by one for each buffer in bufs.
        See Netranger.inc_num_fs_op for detail.
        """

        for buf in bufs:
            buf.dec_num_fs_op()

        if Vim.current.buffer.number in self._bufs:
            cur_buf = self.cur_buf
            if not cur_buf.fs_busy(echo=False):
                cur_buf.update_nodes_and_redraw(force_redraw=True,
                                                cheap_remote_ls=True)
                # If cursor changed, we need to reest the preview.
                if self._is_previewing:
                    cur_buf.preview_on()

    def _reset_pick_cut_copy(self):
        """
        Clean all picked_nodes/cut_nodes/copied_nodes. Separate from
        NETRCancelPickCutCopy for use in test.
        """
        for buf, nodes in self._cut_nodes.items():
            buf.reset_highlight(nodes)
        for buf, nodes in self._copied_nodes.items():
            buf.reset_highlight(nodes)
        for buf, nodes in self._picked_nodes.items():
            buf.reset_highlight(nodes)
        self._picked_nodes = defaultdict(set)
        self._cut_nodes = defaultdict(set)
        self._copied_nodes = defaultdict(set)

    def remove_pick_cut_copy(self, buf, nodes):
        nodes = set(nodes)
        self._picked_nodes[buf].difference_update(nodes)
        self._cut_nodes[buf].difference_update(nodes)
        self._copied_nodes[buf].difference_update(nodes)

    def NETRCancelPickCutCopy(self):
        self._reset_pick_cut_copy()
        self.cur_buf.redraw_if_highlight_outdated()

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
            self._picked_nodes[cur_buf].add(cur_node)
        elif res == Node.ToggleOpRes.OFF:
            self._picked_nodes[cur_buf].remove(cur_node)
        self.cur_buf.redraw_cur_line()

    def NETRTogglePickVisual(self):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        beg = Vim.current.range.start
        end = Vim.current.range.end + 1
        for i in range(beg, end):
            node = cur_buf.nodes[i]
            if node.is_INFO:
                continue
            res = node.toggle_pick()
            if res == Node.ToggleOpRes.ON:
                self._picked_nodes[cur_buf].add(node)
            else:
                self._picked_nodes[cur_buf].remove(node)
        cur_buf.redraw_lines([i for i in range(beg, end)])

    def NETRCut(self):
        """Move picked_nodes to cut_nodes.

        All buffers containing picked nodes are marked as
        highlight_outdated so that their highlight will be updated when
        entered again.
        """
        for buf, nodes in self._picked_nodes.items():
            buf.cut(nodes)
            self._cut_nodes[buf].update(nodes)
        self._picked_nodes = defaultdict(set)
        self.cur_buf.redraw_if_highlight_outdated()

    def NETRCutSingle(self):
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        cur_node = self.cur_node
        cur_node.cut()
        self._cut_nodes[cur_buf].add(cur_node)
        cur_buf.redraw_cur_line()

    def NETRCopy(self):
        """Move picked_nodes to copied_nodes.

        All buffers containing picked nodes are marked as highlight_outdated so
        that their highlight will be updated when entered again.
        """
        for buf, nodes in self._picked_nodes.items():
            buf.copy(nodes)
            self._copied_nodes[buf].update(nodes)
        self._picked_nodes = defaultdict(set)
        self.cur_buf.redraw_if_highlight_outdated()

    def NETRCopySingle(self):
        """ Store the current node to copied_nodes. """
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        cur_node = self.cur_node
        cur_node.copy()
        self._copied_nodes[cur_buf].add(cur_node)
        cur_buf.redraw_cur_line()

    def _NETRPaste_cut_nodes(self, busy_bufs):
        """ Perform mv for cut_nodes.

        For each source buffer, we reset the highlight of the cut nodes so that
        the soure buffer will be redrawed.
        """
        cwd = Vim.eval('getcwd()')
        fsfilter = FSTarget(cwd)

        alreday_moved = set()
        for buf, nodes in self._cut_nodes.items():
            buf.reset_highlight(nodes)

            # For all ancestor directories of the source directory, It's
            # possible that their content contains the cutted entry (by
            # expansion). Hence we also mark them as content_outdated.
            wd = buf.wd
            while True:
                if wd in self._wd2bufnum:
                    self._bufs[self._wd2bufnum[wd]].content_outdated = True
                wd = os.path.dirname(wd)
                if len(wd) == 1:
                    break

            # We need to mv longer (deeper) file name first
            nodes = sorted(nodes, key=lambda n: n.fullpath, reverse=True)
            for node in nodes:
                if node.fullpath not in alreday_moved:
                    fsfilter.append(node.fullpath)
                    alreday_moved.add(node.fullpath)

            self._cut_nodes = defaultdict(set)

            fsfilter.mv(cwd,
                        sudo=self._sudo,
                        on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                        on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def _NETRPaste_copied_nodes(self, busy_bufs):
        """ Perform cp for copied_nodes.

        For each source buffer, we reset the highlight of the copied nodes so
        that the source buffer will be redrawed.
        """
        cwd = Vim.eval('getcwd()')
        fsfilter = FSTarget(cwd)

        for buf, nodes in self._copied_nodes.items():
            buf.reset_highlight(nodes)
            for node in nodes:
                fsfilter.append(node.fullpath)

        self._copied_nodes = defaultdict(set)
        fsfilter.cp(cwd,
                    sudo=self._sudo,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def NETRPaste(self):
        """ Perform mv from self.cut_nodes or cp from self.copied_nodes to cwd. """
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return

        # Set locked bufs. See comments in inc_num_fs_op.
        cut_busy_bufs = list(self._cut_nodes.keys()) + [cur_buf]
        copy_busy_bufs = [cur_buf]

        Vim.WarningMsg(f'Paste to {Vim.eval("getcwd()")}')
        self._NETRPaste_copied_nodes(copy_busy_bufs)
        self._NETRPaste_cut_nodes(cut_busy_bufs)

    def NETRDelete(self, force=False):
        """ Delete the selected nodes. """
        fsfilter = FSTarget('')

        for buf, nodes in self._picked_nodes.items():
            buf.content_outdated = True
            buf.reset_highlight(nodes)
            fsfilter.extend([n.fullpath for n in nodes], hint=buf.wd)

        # Set locked bufs. See comments in inc_num_fs_op.
        busy_bufs = list(self._picked_nodes.keys())
        self._picked_nodes = defaultdict(set)

        fsfilter.rm(force=force,
                    sudo=self._sudo,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def NETRDeleteSingle(self, force=False):
        """ Delete the current node. """
        cur_buf = self.cur_buf
        if cur_buf.fs_busy():
            return
        fsfilter = FSTarget('')

        cur_buf.content_outdated = True
        fsfilter.append(self.cur_node.fullpath)
        busy_bufs = [cur_buf]

        fsfilter.rm(force=force,
                    sudo=self._sudo,
                    on_begin=lambda: self.inc_num_fs_op(busy_bufs),
                    on_exit=lambda: self.dec_num_fs_op(busy_bufs))

    def _tabdrop(self, path):
        if Vim.current.buffer.number in self._bufs and self._is_previewing:
            previewing_tab_num = Vim.current.tabpage.number
        else:
            previewing_tab_num = -1

        for tab in Vim.tabpages:
            if tab.number == previewing_tab_num:
                continue
            for window in tab.windows:
                if window.buffer.name == path:
                    Vim.current.window = window
                    return

        Vim.command(f'tabedit {path}')

    def _newtabdrop(self, path):
        num_tabpages = len(Vim.tabpages)
        if num_tabpages > 1:
            Vim.command('tabclose')
            self._tabdrop(path)
        else:
            self._tabdrop(path)
            Vim.command('tabclose 1')

    def NETRForceDelete(self):
        """ Force delete selected nodes. """
        self.NETRDelete(force=True)

    def NETRForceDeleteSingle(self):
        """ Force delete the current node. """
        self.NETRDeleteSingle(force=True)

    def _NETRSearchUpdate(self):
        if not Vim.current.buffer.options['filetype'] == 'netranger_search':
            return

        pattern = Vim.eval('getcmdline()')
        if pattern == self._last_search_pattern:
            Vim.command('redraw')
            return Vim.Timer(Vim.Var('NETRPromptDelay'),
                             self._NETRSearchUpdate,
                             'ranger._NETRSearchUpdate')
        self._last_search_pattern = pattern

        filtered_nodes = self._cur_search_buf.nodes[0:-1]

        ignore_case = False
        if pattern and pattern:
            if (Vim.options['smartcase'] and re.match(
                    '[A-Z]', pattern)) or not Vim.options['ignorecase']:
                pattern = re.compile('.*' + pattern)
            else:
                pattern = re.compile('.*' + pattern, re.IGNORECASE)
                ignore_case = True
            filtered_nodes = [
                n for n in filtered_nodes if pattern.match(n.name)
            ]

        Vim.current.buffer[:] = [n.name for n in filtered_nodes]

        Vim.command('call clearmatches()')
        for i, node in enumerate(filtered_nodes):
            Vim.command(f'call matchaddpos("{node.vim_hi_group}", [{i+1}])')
        Vim.command(
            f'call matchadd("IncSearch", "{self._last_search_pattern}")')
        if ignore_case:
            # Do our best here
            Vim.command(
                f'call matchadd("IncSearch", "{self._last_search_pattern.lower()}")'
            )
            Vim.command(
                f'call matchadd("IncSearch", "{self._last_search_pattern.upper()}")'
            )
        Vim.command('redraw')
        Vim.Timer(Vim.Var('NETRPromptDelay'), self._NETRSearchUpdate,
                  'ranger._NETRSearchUpdate')

    def _NETRSearchStop(self, accept):
        accept = accept and len(Vim.current.buffer[0])
        if accept:
            accept_line_nr = [n.name for n in self._cur_search_buf.nodes
                              ].index(Vim.current.line) + 1
        Vim.command(f'{self._buf_num_before_search}b')
        Vim.command('call clearmatches()')
        if accept:
            Vim.command(f'execute {accept_line_nr}')
        self._cur_search_buf = None
        self._last_search_pattern = None
        with self.cur_buf.SetBufferApiGuard():
            self.cur_buf.redraw_pedueo_header_footer()
        # clear command line
        Vim.command('echo')

    def _NETRSearchMove(self, binding):
        if binding[0] == '<':
            binding = f'\{binding}>'
        Vim.command(f'execute "normal! {binding}"')

    def _NETRSearchMap(self):
        stop_template = 'cnoremap <buffer> {} <cmd>python3 ranger._NETRSearchStop({})<cr><cr>'
        move_template = 'cnoremap <buffer><nowait> {} <cmd>python3 ranger._NETRSearchMove("{}")<cr>'
        Vim.command(stop_template.format('<cr>', True))
        Vim.command(stop_template.format('<esc>', False))
        Vim.command(stop_template.format('<c-c>', False))
        Vim.command(move_template.format('<c-j>', '<down'))
        Vim.command(move_template.format('<c-k>', '<up'))
        Vim.command(move_template.format('<down>', '<down'))
        Vim.command(move_template.format('<up>', '<up'))

    def NETRSearch(self):
        self._cur_search_buf = self.cur_buf
        self._buf_num_before_search = Vim.current.buffer.number
        Vim.command(f'edit netranger_search{self.cur_buf.wd}')
        search_vim_buf = Vim.current.buffer
        search_vim_buf.options['buftype'] = 'nofile'
        search_vim_buf.options['bufhidden'] = 'wipe'
        search_vim_buf.options['filetype'] = 'netranger_search'
        Vim.current.window.options['cursorline'] = True
        Vim.current.window.options['wrap'] = True
        self._NETRSearchMap()
        self._NETRSearchUpdate()
        Vim.command('call timer_start(0, {->input("/")})')

    def NETRemotePull(self):
        """Sync local so that the local content of the current directory will
        be the same as the remote content."""
        try:
            cur_buf = self.cur_buf
        except KeyError:
            Vim.ErrorMsg('Not a netranger buffer')
            return

        if not self.cur_buf.is_remote:
            Vim.ErrorMsg('Not a remote directory')
        else:
            Rclone.sync(cur_buf.wd, Rclone.SyncDirection.DOWN)
        cur_buf.update_nodes_and_redraw(force_redraw=True,
                                        cheap_remote_ls=True)

    def NETRemotePush(self):
        """ Sync remote so that the remote content of the current directory will
        be the same as the local content. """
        try:
            cur_buf = self.cur_buf
        except KeyError:
            Vim.ErrorMsg('Not a netranger buffer')
            return

        if not self.cur_buf.is_remote:
            Vim.ErrorMsg('Not a remote directory')
        else:
            Rclone.sync(cur_buf.wd, Rclone.SyncDirection.UP)

    def NETRemoteList(self):
        """ List rclone remotes in NETRemoteCacheDir. """
        Rclone.list_remotes_in_vim_buffer()
