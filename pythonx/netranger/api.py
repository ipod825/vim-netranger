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


def has_hooker(*hooker_names):
    for name in hooker_names:
        if len(Hookers[name]) > 0:
            return True
    return False


def disableHookers():
    for name in Hookers:
        Hookers[name] = []


class Api(object):
    def set_ranger(self, ranger):
        self.ranger = ranger

    def node_index(self, node):
        return self.ranger.curBuf.nodes.index(node)

    def next_lesseq_level_ind(self, begInd):
        return self.ranger.curBuf.next_lesseq_level_ind(begInd)

    @property
    def curNode(self):
        return self.ranger.curNode

    def render(self):
        self.ranger.curBuf.render()


NETRApi = Api()
