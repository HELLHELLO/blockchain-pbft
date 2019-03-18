import socket
import time
a = socket.socket()
a.connect(("127.0.0.1",30001))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()

a = socket.socket()
a.connect(("127.0.0.1",30002))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()

a = socket.socket()
a.connect(("127.0.0.1",30003))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()