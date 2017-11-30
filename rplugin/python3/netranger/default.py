import os
keymap = {
    # should all be in small case for NETRDefaultMapSkip feature
    'NETROpen': ['l','<right>','<cr>'],
    'NETRParentDir': ['h','<left>'],
    'NETRToggleExpand': ['<Space>', 'o'],
    'NETREdit': ['i'],
    'NETRSave': ['<Esc>'],
    'NETRTogglePick': ['v','V'],
    'NETRCut': ['x','d'],
    'NETRCopy': ['y'],
    'NETRDelete': ['D'],
    'NETRForceDelete': ['fD'],
    'NETRCutSingle': ['dd'],
    'NETRCopySingle': ["yy"],
    'NETRDeleteSingle': ['DD'],
    'NETRPaste': ['p'],
    'NETRTogglePinRoot': ["gp"],
    'NETRBookmarkSet': ['m'],
    'NETRBookmarkGo': ["'"],
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
    'NETRHiCWD': 'yellow',
    'NETRRootDir': root_dir,
    'NETRBookmark': root_dir+'bookmark',
    'NETRCacheDir': root_dir+'cache',
}
