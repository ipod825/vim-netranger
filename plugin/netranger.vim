if exists("g:loaded_netranger") || &cp
  finish
endif
let g:loaded_netranger = 1

let s:save_cpo = &cpo
set cpo&vim

if !has('python3') && !has('python')
    echo "Error: Required vim compiled with +python or +python3"
    finish
endif

let g:loaded_netrwPlugin = 0
let g:loaded_netrw = 0

" if has('python3')
"     let s:pyx = 'python3 '
" else
"     let s:pyx = 'python '
" endif
let s:pyx = 'python3 '

exec s:pyx "import netranger"
exec s:pyx "from netranger.netranger import Netranger"
exec s:pyx "ranger = Netranger()"
exec s:pyx "from netranger.api import NETRApi"
exec s:pyx "NETRApi.init(ranger)"

augroup NETRANGER
    autocmd!
    autocmd BufEnter * exec s:pyx 'ranger.on_bufenter('.expand("<abuf>").')'
    autocmd WinEnter * exec s:pyx 'ranger.on_winenter('.expand("<abuf>").')'
    autocmd CursorMoved * exec s:pyx 'ranger.on_cursormoved('.expand("<abuf>").')'
augroup END

func! _NETRInvokeMap(fn)
    exec s:pyx 'ranger.invoke_map("'.a:fn.'")'
endfunc

func! _NETROnCursorMovedPost(bufnum, timerid)
    exec s:pyx 'ranger.on_cursormoved_post('.a:bufnum.')'
endfunc

command! NETRemoteList exec s:pyx 'ranger.NETRemoteList()'
command! NETRemotePull exec s:pyx 'ranger.NETRemotePull()'
command! NETRemotePush exec s:pyx 'ranger.NETRemotePush()'
command! -nargs=1 -complete=file NETRTabdrop exec s:pyx 'netranger.Vim.tabdrop("'.fnamemodify("<args>", ":p").'")'


let &cpo = s:save_cpo
