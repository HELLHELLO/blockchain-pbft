import socket
import time
a = socket.socket()
a.bind(("127.0.0.1", 23333))
a.listen(10)
while True:
    c, addr = a.accept()
    all_msg = ""
    msg = c.recv(4).decode()
    while msg != "":
        all_msg = all_msg+msg
        msg = c.recv(5)
        msg = msg.decode()
    c.close()
    print(all_msg)
