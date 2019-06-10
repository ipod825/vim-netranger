import inspect
import os
import shutil
import subprocess

import _thread as thread
import vim
from netranger.Vim import VimErrorMsg


class Shell():
    userhome = os.path.expanduser('~')

    @classmethod
    def ls(cls, dirname):
        return os.listdir(dirname)

    @classmethod
    def abbrevuser(cls, path):
        return path.replace(Shell.userhome, '~')

    @classmethod
    def run(cls, cmd):
        try:
            return subprocess.check_output(
                cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
        except subprocess.CalledProcessError as e:
            VimErrorMsg(e)

    @classmethod
    def run_async(cls, cmd, cbk=None):
        def run():
            try:
                res = subprocess.check_output(
                    cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
                if cbk:
                    if len(inspect.getargspec(cbk).args) == 1:
                        vim.async_call(lambda: cbk(res))
                    else:
                        vim.async_call(lambda: cbk())

            except subprocess.CalledProcessError as e:
                ee = e
                vim.async_call(lambda: VimErrorMsg(ee))

        thread.start_new_thread(run, ())

    @classmethod
    def touch(cls, name):
        Shell.run('touch "{}"'.format(name))

    @classmethod
    def rm(cls, name):
        Shell.run('rm -r ' + name)

    @classmethod
    def shellrc(cls):
        return os.path.expanduser('~/.{}rc'.format(
            os.path.basename(os.environ['SHELL'])))

    @classmethod
    def cp(cls, src, dst):
        shutil.copy2(src, dst)

    @classmethod
    def mkdir(cls, name):
        if not os.path.isdir(name):
            os.makedirs(name)

    @classmethod
    def chmod(cls, fname, mode):
        os.chmod(fname, mode)

    @classmethod
    def isinPATH(cls, exe):
        return any(
            os.access(os.path.join(path, exe), os.X_OK)
            for path in os.environ["PATH"].split(os.pathsep))

    @classmethod
    def urldownload(cls, url, dst):
        import sys
        if sys.version_info[0] < 3:
            import urllib2 as urllib
        else:
            import urllib.request as urllib

        hstream = urllib.urlopen(url)
        with open(dst, 'wb') as f:
            f.write(hstream.read())


def c256(msg, c, background):
    if background:
        return '[38;5;{};7m{}[0m'.format(c, msg)
    else:
        return '[38;5;{}m{}[0m'.format(c, msg)
