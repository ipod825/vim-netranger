vim-netranger
=============
![Screenshot](https://user-images.githubusercontent.com/1246394/34659373-009ab882-f3ed-11e7-8d69-8df7db6dcb44.png)

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
    - has('python3') or has('python')
2. `neovim`
    - no specific requirement as neovim is shiped with python by default

`rclone`: v1.4.0(v1.3.9) or newer (1.4.0 not yet published, see [Known Issues](#known-issues)). `rclone` is needed if you use remote editing features. However, it will be installed automatically on the first time running `NETRemoteList` command.

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

It is highly recommend you avoid these errors when writing them using. I recommend installing `flake8` and adopt the (vim) settings in this [gist](https://gist.github.com/ipod825/fbee70d8bd063f228951cd4b6f38f4df). Note that `flask8` is required:
~~~{.bash}
$ pip install flask8
~~~

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

### Navigation
1. Press `l` to change directory/open file for the current directory/file under the cursor.
2. Press `h` to jump to the parent directory.
3. Press `<Space>` to toggle expand current directory under cursor.
4. Press `<Cr>` to set vim's cwd to the directory of the file under cursor. This is very useful if you've expanded a directory and want to open an nvim terminal to run a script in the subdirectory. 

### File Rename
1. Press `i` to enter edit mode. You can freely modify any file/directory name in this mode.
2. Note that in this mode, you can't delete file by deleting lines (you can't add file either).
3. After you are done, back into normal mode (i.e. press `<Esc>` or whatever mapping you prefer), then press `<Esc>` again. All files will be renamed as you've modified.

### File Selection/Copy/Cut/Paste/Deletion
1. Press `v` or `V` to select a file for further processing. You can select multiple files and then do one of the following
    * Press `y` to copy all selected files
    * Press `x` or `d` to cut all selected files
    * Press `D` to delete (`rm -r`) all selected files
    * Press `X` to force delete (i.e. `rm -rf`) all selected files
2. For `y`, `x`, `d`, go to the target directory, press `p` to paste all cut/copied files/directories.
3. Note that you can open multiple vim buffer for different directories and cut (copy) files in one buffer and paste files in another buffer. When you jump back to the source buffer, cut files will disappear as expected.
4. If only one file is to be cut/copy, you can simply press `yy` (copy) or `dd` (cut). The current file will be marked. You can then continue `yy`,  `dd` other lines.
5. Similarly, if only one file is to be (force) deleted, you can simply press `DD` or `XX`.

### Bookmark
1. Press `m` to open the bookmark UI. You'll see the current bookmarks you have. Press [azAZ] (any letters) to bookmark the current directory.
2. Press `'` to open the bookmark UI again. You'll see that previous entered character appears there. Press the correct character to navigate to the directory you want to go.
3. Press `em` to edit the bookmark with vim. On saving (e.g. `:x`)the file, your bookmarks will be updated automatically.
4. Note that you can use `:q` to quit the bookmark ui to abort the aforementioned operation. 

### Rifle
1. Rifle is a config file ranger used to open files with external program. vim-netranger mimics its syntax and behavior.
2. If you don't have a `rifle.config` file in `g:NETRRootDir` (default to `$HOME/.netranger/`), vim-netranger will copy a default one to that directory. You can simply modify the default `rifle.config` to serve your need.


### Sort
1. Press `S` to sort.

### Misc
1. Press `zp` to (toggle) pin current directory as the project root, which means you can't use `h` to jump to the parent directory. I think it might be useful when developing a project.
2. Press `zh` to (toggle) show hidden files.

### Remote storage
1. Run `NETRemoteList` command to open a `vim-netranger` buffer showing all configured remote storage.
2. If `rclone` is not in your `PATH`, on first time running `NETRemoteList`. It will be automatically downloaded and installed.
3. Remote files are downloaded on demand and cached in `g:NETRRootDir/remote`. Other than that, it's just like browsing local files.
4. Run `NETRemotePull` to sync the current directory to be the same as the remote directory. Use this command when remote directory is modified elsewhere.
5. Netranger does not provide `NETRemotePush` command. When any file in a remote directory is modified. You must reenter that directory to sync remote content to be the same as the local content.

__Note__ Remote functions hasn't been fully tested. You might lose your data in current implementation. Use it with caution.

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
| Variable             | Description                                               | Default               |
| :------------        | :--------------                                           | :----------------     |
| g:NETRIgnore         | File patterns (bash wild card) to ignore (not displaying) | []                    |
| g:NETRRootDir        | Directory for storing remote cache and bookmark file      | ['$HOME/.netranger/'] |
| g:NETROpenCmd        | Vim command to open files from netranger buffer           | 'tab drop'            |

## Known Issues
1. In neovim, when opening two vim buffers for the same directory, there is a delay for moving cursor up and down. This seems to be an nvim api [issue](https://github.com/neovim/neovim/issues/7756)
2. When remote directory is empty, it will not be copied to remote. It is an rclone [bug] (https://github.com/ncw/rclone/issues/1837), which is expected to be fixed in next release.
