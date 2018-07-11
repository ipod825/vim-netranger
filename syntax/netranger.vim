if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "netranger"

syn match ansiSuppress conceal contained '\e\[[0-9;]*m'
hi def link ansiSuppress Conceal

let c = 0
while c < 256
  exec 'syntax match NETRhi'.c.' "\e\[38;5;'.c.'m[^\e]*\e\[0m"  contains=ansiSuppress'
  exec 'syntax match NETRhi'.c.'r "\e\[38;5;'.c.';7m[^\e]*\e\[0m"  contains=ansiSuppress'
  exec 'hi NETRhi'.c.' ctermfg='.c.' ctermbg=None'
  exec 'hi NETRhi'.c.'r ctermbg='.c.' ctermfg=black'
  let c += 1
endwhile

hi NETRhiProgressBar ctermfg=None ctermbg=Blue
