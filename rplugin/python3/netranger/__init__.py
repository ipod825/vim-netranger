import neovim
from netranger.netranger import Netranger


@neovim.plugin
class Main(object):
    def __init__(self, vim):
        self.vim = vim
        self.ranger = Netranger(vim)

    @neovim.autocmd('BufEnter', pattern='*', eval='expand("<abuf>")', sync=True)
    def on_bufenter(self, bufnum):
        self.ranger.on_bufenter(int(bufnum))

    @neovim.autocmd('CursorMoved', pattern='*', eval='expand("<abuf>")', sync=True)
    def on_cursormoved(self, bufnum):
        self.ranger.on_cursormoved(int(bufnum))

    @neovim.function('_NETRInvokeMap', sync=True)
    def NETRInvokeMap(self, args):
        self.ranger.invoke_map(args[0])

    @neovim.command("NETRemoteList", range='', nargs='*', sync=True)
    def NETRListRemotes(self, args, range):
        self.ranger.NETRemoteList()

    @neovim.command("NETRemotePull", range='', nargs='*', sync=False)
    def NETRDownSync(self, args, range):
        self.ranger.NETRemotePull()
