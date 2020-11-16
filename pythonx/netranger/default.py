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
    (['<cr>'], 'Open file in new vertical split buffer (panel mode).'),
    'NETRAskOpen': (['a'], 'Open file with rifle. Ask for command'),
    'NETRToggleExpand': (['za'],
                         "Toggle expand current directory under cursor"),
    'NETRToggleExpandRec':
    (['zA'], "Recursively toggle expand current directory under cursor"),
    'NETRVimCD':
    (['L'], "Changing vim's pwd to the directory of the entry under cursor"),
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
    'NETRSort':
    (['S'], 'Sort contnet in current directory, pending for ui selection.'),
    'NETRHelp': (['<F1>'], "Show help message"),
    'NETRedraw':
    (['r'],
     "Force refresh netranger buffer to be the same as the file system"),
    'NETRTogglePreview': (["P"], "Toggle open preview window."),
    'NETRSearch': (['/'], 'Filter/Search content as you type'),
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

gui_color = {
    'cwd': '#ffff00',
    'footer': '#005f00',
    'pick': '#ffff00',
    'copy': '#ff00ff',
    'cut': '#808080',
    'exe': '#005f00',
    'dir': '#005fd7',
    'link': '#00ffff',
    'brokenlink': '#ff0000',
    'file': '#ffffff',
}

variables = {
    'NETRIgnore': ['.*'],
    'NETROpenCmd': 'NETRNewTabdrop',
    'NETRAutochdir': True,
    'NETRDefaultMapSkip': [],
    'NETRDefaultVisualMapSkip': [],
    'NETRRootDir': root_dir,
    'NETRRifleFile': root_dir + 'rifle.conf',
    'NETRRifleDisplayError': True,
    'NETRemoteCacheDir': remote_cache_dir,
    'NETRemoteRoots': {
        test_remote_name: test_remote_dir
    },
    'NETRSplitOrientation': 'belowright',
    'NETRPreviewSize': 1.3,
    'NETRParentPreviewSize': 0.3,
    'NETRColors': {},
    'NETRGuiColors': {},
    'NETRPreviewDelay': 200,
    'NETRLazyLoadStat': False,
    'NETRPreviewDefaultOn': True,
    'NETRcloneRcdPort': 13579,
}

internal_variables = {
    'NETRRegister': [],
    'NETRPromptDelay': 20,
}
