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
let g:_NETRPY = 'python3 '

let s:inited = v:false
function NetrangerInit()
    if s:inited
        autocmd! NETRANGER_LAZY_INIT BufEnter *
        return
    endif
    let s:inited = v:true

    exec g:_NETRPY.'import netranger'
    exec g:_NETRPY.'from netranger.netranger import Netranger'
    exec g:_NETRPY.'ranger = Netranger()'
    exec g:_NETRPY.'from netranger.api import NETRApi'
    exec g:_NETRPY.'NETRApi.init(ranger)'

    command! NETRemotePull exec g:_NETRPY.'ranger.NETRemotePull()'
    command! NETRemotePush exec g:_NETRPY.'ranger.NETRemotePush()'
    command! -nargs=1 -complete=file NETRTabdrop exec g:_NETRPY.'ranger._tabdrop("'.<q-args>.'")'
    command! -nargs=1 -complete=file NETRNewTabdrop exec g:_NETRPY.'ranger._newtabdrop("'.<q-args>.'")'

    augroup NETRANGER
        autocmd!
        autocmd BufEnter * exec g:_NETRPY.'ranger.on_bufenter('.expand("<abuf>").')'
        autocmd Filetype netranger autocmd WinEnter <buffer> exec g:_NETRPY.'ranger.on_winenter('.expand("<abuf>").')'
        autocmd Filetype netranger autocmd CursorMoved <buffer> exec g:_NETRPY.'ranger.on_cursormoved('.expand("<abuf>").')'
        autocmd Filetype netranger autocmd BufWriteCmd <buffer> exec g:_NETRPY.'ranger.NETRSave()'
        autocmd ColorScheme * call netranger#syntax#define()
    augroup END
    silent doautocmd USER NETRInit
endfunction

augroup NETRANGER_LAZY_INIT
    autocmd!
    autocmd BufEnter * if isdirectory(bufname('%')) |
                \call NetrangerInit() |
                \exec g:_NETRPY.'ranger.on_bufenter('.expand("<abuf>").')' |
                \endif
augroup END

command! NETRemoteList call NetrangerInit() | exec g:_NETRPY.'ranger.NETRemoteList()'



let &cpo = s:save_cpo
