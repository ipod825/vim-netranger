import time

import vim

_hasnvim = int(vim.eval('has("nvim")'))
gui_compaitable = int(
    vim.eval('has("gui")')) or (int(vim.eval('has("termguicolors")'))
                                and vim.options['termguicolors'])

# original api
eval = vim.eval
vars = vim.vars
error = vim.error
windows = vim.windows
windows = vim.windows
buffers = vim.buffers
options = vim.options
command = vim.command
strwidth = vim.strwidth
current = vim.current
buffers = vim.buffers
tabpages = vim.tabpages

if _hasnvim:

    def walk(fn, obj, *args, **kwargs):
        return obj
else:

    def walk(fn, obj, *args, **kwargs):
        """Recursively walk an object graph applying `fn`/`args` to objects."""
        objType = type(obj)
        if objType in [list, tuple, vim.List]:
            return list(walk(fn, o, *args) for o in obj)
        elif objType in [dict, vim.Dictionary]:
            return dict((walk(fn, k, *args), walk(fn, v, *args))
                        for k, v in obj.items())
        return fn(obj, *args, **kwargs)


if vim.eval('has("timers")') == "1" and not vim.vars.get("_NETRDebug", False):

    def Timer(delay, pyfn, pyfn_str, *args):
        fn_args = ','.join([vim.eval(str(arg)) for arg in args])
        vim.command(
            f'call timer_start({delay}, {{->execute("python3 {pyfn_str}({fn_args})")}})'
        )
else:

    def Timer(delay, pyfn, pyfn_str, *args):
        pyfn(*args)


if gui_compaitable:

    def ColorMsg(msg, c, foreground):
        if foreground:
            return f'[48;2;{c}m{msg}[0m'
        else:
            return f'[38;2;{c}m{msg}[0m'
else:

    def ColorMsg(msg, c, foreground):
        if foreground:
            return f'[48;5;{c}m{msg}[0m'
        else:
            return f'[38;5;{c}m{msg}[0m'


def log(*msg):
    with open('/tmp/netrlog', 'a') as f:
        f.write(' '.join([str(m) for m in msg]) + '\n')


def decode_if_bytes(obj, mode=True):
    """Decode obj if it is bytes."""
    if mode is True:
        mode = 'strict'
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors=mode)
    return obj


def VimChansend(job_id, msg):
    vim.command(f'chansend({job_id},"{msg}\n")')


_NETRcbks = {}


def VimAsyncCallBack(job_id, event, data):
    cbk = _NETRcbks[job_id][event]
    if event == 'exit':
        cbk()
        del _NETRcbks[job_id]
    else:
        cbk(job_id, data)


def do_nothing_with_args(job_id, data):
    pass


def do_nothing():
    pass


if _hasnvim:

    def JobStart(cmd, term=False, termopencmd=''):
        if not term:
            vim.command(f'let g:NETRJobId = jobstart("{cmd}",\
                    {{"detach":1,\
                      "on_stdout":function("netranger#async#callback"),\
                      "on_stderr":function("netranger#async#callback"),\
                      "on_exit":function("netranger#async#callback")}})')
        else:
            vim.command(termopencmd)
            cmd_win_id = vim.eval('win_getid()')
            vim.command('let g:NETRJobId = termopen("{}",\
                        {{"on_exit":{{j,d,e -> function("netranger#async#term_callback")(j,d,e, {})}} }})'
                        .format(cmd, cmd_win_id))
        return str(vim.vars['NETRJobId'])

else:

    def JobStart(cmd, term=False, termopencmd=''):
        cur_time = str(time.time())
        if not term:
            vim.command(f'call job_start("{cmd}", {{\
                    "stoponexit": "",\
                    "out_cb":{{j,d-> netranger#async#callback("{cur_time}",d,"stdout")}},\
                      "err_cb":{{j,d-> netranger#async#callback("{cur_time}",d,"stderr")}},\
                      "exit_cb":{{j,s-> netranger#async#callback("{cur_time}",s,"exit")}}\
                                                   }})')
        else:
            vim.command(termopencmd)
            cmd_win_id = vim.eval('win_getid()')
            vim.command('call term_start("{}", {{\
                        "curwin":v:true,\
                        "term_kill":"9",\
                        "exit_cb":{{j,s-> netranger#async#term_callback("{}",s,"exit",{})}}\
                                                 }})'.format(
                cmd, cur_time, cmd_win_id))
        return cur_time


def AsyncRun(cmd,
             on_stdout=None,
             on_stderr=None,
             on_exit=None,
             term=False,
             termopencmd='10 new | wincmd J | startinsert'):

    if on_stdout is None:
        on_stdout = do_nothing_with_args
    if on_stderr is None:
        on_stderr = do_nothing_with_args
    if on_exit is None:
        on_exit = do_nothing

    job_id = JobStart(cmd.replace('"', '\\"'),
                      term=term,
                      termopencmd=termopencmd)
    _NETRcbks[job_id] = {
        'stdout': on_stdout,
        'stderr': on_stderr,
        'exit': on_exit
    }
    return job_id


def Var(name, default=None):
    if name not in vim.vars:
        return default
    return walk(decode_if_bytes, vim.vars[name])


def WindowVar(name, default=None):
    if name not in vim.current.window.vars:
        return default
    return walk(decode_if_bytes, vim.current.window.vars[name])


def SetVar(name, value):
    vim.vars[name] = value


def ErrorMsg(exception):
    if hasattr(exception, 'output'):
        msg = exception.output.decode('utf-8')
    else:
        msg = str(exception)
    msg = msg.strip()
    if not msg:
        return
    vim.command(
        'unsilent echohl ErrorMsg | unsilent echo "{}" | echohl None '.format(
            msg.replace('"', '\\"')))


def debug(*msg):
    vim.command('unsilent echom "{}"'.format(' '.join([str(m) for m in msg])))


def WarningMsg(msg):
    vim.command(
        'unsilent echohl WarningMsg | unsilent echo "{}" | echohl None '.
        format(msg.replace('"', '\\"').replace('\\','\\\\')))


def Echo(msg):
    vim.command('unsilent echo "%s"' % (msg.replace("\\","\\\\"),))


def UserInput(hint, default=''):
    vim.command(f'let g:NETRRegister=input("{hint}: ", "{default}")')
    return decode_if_bytes(vim.vars['NETRRegister'])


def CurWinWidth():
    # This function takes gutter into consideration.
    ve = vim.options['virtualedit']
    vim.options['virtualedit'] = 'all'
    vim.command('noautocmd norm! g$')
    res = int(vim.eval('virtcol(".")'))
    vim.command('noautocmd norm! g0')
    vim.options['virtualedit'] = ve
    return res


class pbar(object):
    def __init__(self, objects, total=None, chunkSize=100):
        self.objects = iter(objects)
        if total is None:
            self.total = len(objects)
        else:
            self.total = total
        self.cur = 0
        self.chunkSize = chunkSize
        self.wid = vim.current.window.width
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
