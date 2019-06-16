from __future__ import absolute_import

import os
import pickle
import re
import shutil
import tempfile

from netranger.config import file_sz_display_wid
from netranger.enum import Enum
from netranger.util import Shell
from netranger.Vim import VimUserInput, debug

FType = Enum('FileType', 'SOCK, LNK, REG, BLK, DIR, CHR, FIFO')


class FS(object):
    # Putting fs_server.py in the pythonx directory fail to import shutil
    # so put it in the upper directory
    FScmds = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '../fs_server.py')

    acl_tbl = {
        '7': ['r', 'w', 'x'],
        '6': ['r', 'w', '-'],
        '5': ['r', '-', 'x'],
        '4': ['r', '-', '-'],
        '3': ['-', 'w', 'x'],
        '2': ['-', 'w', '-'],
        '1': ['-', '-', 'x'],
        '0': ['-', '-', '-'],
    }

    uid_tbl = {
        '7': ['s', 's', 't'],
        '6': ['s', 's', '-'],
        '5': ['s', '-', 't'],
        '4': ['s', '-', '-'],
        '3': ['-', 's', 't'],
        '2': ['-', 's', '-'],
        '1': ['-', '-', 't'],
        '0': ['-', '-', '-'],
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

    def ls(self, dirname, cheap_remote_ls=False):
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

    def rename(self, src, dst):
        shutil.move(src, dst)

    def exec_fs_server_cmd(self, cmd, src_arr, dst=None, on_exit=None):
        src = ' '.join(['"{}"'.format(s) for s in src_arr])
        if dst:
            dst = '"{}"'.format(dst)
            cmd = 'python {} {} {} {}'.format(FS.FScmds, cmd, src, dst)
            Shell.run_async(cmd, on_exit=on_exit)
        else:
            cmd = 'python {} {} {}'.format(FS.FScmds, cmd, src)
            Shell.run_async(cmd, on_exit=on_exit)

    def mv(self, src_arr, dst, on_exit=None):
        self.exec_fs_server_cmd('mv', src_arr, dst, on_exit)

    def cp(self, src_arr, dst, on_exit):
        self.exec_fs_server_cmd('cp', src_arr, dst, on_exit)

    def rm(self, src_arr, force=False, on_exit=None):
        # TODO force?
        self.exec_fs_server_cmd('rm', src_arr, on_exit=on_exit)

    def touch(self, name):
        Shell.touch(name)

    def mkdir(self, name):
        Shell.mkdir(name)

    def mtime(self, fname):
        return os.stat(fname).st_mtime

    def size_str(self, path, statinfo):
        if os.path.isdir(path):
            return str(len(os.listdir(path)))

        res = float(statinfo.st_size)
        for u in ['B', 'K', 'M', 'G', 'T', 'P']:
            if res < 1024:
                return '{} {}'.format(
                    re.sub(r'\.0*$', '',
                           str(res)[:file_sz_display_wid - 2]), u)
            res /= 1024
        return '?' * file_sz_display_wid

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


class Rclone(FS):
    FScmds = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '../rclone_server.py')
    SyncDirection = Enum('SyncDirection', 'DOWN, UP')

    def sync_src_dst(self, lpath, direction):
        rpath = self.rpath(lpath)
        if direction == Rclone.SyncDirection.UP:
            return lpath, rpath
        else:
            return rpath, lpath

    def __init__(self, root_dir, remote_remap):
        if root_dir[-1] == '/':
            root_dir = root_dir[:-1]

        self.root_dir = root_dir
        self.rplen = len(root_dir) + 1
        for remote, root in remote_remap.items():
            if root[-1] != '/':
                remote_remap[remote] += '/'
        self.remote_remap = remote_remap
        Shell.mkdir(root_dir)

        remotes = set([
            line for line in Shell.run('rclone listremotes').split(':\n')
            if line
        ])
        local_remotes = set(super(Rclone, self).ls(root_dir))
        for remote in remotes.difference(local_remotes):
            Shell.mkdir(os.path.join(root_dir, remote))
        for remote in local_remotes.difference(remotes):
            Shell.rm(os.path.join(root_dir, remote))

        self.has_remote = len(remotes) > 0
        self.ls_time_stamp = {}

    def rpath(self, lpath):
        if not lpath.startswith(self.root_dir):
            return lpath
        rpath = lpath[self.rplen:]
        if '/' not in rpath:
            rpath += ':/'
        else:
            rpath = rpath.replace('/', ':/', 1)

        for remote, root in self.remote_remap.items():
            if rpath.startswith(remote):
                rpath = rpath.replace('/', root, 1)
        return rpath

    def ls(self, dirname, cheap_remote_ls=False):
        if not cheap_remote_ls and len(dirname) > len(self.root_dir):
            local_files = set([
                name
                for name in Shell.run('ls -p {}'.format(dirname)).split('\n')
                if len(name) > 0
            ])
            remote_files = set([
                name for name in Shell.run('rclone lsf "{}"'.format(
                    self.rpath(dirname))).split('\n') if len(name) > 0
            ])
            for name in remote_files.difference(local_files):
                if name[-1] == '/':
                    Shell.mkdir(os.path.join(dirname, name))
                else:
                    Shell.touch(os.path.join(dirname, name))

            for name in local_files.difference(remote_files):
                Shell.run('rclone copyto --tpslimit=10 "{}" "{}"'.format(
                    os.path.join(dirname, name),
                    os.path.join(self.rpath(dirname), name)))
        return super(Rclone, self).ls(dirname)

    def ensure_downloaded(self, lpath):
        if os.stat(lpath).st_size == 0:
            src, dst = self.sync_src_dst(lpath, Rclone.SyncDirection.DOWN)
            Shell.run('rclone copyto --tpslimit=10 "{}" "{}"'.format(src, dst))

    def rename(self, src, dst):
        Shell.run('rclone moveto "{}" "{}"'.format(self.rpath(src),
                                                   self.rpath(dst)))
        super(Rclone, self).rename(src, dst)

    def exec_rclone_server_cmd(self, cmd, on_exit, arguments):
        fname = tempfile.mkstemp()[1]
        with open(fname, 'ab') as f:
            pickle.dump(arguments, f)
        Shell.run_async('python {} {} {}'.format(Rclone.FScmds, cmd, fname),
                        on_exit=on_exit)

    def mv(self, src_arr, dst, on_exit):
        self.exec_rclone_server_cmd(
            'mv', on_exit, {
                'rsrc': [self.rpath(s) for s in src_arr],
                'src': src_arr,
                'rdst': self.rpath(dst),
                'dst': dst
            })

    def cp(self, src_arr, dst, on_exit):
        self.exec_rclone_server_cmd(
            'cp', on_exit, {
                'rsrc': [self.rpath(s) for s in src_arr],
                'src': src_arr,
                'rdst': self.rpath(dst),
                'dst': dst
            })

    def rm(self, src_arr, force=False, on_exit=None):
        self.exec_rclone_server_cmd('rm', on_exit, {
            'rsrc': [self.rpath(s) for s in src_arr],
            'src': src_arr
        })

    def touch(self, name):
        Shell.touch(name)
        Shell.run('rclone copyto "{}" "{}"'.format(
            name, os.path.join(self.rpath(name), os.path.basename(name))))

    def mkdir(self, name):
        Shell.mkdir(name)

    def sync(self, lpath, direction):
        src, dst = self.sync_src_dst(lpath, direction)
        Shell.run('rclone sync "{}" "{}"'.format(src, dst))

    def parent_dir(self, cwd):
        if len(cwd) == self.rplen - 1:
            return cwd
        return os.path.abspath(os.path.join(cwd, os.pardir))

    @classmethod
    def valid_or_install(cls, vim):
        import platform
        import zipfile

        if Shell.isinPATH('rclone'):
            return True
        else:
            rclone_dir = VimUserInput(
                'Rclone not in PATH. Install it at (modify/enter)',
                os.path.expanduser('~/rclone'))
            Shell.mkdir(rclone_dir)

            system = platform.system().lower()
            processor = 'amd64'
            if '386' in platform.processor():
                processor = '386'
            else:
                # Should support arm??
                pass

            url = 'https://downloads.rclone.org/rclone-current-{}-{}.zip'\
                .format(system, processor)
            zip_fname = os.path.join(rclone_dir, 'rclone.zip')
            Shell.urldownload(url, zip_fname)
            zip_ref = zipfile.ZipFile(zip_fname, 'r')
            zip_ref.extractall(rclone_dir)
            for entry in zip_ref.NameToInfo:
                if entry.endswith('rclone'):
                    Shell.cp(os.path.join(rclone_dir, entry), rclone_dir)
                    Shell.chmod(os.path.join(rclone_dir, 'rclone'), 755)

            zip_ref.close()
            os.remove(zip_fname)

            shellrc = VimUserInput(
                'Update PATH in (leave blank to set manually later)',
                Shell.shellrc())
            if len(shellrc) > 0:
                with open(shellrc, 'a') as f:
                    f.write('PATH={}:$PATH\n'.format(rclone_dir))
            os.environ['PATH'] += ':' + rclone_dir
