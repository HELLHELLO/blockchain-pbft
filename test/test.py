import socket
import time
a = socket.socket()
a.bind(("127.0.0.1", 60000))
a.listen(10)
while True:
    c, addr = a.accept()
    d=c.recv(1024)
    print(d.decode())
    c.close()
