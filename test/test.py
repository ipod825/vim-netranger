import argparse
import os
import re
import sys
import time
import unittest

from neovim import attach

from netranger import default
from netranger.colortbl import colorname2ind
from netranger.config import (file_sz_display_wid, test_dir, test_local_dir,
                              test_remote_cache_dir, test_remote_dir)
from tshell import Shell


class NetrangerTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        while nvim.eval('&ft') == 'netranger':
            nvim.command('bwipeout')

    def prepare_test_dir(self, dirname):
        Shell.mkdir(dirname)
        os.chdir(dirname)
        Shell.mkdir('dir/subdir')
        Shell.mkdir('dir/subdir/subsubdir')
        Shell.mkdir('dir/subdir2')
        Shell.touch('dir/a')
        Shell.touch('.a')
        Shell.mkdir('dir2/')

        # The following should be removed when rclone fix "not copying empty
        # directories" bug.
        Shell.touch('dir/subdir/subsubdir/placeholder')
        Shell.touch('dir/subdir2/placeholder')
        Shell.touch('dir/subdir2/placeholder')

    def ensure_buf_no_expand(self):
        nvim.input('2G')
        m2 = re.search(r'\[48;5;[0-9]+mdir.*', nvim.call('getline', 2))
        assert m2, "Assumes line2 is dir"

        m3 = re.search(r'\[38;5;[0-9]+mdir2.*', nvim.call('getline', 3))
        if not m3:
            nvim.input('za')

    @property
    def clineinfo(cls):
        return cls.LineComponent(nvim.current.line)

    class LineComponent(object):
        def __init__(self, line):
            m = re.search(r'\[([34])8;5;([0-9]+)?m( *)([^ ]+)([ ]*)([^]*)',
                          line)
            self.is_foreground = True
            if m.group(1) == '3':
                self.is_foreground = False
            elif m.group(1) != '4':
                assert False, f"Bg/Fg should use 3/4. Got {m.group(1)}"
            self.hi = m.group(2)
            self.level = len(m.group(3)) // len('  ')
            self.file_name = m.group(4)
            self.size_str = m.group(6)
            self.visible_text = f'{self.file_name}{m.group(5)}{self.size_str}'

    def wait_for_fs_free(self):
        while nvim.command_output(
                'python3 print(ranger.cur_buf._num_fs_op)') != '0':
            pass
        return

    def editable_win_width(self):
        # This function takes gutter into consideration.
        ve = self.set_vim_option('virtualedit', 'all')
        nvim.command('noautocmd norm! g$')
        res = nvim.call('virtcol', '.')
        nvim.command('noautocmd norm! g0')
        self.set_vim_option('virtualedit', ve)
        return res

    def set_vim_option(self, opt, value):
        ori = nvim.options[opt]
        nvim.options[opt] = value
        return ori

    def set_vim_window_option(self, opt, value):
        ori = nvim.current.window.options[opt]
        nvim.current.window.options[opt] = value
        return ori

    def unlock_fs(self):
        # nvim.input is asynchronous, we need make sure there's enough time for it
        # to take effects.
        time.sleep(0.05)
        nvim.command('python3 ranger.cur_buf._num_fs_op=0')

    def lock_fs(self):
        nvim.command('python3 ranger.cur_buf._num_fs_op=1')

    def assert_fs(self, d, expect, root=test_local_dir):
        """
        Test whether 'expect' exists in directory root/d.
        """
        real = None
        for i in range(10):
            real = Shell.run(
                f'ls --group-directories-first {root}/{d}').split()
            if real == expect:
                return
            time.sleep(0.05)

        self.assertEqual(expect, real)

    def assert_fs_cache(self, d, expect):
        """ Test whether 'expect' exists in directory cwd/d, where cwd is
        test_remote_cache_dir.
        """
        self.assert_fs(d, expect, root=test_remote_cache_dir)

    def assert_fs_local(self, d, expect):
        """ Test whether 'expect' exists in directory cwd/d, where cwd is
        test_local_dir. Use this only when testing remote functions that involves
        bidirectional operations between test_remote_dir and test_local_dir. When
        testing remote functions that involves only test_remote_cache_dir and
        test_remote_dir, use assert_fs_cache instead. When testing local functions,
        use assert_fs directly for brevity. 
        """
        self.assert_fs(d, expect, root=test_local_dir)

    def assert_fs_remote(self, d, expect):
        """ Test whether 'expect' exists in directory cwd/d, where cwd is
        test_remote_dir.
        """
        self.assert_fs(d, expect, root=test_remote_dir)

    def color_str(self, hi_key):
        hi = default.color[hi_key]
        if type(hi) is str:
            hi = colorname2ind[hi]
        return str(hi)

    def assert_content(self, file_name, level=None, ind=None, hi=None):
        if ind is None:
            line = nvim.current.line
        else:
            ind += 1
            line = nvim.current.buffer[ind]

        lc = NetrangerTest.LineComponent(line)

        self.assertEqual(file_name, lc.file_name)
        if level is not None:
            self.assertEqual(level, lc.level)

        if hi is not None:
            expect_hi = self.color_str(hi)
            self.assertEqual(expect_hi, lc.hi)

        cLineNo = nvim.call('line', '.') - 1
        if ind is None or ind == cLineNo:
            self.assertTrue(
                lc.is_foreground,
                f'Background highlight mismatch. ind: {ind}, curLine: {cLineNo}'
            )
        else:
            self.assertFalse(
                lc.is_foreground,
                f'Background highlight mismatch. ind: {ind}, curLine: {cLineNo}'
            )

    def assert_num_content_line(self, numLine):
        self.assertEqual(numLine, len(nvim.current.buffer) - 2)


class NetrangerLocalTest(NetrangerTest):
    def setUp(self):
        Shell.run('rm -rf {}'.format(test_dir))
        self.prepare_test_dir(test_local_dir)
        nvim.command('silent tabe {}'.format(test_local_dir))
        self.ensure_buf_no_expand()
        # Clear all previous selection
        nvim.input('u')


class NetrangerRemoteTest(NetrangerTest):
    def setUp(self):

        Shell.run('rm -rf {}'.format(test_dir))
        self.prepare_test_dir(test_local_dir)
        self.prepare_test_dir(test_remote_dir)
        Shell.run('rm -rf {}/*'.format(test_remote_cache_dir))
        nvim.command('NETRemoteList')
        # There is only one remote configure by netrtest_rclone.conf
        nvim.input('l')
        nvim.command('NETRemotePull')
        nvim.command('call cursor(2, 1)')
        self.ensure_buf_no_expand()
        # Clear all previous selection
        nvim.input('u')


class TestBuilitInFunctions(NetrangerLocalTest):
    def test_NETROpen_dir(self):
        nvim.input('l')
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('subdir2', ind=1, hi='dir')

    def test_NETROpen_file(self):
        nvim.input('lGl')
        self.assertEqual('a', nvim.call('expand', '%:t'))

    def test_NETRParent(self):
        nvim.input('h')
        self.assert_content('local', ind=0, hi='dir')

    def test_NETRGoPrevSibling(self):
        # Test both NETRGoPrevSibling and NETRGoNextSibling
        nvim.input('zA')
        nvim.input('j')
        nvim.input('}')
        self.assert_content('subdir2', hi='dir')
        nvim.input('}')
        self.assert_content('a', hi='file')
        nvim.input('{')
        self.assert_content('subdir2', hi='dir')
        nvim.input('{')
        self.assert_content('subdir', hi='dir')
        nvim.input('{')
        self.assert_content('dir', hi='dir')

    def test_NETRVimCD(self):
        nvim.input('L')
        self.assertEqual('dir', os.path.basename(nvim.call('getcwd')))

    def test_NETRDelete(self):
        nvim.input('zajvjjvD')
        self.wait_for_fs_free()
        self.assert_fs('dir', ['subdir2'])
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir2', ind=1, level=1, hi='dir')
        self.assert_content('dir2', ind=2, hi='dir')

    def test_NETRDeleteSingle(self):
        nvim.input('DD')
        self.wait_for_fs_free()
        self.assert_content('dir2', ind=0, hi='dir')

    def test_delete_fail_if_fs_lock(self):
        nvim.input('v')
        self.lock_fs()
        nvim.input('D')
        self.assert_content('dir', ind=0, hi='pick')
        self.unlock_fs()

    def test_delete_single_fail_if_fs_lock(self):
        self.lock_fs()
        nvim.input('DD')
        self.assert_content('dir', ind=0, hi='dir')
        self.unlock_fs()

    def test_NETRForceDelete(self):
        Shell.run('chmod u-w dir/a')
        nvim.input('zajjjvX')
        self.wait_for_fs_free()
        self.assert_content('dir2', ind=3, hi='dir')

    def test_NETRForceDeleteSingle(self):
        Shell.run('chmod u-w dir/a')
        nvim.input('zajjjXX')
        self.wait_for_fs_free()
        self.assert_content('dir2', ind=3, hi='dir')

    def test_force_delete_fail_if_fs_lock(self):
        nvim.input('v')
        self.lock_fs()
        nvim.input('X')
        self.assert_content('dir', ind=0, hi='pick')
        self.unlock_fs()

    def test_force_delete_single_fail_if_fs_lock(self):
        self.lock_fs()
        nvim.input('XX')
        self.assert_content('dir', ind=0, hi='dir')
        self.unlock_fs()

    def test_NETRTogglePick(self):
        nvim.input('vjvklh')
        self.assert_content('dir', ind=0, hi='pick')
        self.assert_content('dir2', ind=1, hi='pick')
        nvim.input('v')
        self.assert_content('dir', ind=0, hi='dir')

    def test_NETRTogglePickVisual(self):
        nvim.input('vVjv')
        self.assert_content('dir', ind=0, level=0, hi='dir')
        self.assert_content('dir2', ind=1, level=0, hi='pick')

    def test_NETRCut(self):
        nvim.input('zajvjjvjd')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', ind=1, level=1, hi='cut')
        self.assert_content('subdir2', ind=2, level=1, hi='dir')
        self.assert_content('a', ind=3, level=1, hi='cut')

    def test_NETRCutSingle(self):
        nvim.input('ddjdd')
        self.assert_content('dir', ind=0, hi='cut')
        self.assert_content('dir2', ind=1, hi='cut')

    def test_NETRCopy(self):
        nvim.input('zajvjjvjy')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', ind=1, level=1, hi='copy')
        self.assert_content('subdir2', ind=2, level=1, hi='dir')
        self.assert_content('a', ind=3, level=1, hi='copy')

    def test_NETRCopySingle(self):
        nvim.input('yyjyy')
        self.assert_content('dir', ind=0, hi='copy')
        self.assert_content('dir2', ind=1, hi='copy')

    def test_NETRPaste_by_cut(self):
        nvim.input('zajddjjddkkkzajlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        self.assert_fs('dir', ['subdir2'])
        self.assert_fs('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_copy(self):
        nvim.input('zajyyjjyykkkzajlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        self.assert_fs('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs('dir2', ['subdir', 'a'])

    def test_NETRPaste_sided_by_side(self):
        nvim.input('zajyyjjddkkkza')
        nvim.command('vsplit')
        nvim.input('jlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        self.assert_fs('dir', ['subdir', 'subdir2'])
        self.assert_fs('dir2', ['subdir', 'a'])

    def test_NETRNew(self):
        nvim.input('odzd<CR>')
        nvim.input('ofzf<CR>')
        self.assert_content('zd', ind=2, hi='dir', level=0)
        self.assert_content('zf', ind=3, hi='file', level=0)
        self.assert_fs('', ['dir', 'dir2', 'zd', 'zf'])
        nvim.input('<CR>odzd<CR>')
        nvim.input('ofzf<CR>')
        self.assert_fs('dir', ['subdir', 'subdir2', 'zd', 'a', 'zf'])

    def test_NETRToggleExpand(self):
        nvim.input('za')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', level=1, ind=1, hi='dir')
        self.assert_content('subdir2', ind=2, level=1, hi='dir')
        self.assert_content('a', ind=3, level=1, hi='file')
        self.assert_content('dir2', ind=4, hi='dir')
        nvim.input('za')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('dir2', ind=1, hi='dir')

    def test_NETRToggleExpandRec(self):
        nvim.input('zA')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', level=1, ind=1, hi='dir')
        self.assert_content('subsubdir', level=2, ind=2, hi='dir')
        self.assert_content('placeholder', level=3, ind=3, hi='file')
        self.assert_content('subdir2', level=1, ind=4, hi='dir')
        self.assert_content('placeholder', level=2, ind=5, hi='file')
        self.assert_content('a', level=1, ind=6, hi='file')
        self.assert_content('dir2', level=0, ind=7, hi='dir')
        nvim.input('zA')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('dir2', ind=1, hi='dir')

    def test_NETRToggleShowHidden(self):
        nvim.input('zh')
        self.assert_content('.a', ind=2, hi='file')
        nvim.input('zh')
        self.assert_num_content_line(2)

    def test_sort(self):
        # only test extension, mtime, size
        # extension: [a, a.a, a.b]
        # size: [a.b, a.a, a]
        # mtime: [a, a.b, a.a]
        Shell.run('echo {} > dir/{}'.format('a' * 3, 'a'))
        Shell.run('echo {} > dir/{}'.format('a' * 2, 'a.a'))
        Shell.run('echo {} > dir/{}'.format('a' * 1, 'a.b'))
        time.sleep(0.01)
        Shell.run('touch dir/a.a')

        nvim.input('zaSe')
        self.assert_content('dir', ind=0, hi='dir', level=0)
        self.assert_content('a', ind=3, hi='file', level=1)
        self.assert_content('a.a', ind=4, hi='file', level=1)
        self.assert_content('a.b', ind=5, hi='file', level=1)
        self.assert_content('dir2', ind=6, hi='dir', level=0)

        nvim.input('SE')
        self.assert_content('dir2', ind=0, hi='dir', level=0)
        self.assert_content('dir', ind=1, hi='dir', level=0)
        self.assert_content('a.b', ind=2, hi='file', level=1)
        self.assert_content('a.a', ind=3, hi='file', level=1)
        self.assert_content('a', ind=4, hi='file', level=1)

        nvim.input('Ss')
        self.assert_content('dir2', ind=0, hi='dir', level=0)
        self.assert_content('dir', ind=1, hi='dir', level=0)
        self.assert_content('a.b', ind=4, hi='file', level=1)
        self.assert_content('a.a', ind=5, hi='file', level=1)
        self.assert_content('a', ind=6, hi='file', level=1)

        nvim.input('SS')
        self.assert_content('dir', ind=0, hi='dir', level=0)
        self.assert_content('a', ind=1, hi='file', level=1)
        self.assert_content('a.a', ind=2, hi='file', level=1)
        self.assert_content('a.b', ind=3, hi='file', level=1)
        self.assert_content('dir2', ind=6, hi='dir', level=0)

        nvim.input('Sm')
        self.assert_content('dir2', ind=0, hi='dir', level=0)
        self.assert_content('dir', ind=1, hi='dir', level=0)
        self.assert_content('a', ind=4, hi='file', level=1)
        self.assert_content('a.b', ind=5, hi='file', level=1)
        self.assert_content('a.a', ind=6, hi='file', level=1)

        nvim.input('SM')
        self.assert_content('dir', ind=0, hi='dir', level=0)
        self.assert_content('a.a', ind=1, hi='file', level=1)
        self.assert_content('a.b', ind=2, hi='file', level=1)
        self.assert_content('a', ind=3, hi='file', level=1)
        self.assert_content('dir2', ind=6, hi='dir', level=0)
        nvim.input('Sd')


class TestDisplay(NetrangerLocalTest):
    def test_fit_winwidth_display(self):
        self.assertEqual(nvim.current.window.width,
                         len(self.clineinfo.visible_text))

    def test_size_display(self):
        Shell.run('echo {} > {}'.format('a' * 1035, 'a'))
        Shell.run('echo {} > {}'.format('b' * 1024, 'b'))

        nvim.command('edit .')
        nvim.input('Gk')

        self.assertEqual('1.01 K', self.clineinfo.size_str)

        nvim.input('j')
        self.assertEqual('1 K', self.clineinfo.size_str)

    def test_abbrev_cwd(self):
        cwd = nvim.call('getcwd')
        nvim.command('vsplit')
        nvim.input('gg')

        self.assertEqual(len(cwd), nvim.strwidth(self.clineinfo.visible_text),
                         f'[{cwd}] [{self.clineinfo.visible_text}]')

        nvim.command(f'vertical resize {len(cwd)-1}')
        nvim.input('r')
        self.assertEqual(
            len(cwd) - len(cwd.split('/')[1]) + 1,
            nvim.strwidth(self.clineinfo.visible_text),
            f'[{cwd}] [{self.clineinfo.visible_text}]')

    def test_abbrev_visible_text(self):
        def doit(name, offset):
            Shell.touch(name)
            exact_width = nvim.strwidth(name) + file_sz_display_wid + 1
            assert exact_width + offset > 0, "Not reasonable to test width <= 0"
            nvim.command(f'vertical resize {exact_width+offset}')
            nvim.input('rG')
            self.assertEqual(nvim.current.window.width,
                             nvim.strwidth(self.clineinfo.visible_text),
                             self.clineinfo.visible_text)

        nvim.command('vsplit')
        doit('測試', 0)
        doit('測試', -1)
        doit('測試', -2)
        doit('測試a', 0)
        doit('測試a', -1)
        doit('測試a', -2)


class TestApi(NetrangerLocalTest):
    def test_api_cur_node_name(self):
        self.assertEqual('dir', nvim.call('netranger#api#cur_node_name'))

    def test_api_cur_node_path(self):
        self.assertEqual(os.path.abspath('dir'),
                         nvim.call('netranger#api#cur_node_path'))

    def test_api_cp(self):
        nvim.input('za')
        nvim.call('netranger#api#cp', 'dir/subdir', './')
        nvim.call('netranger#api#cp', 'dir/a', './')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=5, hi='dir')
        self.assert_content('a', ind=6, hi='file')
        self.assert_fs('', ['dir', 'dir2', 'subdir', 'a'])

    def test_api_mv(self):
        nvim.input('za')
        nvim.call('netranger#api#mv', 'dir/subdir', './')
        nvim.call('netranger#api#mv', 'dir/a', './')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=3, hi='dir')
        self.assert_content('a', ind=4, hi='file')
        self.assert_fs('', ['dir', 'dir2', 'subdir', 'a'])
        self.assert_fs('dir', ['subdir2'])

    def test_api_rm(self):
        nvim.input('za')
        nvim.call('netranger#api#rm', 'dir/subdir')
        nvim.call('netranger#api#rm', 'dir/a')
        self.wait_for_fs_free()
        self.assert_content('subdir2', ind=1, hi='dir', level=1)
        self.assert_content('dir2', ind=2, hi='dir')
        self.assert_fs('dir', ['subdir2'])


class TestApiRemote(NetrangerRemoteTest):
    def test_api_cp_remote(self):
        nvim.input('za')
        cwd = nvim.call('getcwd')
        nvim.call('netranger#api#cp', f'{cwd}/dir/subdir', cwd)
        nvim.call('netranger#api#cp', f'{cwd}/dir/a', cwd)
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=5, hi='dir')
        self.assert_content('a', ind=6, hi='file')
        self.assert_fs_cache('', ['dir', 'dir2', 'subdir', 'a'])
        self.assert_fs_remote('', ['dir', 'dir2', 'subdir', 'a'])

    def test_api_mv_remote(self):
        nvim.input('za')
        cwd = nvim.call('getcwd')
        nvim.call('netranger#api#mv', f'{cwd}/dir/subdir', cwd)
        nvim.call('netranger#api#mv', f'{cwd}/dir/a', cwd)
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=3, hi='dir')
        self.assert_content('a', ind=4, hi='file')
        self.assert_fs_cache('', ['dir', 'dir2', 'subdir', 'a'])
        self.assert_fs_cache('dir', ['subdir2'])
        self.assert_fs_remote('', ['dir', 'dir2', 'subdir', 'a'])
        self.assert_fs_remote('dir', ['subdir2'])

    def test_api_rm_remote(self):
        nvim.input('za')
        cwd = nvim.call('getcwd')
        nvim.call('netranger#api#rm', f'{cwd}/dir/subdir')
        nvim.call('netranger#api#rm', f'{cwd}/dir/a')
        self.wait_for_fs_free()
        self.assert_content('subdir2', ind=1, hi='dir', level=1)
        self.assert_content('dir2', ind=2, hi='dir')
        self.assert_fs_cache('dir', ['subdir2'])
        self.assert_fs_remote('dir', ['subdir2'])


class TestAutoCmd(NetrangerLocalTest):
    # TODO add SORT test for broken link #issue 21
    # TODO test toggle sudo
    # TODO test rifle
    def test_on_cursormoved(self):
        nvim.input('j')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('dir2', ind=1, hi='dir')

        nvim.input('k')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('dir2', ind=1, hi='dir')

    def test_on_bufenter_content_stay_the_same(self):
        nvim.input('zalh')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', level=1, ind=1, hi='dir')
        self.assert_content('dir2', ind=4, hi='dir')

    def test_on_bufenter_fs_change(self):
        nvim.input('lh')
        Shell.touch('dir/b')
        Shell.mkdir('dir3')
        nvim.command('split new')
        nvim.command('quit')
        nvim.input('zA')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('b', ind=7, level=1, hi='file')
        self.assert_content('dir3', ind=9, hi='dir')
        self.assert_num_content_line(10)

        Shell.rm('dir/subdir2/placeholder')
        nvim.input('lh')
        self.assert_num_content_line(9)

    def test_on_bufenter_fs_change_with_expanded_nodes(self):
        nvim.input('za')
        nvim.command('split new')
        Shell.touch('dir/b')
        nvim.command('quit')
        self.assert_num_content_line(6)

    def test_on_bufenter_cursor_stay_the_same_pos(self):
        nvim.input('ljhl')
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('subdir2', ind=1, hi='dir')

    def test_on_winenter_adjust_visible_text_width(self):
        nvim.command('vsplit')
        nvim.command('wincmd w')
        self.assertEqual(nvim.current.window.width,
                         len(self.clineinfo.visible_text))

    def test_on_winenter_cursor_stay_the_same_pos(self):
        nvim.input('j')
        left_panel_line_no = nvim.call('line', '.')
        nvim.command('vsplit')
        nvim.command('wincmd w')
        self.assertEqual(left_panel_line_no, nvim.call('line', '.'))
        nvim.input('j')
        right_panel_line_no = nvim.call('line', '.')
        nvim.command('wincmd w')
        self.assertEqual(left_panel_line_no, nvim.call('line', '.'))
        nvim.command('wincmd w')
        self.assertEqual(right_panel_line_no, nvim.call('line', '.'))


class TestSetOption(NetrangerLocalTest):
    def test_opt_Autochdir(self):
        default_value = nvim.vars['NETRAutochdir']

        nvim.vars['NETRAutochdir'] = True
        nvim.input('l')
        self.assertNotEqual(test_local_dir, nvim.call('getcwd'))
        nvim.input('h')
        self.assertEqual(test_local_dir, nvim.call('getcwd'))

        nvim.vars['NETRAutochdir'] = False
        nvim.input('l')
        self.assertEqual(test_local_dir, nvim.call('getcwd'))
        nvim.input('h')
        self.assertEqual(test_local_dir, nvim.call('getcwd'))

        nvim.vars['NETRAutochdir'] = default_value

    def test_NETRToggleExpandRec(self):
        # Set foldnestmax=1 should behave exactly the same as NETRToggleExpand
        fdn = self.set_vim_window_option('foldnestmax', 1)
        nvim.input('zA')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir', level=1, ind=1, hi='dir')
        self.assert_content('subdir2', ind=2, level=1, hi='dir')
        self.assert_content('a', ind=3, level=1, hi='file')
        self.assert_content('dir2', ind=4, hi='dir')
        nvim.input('zA')
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('dir2', ind=1, hi='dir')
        self.set_vim_window_option('foldnestmax', fdn)


class TestBuilitInFunctionsRemote(NetrangerRemoteTest):
    def test_NETREdit_remote(self):
        nvim.input('za')
        nvim.input('iiz<Left><Down>')
        nvim.input('y<Left><Down>')
        nvim.input('x<Left><Down>')
        nvim.input('w')
        nvim.input('<esc>:w<cr>')
        self.assert_content('dir2', ind=0, hi='dir')
        self.assert_content('zdir', ind=1, hi='dir')
        self.assert_content('xsubdir2', ind=2, level=1, hi='dir')
        self.assert_content('ysubdir', ind=3, level=1, hi='dir')
        self.assert_content('wa', ind=4, level=1, hi='file')

        self.assert_fs_cache('', ['dir2', 'zdir'])
        self.assert_fs_remote('', ['dir2', 'zdir'])
        self.assert_fs_cache('zdir', ['xsubdir2', 'ysubdir', 'wa'])
        self.assert_fs_remote('zdir', ['xsubdir2', 'ysubdir', 'wa'])

    def test_NETRPaste_by_cut_remote2local(self):
        nvim.input('zajvjjvd')
        nvim.command('vsplit {}'.format(test_local_dir))
        nvim.input('jlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        nvim.command('bwipeout')

        self.assert_fs_remote('dir', ['subdir2'])
        self.assert_fs_cache('dir', ['subdir2'])
        self.assert_fs_local('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_cut_local2remote(self):
        nvim.command('vsplit {}'.format(test_local_dir))
        self.ensure_buf_no_expand()
        nvim.input('zajvjjvd')
        nvim.command('wincmd w')
        nvim.input('jlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        nvim.command('bwipeout')
        self.assert_fs_local('dir', ['subdir2'])
        self.assert_fs_remote('dir2', ['subdir', 'a'])
        self.assert_fs_cache('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_cut_remote2remote(self):
        nvim.input('zajvjjvd')
        nvim.input('Glp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')

        self.assert_fs_remote('dir', ['subdir2'])
        self.assert_fs_remote('dir2', ['subdir', 'a'])

        self.assert_fs_cache('dir', ['subdir2'])
        self.assert_fs_cache('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_copy_remote2local(self):
        nvim.input('zajvjjvy')
        nvim.command('vsplit {}'.format(test_local_dir))
        self.ensure_buf_no_expand()
        nvim.input('jlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        nvim.command('bwipeout')

        self.assert_fs_remote('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs_cache('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs_local('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_copy_local2remote(self):
        nvim.command('vsplit {}'.format(test_local_dir))
        self.ensure_buf_no_expand()
        nvim.input('zajvjjvy')
        nvim.command('wincmd w')
        nvim.input('jlp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')
        nvim.command('bwipeout')
        self.assert_fs_local('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs_remote('dir2', ['subdir', 'a'])
        self.assert_fs_cache('dir2', ['subdir', 'a'])

    def test_NETRPaste_by_copy_remote2remote(self):
        nvim.input('zajvjjvy')
        nvim.input('Glp')
        self.wait_for_fs_free()
        self.assert_content('subdir', ind=0, hi='dir')
        self.assert_content('a', ind=1, hi='file')

        self.assert_fs_remote('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs_remote('dir2', ['subdir', 'a'])

        self.assert_fs_cache('dir', ['subdir', 'subdir2', 'a'])
        self.assert_fs_cache('dir2', ['subdir', 'a'])

    def test_help(self):
        nvim.input('<F1>')
        nvim.command('quit')

    def test_NETREdit(self):
        nvim.input('za')
        nvim.input('iiz<Left><Down>')
        nvim.input('y<Left><Down>')
        nvim.input('x<Left><Down>')
        nvim.input('w')
        nvim.input('<esc>:w<cr>')
        self.assert_content('dir2', ind=0, hi='dir')
        self.assert_content('zdir', ind=1, hi='dir')
        self.assert_content('xsubdir2', ind=2, level=1, hi='dir')
        self.assert_content('ysubdir', ind=3, level=1, hi='dir')
        self.assert_content('wa', ind=4, level=1, hi='file')

        self.assert_fs_cache('', ['dir2', 'zdir'])
        self.assert_fs_cache('zdir', ['xsubdir2', 'ysubdir', 'wa'])
        self.assert_fs_remote('', ['dir2', 'zdir'])
        self.assert_fs_remote('zdir', ['xsubdir2', 'ysubdir', 'wa'])

    def test_NETRDelete_remote(self):
        nvim.input('zajvjjvD')
        self.wait_for_fs_free()
        self.assert_fs_cache('dir', ['subdir2'])
        self.assert_fs_remote('dir', ['subdir2'])
        self.assert_content('dir', ind=0, hi='dir')
        self.assert_content('subdir2', ind=1, level=1, hi='dir')
        self.assert_content('dir2', ind=2, hi='dir')

    def test_NETRNew_remote(self):
        # Currently only touching remote file is supported
        # See https://github.com/rclone/rclone/issues/2629
        nvim.input('ofzf<CR>')
        self.assert_fs_cache('', ['dir', 'dir2', 'zf'])
        self.assert_fs_remote('', ['dir', 'dir2', 'zf'])
        self.assert_content('zf', ind=2, hi='file', level=0)


class TestPreview(NetrangerLocalTest):
    def test_NETRTogglePreview(self):
        #TODO
        pass


parser = argparse.ArgumentParser(description='')
parser.add_argument(
    '--listen_address',
    default=None,
    help='NVIM_LISTEN_ADDRESS for an open neovim. If set to none, open a \
    headless neovim instead.')
parser.add_argument('unittest_args', nargs='*')
args = parser.parse_args(sys.argv[1:])

if args.listen_address:
    nvim = attach('socket', path=args.listen_address)
else:
    nvim = attach(
        'child',
        argv=['nvim', '-u', './test_init.vim', '--embed', '--headless'])

if __name__ == '__main__':
    sys.argv[1:] = args.unittest_args
    unittest.main()
    nvim.close()
