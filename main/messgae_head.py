import enum


class Request(enum.Enum):
    empty = 0
    read = 1
    write = 2


class MessageHead(enum.Enum):
    request = 0
    pre_prepare = 1
    prepare = 2
    commit = 3
    reply = 4
    checkpoint = 5
    view_change = 6
    new_view = 7


class Authentication(enum.Enum):
    register = 0
    authenticate = 1
