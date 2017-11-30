vim-netranger
=============

__Note__ Some features describe below is still in progress.

Vim-netranger is a ranger-like system/cloud storage explorer for Vim. It brings together the best of Vim, [ranger](https://github.com/ranger/ranger), and [rclone](https://rclone.org/):

1. Against Vim (netrw):
    - Better rendering
    - Open file with extern program
    - Supports various cloud storages (via rclone)
2. Against ranger:
    - No `sudo` required
    - Native Vim key-binding rather than just mimicking Vim
3. Against rclone
    - Display/modify remote content without typing commands in terminal

## Installation
------------

Using vim-plug

```viml
if has('nvim')
  Plug 'ipod825/vim-netranger', { 'do': ':UpdateRemotePlugins' }
endif
```
__Note__: Other explorer plugins (e.g. [NERDTree](https://github.com/scrooloose/nerdtree)) might prohibit `vim-netranger`. You must disable them to make `vim-netranger` work.

## Requirements

vim-netranger requires Neovim. You should install neovim's Python3 api with pip:

```bash
    pip3 install neovim
```

`rclone` is needed if you use the remote editing feature. However, it will be installed automatically on the first time running `NETRListRemotes` command.


## Usage

### Opening a `vim-netranger` buffer
1. vim a directory
2. Inside vim, use edit commands (e.g. `vsplit`, `edit`, `tabedit`) to edit a directory. Just like `netrw`.

### Navigation
1. Press `l` to change directory/open file for the current directory/file under the cursor.
2. Press `h` to jump to the parent directory.
3. Press `<Space>` to toggle expand current directory under cursor.
4. Press `gp` to (toggle) pin current directory as the project root, which means you can't use `h` to jump to the parent directory. I think it might be useful when developing a project.
5. Type `:NETRCD dir/you/want/to/go` to navigate to where you want. Though I don't think you would want to do this very often.

### File Rename
1. Press `i` to enter edit mode. You can freely modify any file/directory name in this mode.
2. Note that in this mode, you can't delete file by deleting lines (you can't add file either).
3. After you are done, back into normal mode (i.e. press `<Esc>` or whatever mapping you prefer), then press `<Esc>` again. All file will be renamed as you've modified.

### File Selection/Copy/Cut/Paste
1. Press `v` or `V` to select a file for further processing. You can select multiple files and then do one of the following
    * Press `y` to copy all selected files
    * Press `x` or `d` to cut all selected files
2. Note that if you leave the directory before pressing `y`,`x` or `d`, your selection will be lost.
3. Then go to the target directory, press `p` to paste all cut/copied files/directories.
4. If only one file is to be copied/cut, you can simply press `yy` (copy) or `dd` (cut). The current file will be marked. You can then continue `yy`,  `dd` other lines. I personally think this is more convenient then using `v`.

### File Deletion

### Sort

### Bookmark

### Remote storage
1. Run `NETRListRemotes` command to open a `vim-netranger` buffer showing all configured remote storage.
2. If `rclone` is not in your `PATH`, on first time running `NETRListRemotes`. It will be automatically downloaded and installed.
3. Remote files are downloaded on demand and cached in `g:NETRRootDir/cache`. Other than that, it's just like browsing local files.


## Customization
### Key mappings:
Assign a list to each folloing variable to provide extra key mappings.

| Variable            | Description                                                          | Default                |
| :-----------:       | :-------------:                                                      | ----------------:      |
| g:NETROpen          | Change directory/open file                                           | ['l','<right>','<cr>'] |
| g:NETRParentDir     | Change to parent directory                                           | ['h','<left>']         |
| g:NETRToggleExpand  | Toggle expand current directory under cursor                         | ['<space>']            |
| g:NETRBookmarkSet   | Bookmark current directory, pending for single character             | ['m']                  |
| g:NETRBookmarkGo    | Jump to bookmark, pending for single character                       | ["'"]                  |
| g:NETREdit          | Enter edit mode to rename file/directory names                       | ['i']                  |
| g:NETRSave          | Leave edit mode to save changes made in edit mode                    | ['<Esc>']              |
| g:NETRTogglePick    | Pick the current entry for further copy/cut                          | ['v','V']              |
| g:NETRCut           | Cut all picked entries                                               | ['x','d']              |
| g:NETRCopy          | Copy all picked entries                                              | ['y']                  |
| g:NETRCutSingle     | Cut the current entry. Equivalent to `vd`                            | ['dd']                 |
| g:NETRCopySingle    | Copy the current entry. Equivalent to `vy`                           | ['yy']                 |
| g:NETRPaste         | Paste all cut/copied entries                                         | ['p']                  |
| g:NETRTogglePinRoot | Pin current directory as "root", such that you can't go one level up | ['gp']                 |
    

Assign a list to `g:NETRDefaultMapSkip` to ignore default mappings. For example, if you want to switch the mappings for `g:NETRBookmarkSet`, `g:NETRBookmarkGo`, you'll put the following in your `.vimrc`:
```vim
let g:NETRDefaultMapSkip = ['m',"'"]
let g:NETRBookmarkSet = ["'"]
let g:g:NETRBookmarkGo = ["m"]
```

### Variables
| Variable          | Description                                              | Default                |
| -------------     | :-------------:                                          | ----------------:      |
| g:NETRIgnore      | File patterns (bash wild card) to ignore (not displaying)| []                     |
| g:NETRRootDir     | Directory for storing remote cache and bookmark file     | ['$HOME/.netranger/']  |
