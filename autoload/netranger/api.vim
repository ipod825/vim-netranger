function! netranger#api#cur_node_name()
    " return the basename of the current node
    return py3eval('NETRApi.cur_node_name()')
endfunction

function! netranger#api#cur_node_path()
    " return the full path of the current node
    return py3eval('NETRApi.cur_node_path()')
endfunction

function! netranger#api#render()
    " redraw the highlight of all nodes
    return py3eval('NETRApi.render()')
endfunction

function! netranger#api#cp(src, dst)
    " src: full path of the source file/directory
    " dst: full path of the target directory
    return py3eval('NETRApi.cp("'.a:src.'","'.a:dst.'")')
endfunction

function! netranger#api#mv(src, dst)
    " src: full path of the source file/directory
    " dst: full path of the target directory
    return py3eval('NETRApi.mv("'.a:src.'","'.a:dst.'")')
endfunction

function! netranger#api#rm(src)
    " src: full path of the file/directory to be removed
    return py3eval('NETRApi.rm("'.a:src.'")')
endfunction

function! netranger#api#cpas(src, dst)
    " src: full path of the source file/directory
    " dst: full path of the target name, behaves differently from cp only when dst is in $HOME/.netranger/remote (i.e. a remote target)
    return py3eval('NETRApi.cpas("'.a:src.'","'.a:dst.'")')
endfunction

function! netranger#api#mvas(src, dst)
    " src: full path of the source file/directory
    " dst: full path of the target name, behaves differently from cp only when dst is in $HOME/.netranger/remote (i.e. a remote target)
    return py3eval('NETRApi.mvas("'.a:src.'","'.a:dst.'")')
endfunction
