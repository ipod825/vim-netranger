from netranger import Vim, util


def plaintext(path):
    bak_shortmess = Vim.options['shortmess']
    Vim.options['shortmess'] = 'A'
    Vim.command(f'edit {path}')
    Vim.options['shortmess'] = bak_shortmess
    Vim.current.window.options['foldenable'] = False


def mime(
    path,
    guees_type,
):
    Vim.command('setlocal buftype=nofile')
    Vim.command('setlocal noswapfile')
    Vim.command('setlocal nobuflisted')
    Vim.command('setlocal bufhidden=wipe')
    Vim.current.buffer[:] = [path, guees_type]
    Vim.command('setlocal nomodifiable')


def image(path, guees_type, total_width, preview_width):
    try:
        Vim.AsyncRun(f'{util.GenNetRangerScriptCmd("image_preview")}\
                        {path} {total_width} {preview_width}',
                     term=True,
                     termopencmd='')
        Vim.command('setlocal nocursorline')
    except Exception:
        mime(path, guees_type)
