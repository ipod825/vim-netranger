if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "netranger"

syn match ansiSuppress conceal contained '\e\[[0-9;]*m'
hi def link ansiSuppress Conceal


if has('gui') || (has('termguicolors') && &termguicolors)
    for c in g:_NETRSavedGuiColors
      exec 'syntax match NETR'.c[0].' "\e\[38;2;'.c[2].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'syntax match NETR'.c[0].'Sel "\e\[48;2;'.c[2].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'hi NETR'.c[0].' guifg='.c[1]
      exec 'hi NETR'.c[0].'Sel guibg='.c[1].' guifg=black'
    endfor
else
    for c in g:_NETRSavedColors
      exec 'syntax match NETR'.c[0].' "\e\[38;5;'.c[2].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'syntax match NETR'.c[0].'Sel "\e\[48;5;'.c[2].'m[^\e]*\e\[0m"  contains=ansiSuppress'
      exec 'hi NETR'.c[0].' ctermfg='.c[2].' guifg='.c[1]
      exec 'hi NETR'.c[0].'Sel ctermbg='.c[2].' ctermfg=black guibg='.c[1].' guifg=black'
    endfor
endif
