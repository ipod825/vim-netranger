if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "netranger"

syn match ansiSuppress conceal contained '\e\[[0-9;]*m'
hi def link ansiSuppress Conceal

call netranger#syntax#define()
