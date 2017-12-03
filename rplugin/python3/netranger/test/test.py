import os
from netranger.util import Shell
from netranger import default
from netranger.colortbl import colortbl
from neovim import attach
import re
import time


def assert_content(expected, level=0, ind=None):
    time.sleep(0.01)
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search('(\[[0-9;]+m)?(.+)', line)
    expected = '  '*level+expected

    assert m.group(2) == expected, 'expected:"{}", real: "{}"'.format(expected, m.group(2))


def assert_highlight(expected, background=True, ind=None):
    if ind is None:
        line = nvim.current.line
    else:
        ind += 1
        line = nvim.current.buffer[ind]

    m = re.search('\[38;5;([0-9]+)(;7)?m', line)
    expected = str(colortbl[default.color[expected]])
    assert m.group(1) == expected, 'expected: "{}", real: "{}"'.format(expected, m.group(1))


def assert_fs(fn):
    succ = False
    trial = 0
    while not succ or trial<10:
        succ = fn()
        if not succ:
            time.sleep(0.05)
        trial += 1

    assert fn()


def dummy():
    pass


def do_test(fn, wipe_on_done=True):
    old_cwd = os.getcwd()
    test_root = os.path.expanduser('~/netranger_test_dir')
    Shell.run('rm -rf {}'.format(test_root))
    Shell.mkdir(test_root)

    os.chdir(test_root)
    Shell.mkdir(os.path.join(test_root, 'dir/subdir'))
    Shell.mkdir(os.path.join(test_root, 'dir/subdir/subsubdir'))
    Shell.mkdir(os.path.join(test_root, 'dir/subdir2'))
    Shell.run('touch {}/dir/a'.format(test_root))
    Shell.mkdir(os.path.join(test_root, 'dir2/'))

    nvim.command('tabe {}'.format(test_root))
    fn()
    if wipe_on_done:
        nvim.command('bwipeout')

    os.chdir(old_cwd)
    print('== {} success =='.format(str(fn.__name__)))


def test_navigation():
    nvim.input('j')
    assert_content('dir2')

    assert_highlight('dir')
    assert_highlight('dir', background=False, ind=0)

    nvim.input('kl')
    assert_content('subdir')

    nvim.input('h')
    assert_content('dir')

    nvim.input(' ')
    assert_content('subdir', level=1, ind=1)
    nvim.input(' ')
    assert_content('dir2', ind=1)

    nvim.input('j'+chr(13))
    assert os.path.basename(nvim.command_output('pwd')) == 'dir2'
    nvim.input('k 3j'+chr(13))
    assert os.path.basename(nvim.command_output('pwd')) == 'dir'


def test_edit():
    nvim.input('iz')
    nvim.input('')

    assert_fs(lambda: 'zdir' in Shell.run('ls').split())
    assert_content('dir2')


def test_pickCutCopyPaste():
    nvim.input('v')
    assert_highlight('pick')
    nvim.input('j')
    assert_highlight('pick', background=False, ind=0)

    nvim.input('lhk')
    assert_highlight('dir')

    nvim.input('l vx')
    assert_highlight('cut')

    nvim.input('jjjvy')
    assert_highlight('copy')

    nvim.input('khl')
    assert_highlight('cut', ind=0)
    assert_highlight('copy', ind=3)

    nvim.input('hjlp')
    assert_content('subdir')
    assert_highlight('dir')
    assert_content('a', ind=1)
    assert_highlight('file', background=False, ind=1)

    nvim.input('hkl')
    assert_content('subdir2')
    assert_highlight('dir')
    assert_content('a', ind=1)
    assert_highlight('file', background=False, ind=1)


def test_delete():
    nvim.input('vD')
    assert_fs(lambda: Shell.run('ls').split()[0]=='dir2')
    nvim.input('XX')
    assert_fs(lambda: Shell.run('ls')=='')


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


if __name__ == '__main__':
    nvim = attach('socket', path='/tmp/nvim')
    ori_timeoutlen = nvim.options['timeoutlen']
    nvim.options['timeoutlen'] = 1

    try:
        do_test(dummy,False)
        # do_test(test_navigation, False)
        # do_test(test_edit)
        # do_test(test_pickCutCopyPaste)
        # do_test(test_delete)
        do_test(test_bookmark)
        # do_test(test_misc)
    except Exception as e:
        print(e)
    finally:
        nvim.options['timeoutlen'] = ori_timeoutlen
