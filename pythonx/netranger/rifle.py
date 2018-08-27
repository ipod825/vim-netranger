from __future__ import absolute_import
import re
import os
from netranger.util import Shell, log
from netranger.Vim import VimErrorMsg
from netranger.config import config_dir

log('')


class Rule(object):
    def __init__(self, arg):
        self.arg = arg

    def __call__(self, fname):
        pass


class ext(Rule):
    def __call__(self, fname):
        return re.search(self.arg, fname) is not None


class has(Rule):
    def __call__(self, fname):
        return Shell.isinPATH(self.arg)


class Rifle(object):
    def __init__(self, vim, path):
        self.vim = vim
        self.rules = []

        if not os.path.isfile(path):
            Shell.cp(os.path.join(config_dir, 'rifle.conf'), path)

        with open(path, 'r') as f:
            for i, line in enumerate(f):
                try:
                    # remove things after the first # (including)
                    line = line[:line.index('#')]
                except ValueError:
                    pass

                line = line.strip()
                if len(line) == 0:
                    continue
                sp = line.split('=')
                if len(sp) != 2:
                    VimErrorMsg(
                        'invalid rule: rifle.conf line {}. There should be one'
                        ' and only one "=" for each line'.format(i + 1))
                    continue

                tests = []
                for test in sp[0].strip().split(','):
                    testSp = [e for e in test.split(' ') if e != '']
                    tests.append(globals()[testSp[0]](testSp[1]))
                command = sp[1].strip()

                # simple case, used specify only the command
                # For sophisicated command like bash -c "command {}"
                # user should add '{}' themselves
                if '{}' not in command:
                    command = command + ' {}'
                self.rules.append((tests, command))

    def decide_open_cmd(self, fname):
        for tests, command in self.rules:
            succ = True
            for test in tests:
                if not test(fname):
                    succ = False
                    break
            if succ:
                return command

    def list_available_cmd(self, fname):
        res = []
        for tests, command in self.rules:
            succ = True
            for test in tests:
                if not test(fname):
                    succ = False
                    break
            if succ:
                res.append(command)
        return res
