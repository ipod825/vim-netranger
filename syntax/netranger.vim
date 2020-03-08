if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "netranger"

syn match ansiSuppress conceal contained '\e\[[0-9;]*m'
hi def link ansiSuppress Conceal


if has('gui') || (has('termguicolors') && &termguicolors)
    for c in items(g:_NETRSavedGuiColors)
      exec 'syntax match NETRhi'.c[0].' "\e\[38;2;'.c[1].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'syntax match NETRhi'.c[0].'r "\e\[48;2;'.c[1].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'hi NETRhi'.c[0].' guifg=#'.c[0]
      exec 'hi NETRhi'.c[0].'r guibg=#'.c[0].' guifg=black'
    endfor
else
    for c in items(g:_NETRSavedColors)
      exec 'syntax match NETRhi'.c[0].' "\e\[38;5;'.c[0].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'syntax match NETRhi'.c[0].'r "\e\[48;5;'.c[0].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'hi NETRhi'.c[0].' ctermfg='.c[0].' guifg='.c[1]
      exec 'hi NETRhi'.c[0].'r ctermbg='.c[0].' ctermfg=black guibg='.c[1].' guifg=black'
    endfor
endif
