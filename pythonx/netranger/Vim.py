import vim


def walk(fn, obj, *args, **kwargs):
    """Recursively walk an object graph applying `fn`/`args` to objects."""
    if int(vim.eval('has("nvim")')):
        return obj
    objType = type(obj)
    if objType in [list, tuple, vim.List]:
        return list(walk(fn, o, *args) for o in obj)
    elif objType in [dict, vim.Dictionary]:
        return dict((walk(fn, k, *args), walk(fn, v, *args)) for k, v in obj.items())
    return fn(obj, *args, **kwargs)


def decode_if_bytes(obj, mode=True):
    """Decode obj if it is bytes."""
    if mode is True:
        mode = 'strict'
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors=mode)
    return obj


def VimVar(name):
    return walk(decode_if_bytes, vim.vars[name])


def VimErrorMsg(exception):
    if hasattr(exception, 'output'):
        msg = exception.output.decode('utf-8')
    else:
        msg = str(exception)
    vim.command('echohl ErrorMsg | unsilent echo "{}" | echohl None '.format(msg.replace('"','\\"')))


def VimWarningMsg(msg):
    vim.command('unsilent echohl WarningMsg | unsilent echo "{}" | echohl None '.format(msg.replace('"','\\"')))


def VimUserInput(hint, default=''):
    vim.command('let g:NETRRegister=input("{}: ", "{}")'.format(hint, default))
    return decode_if_bytes(vim.vars['NETRRegister'])


def VimCurWinWidth():
    return vim.current.window.width


class pbar(object):
    def __init__(self, objects, chunkSize=10):
        self.objects = iter(objects)
        self.total = len(objects)
        self.cur = 0
        self.chunkSize = chunkSize
        self.wid = VimCurWinWidth()
        # TODO: change back to local statusline when https://github.com/neovim/neovim/issues/8706 is fixxed
        # self.st_save = vim.current.window.options['statusline']
        self.st_save = vim.options['statusline']

    def __iter__(self):
        return self

    def __next__(self):
        if self.cur == self.total:
            # vim.current.window.options['statusline'] = self.st_save
            vim.options['statusline'] = self.st_save
            vim.command("redraw")
            raise StopIteration
        else:
            self.cur += 1
            if self.cur % self.chunkSize == 0:
                # vim.current.window.options['statusline'] = "%#NETRhiProgressBar#{}%##".format(' '*int(self.cur*self.wid/self.total))
                vim.options['statusline'] = "%#NETRhiProgressBar#{}%##".format(' '*int(self.cur*self.wid/self.total))
                vim.command("redraw")
            return next(self.objects)
