Hookers = {
    'node_highlight_content_l': [],
    'node_highlight_content_r': [],
    'render_begin': [],
    'render_end': [],
}


def RegisterHooker(hooker):
    Hookers[hooker.__name__].append(hooker)


def RegisterKeyMaps(fn_keys):
    NETRApi.ranger.register_keymap(fn_keys)


def HasHooker(*hooker_names):
    for name in hooker_names:
        if len(Hookers[name]) > 0:
            return True
    return False


class Api(object):
    def set_ranger(self, ranger):
        self.ranger = ranger

    def node_index(self, node):
        return self.ranger.cur_buf.nodes.index(node)

    def next_lesseq_level_ind(self, begInd):
        return self.ranger.cur_buf.next_lesseq_level_ind(begInd)

    @property
    def cur_node(self):
        return self.ranger.cur_node

    def render(self, bufNum=None):
        if bufNum:
            buf = self.ranger.bufs[int(bufNum)]
        else:
            buf = self.ranger.cur_buf
        buf.render()


NETRApi = Api()
