import vim


def walk(fn, obj, *args, **kwargs):
    """Recursively walk an object graph applying `fn`/`args` to objects."""
    if int(vim.eval('has("nvim")')):
        return obj
    objType = type(obj)
    if objType in [list, tuple, vim.List]:
        return list(walk(fn, o, *args) for o in obj)
    elif objType in [dict, vim.Dictionary]:
        return dict(
            (walk(fn, k, *args), walk(fn, v, *args)) for k, v in obj.items())
    return fn(obj, *args, **kwargs)


if vim.eval('has("timers")') == "1":

    def VimTimer(delay, fn, pyfn):
        vim.command('call timer_start({}, "{}")'.format(delay, fn))
else:

    def VimTimer(delay, fn, pyfn):
        pyfn()


def decode_if_bytes(obj, mode=True):
    """Decode obj if it is bytes."""
    if mode is True:
        mode = 'strict'
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors=mode)
    return obj


def VimVar(name, default=None):
    if name not in vim.vars:
        return default
    return walk(decode_if_bytes, vim.vars[name])


def VimErrorMsg(exception):
    if hasattr(exception, 'output'):
        msg = exception.output.decode('utf-8')
    else:
        msg = str(exception)
    vim.command(
        'unsilent echohl ErrorMsg | unsilent echo "{}" | echohl None '.format(
            msg.replace('"', '\\"')))


def VimWarningMsg(msg):
    vim.command(
        'unsilent echohl WarningMsg | unsilent echo "{}" | echohl None '.
        format(msg.replace('"', '\\"')))


def VimEcho(msg):
    vim.command('unsilent echo "{}"'.format(msg))


def VimUserInput(hint, default=''):
    vim.command('let g:NETRRegister=input("{}: ", "{}")'.format(hint, default))
    return decode_if_bytes(vim.vars['NETRRegister'])


lastWidth = None


def VimCurWinWidth(cache=False):
    global lastWidth
    if cache:
        return lastWidth
    ve = vim.options['virtualedit']
    vim.options['virtualedit'] = 'all'
    vim.command('norm! g$')
    lastWidth = int(vim.eval('virtcol(".")'))
    vim.command('norm! g0')
    vim.options['virtualedit'] = ve
    return lastWidth


def VimCurWinHeight():
    return int(vim.eval("winheight('.')"))


class pbar(object):
    def __init__(self, objects, total=None, chunkSize=100):
        self.objects = iter(objects)
        if total is None:
            self.total = len(objects)
        else:
            self.total = total
        self.cur = 0
        self.chunkSize = chunkSize
        self.wid = VimCurWinWidth()
        self.st_save = vim.current.window.options['statusline']

    def __iter__(self):
        return self

    def __next__(self):
        if self.cur == self.total:
            vim.current.window.options['statusline'] = self.st_save
            vim.command("redrawstatus!")
            raise StopIteration
        else:
            self.cur += 1
            if self.cur % self.chunkSize == 0:
                vim.current.window.options[
                    'statusline'] = "%#NETRhiProgressBar#{}%##".format(
                        ' ' * int(self.cur * self.wid / self.total))
                vim.command("redrawstatus!")
            return next(self.objects)
