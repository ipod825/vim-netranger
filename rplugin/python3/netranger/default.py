import os
keymap = {
    # should all be in small case for NETRDefaultMapSkip feature
    'NETROpen': ['l','<right>'],
    'NETRParentDir': ['h','<left>'],
    'NETRToggleExpand': ['<Space>', 'o'],
    'NETRVimCD': ['<cr>'],
    'NETREdit': ['i'],
    'NETRSave': ['<Esc>'],
    'NETRTogglePick': ['v','V'],
    'NETRCut': ['x','d'],
    'NETRCopy': ['y'],
    'NETRCutSingle': ['dd'],
    'NETRCopySingle': ['yy'],
    'NETRPaste': ['p'],
    'NETRDelete': ['D'],
    'NETRDeleteSingle': ['DD'],
    'NETRForceDelete': ['X'],
    'NETRForceDeleteSingle': ['XX'],
    'NETRTogglePinRoot': ['zp'],
    'NETRToggleShowHidden': ['zh'],
    'NETRBookmarkSet': ['m'],
    'NETRBookmarkGo': ["'"],
    'NETRBookmarkEdit': ["em"],
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
    '_NETRRegister': '',  # internal use only
}
