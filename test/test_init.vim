set timeoutlen=1
let g:_NETRDebug=v:true
let g:NETRRootDir='/tmp/netrtestroot'
let g:NETRPreviewDefaultOn=v:false
let g:_NETRRcloneFlags='--config='.expand('%:p:h').'/netrtest_rclone.conf'
exec 'set runtimepath^='.expand('%:p:h').'/..'
set winwidth=1
set winheight=1
set winminwidth=1
set winminheight=1
set noswapfile
