import os
import tempfile
root_dir = os.path.expanduser('~/.netranger/')
config_dir = '{}/../../config'.format(os.path.dirname(__file__))
test_remote_name = 'netrtest'
test_dir = os.path.join(tempfile.gettempdir(), 'netrtest')
test_local_dir = os.path.join(test_dir, 'local')
test_remote_dir = os.path.join(test_dir, 'remote')
file_sz_display_wid = 6
