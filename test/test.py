import threading
import time

class node:
    def __init__(self):
        self.timeout = 10
        self.timer = None
        self.fin = False

    def hello(self,msg):
        print("hello" + msg)
        self.fin = True

    def execute(self):
        timer = threading.Timer(float(self.timeout),self.hello,["nihao"])
        self.timer = timer
        timer.start()


a=node()
a.execute()
while a.fin == False:
    continue
if a.timer is not None:
    print("hh")