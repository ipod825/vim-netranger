import os
keymap = {
    # should all be in small case for NETRDefaultMapSkip feature
    'NETROpen': (['l','<right>'], "Change directory/open file under cursor"),
    'NETRParentDir': (['h','<left>'], "Change to parent directory"),
    'NETRToggleExpand': (['<Space>', 'o'], "Toggle expand current directory under cursor"),
    'NETRVimCD': (['<cr>'], "Changing vim's pwd to the directory of the entry under cursor"),
    'NETREdit': (['i'], "Enter edit mode to rename file/directory names"),
    'NETRSave': (['<Esc>'], "Leave edit mode to save changes made in edit mode"),
    'NETRTogglePick': (['v','V'], "Pick the current entry for further copy/cut"),
    'NETRCut': (['x','d'], "Cut all picked entries"),
    'NETRCopy': (['y'], "Copy the current entry."),
    'NETRCutSingle': (['dd'], "Cut the current entry."),
    'NETRCopySingle': (['yy'], "Copy the current entry."),
    'NETRPaste': (['p'], "Paste all cut/copied entries"),
    'NETRDelete': (['D'], "Delete all picked entries"),
    'NETRDeleteSingle': (['DD'], "Delete the current entry."),
    'NETRForceDelete': (['X'], "Force delete all picked entries"),
    'NETRForceDeleteSingle': (['XX'], "Force delete the current entry."),
    'NETRTogglePinRoot': (['zp'], "(Toggle) Pin current directory as \"root\""),
    'NETRToggleShowHidden': (['zh'], "(Toggle) Show hidden files"),
    'NETRBookmarkSet': (['m'], "Jump to bookmark, pending for single character"),
    'NETRBookmarkGo': (["'"], "Bookmark current directory, pending for single character"),
    'NETRBookmarkEdit': (["em"], "Open bookmark file to edit"),
    'NETRBookmarkHelp':(['?'], "Show help message")
}

color = {
    'cwd': 'yellow',
    'pick': 'yellow',
    'copy': 'fuchsia',
    'cut': 'grey',
    'exe': 'darkgreen',
    'dir': 'dodgerblue3',
    'link': 'cyan1',
    'file': 'white',
}


# TODO
root_dir = os.path.expanduser('~/.netranger/')
variables = {
    'NETRIgnore': [],
    'NETRDefaultMapSkip': [],
    'NETRTabAutoToFirst': False,
    'NETRHiCWD': 'yellow',
    'NETRRootDir': root_dir,
    'NETRBookmarkFile': root_dir+'bookmark',
    'NETRCacheDir': root_dir+'cache',
    '_NETRRegister': [],  # internal use only
}
