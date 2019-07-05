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
    def RegisterKeyMaps(self, fn_keys):
        self.ranger.register_keymap(fn_keys)

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

    @property
    def cur_node(self):
        return self.ranger.cur_node

    @classmethod
    def render(self, bufNum=None):
        if bufNum:
            buf = self.ranger.bufs[int(bufNum)]
        else:
            buf = self.ranger.cur_buf
        buf.render()
