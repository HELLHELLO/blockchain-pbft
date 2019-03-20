import socket
import time


a = socket.socket()
a.connect(("127.0.0.1",30001))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()

time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30002))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()

time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30003))
a.send(str([0, time.time(),0,"2","zero"]).encode())
a.close()


ti=time.time()
time.sleep(20)
a = socket.socket()
a.connect(("127.0.0.1",30001))
a.send(str([0, ti,0,"2","zero"]).encode())
a.close()

#time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30002))
a.send(str([0, ti,0,"2","zero"]).encode())
a.close()

#time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30003))
a.send(str([0, ti,0,"2","zero"]).encode())
a.close()