from __future__ import absolute_import
import os
from netranger.util import Shell
from netranger.util import log
from netranger.Vim import VimUserInput
from netranger.enum import Enum
from netranger.config import file_sz_display_wid
import shutil
import re

log('')

FType = Enum('FileType', 'SOCK, LNK, REG, BLK, DIR, CHR, FIFO')


class FS(object):
    acl_tbl = {
        '7': ['r','w','x'],
        '6': ['r','w','-'],
        '5': ['r','-','x'],
        '4': ['r','-','-'],
        '3': ['-','w','x'],
        '2': ['-','w','-'],
        '1': ['-','-','x'],
        '0': ['-','-','-'],
    }

    uid_tbl = {
        '7': ['s','s','t'],
        '6': ['s','s','-'],
        '5': ['s','-','t'],
        '4': ['s','-','-'],
        '3': ['-','s','t'],
        '2': ['-','s','-'],
        '1': ['-','-','t'],
        '0': ['-','-','-'],
    }

    ft_tbl = {
        '14': 's',
        '12': 'l',
        '10': '-',
        '06': 'b',
        '04': 'd',
        '02': 'c',
        '01': 'p',
        'o6': 'b',
        'o4': 'd',
        'o2': 'c',
        'o1': 'p',
    }

    @property
    def isRemote(self):
        return type(self) is Rclone

    def ls(self, dirname):
        if not os.access(dirname, os.R_OK):
            return []
        return sorted(os.listdir(dirname), key=lambda x: os.path.isdir(x))

    def parent_dir(self, cwd):
        return os.path.abspath(os.path.join(cwd, os.pardir))

    def fftype(self, fname):
        if os.path.islink(fname):
            catlog = 'link'
        if os.path.isdir(fname):
            catlog = 'dir'
        elif os.access(fname, os.X_OK):
            catlog = 'exe'
        else:
            catlog = 'file'
        return catlog

    def mv(self, src, dst):
        shutil.move(src, dst)

    def cp(self, src, dst):
        if os.path.isdir(src) and src[-1]!='/':
            src = src+'/'
        if os.path.isdir(dst) and dst[-1]!='/':
            dst = dst+'/'
        Shell.run('cp -r "{}" "{}"'.format(src, dst))

    def rm(self, target, force=False):
        if force:
            Shell.run('rm -rf "{}"'.format(target))
        else:
            Shell.run('rm -r "{}"'.format(target))

    def mtime(self, fname):
        return os.stat(fname).st_mtime

    def size_str(self, path, statinfo):
        if os.path.isdir(path):
            return str(len(os.listdir(path)))

        res = float(statinfo.st_size)
        for u in ['B', 'K', 'M', 'G', 'T', 'P']:
            if res < 1024:
                return '{} {}'.format(re.sub('\.0*$', '', str(res)[:file_sz_display_wid-2]), u)
            res /= 1024
        return '?'*file_sz_display_wid

    def acl_str(self, statinfo):
        statinfo = oct(statinfo.st_mode)
        acl = statinfo[-4:]
        rwx = FS.acl_tbl[acl[1]] + FS.acl_tbl[acl[2]] + FS.acl_tbl[acl[3]]
        sst = FS.uid_tbl[acl[0]]
        i = 2
        for b in sst:
            if b != '-':
                rwx[i] = b
            i += 3

        rwx.insert(0, FS.ft_tbl[statinfo[-6:-4]])
        return ''.join(rwx)


class RcloneFile(object):
    def __init__(self, lpath, rpath):
        self.lpath = lpath
        self.rpath = rpath
        self.inited = os.path.isfile(lpath)

        if not self.inited:
            Shell.touch(lpath)

    def lazy_init(self):
        if self.inited:
            return
        self.inited = True
        self.sync(Rclone.SyncDirection.DOWN)

    def sync(self, direction):
        src, dst = Rclone.sync_src_dst(self.lpath, self.rpath, direction)
        Shell.run('rclone copyto "{}" "{}"'.format(src, dst))


class RcloneDir(object):
    def __init__(self, lpath, rpath):
        Shell.mkdir(lpath)
        self.lpath = lpath

        self.children = {}
        self.inited = False
        self.rpath = rpath

        if type(rpath) is dict:
            remotes = Shell.run('rclone listremotes').split(':\n')
            for remote in remotes:
                if len(remote)==0:
                    continue
                root = rpath.get(remote, '')
                self.children[remote] = RcloneDir(os.path.join(lpath, remote), remote+':'+root)
            self.inited = True

    def lsd(self):
        info = Shell.run('rclone lsd "{}" --max-depth 1'.format(self.rpath))

        for line in info.split('\n'):
            line = line.strip()
            if len(line)>0:
                name = line.split()[-1]
                self.children[name] = RcloneDir(os.path.join(self.lpath, name), os.path.join(self.rpath, name))

    def lsl(self):
        info = Shell.run('rclone lsl "{}" --max-depth 1'.format(self.rpath))

        for line in info.split('\n'):
            line = line.strip()
            if len(line)>0:
                name = line.split()[-1]
                self.children[name] = RcloneFile(os.path.join(self.lpath, name), os.path.join(self.rpath, name))

    def lazy_init(self):
        if self.inited:
            return
        self.inited = True
        self.lsd()
        self.lsl()

    def sync(self, direction):
        src, dst = Rclone.sync_src_dst(self.lpath, self.rpath, direction)
        Shell.run('rclone sync "{}" "{}"'.format(src, dst))

    def refresh_children(self):
        fs_files = set(Shell.ls(self.lpath))
        cur_files = set(self.children.keys())

        for name in cur_files.difference(fs_files):
            del self.children[name]

        for name in fs_files.difference(cur_files):
            fullpath = os.path.join(self.lpath, name)
            if os.path.isdir(fullpath):
                self.children[name] = RcloneDir(fullpath, os.path.join(self.rpath, name))
            else:
                self.children[name] = RcloneFile(fullpath, os.path.join(self.rpath, name))


class Rclone(FS):
    SyncDirection = Enum('SyncDirection', 'DOWN, UP')

    @classmethod
    def sync_src_dst(self, lpath, rpath, direction):
        if direction == Rclone.SyncDirection.UP:
            return lpath, rpath
        else:
            return rpath, lpath

    @property
    def has_remote(self):
        return len(self.root_dir.children)>0

    def __init__(self, root_dir, remote_roots):
        if root_dir[-1] == '/':
            root_dir = root_dir[:-1]
        super(Rclone, self).rm(root_dir, force=True)

        self.rplen = len(root_dir)+1
        self.root_dir = RcloneDir(root_dir, remote_roots)

    def getNode(self, lpath):
        """
        Reutrn the RcloneDir/RcloneFile node corresponding to lpath.
        """
        curNode = self.root_dir

        for name in lpath[self.rplen:].split('/'):
            if len(name) == 0:
                continue
            curNode = curNode.children[name]
        return curNode

    def ls(self, dirname):
        """
        Ensure directory entries match remote entries then return local ls result.
        """
        self.lazy_init(dirname)
        return super(Rclone, self).ls(dirname)

    def lazy_init(self, lpath):
        self.getNode(lpath).lazy_init()

    def sync(self, lpath, direction):
        self.getNode(lpath).sync(direction)

    def parent_dir(self, cwd):
        if len(cwd) == self.rplen-1:
            return cwd
        return os.path.abspath(os.path.join(cwd, os.pardir))

    def refresh_remote(self, lpath):
        """
        Sync remote so that remote content is the same as local content. If lpath is a directory, we also need to update its children data structure.
        """
        node = self.getNode(lpath)
        node.sync(Rclone.SyncDirection.UP)
        if type(node) is RcloneDir:
            node.refresh_children()

    @classmethod
    def valid_or_install(cls, vim):
        import platform
        import zipfile

        if Shell.isinPATH('rclone'):
            return True
        else:
            rclone_dir = VimUserInput('Rclone not in PATH. Install it at (modify/enter)', os.path.expanduser('~/rclone'))
            Shell.mkdir(rclone_dir)

            system = platform.system().lower()
            processor = 'amd64'
            if '386' in platform.processor():
                processor = '386'
            else:
                # Should support arm??
                pass

            url = 'https://downloads.rclone.org/rclone-current-{}-{}.zip'.format(system, processor)
            zip_fname = os.path.join(rclone_dir, 'rclone.zip')
            Shell.urldownload(url, zip_fname)
            zip_ref = zipfile.ZipFile(zip_fname, 'r')
            zip_ref.extractall(rclone_dir)
            for entry in zip_ref.NameToInfo:
                if entry.endswith('rclone'):
                    Shell.cp(os.path.join(rclone_dir, entry), rclone_dir)
                    Shell.chmod(os.path.join(rclone_dir,'rclone'), 755)

            zip_ref.close()
            os.remove(zip_fname)

            shellrc = VimUserInput('Update PATH in (leave blank to set manually later)', Shell.shellrc())
            if len(shellrc)>0:
                with open(shellrc, 'a') as f:
                    f.write('PATH={}:$PATH\n'.format(rclone_dir))
            os.environ['PATH'] += ':' + rclone_dir
