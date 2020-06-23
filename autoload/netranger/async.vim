function! netranger#async#callback(job_id, data, event)
   if a:event == "exit"
        exec g:_NETRPY.'netranger.Vim.VimAsyncCallBack("'.a:job_id.'","'.a:event.'","[]")'
    else
        if has("nvim")
            let data = escape(join(a:data,'\n'),'"')
        else
            let data = escape(a:data, '"')
        endif
        let data = substitute(data, '', '\\n', 'g')
        exec g:_NETRPY.'netranger.Vim.VimAsyncCallBack("'.a:job_id.'","'.a:event.'","'.data.'")'
   endif
endfunction

function! netranger#async#term_callback(job_id, data, event, cmd_win_id)
   call assert_true(a:event == "exit", "Only handle exit")
   call win_gotoid(a:cmd_win_id)
   if a:data==0
       wincmd c
   endif
   exec g:_NETRPY.'netranger.Vim.VimAsyncCallBack("'.a:job_id.'","'.a:event.'","[]")'
endfunction
