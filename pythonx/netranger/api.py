from netranger import Vim
from netranger.fs import FSTarget


class NETRApi(object):
    Hookers = {
        'node_highlight_content_l': [],
        'node_highlight_content_r': [],
        'render_begin': [],
        'render_end': [],
    }
    ranger = None

    @classmethod
    def init(self, ranger):
        self.ranger = ranger

    @classmethod
    def RegisterHooker(self, hooker):
        self.Hookers[hooker.__name__].append(hooker)

    @classmethod
    def map(self, key, fn, check=False):
        self.ranger.map(key, fn, check=check)

    @classmethod
    def mapvimfn(self, key, fn):
        self.map(key, lambda: Vim.eval('function("{}")()'.format(fn)))

    @classmethod
    def HasHooker(self, *hooker_names):
        for name in hooker_names:
            if len(self.Hookers[name]) > 0:
                return True
        return False

    @classmethod
    def node_index(self, node):
        return self.ranger.cur_buf.nodes.index(node)

    @classmethod
    def next_lesseq_level_ind(self, begInd):
        return self.ranger.cur_buf.next_lesseq_level_ind(begInd)

    @classmethod
    def cur_node(self):
        return self.ranger.cur_node

    @classmethod
    def cur_node_name(self):
        return self.ranger.cur_node.name

    @classmethod
    def cur_node_path(self):
        return self.ranger.cur_node.fullpath

    @classmethod
    def cp(self, src, dst):
        cur_buf = self.ranger.cur_buf
        FSTarget(dst).append(src).cp(
            dst,
            on_begin=lambda: self.ranger.inc_num_fs_op([cur_buf]),
            on_exit=lambda: self.ranger.dec_num_fs_op([cur_buf]))

    @classmethod
    def mv(self, src, dst):
        cur_buf = self.ranger.cur_buf
        FSTarget(dst).append(src).mv(
            dst,
            on_begin=lambda: self.ranger.inc_num_fs_op([cur_buf]),
            on_exit=lambda: self.ranger.dec_num_fs_op([cur_buf]))

    @classmethod
    def rm(self, src):
        cur_buf = self.ranger.cur_buf
        FSTarget().append(src).rm(
            False,
            on_begin=lambda: self.ranger.inc_num_fs_op([cur_buf]),
            on_exit=lambda: self.ranger.dec_num_fs_op([cur_buf]))

    @classmethod
    def render(self, bufNum=None):
        if bufNum:
            buf = self.ranger.bufs[int(bufNum)]
        else:
            buf = self.ranger.cur_buf
        buf.render()
