from messgae_head import *
from crypto_algorithm import *
import time
import threading
import socket
import communication
import math


class Client:
    def __init__(self, node_list=None, client_config=None, client_id=0, view=0, node_sum=1, timeout=5, test=False):
        self.node_list = node_list
        self.test = test
        if node_list is None:
            self.node_list = {"0": {"ip": "127.0.0.1", "port": "30000", "key": "hehe"}}
        self.client_config = client_config
        if client_config is None:
            self.client_config = {"ip": "127.0.0.1", "port": "23333"}
        self.client_id = client_id
        # 已发送的请求，以时间戳为关键字
        self.request_list = {}
        # 已收到的回复，以时间戳为关键字
        self.reply_list = {}
        # 已发送的请求的计时器，以时间戳为关键字
        self.timers = {}
        # 当前视图
        self.view = view
        # 节点总数
        self.node_sum = node_sum
        # 当前主节点编号
        self.p_node = view % node_sum
        # 互斥锁
        self.p_node_lock = threading.Lock()
        # 等待响应的超时时间
        self.timeout = timeout
        # 任务队列
        self.task_list = {}

    # request格式为<request,t,o,c,data>，t为时间戳，o为操作，c为客户端标识,data为数据
    def send_request(self, timestamp, request_type=Request.empty.value, request_data=""):
        message = [MessageHead.request.value, timestamp, request_type, str(self.client_id), request_data]
        p_node = self.p_node
        p_node_ip = self.node_list[str(p_node)]["ip"]
        p_node_port = int(self.node_list[str(p_node)]["port"])
        # 尝试发送请求
        try:
            communication.send(ip=p_node_ip, port=p_node_port, msg=message, catch_connection_exception=True)
        # 如果连接主节点失败，则直接向所有节点广播该请求
        except ConnectionError:
            for i in self.node_list:
                communication.send(msg=message, **self.node_list[i])
        self.request_list[str(message[1])] = message
        # 创建相应的响应的字典，以响应结果为关键字
        self.reply_list[str(message[1])] = {}
        # 创建关于该请求的计时器
        timer = threading.Timer(float(self.timeout), self.re_send_request, [message])
        self.timers[str(message[1])] = timer
        timer.start()

    def re_send_request(self, message):
        # 超时后直接向所有节点广播请求
        for i in self.node_list:
            communication.send(msg=message, **self.node_list[i])
        # 创建关于该请求的计时器
        timer = threading.Timer(float(self.timeout), self.re_send_request, [message])
        self.timers[str(message[1])] = timer
        timer.start()

    def receive_reply(self):
        ip = self.client_config["ip"]
        port = int(self.client_config["port"])
        s = socket.socket()
        s.bind((ip, port))
        s.listen(5)
        while True:
            msg = ""
            c, addr = s.accept()
            message = c.recv(1024).decode()
            while message != "":
                msg = msg + message
                message = c.recv(1024).decode()
            c.close()
            if self.test:
                print(msg)
            t = threading.Thread(target=self.get_reply, args=(msg,))
            t.start()

    def get_reply(self, reply):
        reply = eval(reply)
        if self.check_message(reply) is False:
            if self.test:
                print("wrong reply")
            return
        result = reply[-2]
        view = reply[1]
        timestamp = reply[2]
        node_id = reply[4]
        get_reply_num = 0
        try:
            if self.reply_list[str(timestamp)].get(result) is not None:
                self.reply_list[str(timestamp)][result][node_id] = view
            else:
                self.reply_list[str(timestamp)][result] = {node_id: view}
            get_reply_num = len(self.reply_list[str(timestamp)][result])
            if self.test:
                print("in try catch:",get_reply_num)
        except Exception:
            if self.test:
                print("Exception")
            return
        if self.test:
            print("out of try catch:",get_reply_num)
        if get_reply_num >= (math.floor(self.node_sum/3)+1):
            try:
                if self.test:
                    print("wait for done semaphore")
                done_semaphore = self.task_list[str(timestamp)].get("done_semaphore")
                done_semaphore.acquire()
                if self.test:
                    print("get done semaphore")
                done = self.task_list.get(str(timestamp)).get("done")
                self.task_list.get(str(timestamp))["done"] = True
                done_semaphore.release()
            except Exception as e:
                if self.test:
                    print("wrong with get enough reply")
                    print(e.args)
                done = True
            if not done:
                # 收集到足够的回复
                # 停止计时器
                if self.timers.get(str(timestamp)) is not None:
                    self.timers[str(timestamp)].cancel()
                    self.timers.pop(str(timestamp))
                pass
                # 更新view信息
                for i in self.reply_list[str(timestamp)][result]:
                    if view < self.reply_list[str(timestamp)][result][i]:
                        view = self.reply_list[str(timestamp)][result][i]

                self.p_node_lock.acquire()
                self.view = view
                self.p_node = view % self.node_sum
                self.p_node_lock.release()
                # 删除request_list,reply_list中的响应消息
                self.request_list.pop(str(timestamp))
                self.reply_list.pop(str(timestamp))
                # 通知执行函数取结果
                self.task_list[str(timestamp)]["result"] = result
                self.task_list[str(timestamp)]["done"] = True
                semaphore = self.task_list[str(timestamp)].get("finish_semaphore")
                semaphore.release()

    def check_message(self, reply):
        if reply[0] != MessageHead.reply.value:
            if self.test:
                print("wrong head")
            return False
        c_id = reply[3]
        if int(c_id) != self.client_id:
            if self.test:
                print("wrong cid")
            return False
        timestamp = reply[2]
        if self.request_list.get(str(timestamp)) is None:
            if self.test:
                print("wrong timestamp")
            return False
        node_id = reply[4]
        node_config = self.node_list.get(str(node_id))
        if node_config is None:
            if self.test:
                print("wrong node")
            return False
        else:
            node_key = self.node_list[str(node_id)]["key"]
            if reply[-1] != sign(reply[:-1],node_key):
                if self.test:
                    print("wrong sign")
                return False
            else:
                return True

    def execute_request(self, request_type=Request.empty.value, request_data=""):
        timestamp = time.time()
        semaphore = threading.Semaphore(0)
        done_semaphore = threading.Semaphore(1)
        self.task_list[str(timestamp)] = {"finish_semaphore": semaphore, "result": None, "done": False, "done_semaphore": done_semaphore}
        self.send_request(timestamp=timestamp, request_data=request_data, request_type=request_type)
        semaphore.acquire()
        result = str(self.task_list[str(timestamp)]["result"])
        self.task_list.pop(str(timestamp))
        return result

    def start_client(self):
        receive_thread = threading.Thread(target=self.receive_reply)
        receive_thread.start()

if __name__ == "__main__":
    a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "hehe"}
    a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "hehe"}
    a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "hehe"}
    a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "hehe"}
    a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d}
    client_config = {"ip": "127.0.0.1", "port": "23333"}
    client = Client(node_list=a_list, client_config=client_config, client_id=2, node_sum=4, timeout=20, test=False)
    client.start_client()
    result = client.execute_request(request_type=Request.read.value, request_data=(5,0))
    print(result)