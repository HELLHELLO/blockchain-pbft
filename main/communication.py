import socket


def send(ip, port, msg, catch_connection_exception=False, **kw):
    msg_send = str(msg)
    try:
        s = socket.socket()
        s.connect((ip, int(port)))
        s.send(msg_send.encode())
        s.close()
    except ConnectionError:
        if catch_connection_exception:
            raise
    except Exception:
        pass
    return
