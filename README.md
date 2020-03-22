vim-netranger
=============
[![Build Status](https://travis-ci.org/ipod825/vim-netranger.svg?branch=master)](https://travis-ci.org/ipod825/vim-netranger)
![Screenshot](https://user-images.githubusercontent.com/1246394/43560750-3c559f28-95d1-11e8-85e4-a05d6f44e97e.png)


**New: preview window is on now by default. To turn it off, set `g:NETRPreviewDefaultOn=v:false`.**

Vim-netranger is a ranger-like system/cloud storage explorer for Vim/Neovim. It brings together the best of Vim, [ranger](https://github.com/ranger/ranger), and [rclone](https://rclone.org/):

1. Against Vim (netrw):
    - Fancy rendering
    - Supports various cloud storages (via rclone)
2. Against ranger:
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

1. `vim` & `neovim`
    - `echo has('python3')` should output 1
    - `echo has('virtualedit')` should output 1

2. `rclone`: v1.4.0(v1.3.9) or newer (1.4.0 not yet published, see [Known Issues](#known-issues)). `rclone` is needed if you use remote editing features. However, it will be installed automatically on the first time running `NETRemoteList` command.

### Workflow preferences
1. If you are more used to tabpages, and want to always keep a netranger buffer for the project folder. Have `let g:NETROpenCmd = 'NETRTabdrop'` in your vimrc.
2. If you are more used to tabpages, but want to close the netranger when openning a file. Have `let g:NETROpenCmd = 'NETRNewTabdrop'` in your vimrc.
3. If you are not used to tabpages, `let g:NETROpenCmd = 'NETRNewTabdrop'` is still a good option for you. Otherwise, customize it to your favorite command.

## Usage

```vim
:help vim-netranger-usage
```

### Remote storage
```vim
:help vim-netranger-rclone
```


## Customization
```vim
:help vim-netranger-customization-mapping
:help vim-netranger-customization-option
```

### Advanced Key mappings:
```vim
:help vim-netranger-functions
```

### Colors
```vim
:help vim-netranger-colors
```


### Python Api
```vim
:help vim-netranger-api
```

## Known Issues
1. When remote directory is empty, it will not be copied to remote. It is an rclone [bug] (https://github.com/ncw/rclone/issues/1837), which is expected to be fixed in next release.
2. In some cases when `listchars` is set, `vim-netranger` buffer does not display correctly. For possible solutions, see the comment in this [issue](https://github.com/ipod825/vim-netranger/issues/14).



## Contributing
Pull request is welcomed. However, please run tests before sending pull request.

### Testing
~~~{.bash}
$ cd test
$ bash test.sh  # test with visualization, xterm required
$ python test.py # test without visualization
~~~
