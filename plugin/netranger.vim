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

if has('python3')
    let s:pyx = 'python3 '
else
    let s:pyx = 'python '
endif

exec s:pyx "import vim"
exec s:pyx "from netranger.netranger import Netranger"
exec s:pyx "ranger = Netranger(vim)"

augroup NETRANGER
    autocmd!
    autocmd BufEnter * exec s:pyx 'ranger.on_bufenter('.expand("<abuf>").')'
    autocmd CursorMoved * if &ft=='netranger' | exec s:pyx 'ranger.on_cursormoved('.expand("<abuf>").')' | fi
augroup END

func! _NETRInvokeMap(fn)
    exec s:pyx 'ranger.invoke_map("'.a:fn.'")'
endfunc

command! NETRemoteList exec s:pyx 'ranger.NETRemoteList()'
command! NETRemotePull exec s:pyx 'ranger.NETRemotePull()'


let &cpo = s:save_cpo
