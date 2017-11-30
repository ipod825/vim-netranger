import os
import shutil
import subprocess
import sys


def log(*msg):
    with open("/tmp/netlog", 'a') as f:
        f.write(' '.join([str(m) for m in msg])+"\n")


def spawnDaemon(func):
    # do the UNIX double-fork magic, see Stevens' "Advanced
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    try:
        pid = os.fork()
        if pid > 0:
            # parent process, return and keep running
            return
    except OSError as e:
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    os.setsid()

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as e:
        print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # do stuff
    func()

    # all done
    os._exit(os.EX_OK)


class Shell():
    @classmethod
    def run(cls, cmd):
        return subprocess.check_output(cmd, shell=True).decode('utf-8')

    @classmethod
    def spawn(cls, cmd):
        spawnDaemon(lambda: subprocess.check_output(cmd.split(' ')).decode('utf-8'))

    @classmethod
    def shellrc(cls):
        return os.path.expanduser('~/.{}rc'.format(os.path.basename(os.environ['SHELL'])))

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
        return any(os.access(os.path.join(path, exe), os.X_OK) for path in os.environ["PATH"].split(os.pathsep))

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
