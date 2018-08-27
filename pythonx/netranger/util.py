import os
import shutil
import subprocess
import sys
import tempfile
import _thread as thread
try:
    from netranger.Vim import VimErrorMsg as CmdFailLog
except Exception:
    CmdFailLog = print


def log(*msg):
    with open(os.path.join(tempfile.gettempdir(), "netlog"), 'a') as f:
        f.write(' '.join([str(m) for m in msg]) + "\n")


def spawnDaemon(func):
    # do the UNIX double-fork magic, see Stevens' "Advanced
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    try:
        pid = os.fork()
        if pid > 0:
            # parent process, return and keep running
            return
    except OSError as e:
        print >> sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    os.setsid()

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as e:
        print >> sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # do stuff
    func()

    # all done
    os._exit(os.EX_OK)


class Shell():
    userhome = os.path.expanduser('~')

    @classmethod
    def ls(cls, dirname):
        return os.listdir(dirname)

    @classmethod
    def abbrevuser(cls, path):
        return path.replace(Shell.userhome, '~')

    @classmethod
    def run(cls, cmd, log_if_error=True):
        try:
            return subprocess.check_output(
                cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
        except subprocess.CalledProcessError as e:
            if log_if_error:
                CmdFailLog(e)

    @classmethod
    def run_async(cls, cmd):
        thread.start_new_thread(lambda: Shell.run(cmd), ())

    @classmethod
    def touch(cls, name):
        Shell.run('touch "{}"'.format(name))

    @classmethod
    def rm(cls, name):
        Shell.run('rm -r ' + name)

    @classmethod
    def spawn(cls, cmd):
        spawnDaemon(
            lambda: subprocess.check_output(cmd.split(' ')).decode('utf-8'))

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
