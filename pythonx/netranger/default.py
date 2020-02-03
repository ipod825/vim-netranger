from __future__ import absolute_import

from netranger.config import (remote_cache_dir, root_dir, test_remote_dir,
                              test_remote_name)

keymap = {
    # non-printable characters (e.g. <cr>) should be in small case for
    # NETRDefaultMapSkip feature
    'NETROpen': (['l', '<right>'], "Change directory/open file under cursor"),
    'NETRParentDir': (['h', '<left>'], "Change to parent directory"),
    'NETRGoPrevSibling':
    (['{'], "Move the cursor to the previous node with less or equal indent."),
    'NETRGoNextSibling':
    (['}'], "Move the cursor to the next node with less or equal indent."),
    'NETRTabOpen': (['t'], 'Open file in new tab. Skip for directory'),
    'NETRTabBgOpen': (['T'],
                      'Same as NETRTabOpen but stay in the current tab.'),
    'NETRBufOpen': (['e'], 'Open file in current window.'),
    'NETRBufVSplitOpen': (['ev'], 'Open file in new vertical split buffer.'),
    'NETRBufHSplitOpen': (['es'], 'Open file in new horizontal split buffer.'),
    'NETRBufPanelOpen':
    (['ep'], 'Open file in new vertical split buffer (panel mode).'),
    'NETRAskOpen': (['a'], 'Open file with rifle. Ask for command'),
    'NETRToggleExpand': (['za'],
                         "Toggle expand current directory under cursor"),
    'NETRToggleExpandRec':
    (['zA'], "Recursively toggle expand current directory under cursor"),
    'NETRVimCD':
    (['<cr>'],
     "Changing vim's pwd to the directory of the entry under cursor"),
    'NETRNew': (['o'], 'Create new directory/file, pending for ui selection'),
    'NETREdit':
    (['i'],
     "Enter edit mode to rename file/directory names. Use ':w' to save changes."
     ),
    'NETRTogglePick': (['v'], "Pick the current entry for further copy/cut"),
    'NETRCut': (['x', 'd'], "Cut all picked entries"),
    'NETRCopy': (['y'], "Copy all picked entries."),
    'NETRCutSingle': (['dd'], "Cut the current entry."),
    'NETRCopySingle': (['yy'], "Copy the current entry."),
    'NETRPaste': (['p'], "Paste all cut/copied entries"),
    'NETRCancelPickCutCopy': (['u'], "Cancel all selection/cut/copy"),
    'NETRDelete': (['D'], "Delete all picked entries"),
    'NETRDeleteSingle': (['DD'], "Delete the current entry."),
    'NETRForceDelete': (['X'], "Force delete all picked entries"),
    'NETRForceDeleteSingle': (['XX'], "Force delete the current entry."),
    'NETRToggleShowHidden': (['zh'], "(Toggle) Show hidden files"),
    'NETRToggleSudo': (['zs'],
                       "Toggle sudo privilege for paste/rm operations."),
    'NETRBookmarkSet':
    (['m'], "Bookmark current directory, pending for ui selection"),
    'NETRBookmarkGo': (["'"], "Jump to bookmark, pending for ui selection"),
    'NETRBookmarkEdit': (["em"], "Open bookmark file to edit"),
    'NETRSort':
    (['S'], 'Sort contnet in current directory, pending for ui selection.'),
    'NETRHelp': (['?'], "Show help message"),
    'NETRefresh':
    (['r'],
     "Force refresh netranger buffer to be the same as the file system"),
    'NETRTogglePreview': (["P"], "Toggle open preview window."),
}

visual_keymap = {
    'NETRTogglePickVisual':
    (['v'], "Pick the visually selected entries for further copy/cut")
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
    'NETROpenCmd': 'NETRTabdrop',
    'NETRAutochdir': True,
    'NETRDefaultMapSkip': [],
    'NETRDefaultVisualMapSkip': [],
    'NETRRootDir': root_dir,
    'NETRBookmarkFile': root_dir + 'bookmark',
    'NETRRifleFile': root_dir + 'rifle.conf',
    'NETRemoteCacheDir': remote_cache_dir,
    'NETRemoteRoots': {
        test_remote_name: test_remote_dir
    },
    'NETRSplitOrientation': 'belowright',
    'NETRPanelSize': 1.5,
    'NETRPreviewSize': 1.2,
    'NETRParentPreviewSize': 0.3,
    'NETRColors': {},
    'NETRRedrawDelay': 200,
    'NETRLazyLoadStat': False,
    'NETRPreviewDefaultOn': True,
}

internal_variables = {
    'NETRRegister': [],
}
