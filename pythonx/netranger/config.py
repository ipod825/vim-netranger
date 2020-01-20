import os
import tempfile

root_dir = os.path.expanduser('~/.netranger/')
remote_cache_dir = os.path.join(root_dir, 'remote')
config_dir = f'{os.path.dirname(__file__)}/../../config'
test_remote_name = 'netrtest'
test_remote_cache_dir = os.path.join(remote_cache_dir, test_remote_name)
test_dir = os.path.join(tempfile.gettempdir(), 'netrtest')
test_local_dir = os.path.join(test_dir, 'local')
test_remote_dir = os.path.join(test_dir, 'remote')
file_sz_display_wid = 6
rclone_rcd_port = 13579
