import os
import sys
import re
import time
import tempfile
import argparse
from netranger.util import Shell
from netranger import default
from netranger.colortbl import colortbl
from neovim import attach
from netranger.config import test_dir
from netranger.config import test_local_dir
from netranger.config import test_remote_dir
from netranger.config import test_remote_name
from netranger.config import test_remote_cache_dir


def color_str(hi_key):
    hi = default.color[hi_key]
    if type(hi) is str:
        hi = colortbl[hi]
    return str(hi)


def assert_content(expected, level=0, ind=None, hi=None,
                   hi_is_foreround=False):
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search(r'\[38;5;([0-9]+)(;7)?m( *)([^ ]+)', line)
    assert m.group(4) == expected, 'expected:"{}",'
    ' real: "{}"'.format(expected, m.group(4))
    assert m.group(3) == '  ' * level, "level mismatch: expected: {}, "
    "real:{}".format('"{}"'.format('  ' * level), '"{}"'.format(m.group(3)))

    if hi is not None:
        expected_hi = color_str(hi)
        assert m.group(1) == expected_hi, 'expected_hi: "{}", '
        'real_hi: "{}"'.format(expected_hi, m.group(1))

        if hi_is_foreround:
            assert m.group(2) is not None, 'Expect a foreground highlight'

    cLineNo = nvim.eval("line('.')") - 1
    if ind is None or ind == cLineNo:
        assert m.group(2) is not None, 'Background highlight mismatch. '
        'ind: {}, curLine: {}'.format(ind, cLineNo)
    else:
        assert m.group(2) is None, 'Background highlight mismatch. '
        'ind: {}, curLine: {}'.format(ind, cLineNo)


def assert_highlight(expected, ind=None):
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search(r'\[38;5;([0-9]+)(;7)?m', line)
    expected = color_str(expected)
    assert m.group(1) == expected, 'expected: "{}", real: "{}"'.format(
        expected, m.group(1))
    if ind == nvim.current.buffer.number:
        assert m.group(2) is not None
    else:
        assert m.group(2) is None


def assert_num_content_line(numLine):
    assert numLine == len(nvim.current.buffer
                          ) - 2, 'expected line #: {}, real line #: {}'.format(
                              numLine,
                              len(nvim.current.buffer) - 1)


def assert_fs(d, expected):
    """
    Test whether 'expected' exists in directory cwd/d, where
    cwd is /tmp/netrtest/local when testing local functions and
    cwd is /tmp/netrtest/remote when testing remote functions.
    """
    real = None
    for i in range(10):
        real = Shell.run('ls --group-directories-first ' + d).split()
        if real == expected:
            return
        time.sleep(0.05)

    assert real == expected, 'expected: {}, real: {}'.format(expected, real)


def assert_fs_remote(d, expected):
    """
    Test whether 'expected' exists in directory test_remote_cache_dir/d
    (defaults to $HOME/.netranger/remote/netrtest/d)
    """
    assert_fs(os.path.join(test_remote_cache_dir, d), expected)


def print_vim_buffer():
    for l in nvim.current.buffer:
        print(l)
    print('======')


def do_test(fn=None, fn_remote=None):
    """
    Note on the mecahnism of testing rclone on localhost:
    1. Tester run rclone to create a "local" remote named netrtest (must be
       exact this name)
    2. In default.py, the vim variable 'NETRemoteRoots' is set to
       {test_remote_name: test_remote_dir}, which defaults to
       {'netrtest', '/tmp/netrtest/remote'}.
    3. 'NETRemoteRoots' is passed to Rclone constructor, so that the rpath
       of the netrtest remote is mapped to '/tmp/netrtest/remote'.
    4. This just works in netranger. In cmd line, running
       'rclone lsl netranger:/' still shows you the content of the root
       directory of the localhost.
    """
    old_cwd = os.getcwd()
    Shell.run('rm -rf {}'.format(test_dir))

    def prepare_test_dir(dirname):
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

    prepare_test_dir(test_local_dir)
    if fn is not None:
        nvim.command('silent tabe {}'.format(test_local_dir))
        fn()
        nvim.command('bwipeout')
        print('== {} success =='.format(str(fn.__name__)))

    prepare_test_dir(test_remote_dir)
    if fn_remote is not None:
        nvim.command('NETRemoteList')
        found_remote = False
        for i, line in enumerate(nvim.current.buffer):
            if re.findall('.+(netrtest)', line):
                nvim.command('call cursor({}, 1)'.format(i + 1))
                found_remote = True
                break

        assert found_remote, 'You must set up an rclone remote named "{}" \
            to test remote function'.format(test_remote_name)
        nvim.input('l')
        nvim.command('NETRemotePull')
        nvim.command('call cursor(2, 1)')
        fn_remote()
        nvim.command('bwipeout')
        print('== {} success =='.format(str(fn_remote.__name__)))

    os.chdir(old_cwd)


def test_navigation():
    nvim.input('j')
    assert_content('dir', ind=0, hi='dir')
    assert_content('dir2', ind=1, hi='dir', hi_is_foreround=True)

    nvim.input('kl')
    assert_content('subdir', ind=0, hi='dir', hi_is_foreround=True)

    nvim.input('h')
    assert_content('dir', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('dir2', ind=1, hi='dir')

    nvim.input(' ')
    assert_content('dir', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('subdir', level=1, ind=1, hi='dir')
    assert_content('dir2', ind=4, hi='dir')
    nvim.input(' ')
    assert_content('dir', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('dir2', ind=1, hi='dir')

    nvim.input(' jlhh')
    assert_content('dir', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('subdir', ind=1, level=1, hi='dir')
    assert_content('subdir2', ind=2, level=1, hi='dir')
    assert_content('a', ind=3, level=1, hi='file')
    assert_content('dir2', ind=4, hi='dir')

    nvim.input(' j<Cr>')
    assert os.path.basename(
        nvim.command_output('pwd')) == 'dir2', os.path.basename(
            nvim.command_output('pwd'))
    nvim.input('k 3j<Cr>')
    assert os.path.basename(nvim.command_output('pwd')) == 'dir'


def test_edit():
    nvim.input(' ')
    nvim.input('iiz<Left><Down>')
    nvim.input('y<Left><Down>')
    nvim.input('x<Left><Down>')
    nvim.input('w')
    nvim.input('')
    assert_content('dir2', ind=0, hi='dir')
    assert_content('zdir', ind=1, hi='dir')
    assert_content('xsubdir2', ind=2, level=1, hi='dir')
    assert_content('ysubdir', ind=3, level=1, hi='dir')
    assert_content('wa', ind=4, level=1, hi='file')

    assert_fs('', ['dir2', 'zdir'])
    assert_fs('zdir', ['xsubdir2', 'ysubdir', 'wa'])


def test_edit_remote():
    return
    nvim.input(' ')
    nvim.input('iiz<Left><Down>')
    nvim.input('y<Left><Down>')
    nvim.input('x<Left><Down>')
    nvim.input('w')
    nvim.input('')

    assert_fs('', ['dir2', 'zdir'])
    assert_fs('zdir', ['xsubdir2', 'ysubdir', 'wa'])
    assert_fs_remote('', ['dir2', 'zdir'])
    assert_fs_remote('zdir', ['xsubdir2', 'ysubdir', 'wa'])


def test_pickCutCopyPaste():
    nvim.input('vv')
    nvim.input(' jvjjvjlh')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, level=1, hi='pick')
    assert_content('subdir2', ind=2, level=1, hi='dir')
    assert_content('a', ind=3, level=1, hi='pick')
    assert_content('dir2', ind=4, level=0, hi='dir', hi_is_foreround=True)

    nvim.input('x')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, level=1, hi='cut')
    assert_content('subdir2', ind=2, level=1, hi='dir')
    assert_content('a', ind=3, level=1, hi='cut')

    nvim.input('lp')
    assert_content('subdir', ind=0, hi='dir')
    assert_content('a', ind=1, hi='file')
    assert_fs('dir2', ['subdir', 'a'])

    nvim.input('hkddkdd')
    assert_content('dir', ind=0, hi='cut', hi_is_foreround=True)
    assert_content('subdir2', ind=1, level=1, hi='cut')

    nvim.input('jjlp')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='dir')
    assert_content('subdir2', ind=2, hi='dir')
    assert_content('a', ind=3, hi='file')
    assert_fs('dir2', ['dir', 'subdir', 'subdir2', 'a'])

    nvim.input('Gvkkvjyy')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='pick')
    assert_content('subdir2', ind=2, hi='copy', hi_is_foreround=True)
    assert_content('a', ind=3, hi='pick')

    nvim.input('x')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='cut')
    assert_content('subdir2', ind=2, hi='copy', hi_is_foreround=True)
    assert_content('a', ind=3, hi='cut')

    nvim.command('wincmd v')
    nvim.command('wincmd l')
    nvim.input('hp')
    assert_content('dir2', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('subdir', ind=1, hi='dir')
    assert_content('subdir2', ind=2, hi='dir')
    assert_content('a', ind=3, hi='file')
    assert_fs('', ['dir2', 'subdir', 'subdir2', 'a'])
    assert_fs('dir2', ['dir', 'subdir2'])

    nvim.input(' jddj<Cr>p')
    assert_content('subdir2', ind=1, hi='dir', level=1)
    assert_fs('dir2/subdir2', ['dir', 'placeholder'])


def test_visual_pick():
    nvim.input('vVjv')
    assert_content('dir', ind=0, level=0, hi='dir')
    assert_content('dir2', ind=1, level=0, hi='pick', hi_is_foreround=True)
    nvim.input('D')
    assert_fs('', ['dir'])


def test_pickCutCopyPaste_remote_r2r():
    nvim.input(' jvjjvjlh')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, level=1, hi='pick')
    assert_content('subdir2', ind=2, level=1, hi='dir')
    assert_content('a', ind=3, level=1, hi='pick')

    nvim.input('x')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, level=1, hi='cut')
    assert_content('subdir2', ind=2, level=1, hi='dir')
    assert_content('a', ind=3, level=1, hi='cut')

    nvim.input('lp')
    assert_content('subdir', ind=0, hi='dir')
    assert_content('a', ind=1, hi='file')
    assert_fs('dir2', ['subdir', 'a'])
    assert_fs_remote('dir2', ['subdir', 'a'])

    nvim.input('hkddkdd')
    assert_content('dir', ind=0, hi='cut')
    assert_content('subdir2', ind=1, level=1, hi='cut')

    nvim.input('jjlp')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='dir')
    assert_content('subdir2', ind=2, hi='dir')
    assert_content('a', ind=3, hi='file')
    assert_fs('dir2', ['dir', 'subdir', 'subdir2', 'a'])
    assert_fs_remote('dir2', ['dir', 'subdir', 'subdir2', 'a'])

    nvim.input('Gvkkvjyy')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='pick')
    assert_content('subdir2', ind=2, hi='copy')
    assert_content('a', ind=3, hi='pick')

    nvim.input('x')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='cut')
    assert_content('subdir2', ind=2, hi='copy')
    assert_content('a', ind=3, hi='cut')

    nvim.command('wincmd v')
    nvim.command('wincmd l')
    nvim.input('hp')
    assert_content('dir2', ind=0, hi='dir')
    assert_content('subdir', ind=1, hi='dir')
    assert_content('subdir2', ind=2, hi='dir')
    assert_content('a', ind=3, hi='file')
    assert_fs('', ['dir2', 'subdir', 'subdir2', 'a'])
    assert_fs('dir2', ['dir', 'subdir2'])
    assert_fs_remote('', ['dir2', 'subdir', 'subdir2', 'a'])
    assert_fs_remote('dir2', ['dir', 'subdir2'])

    nvim.input(' jddj<Cr>p')
    assert_content('subdir2', ind=1, hi='dir', level=1)
    assert_fs('dir2/subdir2', ['dir', 'placeholder'])
    assert_fs_remote('dir2/subdir2', ['dir', 'placeholder'])


def test_delete():
    nvim.input(' jvjjvD')
    assert_fs('dir', ['subdir2'])
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir2', ind=1, level=1, hi='dir')
    assert_content('dir2', ind=2, hi='dir', hi_is_foreround=True)
    nvim.input('kkXX')
    assert_content('dir2', ind=0, hi='dir', hi_is_foreround=True)
    assert_fs('', ['dir2'])


def test_delete_remote():
    nvim.input(' jvjjvD')
    assert_fs('dir', ['subdir2'])
    assert_fs_remote('dir', ['subdir2'])
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir2', ind=1, level=1, hi='dir')
    assert_content('dir2', ind=2, hi='dir', hi_is_foreround=True)

    nvim.input('kk  ')
    assert_content('subdir2', ind=1, level=1, hi='dir')
    nvim.input('XX')
    assert_content('dir2', ind=0, hi='dir', hi_is_foreround=True)
    assert_fs('', ['dir2'])
    assert_fs_remote('', ['dir2'])


def test_detect_fs_change():
    nvim.input(' ')
    Shell.touch('dir/b')
    Shell.mkdir('dir3')
    nvim.command('split new')
    nvim.command('quit')
    assert_content('dir', ind=0, hi='dir', hi_is_foreround=True)
    assert_content('b', ind=4, level=1, hi='file')
    assert_content('dir3', ind=6, hi='dir')
    assert_num_content_line(7)

    Shell.rm('dir3')
    nvim.input('lh')
    assert_num_content_line(6)


def test_bookmark():
    bookmarkfile = default.variables['NETRBookmarkFile']
    copy = '{}/{}bak'.format(
        os.path.dirname(bookmarkfile), os.path.basename(bookmarkfile))

    if os.path.isfile(bookmarkfile):
        Shell.run('mv {} {}'.format(bookmarkfile, copy))

    Shell.run('rm -f {}'.format(bookmarkfile))

    nvim.input('mal')
    nvim.input("'a")
    assert_content('dir')

    nvim.input('lemjrb')
    nvim.command('exit')
    time.sleep(0.5)
    nvim.input("'b")
    assert_content('dir')

    Shell.run('rm -f {}'.format(bookmarkfile))
    if os.path.isfile(copy):
        Shell.run('mv {} {}'.format(copy, bookmarkfile))


def test_misc():
    nvim.input('zph')
    assert_content('dir')

    nvim.input('zh')
    assert_content('.a', ind=2, hi='file')
    nvim.input('zh')
    assert_num_content_line(2)


def test_size_display():
    width = nvim.current.window.width

    def cLine_ends_with(s):
        # line[-4:] = [0m
        return nvim.current.line[:-4].endswith(s)

    assert cLine_ends_with('3'), 'size display dir fail: {}'.format(
        'a' + nvim.current.line[-1] + 'a')
    Shell.run('echo {} > {}'.format('a' * 1035, 'a' * width + '.pdf'))
    Shell.run('echo {} > {}'.format('b' * 1024, 'b' * width))

    nvim.command('edit .')
    nvim.input('Gk')
    assert cLine_ends_with(
        '~.pdf 1.01 K'), 'size display abbreviation fail: a~.pdf {}'.format(
            nvim.current.line[-10:])
    nvim.input('j')
    assert cLine_ends_with(
        'b~    1 K'), 'size display abbreviation fail: b~ {}'.format(
            nvim.current.line[-10:])


def test_sort():
    # only test extension, mtime, size
    # extension: [a, a.a, a.b]
    # size: [a.b, a.a, a]
    # mtime: [a, a.b, a.a]
    Shell.run('echo {} > dir/{}'.format('a' * 3, 'a'))
    Shell.run('echo {} > dir/{}'.format('a' * 2, 'a.a'))
    Shell.run('echo {} > dir/{}'.format('a' * 1, 'a.b'))
    time.sleep(0.01)
    Shell.run('touch dir/a.a')

    nvim.input(' Se')
    assert_content('dir', ind=0, hi='dir', level=0)
    assert_content('a', ind=3, hi='file', level=1)
    assert_content('a.a', ind=4, hi='file', level=1)
    assert_content('a.b', ind=5, hi='file', level=1)
    assert_content('dir2', ind=6, hi='dir', level=0)

    nvim.input('SE')
    assert_content('dir2', ind=0, hi='dir', level=0)
    assert_content('dir', ind=1, hi='dir', level=0)
    assert_content('a.b', ind=2, hi='file', level=1)
    assert_content('a.a', ind=3, hi='file', level=1)
    assert_content('a', ind=4, hi='file', level=1)

    nvim.input('Ss')
    assert_content('dir2', ind=0, hi='dir', level=0)
    assert_content('dir', ind=1, hi='dir', level=0)
    assert_content('a.b', ind=4, hi='file', level=1)
    assert_content('a.a', ind=5, hi='file', level=1)
    assert_content('a', ind=6, hi='file', level=1)

    nvim.input('SS')
    assert_content('dir', ind=0, hi='dir', level=0)
    assert_content('a', ind=1, hi='file', level=1)
    assert_content('a.a', ind=2, hi='file', level=1)
    assert_content('a.b', ind=3, hi='file', level=1)
    assert_content('dir2', ind=6, hi='dir', level=0)

    nvim.input('Sm')
    assert_content('dir2', ind=0, hi='dir', level=0)
    assert_content('dir', ind=1, hi='dir', level=0)
    assert_content('a', ind=4, hi='file', level=1)
    assert_content('a.b', ind=5, hi='file', level=1)
    assert_content('a.a', ind=6, hi='file', level=1)

    nvim.input('SM')
    assert_content('dir', ind=0, hi='dir', level=0)
    assert_content('a.a', ind=1, hi='file', level=1)
    assert_content('a.b', ind=2, hi='file', level=1)
    assert_content('a', ind=3, hi='file', level=1)
    assert_content('dir2', ind=6, hi='dir', level=0)


def test_rifle():
    # TODO
    pass


def parse_arg(argv):
    parser = argparse.ArgumentParser(description='')
    parser.add_argument(
        '-m',
        '--manual',
        action='store_true',
        help='Only setting up testing directories. Used for testing manually')
    return parser.parse_args(argv[1:])


if __name__ == '__main__':
    args = parse_arg(sys.argv)
    if args.manual:
        do_test()
    else:
        nvim = attach(
            'socket',
            path=os.path.join(tempfile.gettempdir(), 'netrangertest'))
        ori_timeoutlen = nvim.options['timeoutlen']
        nvim.options['timeoutlen'] = 1
        default.color.update(nvim.vars['NETRColors'])
        # disable all plugins
        nvim.command('py3 ranger._NETRTest()')

        do_test(test_navigation)
        do_test(test_edit)
        do_test(fn_remote=test_edit_remote)
        do_test(test_delete)
        do_test(fn_remote=test_delete_remote)
        do_test(test_pickCutCopyPaste)
        do_test(test_visual_pick)
        # do_test(fn_remote=test_pickCutCopyPaste_remote_r2r)
        do_test(test_bookmark)
        do_test(test_misc)
        do_test(test_detect_fs_change)
        do_test(test_size_display)
        do_test(test_sort)
        do_test(test_rifle)

        nvim.options['timeoutlen'] = ori_timeoutlen
