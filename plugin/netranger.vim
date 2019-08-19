if exists("g:loaded_netranger") || &cp
  finish
endif
let g:loaded_netranger = 1

let s:save_cpo = &cpo
set cpo&vim

if !has('python3')
    echo "Error: Required vim compiled with +python3"
    finish
endif

let g:loaded_netrwPlugin = 0
let g:loaded_netrw = 0

let s:pyx = 'python3 '

python3 import netranger
python3 from netranger.netranger import Netranger
python3 ranger = Netranger()
python3 from netranger.api import NETRApi
python3 NETRApi.init(ranger)

augroup NETRANGER
    autocmd!
    autocmd BufEnter * exec s:pyx 'ranger.on_bufenter('.expand("<abuf>").')'
    autocmd Filetype netranger autocmd WinEnter * exec s:pyx 'ranger.on_winenter('.expand("<abuf>").')'
    autocmd Filetype netranger autocmd CursorMoved <buffer> exec s:pyx 'ranger.on_cursormoved('.expand("<abuf>").')'

    " See https://github.com/mg979/vim-visual-multi/issues/73
    if py3eval('ranger.key2fn.get("<esc>", lambda x: x).__name__=="NETRSave"')
        autocmd Filetype netranger autocmd USER visual_multi_exit :nnoremap <nowait> <silent> <buffer> <esc> :py3 ranger.key2fn["<lt>esc>"]()<cr>
    endif
augroup END

func! _NETROnCursorMovedPost(bufnum, timerid)
    exec s:pyx 'ranger.on_cursormoved_post('.a:bufnum.')'
endfunc

command! NETRemoteList python3 ranger.NETRemoteList()
command! NETRemotePull python3 ranger.NETRemotePull()
command! NETRemotePush python3 ranger.NETRemotePush()
command! -nargs=1 -complete=file NETRTabdrop exec s:pyx 'netranger.Vim.tabdrop("'.fnamemodify("<args>", ":p").'")'

silent doautocmd USER NETRInit


let &cpo = s:save_cpo
