import socket
import time


a = socket.socket()
a.connect(("127.0.0.1",30001))
msg = [0, time.time(),0,"2","zero"]
a.send(str(msg).encode())
a.close()
print(msg)

#time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30002))
#msg = [0, time.time(),0,"2","zero"]
a.send(str(msg).encode())
a.close()
print(msg)

#time.sleep(1)
a = socket.socket()
a.connect(("127.0.0.1",30003))
#msg = [0, time.time(),0,"2","zero"]
a.send(str(msg).encode())
a.close()
print(msg)


ti=time.time()
print(ti)
time.sleep(60)
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