import os
import shutil
import subprocess

from netranger.Vim import VimAsyncRun, VimErrorMsg


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
    def run_async(cls, cmd, on_stdout=None, on_exit=None):
        def print_error(job_id, err_msg):
            # Truncate unnecessary message if from fs_server.py
            ind = err_msg.rfind('FSServerException: ')
            if ind > 0:
                err_msg = err_msg[ind + 19:]
            VimErrorMsg(err_msg)

        VimAsyncRun(cmd,
                    on_stdout=on_stdout,
                    on_exit=on_exit,
                    on_stderr=print_error)

    @classmethod
    def touch(cls, name):
        open(name, 'a').close()

    @classmethod
    def rm(cls, name):
        if os.path.isdir(name):
            shutil.rmtree(name)
        else:
            os.remove(name)

    @classmethod
    def shellrc(cls):
        return os.path.expanduser('~/.{}rc'.format(
            os.path.basename(os.environ['SHELL'])))

    @classmethod
    def cp(cls, src, dst):
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, os.path.basename(src)))
        else:
            shutil.copy(src, dst)

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
