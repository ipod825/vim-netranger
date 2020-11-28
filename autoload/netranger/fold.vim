function! netranger#fold#foldtext()
    return substitute(getline(v:foldstart), '\e\[[0-9;]*m', '', 'g')
endfunction
