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
from netranger.config import test_dir, test_local_dir, test_remote_dir, test_remote_name


def assert_content(expected, level=0, ind=None, hi=None):
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search('\[38;5;([0-9]+)(;7)?m(.+)', line)
    expected = '  '*level+expected

    assert m.group(3) == expected, 'expected:"{}", real: "{}"'.format(expected, m.group(3))

    if hi is not None:
        expected_hi = str(colortbl[default.color[hi]])
        assert m.group(1) == expected_hi, 'expected_hi: "{}", real_hi: "{}"'.format(expected_hi, m.group(1))

    cLineNo = nvim.eval("line('.')") - 1
    if ind is None or ind == cLineNo:
        assert m.group(2) is not None, 'Background highlight mismatch. ind: {}, curLine: {}'.format(ind, cLineNo)
    else:
        assert m.group(2) is None,'Background highlight mismatch. ind: {}, curLine: {}'.format(ind, cLineNo)


def assert_highlight(expected, ind=None):
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search('\[38;5;([0-9]+)(;7)?m', line)
    expected = str(colortbl[default.color[expected]])
    assert m.group(1) == expected, 'expected: "{}", real: "{}"'.format(expected, m.group(1))
    if ind == nvim.current.buffer.number:
        assert m.group(2) is not None
    else:
        assert m.group(2) is None


def assert_num_content_line(numLine):
    assert numLine == len(nvim.current.buffer)-1, 'expected line #: {}, real line #: {}'.format(numLine, len(nvim.current.buffer)-1)


def assert_fs(d, expected):
    real = None
    for i in range(10):
        real = Shell.run('ls --group-directories-first '+d).split()
        if real == expected:
            return
        time.sleep(0.05)

    assert real == expected, 'expected: {}, real: {}'.format(expected, real)


def do_test(fn=None, fn_remote=None):
    old_cwd = os.getcwd()
    Shell.run('rm -rf {}'.format(test_dir))

    def chdir(dirname):
        Shell.mkdir(dirname)
        os.chdir(dirname)
        Shell.mkdir('dir/subdir')
        Shell.mkdir('dir/subdir/subsubdir')
        Shell.mkdir('dir/subdir2')
        Shell.touch('dir/a')
        Shell.touch('.a')
        Shell.mkdir('dir2/')

        # The following should be removed when rclone fix "not copying empty directories" bug.
        Shell.touch('dir/subdir/subsubdir/placeholder')
        Shell.touch('dir/subdir2/placeholder')
        Shell.touch('dir/subdir2/placeholder')

    chdir(test_local_dir)
    if fn is not None:
        nvim.command('tabe {}'.format(test_local_dir))
        fn()
        nvim.command('bwipeout')
        print('== {} success =='.format(str(fn.__name__)))

    chdir(test_remote_dir)
    if fn_remote is not None:
        nvim.command('NETRemoteList')
        found_remote = False
        for i, line in enumerate(nvim.current.buffer):
            if re.findall('.+(netrtest)', line):
                nvim.command('call cursor({}, 1)'.format(i+1))
                found_remote = True
                break

        assert found_remote, 'You must set up an rclone remote named "{}" to test remote function'.format(test_remote_name)
        nvim.input('l')
        fn_remote()
        nvim.command('bwipeout')
        print('== {} success =='.format(str(fn_remote.__name__)))

    os.chdir(old_cwd)


def test_navigation():
    nvim.input('j')
    assert_content('dir', ind=0, hi='dir')
    assert_content('dir2', ind=1, hi='dir')

    nvim.input('kl')
    assert_content('subdir', ind=0, hi='dir')

    return
    nvim.input('h')
    assert_content('dir', ind=0, hi='dir')
    assert_content('dir2', ind=1, hi='dir')

    nvim.input(' ')
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir', level=1, ind=1, hi='dir')
    assert_content('dir2', ind=4, hi='dir')
    nvim.input(' ')
    assert_content('dir2', ind=1, hi='dir')

    nvim.input('j<Cr>')
    assert os.path.basename(nvim.command_output('pwd')) == 'dir2'
    nvim.input('k 3j<Cr>')
    assert os.path.basename(nvim.command_output('pwd')) == 'dir'


def test_edit():
    nvim.input(' ')
    nvim.input('iz<Left><Down>')
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
    nvim.input(' ')
    nvim.input('iz<Left><Down>')
    nvim.input('y<Left><Down>')
    nvim.input('x<Left><Down>')
    nvim.input('w')
    nvim.input('')

    assert_fs('', ['dir2', 'zdir'])
    assert_fs('zdir', ['xsubdir2', 'ysubdir', 'wa'])


def test_pickCutCopyPaste():
    nvim.input('vv')
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

    nvim.input('hkddkdd')
    assert_content('dir', ind=0, hi='cut')
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


def test_delete():
    nvim.input(' jvjjvD')
    assert_fs('dir', ['subdir2'])
    assert_content('dir', ind=0, hi='dir')
    assert_content('subdir2', ind=1, level=1, hi='dir')
    assert_content('dir2', ind=2, hi='dir')
    nvim.input('XX')
    assert_content('dir2', ind=0, hi='dir')
    assert_fs('', ['dir2'])


def test_delete_remote():
    nvim.input(' jvjjvD')
    assert_fs('dir', ['subdir2'])
    nvim.input('XX')
    assert_fs('', ['dir2'])


def test_detect_fs_change():
    nvim.input(' ')
    Shell.touch('dir/b')
    Shell.mkdir('dir3')
    nvim.command('split new')
    nvim.command('quit')
    assert_content('dir', ind=0, hi='dir')
    assert_content('b', ind=4, level=1, hi='file')
    assert_content('dir3', ind=6, hi='dir')
    assert_num_content_line(7)

    Shell.rm('dir3')
    nvim.input('lh')
    assert_num_content_line(6)


def test_bookmark():
    bookmarkfile = default.variables['NETRBookmarkFile']
    copy = '{}/{}bak'.format(os.path.dirname(bookmarkfile), os.path.basename(bookmarkfile))

    if os.path.isfile(bookmarkfile):
        Shell.run('mv {} {}'.format(bookmarkfile, copy))

    Shell.run('rm -f {}'.format(bookmarkfile))

    nvim.input('mal')
    nvim.input("'a")
    assert_content('dir')

    nvim.input('lemjrb')
    nvim.command('exit')
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


def parse_arg(argv):
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-m', '--manual', action='store_true', help='Only setting up testing directories. Used for testing manually')
    return parser.parse_args(argv[1:])


if __name__ == '__main__':
    args = parse_arg(sys.argv)
    if args.manual:
        do_test()
    else:
        nvim = attach('socket', path=os.path.join(tempfile.gettempdir(), 'netrangertest'))
        ori_timeoutlen = nvim.options['timeoutlen']
        nvim.options['timeoutlen'] = 1

        do_test(test_navigation)
        do_test(test_edit)
        # do_test(fn_remote=test_edit_remote)
        do_test(test_delete)
        # do_test(fn_remote=test_delete_remote)
        do_test(test_pickCutCopyPaste)
        do_test(test_bookmark)
        do_test(test_misc)
        do_test(test_detect_fs_change)
        nvim.options['timeoutlen'] = ori_timeoutlen
