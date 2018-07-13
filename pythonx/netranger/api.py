Hookers = {
    'node_highlight_content_l': [],
    'node_highlight_content_r': [],
}


def RegisterHooker(hooker):
    Hookers[hooker.__name__].append(hooker)


def has_hooker(*hooker_names):
    for name in hooker_names:
        if len(Hookers[name]) > 0:
            return True
    return False


class Api(object):
    def set_ranger(self, ranger):
        self.ranger = ranger

    def node_index(self, node):
        return self.ranger.curBuf.nodes.index(node)

    def next_lesseq_level_ind(self, begInd):
        return self.ranger.curBuf.next_lesseq_level_ind(begInd)


NETRApi = Api()
