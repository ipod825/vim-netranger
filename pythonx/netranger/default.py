from __future__ import absolute_import
from netranger.config import root_dir
from netranger.config import remote_cache_dir
from netranger.config import test_remote_dir
from netranger.config import test_remote_name

keymap = {
    # non-printable characters (e.g. <cr>) should be in small case for
    # NETRDefaultMapSkip feature
    'NETROpen': (['l', '<right>'], "Change directory/open file under cursor"),
    'NETRParentDir': (['h', '<left>'], "Change to parent directory"),
    'NETRTabOpen': (['t'], 'Open file in new tab. Skip for directory'),
    'NETRTabBgOpen': (['T'],
                      'Same as NETRTabOpen but stay in the current tab.'),
    'NETRBufOpen': (['e'], 'Open file in current window.'),
    'NETRBufVSplitOpen': (['ev'], 'Open file in new vertical split buffer.'),
    'NETRBufHSplitOpen': (['eo'], 'Open file in new horizontal split buffer.'),
    'NETRBufPanelOpen':
    (['ep'], 'Open file in new vertical split buffer (panel mode).'),
    'NETRAskOpen': (['a'], 'Open file with rifle. Ask for command'),
    'NETRToggleExpand': (['za'],
                         "Toggle expand current directory under cursor"),
    'NETRVimCD':
    (['<cr>'],
     "Changing vim's pwd to the directory of the entry under cursor"),
    'NETREdit': (['i'], "Enter edit mode to rename file/directory names"),
    'NETRSave': (['<esc>'],
                 "Leave edit mode to save changes made in edit mode"),
    'NETRTogglePick': (['v'], "Pick the current entry for further copy/cut"),
    'NETRCut': (['x', 'd'], "Cut all picked entries"),
    'NETRCopy': (['y'], "Copy the current entry."),
    'NETRCutSingle': (['dd'], "Cut the current entry."),
    'NETRCopySingle': (['yy'], "Copy the current entry."),
    'NETRPaste': (['p'], "Paste all cut/copied entries"),
    'NETRDelete': (['D'], "Delete all picked entries"),
    'NETRDeleteSingle': (['DD'], "Delete the current entry."),
    'NETRForceDelete': (['X'], "Force delete all picked entries"),
    'NETRForceDeleteSingle': (['XX'], "Force delete the current entry."),
    'NETRTogglePinRoot': (['zp'],
                          "(Toggle) Pin current directory as \"root\""),
    'NETRToggleShowHidden': (['zh'], "(Toggle) Show hidden files"),
    'NETRBookmarkSet': (['m'],
                        "Jump to bookmark, pending for single character"),
    'NETRBookmarkGo':
    (["'"], "Bookmark current directory, pending for single character"),
    'NETRBookmarkEdit': (["em"], "Open bookmark file to edit"),
    'NETRSort':
    (['S'],
     'Sort contnet in current directory, pending for single (double) character'
     ),
    'NETRHelp': (['?'], "Show help message"),
    'NETRefresh': ([
        'r'
    ], "Force refresh netranger buffer to be the same as the file system"),
}

color = {
    'cwd': 'yellow',
    'footer': 'darkgreen',
    'pick': 'yellow',
    'copy': 'fuchsia',
    'cut': 'grey',
    'exe': 'darkgreen',
    'dir': 'dodgerblue3',
    'link': 'cyan1',
    'brokenlink': 'red',
    'file': 'white',
}

variables = {
    'NETRIgnore': ['.*'],
    'NETROpenCmd': 'tabedit',
    'NETRDefaultMapSkip': [],
    'NETRRootDir': root_dir,
    'NETRBookmarkFile': root_dir + 'bookmark',
    'NETRRifleFile': root_dir + 'rifle.conf',
    'NETRemoteCacheDir': remote_cache_dir,
    'NETRemoteRoots': {
        test_remote_name: test_remote_dir
    },
    'NETRSplitOrientation': 'belowright',
    'NETRPanelSize': 1.5,
    'NETRColors': {},
    'NETRMaxFileNumToEagerlyDisplay': 1000,
    'NETRMinFileNumToLoadInParallel': 100,
}

internal_variables = {
    'NETRRegister': [],
}
