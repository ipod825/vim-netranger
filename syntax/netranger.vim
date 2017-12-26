if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "netranger"

syn match ansiSuppress conceal contained '\e\[[0-9;]*m'
hi def link ansiSuppress Conceal

let c = 0
while c < 256
  exec 'syntax region NETRhi'.c.' start="\e\[38;5;'.c.'m"hs=e+1 end="$"he=s-1 contains=ansiSuppress'
  exec 'syntax region NETRhi'.c.'r start="\e\[38;5;'.c.';7m"hs=e+1 end="$"he=s-1 contains=ansiSuppress'
  exec 'hi NETRhi'.c.' ctermfg='.c.' ctermbg=None'
  exec 'hi NETRhi'.c.'r ctermbg='.c.' ctermfg=black'
  let c += 1
endwhile
