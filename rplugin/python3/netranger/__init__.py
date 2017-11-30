import neovim
from netranger.netranger import Netranger


def log(msg):
    with open("~/netlog", 'a') as f:
        f.write(msg+"\n")


@neovim.plugin
class Main(object):
    def __init__(self, vim):
        self.vim = vim
        self.ranger = Netranger(vim)

    @neovim.autocmd('BufEnter', pattern='*', eval='expand("<abuf>")', sync=True)
    def on_bufenter(self, bufnum):
        self.ranger.on_bufenter(int(bufnum))

    # @neovim.autocmd('BufLeave', pattern='*', eval='expand("<abuf>")', sync=True)
    # def on_bufleave(self, bufnum):
    #     self.ranger.on_bufleave(int(bufnum))
    #
    # @neovim.autocmd('BufHidden', pattern='*', eval='expand("<abuf>")', sync=True)
    # def on_bufhidden(self, bufnum):
    #     self.ranger.on_bufhidden(int(bufnum))

    @neovim.autocmd('CursorMoved', pattern='*', eval='expand("<abuf>")', sync=True)
    def on_cursormoved(self, bufnum):
        self.ranger.on_cursormoved(int(bufnum))

    @neovim.function('NETRInvokeMap', sync=True)
    def NETRInvokeMap(self, args):
        self.ranger.invoke_map(args[0])

    @neovim.function('_NETRBookmarkSet', sync=True)
    def _NETRBookmarkSet(self, args):
        self.ranger._NETRBookmarkSet(args[0])

    @neovim.command("NETRCD", range='', nargs='*', sync=True)
    def NETRCD(self, args, range):
        self.ranger.cd(args[0])

    @neovim.command("NETRListRemotes", range='', nargs='*', sync=True)
    def NETRListRemotes(self, args, range):
        self.ranger.listremotes()
