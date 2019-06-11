function! s:list2str(lst)
    if len(a:lst)==0
        return '[]'
    endif

    let res='[\"'.a:lst[0]
    for s in a:lst
        if s
            let res.='\",\"'.s
        endif
    endfor
    let res.='\"]'
    return res
endfunction

function! netranger#AsyncCallBack(job_id, data, event)
   if a:event == "exit"
        exec 'python3 netranger.Vim.VimAsyncCallBack("'.a:job_id.'","'.a:event.'","[]")'
    else
        exec 'python3 netranger.Vim.VimAsyncCallBack("'.a:job_id.'","'.a:event.'","'.s:list2str(a:data).'")'
   endif
endfunction
