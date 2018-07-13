vim-netranger
=============
[![Build Status](https://travis-ci.org/ipod825/vim-netranger.svg?branch=master)](https://travis-ci.org/ipod825/vim-netranger)
![Screenshot](https://user-images.githubusercontent.com/1246394/36007869-45dff1bc-0cf9-11e8-9cd5-f0d0e789135a.png)

Vim-netranger is a ranger-like system/cloud storage explorer for Vim/Neovim. It brings together the best of Vim, [ranger](https://github.com/ranger/ranger), and [rclone](https://rclone.org/):

1. Against Vim (netrw):
    - Better rendering
    - Open files with extern programs (see [Rifle](#rifle))
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
Plug 'ipod825/vim-netranger'
```
__Note__: Other explorer plugins (e.g. [NERDTree](https://github.com/scrooloose/nerdtree)) might prohibit `vim-netranger`. You must disable them to make `vim-netranger` work.

## Requirements

1. `vim`
    - has('python3')
2. `neovim`
    - no specific requirement as neovim is shipped with python3 by default

`rclone`: v1.4.0(v1.3.9) or newer (1.4.0 not yet published, see [Known Issues](#known-issues)). `rclone` is needed if you use remote editing features. However, it will be installed automatically on the first time running `NETRemoteList` command.

## Usage

### Opening a `vim-netranger` buffer
1. vim a directory
2. Inside vim, use edit commands (e.g. `vsplit`, `edit`, `tabedit`) to edit a directory. Just like `netrw`.
3. Note that you can open multiple vim buffer for the same directory. When the directory content is changed, all window's content will be modified. You can even copy file in one window and paste in another widow.

### Help
1. Press `?` to see current key bindings

### Automatic Update
1. vim-netranger does not provide any function or key-binding for creating directories, touching new files, etc. The reason is because it's cheap to open a terminal to get this jobs done. However, when the directory content is changed elsewhere, the vim-netranger buffer will be updated when you reenter it.
2. This applies in general, You can always manipulate directory content manually and expect the vim-nertanger buffer be updated when you reenter it. For example, you could run `:tabe newfile` in a vim-netranger buffer. After writing file with `:w` and switching back to the vim-netranger buffer, you'll see `newfile` there.
3. It is possible that the mechanism to detect file changes might fail on some remotefs. Hence, the user can still press `r` to force syncing the vim-netranger buffer content to be the same as the file system.

### Navigation
1. Press `l` to change directory/open file for the current directory/file under the cursor. A file is opened by rifle if available (see [Rifle](#rifle)). Otherwise, the default behaviour is to open the file in vim by `g:NETROpenCmd`.
2. Press `h` to jump to the parent directory.
3. Press `e` to open current file/directory in the current window.
4. Press `ev` to open current file/directory in a vertical split buffer.
5. Press `eo` to open current file/directory in a horizontal split buffer.
6. Press `ep` to open current file/directory in a vertical split buffer in [panel mode](#panel-mode) (in resemblance to NERDTreeToggle command).
7. Press `t` to open current file/directory in a new tab.
8. Press `T` to open current file/directory in a new tab while staying in the current window.
9. Press `a` to select a program to open the current file via rifle (see [Rifle](#rifle))
10. Press `za` to toggle expand current directory under cursor (`za` in vim is used to fold/unfold code).
11. Press `<Cr>` to set vim's cwd to the directory of the file under cursor (also applies to the first line, i.e. the current directory). This is very useful if you've expanded a directory and want to open an nvim terminal to run a script in the subdirectory.

### File Rename
1. Press `i` to enter edit mode. You can freely modify any file/directory name in this mode. Note that after pressing `i`, you are in normal mode, you need to press `i` again to enter insert mode.
2. Note that in this mode, you can't delete file by deleting lines (you can't add file either).
3. After you are done, back into normal mode (i.e. press `<Esc>` or whatever mapping you prefer), then press `<Esc>` again. All files will be renamed as you've modified.

### File Selection/Copy/Cut/Paste/Deletion
1. Press `v` or `V` to select a file for further processing. You can select multiple files and then do one of the following
    * Press `y` to copy all selected files
    * Press `x` or `d` to cut all selected files
    * Press `D` to delete (`rm -r`) all selected files
    * Press `X` to force delete (i.e. `rm -rf`) all selected files
2. For `y`, `x`, `d`, go to the target directory, press `p` to paste all cut/copied files/directories.
3. Note that the directory you paste is vim's pwd (`getcwd()`). Hence, you can press `<Cr>` to change directory to an expanded directory and paste without changing directory into it.
4. Note that you can open multiple vim buffer for different directories and cut (copy) files in one buffer and paste files in another buffer. When you jump back to the source buffer, cut files will disappear as expected.
5. If only one file is to be cut/copy, you can simply press `yy` (copy) or `dd` (cut). The current file will be marked. You can then continue `yy`,  `dd` other lines.
6. Similarly, if only one file is to be (force) deleted, you can simply press `DD` or `XX`.

### Bookmark
1. Press `m` to open the bookmark UI. You'll see the current bookmarks you have. Press [azAZ] (any letters) to bookmark the current directory.
2. Press `'` to open the bookmark UI again. You'll see that previous entered character appears there. Press the correct character to navigate to the directory you want to go.
3. Press `em` to edit the bookmark with vim. On saving (e.g. `:x`)the file, your bookmarks will be updated automatically.
4. Note that you can use `:q` to quit the bookmark ui to abort the aforementioned operation.

### Rifle
1. Rifle is a config file ranger used to open files with external program. vim-netranger mimics its syntax and behavior.
2. If you don't have a `rifle.config` file in `g:NETRRootDir` (default to `$HOME/.netranger/`), vim-netranger will copy a default one to that directory. You can simply modify the default `rifle.config` to serve your need.
3. The first match (if any) in `rifle.config` is adopted.
4. If multiple match are found, you can press `a` to select which program you want to use.


### Sort
1. Press `S` to sort.


### Panel Mode
NERDTree enables users to have a single panel on the left side that always open files on the right side when pressing enter. vim-netranger provides a similar functionality. In a vim-netranger buffer, press `ep` to open the file under cursor on the right. The size of the right panel can be customized by the `g:NETRPanelSize`, which is the ratio between the actual size of the right panel to half of the screen width (e.g. setting it to `1` you'll get a equal split.)

### Misc
1. Press `zp` to (toggle) pin current directory as the project root, which means you can't use `h` to jump to the parent directory. I think it might be useful when developing a project.
2. Press `zh` to (toggle) show hidden files.

### Remote storage
__Note__ Due to a bug (see known issue), remote operations haven't been fully tested. You might encounter weird behavior of cp/mv. So please use it with caution.
1. Run `NETRemoteList` command to open a `vim-netranger` buffer showing all configured remote storage.
2. If `rclone` is not in your `PATH`, on first time running `NETRemoteList`. It will be automatically downloaded and installed.
3. You can navigate to any remote directory just as local directories. Files are downloaded on demand to save bandwidth.
4. Every time you enter a remote directory, vim-netranger does two things at the background. If a file/directory exists at remote, but not at local, vim-netranger put a placeholder (by touch/mkdir) at local side. On the other hand, if a file/directory exists at local but not at remote, vim-netranger upload the file/directory automatically.
5. For the case that both remote and local contains the same file, vim-netranger does not do anything automatically. Instead, you need to run `:NETRemotePush` or `:NETRemotePull` to overwrite either the remote or local manually.
6. Both `:NETRemotePush` and `:NETRemotePull` sync the current directory between remote and local, while the push command overwrites the remote with the local contents and the pull command does the other way around.


## Customization
### Key mappings:
1. In any `vim-netranger`, pressing `?` shows a list of mapping. You can change these default mapping by assigning a list to each variable in your `vimrc`.
2. Assign a list to `g:NETRDefaultMapSkip` to ignore default mappings. For example, if you want to switch the mappings for `g:NETRBookmarkSet`, `g:NETRBookmarkGo`, you'll put the following in your `.vimrc`:
```vim
let g:NETRDefaultMapSkip = ['m',"'"]
let g:NETRBookmarkSet = ["'"]
let g:NETRBookmarkGo = ["m"]
```

### Variables
| Variable      | Description                                               | Default               |
| :------------ | :--------------                                           | :----------------     |
| g:NETRIgnore  | File patterns (bash wild card) to ignore (not displaying) | []                    |
| g:NETRRootDir | Directory for storing remote cache and bookmark file      | ['$HOME/.netranger/'] |
| g:NETROpenCmd | Vim command to open files from netranger buffer           | 'tab drop'            |
| g:NETRSplitOrientation | Split orientation when a split buffer is created | 'belowright'          |
| g:NETRColors  | Colors for nodes in vim-netranger buffer. See below.      | {}                    |
| g:NETRPanelSize| Controls the size of split in [panel mode](#panel-mode). | 1.5                   |

### Colors
1. Set `g:NETRColors` to a dictionary to overwrite the default colors. Possible keys are:
```
'cwd': the first line
'pick': node color after pressing `v`
'copy': node color after pressing `yy`
'cut': node color after pressing `dd`
'exe': executable file node color
'dir': directory node color
'link': link node color
'brokenlink': link node color
'file': file node color
```
2. Values can be either string or integer between 0~255. Please refer to [this page](https://jonasjacek.github.io/colors/). For example, in your `.vimrc`:
```
let g:NETRColors = {'pick': 'maroon', 'cut': 95}
```
3. Or you could add the following to your shell rc and run `palette` to see directly how the colors look in your terminal:
```sh
alias palette='for i in {0..255}; do echo -e "\e[38;05;${i}m${i}"; done | column -c 180 -s "  "; echo -e "\e[m"'
```


### Writing plugin for vim-netranger
vim-netranger will expose some api so that users can write (python) code to customize the appearance of vim-netranger. An example plugin is [netranger-diricon](https://github.com/ipod825/netranger-diricon), which shows a small icon indicating whether a directory is expanded or not. Generally, in your `plugin/YOURPLUGIN.vim` file, you'll have the following boilplate code:
```vim
let s:pyx = 'python3 '
exec s:pyx 'from netranger.api import RegisterHooker'
exec s:pyx 'from netranger.api import NETRApi'
exec s:pyx 'from netrangerPlugin.netrangerPlugin import NETRPlugin'
exec s:pyx 'netrPlugin = NETRPlugin(NETRApi)'
exec s:pyx 'RegisterHooker(netrPlugin.node_highlight_content_l)'
```
In your `pythonx/netrangerPlugin/netrangerPlugin.py` (you should change netrangerPlugin to a different name), you should implemnt a `NETRPlugin` class (again, change it to proper name), whose constructor has the following signature: 
```py
def __init__(self, api):
    pass
```
The api argument passed to you give you access to netranger internal. See `api.py` in vim-netranger repo for newest api.  Your can then register some hookers to control the behavior of vim-netrange. Hookers function name must be a valid vim-netranger hooker name.


## Known Issues
1. In neovim, when opening two vim buffers for the same directory, there is a delay for moving cursor up and down. This seems to be an nvim api [issue](https://github.com/neovim/neovim/issues/7756)
2. When remote directory is empty, it will not be copied to remote. It is an rclone [bug] (https://github.com/ncw/rclone/issues/1837), which is expected to be fixed in next release.




## Contributing
Pull request is welcomed. However, please run tests and coding style check before sending pull request.

Additional requirement: `pytest-flake8`

~~~{.bash}
$ pip3 install pytest-flake8
~~~

### Testing
~~~{.bash}
$ cd test
$ bash test.sh
~~~

### Coding Style
~~~{.bash}
$ cd test
$ py.test --flake8 .
~~~
If you fail on syntax check, you could use `autopep8` to fix it:
~~~{.bash}
$ pip install autopep8
$ autopep8 --recursive -i --select E128 test/netranger # fix all error no.128
~~~

It is highly recommend you avoid these errors when writing them using. I recommend installing `flake8` and adopt the (vim) settings in this [gist](https://gist.github.com/ipod825/fbee70d8bd063f228951cd4b6f38f4df). Note that `flake8` is required:
~~~{.bash}
$ pip install flake8
~~~
