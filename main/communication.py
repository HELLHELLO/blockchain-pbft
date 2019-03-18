import socket


def send(ip, port, msg, **kw):
    msg_send = str(msg)
    try:
        s = socket.socket()
        s.connect((ip, int(port)))
        s.send(msg_send.encode())
        s.close()
    except Exception:
        pass
    return
