import enum
from crypto_algorithm import *
import communication
import copy


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


class Node:

    def __init__(self, view=0, node_id=0, node_list=None, checkpoint_base=50, seq_space=100, client_list=None):

        # 节点id
        self.node_id = node_id

        # 节点列表，包括节点ip，端口号，id，共享密钥等
        self.node_list = node_list

        # 该节点上的状态及状态副本,分为稳定检查点，最新状态，若干个不稳定检查点
        # 状态包括：区块链状态，消息日志，视图编号，使用dict保存
        # 消息日志用dict保存，key为消息头的值，value也为dict
        # log.value中的key为消息序号，value为dict
        # log.value.value中的key为视图编号，value为消息本身
        log = dict()
        log["request"] = {}
        log["pre_prepare"] = {}
        log["prepare"] = {}
        log["commit"] = {}
        log["reply"] = {}
        log["checkpoint"] = {}
        log["view_change"] = {}
        log["new_view"] = {}
        self.status_current = {"chain": [], "log": log, "view": view}
        self.status_stable_checkpoint = copy.deepcopy(self.status_current)
        self.status_checkpoint = {}

        # 检查点的产生间隔
        self.checkpoint_base = checkpoint_base
        # 消息序号的有效范围的大小
        self.seq_space = seq_space

        # 当前收到的请求消息中的最大序号
        self.seq = 0
        # 当前消息序号的最大最小值
        self.seq_min = 0
        self.seq_max = self.seq_min + self.seq_space

        # 保存的对每一个客户端的最后一次reply
        # 以这种方式来保存：{request的hash值：reply的内容}，当发现收到的request的hash值在该dict中有对应的value时，直接取出对应的value作为reply
        self.latest_reply = {}

        # 正在处理的消息数达到最大值时，多余的请求被缓存
        self.request_list = []

        # 合法的客户端列表，用dict以客户端id为关键字保存对应的客户端信息，包括ip与端口号
        self.client_list = client_list

        # 节点配置
        self.config = self.node_list.get(str(self.node_id))
        if self.config is None:
            self.config = {"ip": "127.0.0.1", "port": "50000", "id": self.node_id, "key": {}}
            self.node_list[str(self.node_id)] = self.config
        self.node_sum = len(self.node_list)

    def read(self):
        pass

    def write(self):
        pass

    def multicast(self, message):
        for i in self.node_list:
            communication.send(msg=message, **self.node_list[i])

    def chose_handler(self, message):
        if message[0] is MessageHead.request.value:
            self.get_request(message)
        elif message[0] is MessageHead.pre_prepare.value:
            self.get_pre_prepare(message)
        elif message[0] is MessageHead.prepare.value:
            self.get_prepare(message)
        elif message[0] is MessageHead.commit.value:
            self.get_commit(message)
        elif message[0] is MessageHead.checkpoint.value:
            self.get_checkpoint(message)
        elif message[0] is MessageHead.view_change:
            self.get_view_change(message)
        elif message[0] is MessageHead.new_view:
            self.get_new_view(message)

    # request的格式为<request,t,o,c>，t为时间戳，o为操作，c为客户端标识
    # 收到request后的处理
    def get_request(self, message):

        # 首先检查该请求是否来自合法客户端
        if self.client_list[message[3]] is None:
            # 该客户端标识没有记录，不进行处理
            return

        # 检查该请求是否已被执行
        message_hash = get_hash(str(message))
        if self.latest_reply[message_hash] is not None:
            communication.send(msg=self.latest_reply[message_hash], **self.client_list[message[3]])
        else:
            # 请求未被执行，根据当前节点是否为主节点采取相应操作
            if self.node_id == (self.status_current["view"] % self.node_sum):
                # 是主节点
                # 当前处理的请求已达最大值，缓存该消息以后处理
                # 预计将在生成稳定检查点之后进行处理
                if self.seq+1 >= self.seq_max:
                    self.request_list.append(message)
                # 当前仍有可分配的序号，为消息分配序号，发送预准备信息
                else:
                    self.seq += 1
                    pre_prepare_msg = self.send_pre_prepare(request_msg=message, seq_number=self.seq)
                    # 将该预准备消息写入消息日志
                    if self.status_current.get("log").get("pre-prepare").get(str(self.seq)) is None:
                        self.status_current["log"]["pre-prepare"][str(self.seq)] = {str(pre_prepare_msg[1]): pre_prepare_msg}
                    else:
                        self.status_current["log"]["pre-prepare"][str(self.seq)][str(pre_prepare_msg[1])] = pre_prepare_msg

            else:
                # 是备份节点，将请求转发至主节点
                p = self.status_current["view"] % self.node_sum
                communication.send(msg=message, **self.node_list[str(p)])
                # 之后启动计时器，以及可能进行的视图更改
                pass

    # 生成预准备信息并发送，生成的预准备信息被返回
    def send_pre_prepare(self, request_msg, seq_number):
        message = [MessageHead.pre_prepare.value, self.status_current["view"], seq_number, get_hash(str(request_msg))]
        # 进行签名，这里用MAC
        msg_sign = []
        for i in self.node_list:
            msg_sign.append(sign(str(message), self.node_list[i].get("key")))

        message.append(msg_sign)
        message.append(request_msg)
        # 发送
        self.multicast(message)
        return message

    # 预准备消息格式为<pre-perpare,v,n,dreq,sign_MAC,req>,其中
    # v为视图编号，n为消息序号，dreq是请求摘要，sign_MAC是对<pre-perpare,v,n,dreq>的签名或MAC，req是请求内容，req可以为空
    # 收到预准备消息后的处理，显然，主节点不会收到预准备消息
    def get_pre_prepare(self, message):
        # 首先判断该预准备消息的视图与当前视图是否一致
        v = message[1]
        if v != self.status_current.get("view"):
            return

        # 其次判断是否收到过具有相同视图v，相同序号n，但不同dreq的预准备消息
        message_old_n = self.status_current.get("log").get("pre_prepare").get(str(message[2]))
        if message_old_n is not None:
            message_old_n_v = message_old_n.get(str(v))
            if message_old_n_v is not None:
                if message_old_n_v[3] != message[3]:
                    return

        # 判断消息签名是否正确
        p = v % self.node_sum
        p_config = self.node_list.get(str(p))
        if p_config is None:
            return
        else:
            key = p_config.get("key")
            message_to_sign = message[:4]
            msg_sign = sign(str(message_to_sign), key=key)
            if msg_sign != message[4][self.node_id]:
                return

        # 判断dreq是否是req的摘要
        dreq = get_hash(str(message[-1]))
        if dreq != message[3]:
            return

        # 判断该消息中的序号n是否处于有效范围：
        if message[2] > self.seq_max or message[2] < self.seq_min:
            return

        # 以上验证都通过了之后，接受该预准备消息，将该预准备消息写入消息日志
        if self.status_current.get("log").get("pre-prepare").get(str(message[2])) is None:
            self.status_current["log"]["pre-prepare"][str(message[2])] = {str(v): message}
        else:
            self.status_current["log"]["pre-prepare"][str(message[2])][str(v)] = message

        # 生成准备消息，写入消息日志并广播
        prepare_msg = self.send_prepare(v, message[2], dreq, self.node_id)
        if self.status_current.get("log").get("prepare").get(str(message[2])) is None:
            self.status_current["log"]["prepare"][str(message[2])] = {}

        if self.status_current["log"]["prepare"][str(message[2])].get(str(v)) is None:
            self.status_current["log"]["prepare"][str(message[2])][str(v)] = {}

        self.status_current["log"]["prepare"][str(message[2])][str(v)][str(self.node_id)] = prepare_msg

    # 生成准备消息并广播，生成的准备消息被返回
    def send_prepare(self, v, n, d, i):
        message = [MessageHead.prepare.value, v, n, d, i]
        msg_sign = []
        for i in self.node_list:
            msg_sign.append(sign(str(message), self.node_list[i].get("key")))

        message.append(msg_sign)
        # 发送
        self.multicast(message)
        return message

    # 准备消息格式为<prepare,v,n,dreq,i,sign_MAC>v为视图编号，n为消息序号，dreq是请求摘要,i是节点标识
    def get_prepare(self, message):
        pass

    def get_commit(self, message):
        pass

    def get_checkpoint(self, message):
        pass

    def get_view_change(self, message):
        pass

    def get_new_view(self, message):
        pass








