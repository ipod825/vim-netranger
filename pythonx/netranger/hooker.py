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
