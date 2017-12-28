import os
import tempfile
root_dir = os.path.expanduser('~/.netranger/')
test_remote_name = 'netrtest'
test_dir = os.path.join(tempfile.gettempdir(), 'netrtest')
test_local_dir = os.path.join(test_dir, 'local')
test_remote_dir = os.path.join(test_dir, 'remote')
