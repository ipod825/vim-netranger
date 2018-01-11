import vim
import sys

if sys.version_info[0] < 3 or int(vim.eval('has("nvim")')):
    VimVar = lambda name: vim.vars[name]
    VimVarLst = lambda name: vim.vars[name]
else:
    VimVar = lambda name: vim.vars[name].decode('utf8')
    VimVarLst = lambda name: [v.decode('utf8') for v in vim.vars[name]]


def VimErrorMsg(exception):
    if hasattr(exception, 'output'):
        msg = exception.output.decode('utf-8')
    else:
        msg = str(exception)
    vim.command('echohl ErrorMsg | echo "{}" | echohl None '.format(msg.replace('"','\\"')))


def VimUserInput(hint, default=''):
    vim.command('let g:NETRRegister=input("{}: ", "{}")'.format(hint, default))
    return vim.vars['NETRRegister']

def VimCurWinWidth():
    return vim.current.window.width
