class SuperEnum(object):
    class __metaclass__(type):
        def __iter__(self):
            for item in self.__dict__:
                if item == self.__dict__[item]:
                    yield item


def Enum(name, members):
    """Builds a class <name> with <class_members> having the name as value."""

    members = [m.strip() for m in members.split(',')]
    return type(name, (SuperEnum, ), {val: val for val in members})
