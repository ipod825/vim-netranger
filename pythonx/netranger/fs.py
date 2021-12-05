from __future__ import absolute_import

import json
import os
import pickle
import re
import shutil
import tempfile
import time

from netranger import Vim, util
from netranger.config import file_sz_display_wid
from netranger.enum import Enum
from netranger.shell import Shell

FType = Enum('FileType', 'SOCK, LNK, REG, BLK, DIR, CHR, FIFO')


def do_nothing():
    pass


class FSTarget(object):
    def __init__(self, target_path=''):
        """ This is a help class for separating local files and remote files
        for mv, cp, rm commands. Though the logic in this class can be done
        in the caller side, it makes the caller has higher branch number and
        hard-to-read code.
        """
        self.remote_targets = []
        self.local_targets = []
        self.remote_root = Vim.Var('NETRemoteCacheDir')
        self.is_remote = self.is_remote_path(target_path)

    def is_remote_path(self, path):
        return path and path.startswith(self.remote_root)

    def append(self, path):
        if self.is_remote or self.is_remote_path(path):
            self.remote_targets.append(path)
        else:
            self.local_targets.append(path)
        return self

    def extend(self, paths, hint=None):
        if hint and self.is_remote_path(hint):
            self.remote_targets.extend(paths)
        else:
            self.local_targets.extend(paths)
        return self

    def mv(self,
           target_dir,
           sudo=False,
           on_begin=do_nothing,
           on_exit=do_nothing):
        if self.local_targets:
            on_begin()
            LocalFS.mv(self.local_targets,
                       target_dir,
                       sudo=sudo,
                       on_exit=on_exit)
        if self.remote_targets:
            on_begin()
            Rclone.mv(self.remote_targets, target_dir, on_exit=on_exit)

    def cp(self,
           target_dir,
           sudo=False,
           on_begin=do_nothing,
           on_exit=do_nothing):
        if self.local_targets:
            on_begin()
            LocalFS.cp(self.local_targets,
                       target_dir,
                       sudo=sudo,
                       on_exit=on_exit)
        if self.remote_targets:
            on_begin()
            Rclone.cp(self.remote_targets, target_dir, on_exit=on_exit)

    def rm(self,
           force=False,
           sudo=False,
           on_begin=do_nothing,
           on_exit=do_nothing):
        if self.local_targets:
            on_begin()
            LocalFS.rm(self.local_targets,
                       force=force,
                       sudo=sudo,
                       on_exit=on_exit)
        if self.remote_targets:
            on_begin()
            Rclone.rm(self.remote_targets, force=force, on_exit=on_exit)


class LocalFS(object):
    # Putting fs_server.py in the pythonx directory fail to import shutil
    # so put it in the upper directory
    ServerCmd = util.GenNetRangerScriptCmd('fs_server')
    is_remote = False

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

    @classmethod
    def ensure_remote_downloaded(cls, _):
        pass

    @classmethod
    def ls(self, dirname, cheap_remote_ls=False):
        return sorted(os.listdir(dirname), key=lambda x: os.path.isdir(x))

    @classmethod
    def parent_dir(self, cwd):
        return os.path.abspath(os.path.join(cwd, os.pardir))

    @classmethod
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

    @classmethod
    def rename(self, src, dst):
        shutil.move(src, dst)

    @classmethod
    def exec_server_cmd(self, cmd, on_exit, arguments, sudo=False):
        def on_stderr(job_id, err_msg):
            ind = err_msg.rfind('FSServerException: ')
            if ind > 0:
                err_msg = err_msg[ind + 19:]
            Vim.ErrorMsg(err_msg)

        fname = tempfile.mkstemp()[1]
        with open(fname, 'ab') as f:
            pickle.dump(arguments, f)

        if sudo:
            Vim.AsyncRun('sudo {} {} {}'.format(self.ServerCmd, cmd, fname).replace('\\','\\\\'),
                         on_exit=on_exit,
                         term=True)
        else:
            Vim.AsyncRun('{} {} {}'.format(self.ServerCmd, cmd, fname).replace('\\','\\\\'),
                         on_stderr=on_stderr,
                         on_exit=on_exit)

    @classmethod
    def mv(self, src_arr, dst, sudo=False, on_exit=None):
        self.exec_server_cmd('mv',
                             on_exit, {
                                 'src': src_arr,
                                 'dst': dst
                             },
                             sudo=sudo)

    @classmethod
    def cp(self, src_arr, dst, sudo=False, on_exit=None):
        print("uuu",src_arr,dst)
        self.exec_server_cmd('cp',
                             on_exit, {
                                 'src': src_arr,
                                 'dst': dst
                             },
                             sudo=sudo)

    @classmethod
    def rm(self, src_arr, force=False, sudo=False, on_exit=None):
        # TODO force?
        self.exec_server_cmd('rm', on_exit, {'src': src_arr}, sudo=sudo)

    @classmethod
    def touch(self, name):
        Shell.touch(name)

    @classmethod
    def mkdir(self, name):
        Shell.mkdir(name)

    @classmethod
    def mtime(self, fname):
        return os.stat(fname).st_mtime

    @classmethod
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

    @classmethod
    def acl_str(self, statinfo):
        statinfo = oct(statinfo.st_mode)
        acl = statinfo[-4:]
        rwx = LocalFS.acl_tbl[acl[1]] + LocalFS.acl_tbl[
            acl[2]] + LocalFS.acl_tbl[acl[3]]
        sst = LocalFS.uid_tbl[acl[0]]
        i = 2
        for b in sst:
            if b != '-':
                rwx[i] = b
            i += 3

        rwx.insert(0, LocalFS.ft_tbl[statinfo[-6:-4]])
        return ''.join(rwx)


class Rclone(LocalFS):
    ServerCmd = util.GenNetRangerScriptCmd('rclone_server')
    is_remote = True
    SyncDirection = Enum('SyncDirection', 'DOWN, UP')

    @classmethod
    def sync_src_dst(self, lpath, direction):
        rpath = self.rpath(lpath)
        if direction == Rclone.SyncDirection.UP:
            return lpath, rpath
        else:
            return rpath, lpath

    @classmethod
    def init(self, root_dir, remote_remap):
        self._flags = Vim.Var("_NETRRcloneFlags", default="")
        self.rclone_rcd_port = Vim.Var('NETRcloneRcdPort')
        if root_dir[-1] == '/':
            root_dir = root_dir[:-1]

        self.root_dir = root_dir
        self.rplen = len(root_dir) + 1
        self.rcd_started = False
        for remote, root in remote_remap.items():
            if root[-1] != '/':
                remote_remap[remote] += '/'
        self.remote_remap = remote_remap
        Shell.mkdir(root_dir)

    @classmethod
    def is_remote_path(self, path):
        return path.startswith(self.root_dir)

    @classmethod
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

    @classmethod
    def ls(self, dirname, cheap_remote_ls=False):
        if not cheap_remote_ls and len(dirname) > len(self.root_dir):
            local_files = set([
                name for name in Shell.run(f'ls -p "{dirname}"').split('\n')
                if len(name) > 0
            ])

            remote_files = set([
                name for name in Shell.run(
                    f'rclone {self._flags} lsf "{self.rpath(dirname)}"').split(
                        '\n') if len(name) > 0
            ])
            for name in remote_files.difference(local_files):
                if name[-1] == '/':
                    Shell.mkdir(os.path.join(dirname, name))
                else:
                    Shell.touch(os.path.join(dirname, name))

            for name in local_files.difference(remote_files):
                # TODO use Vim.AsyncRun instead
                Shell.run_async(f'rclone {self._flags} copyto --tpslimit=10 \
                                "{os.path.join(dirname, name)}" \
                                "{os.path.join(self.rpath(dirname), name)}"')
        return super(Rclone, self).ls(dirname)

    @classmethod
    def ensure_remote_downloaded(self, lpath):
        if os.stat(lpath).st_size == 0:
            src, dst = self.sync_src_dst(lpath, Rclone.SyncDirection.DOWN)
            Shell.run(
                f'rclone {self._flags} copyto --tpslimit=10 "{src}" "{dst}"')

    @classmethod
    def rename(self, src, dst):
        Shell.run(
            f'rclone {self._flags} moveto "{self.rpath(src)}" "{self.rpath(dst)}"'
        )
        super(Rclone, self).rename(src, dst)

    @classmethod
    def mv(self, src_arr, dst, on_exit):
        self.exec_server_cmd(
            'mv', on_exit, {
                'rsrc': [self.rpath(s) for s in src_arr],
                'src': src_arr,
                'rdst': self.rpath(dst),
                'dst': dst,
                'flags': self._flags
            })

    @classmethod
    def cp(self, src_arr, dst, on_exit):
        self.exec_server_cmd(
            'cp', on_exit, {
                'rsrc': [self.rpath(s) for s in src_arr],
                'src': src_arr,
                'rdst': self.rpath(dst),
                'dst': dst,
                'flags': self._flags
            })

    @classmethod
    def rm(self, src_arr, force=False, on_exit=None):
        self.exec_server_cmd(
            'rm', on_exit, {
                'rsrc': [self.rpath(s) for s in src_arr],
                'src': src_arr,
                'flags': self._flags
            })

    @classmethod
    def touch(self, name):
        Shell.touch(name)

    @classmethod
    def mkdir(self, name):
        Shell.mkdir(name)

    @classmethod
    def sync(self, lpath, direction):
        src, dst = self.sync_src_dst(lpath, direction)
        Shell.run(f'rclone {self._flags} sync "{src}" "{dst}"')

    @classmethod
    def run_cmd(self, cmd):
        if not self.rcd_started:
            Vim.AsyncRun(
                f'rclone {self._flags} rcd --rc-no-auth --rc-addr=localhost:{self.rclone_rcd_port}'
            )
            self.rcd_started = True
            # Ensure the server running before executing the next command.
            time.sleep(.1)

        return json.loads(
            Shell.run(
                f'rclone {self._flags} rc --rc-addr=localhost:{self.rclone_rcd_port} {cmd}'
            ))

    @classmethod
    def cmd_listremotes(self):
        return self.run_cmd('config/listremotes')['remotes']

    @classmethod
    def list_remotes_in_vim_buffer(self):
        if not Shell.isinPATH('rclone'):
            self.install_rclone()

        remotes = set(self.cmd_listremotes())
        local_remotes = set(super(Rclone, self).ls(self.root_dir))
        for remote in remotes.difference(local_remotes):
            Shell.mkdir(os.path.join(self.root_dir, remote))
        for remote in local_remotes.difference(remotes):
            Shell.rm(os.path.join(self.root_dir, remote))

        if len(remotes) > 0:
            Vim.command(f'NETRTabdrop {self.root_dir}')
        else:
            Vim.ErrorMsg(
                "There's no remote now. Run 'rclone config' in a terminal to "
                "setup remotes and restart vim again.")

    @classmethod
    def install_rclone(self):
        import platform
        import zipfile

        rclone_dir = Vim.UserInput(
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

        url = f'https://downloads.rclone.org/rclone-current-{system}-{processor}.zip'
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

        shellrc = Vim.UserInput(
            'Update PATH in (leave blank to set manually later)',
            Shell.shellrc())
        if len(shellrc) > 0:
            with open(shellrc, 'a') as f:
                f.write(f'PATH={rclone_dir}:$PATH\n')
        os.environ['PATH'] += ':' + rclone_dir
