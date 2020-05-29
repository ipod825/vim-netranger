function! netranger#ui#bookmarkgo(path)
   let l:can_go = v:true
   if !isdirectory(a:path) && !filereadable(a:path)
       echoerr "Can not open: ".a:path
       let l:can_go = v:false
   endif
   bwipeout
   if l:can_go
       exec 'edit '.a:path
       exec g:_NETRPY.'with ranger.KeepPreviewState(): pass'
   endif
endfunction
