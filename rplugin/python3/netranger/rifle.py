import re
import os
from netranger.util import Shell, log, VimErrorMsg

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
            Shell.cp('{}/../../../config/rifle.conf'.format(os.path.dirname(__file__)), path)

        with open(path, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if len(line)==0 or line[0] == '#':
                    continue
                sp = line.split('=')
                if len(sp) != 2:
                    VimErrorMsg(self.vim, 'invalid rule: rifle.conf line {}'.format(i+1))
                    continue

                tests = []
                for test in sp[0].strip().split(','):
                    log('test', test)
                    testSp = [e for e in test.split(' ') if e!='']
                    log('testSp', testSp)
                    tests.append(globals()[testSp[0]](testSp[1]))
                    log('tests', tests)
                command = sp[1].strip()
                self.rules.append((tests, command))

    def decide_open_cmd(self, fname):
        for tests, command in self.rules:
            succ = True
            for test in tests:
                if not test(fname):
                    succ = False
            if succ:
                return command
