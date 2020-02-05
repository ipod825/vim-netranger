set timeoutlen=1
let g:_NETRDebug=v:true
let g:NETRRootDir='/tmp/netrtestroot'
let g:NETRPreviewDefaultOn=v:false
let g:_NETRRcloneFlags='--config='.expand('%:p:h').'/netrtest_rclone.conf'
exec 'set runtimepath^='.expand('%:p:h').'/..'
