import enum
from crypto_algorithm import *
import communication
import copy
from heapq import *


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
        if node_list is None:
            self.node_list = {}

        # 该节点上的状态及状态副本,分为稳定检查点，最新状态，若干个不稳定检查点
        # 状态包括：区块链状态，消息日志，视图编号，使用dict保存
        # 消息日志用dict保存，key为消息头的值，value也为dict
        # log.pre-prepare中的key为[v,n]，value为消息本身
        # log.prepare与log.commit中的key为[v,n],value为set类型，存储不同节点发送的消息
        log = dict()
        log["request"] = {}
        log["pre_prepare"] = {}
        log["prepare"] = {}
        log["commit"] = {}
        log["reply"] = {}
        log["checkpoint"] = {}
        log["view_change"] = {}
        log["new_view"] = {}
        self.status_current = {"chain": [], "unblock_data": [], "op_to_execute": [], "log": log, "view": view}
        self.status_stable_checkpoint = copy.deepcopy(self.status_current)
        self.status_checkpoint = []

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
        # 以这种方式来保存：{request的hash值：reply的内容}以及{c,reply}，当发现收到的request的hash值在该dict中有对应的value时，直接取出对应的value作为reply
        self.latest_reply = {}

        # 正在处理的消息数达到最大值时，多余的请求被缓存
        self.request_list = []

        # 合法的客户端列表，用dict以客户端id为关键字保存对应的客户端信息，包括ip与端口号
        self.client_list = client_list
        if client_list is None:
            self.client_list = {}

        # 节点配置
        self.config = self.node_list.get(str(self.node_id))
        if self.config is None:
            self.config = {"ip": "127.0.0.1", "port": "50000", "id": self.node_id, "key": "xxx"}
            self.node_list[str(self.node_id)] = self.config
        self.node_sum = len(self.node_list)

    def read(self, request):
        return request

    def write(self, request):
        return request

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
        elif message[0] is MessageHead.view_change.value:
            self.get_view_change(message)
        elif message[0] is MessageHead.new_view.value:
            self.get_new_view(message)

    # request的格式为<request,t,o,c,data>，t为时间戳，o为操作，c为客户端标识,data为数据
    # 收到request后的处理
    def get_request(self, message):

        # 首先检查该请求是否来自合法客户端
        if self.client_list.get(message[3]) is None:
            # 该客户端标识没有记录，不进行处理
            return

        # 检查该请求是否已被执行
        message_hash = get_hash(str(message))
        if self.latest_reply.get(message_hash) is not None:
            communication.send(msg=self.latest_reply[message_hash], **self.client_list[message[3]])
        # 检查该请求的时间戳是否早于最后一次对该客户端回复的时间戳
        if self.latest_reply.get(str(message[3])) is not None:
            if self.compare_timestamp(message[1], self.latest_reply.get(str(message[3]))[2]):
                return
        else:
            # 请求未被执行，根据当前节点是否为主节点采取相应操作
            if self.node_id == (self.status_current["view"] % self.node_sum):
                # 是主节点
                # 当前处理的请求已达最大值，缓存该消息以后处理
                # 预计将在生成检查点之后进行处理
                if self.seq+1 > self.seq_max:
                    self.request_list.append(message)
                # 当前仍有可分配的序号，为消息分配序号，发送预准备信息
                else:
                    self.seq += 1
                    pre_prepare_msg = self.send_pre_prepare(request_msg=message, seq_number=self.seq)
                    # 将该预准备消息写入消息日志
                    pre_prepare_msg_dict = self.status_current["log"]["pre_prepare"]
                    pre_prepare_msg_dict[str([self.status_current.get("view"), self.seq])] = pre_prepare_msg

            else:
                # 是备份节点，将请求转发至主节点
                p = self.status_current["view"] % self.node_sum
                communication.send(msg=message, **self.node_list[str(p)])
                # 之后启动计时器，以及可能进行的视图更改
                pass

    def compare_timestamp(self, time_a, time_b):
        if time_a < time_b:
            return True
        else:
            return False

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
        self.status_current["log"]["pre_prepare"][str([message[1], message[2]])] = message

        # 生成准备消息，写入消息日志并广播
        prepare_msg = self.send_prepare_or_commit(v, message[2], dreq, self.node_id)
        prepare_msg_dict = self.status_current.get("log").get("prepare")
        prepare_msg_for_the_v_n = prepare_msg_dict.get(str([message[1], message[2]]))
        if prepare_msg_for_the_v_n is None:
            prepare_msg_dict[str([message[1], message[2]])] = {str(self.node_id): prepare_msg}
        else:
            prepare_msg_for_the_v_n[str(self.node_id)] = prepare_msg

    # 生成准备或提交消息并广播，生成的消息被返回
    def send_prepare_or_commit(self, v, n, d, i):
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
        v = message[1]
        n = message[2]

        if self.check_message(message) is False:
            return

        # 检查通过后，将该消息存入消息日志
        self.write_to_log(message, "prepare")

        # 写入消息日志后，检查是否已经完成prepare
        pre_prepare_log_for_message = self.status_current.get("log").get("pre_prepare").get(str([v, n]))
        prepare_log_for_v_n = self.status_current.get("log").get("prepare").get(str([v, n]))
        if pre_prepare_log_for_message is None:
            return

        prepared = 0
        for msg in prepare_log_for_v_n:
            if prepare_log_for_v_n[msg][3] == pre_prepare_log_for_message[3]:
                prepared += 1

        if prepared >= (self.node_sum*2)/3:
            # 已完成准备，进入提交阶段，生成提交信息并广播，将提交信息记入消息日志
            self.status_current["log"]["prepare"][str(v, n, "done")] = True
            commit_msg = self.send_prepare_or_commit(v, n, message[3], self.node_id)
            self.write_to_log(commit_msg, "commit")

    # 提交消息格式为<commit,v,n,dreq,i,sign_MAC>v为视图编号，n为消息序号，dreq是请求摘要,i是节点标识
    def get_commit(self, message):
        v = message[1]
        n = message[2]
        # 检查
        if self.check_message(message) is False:
            return

        # 通过检查后，接收消息并写入日志
        self.write_to_log(message, "commit")

        # 检查commit-local(m,v,n,i)是否成立
        # 先检查prepare(m,v,n,i)是否成立
        prepared = self.status_current["log"]["prepare"].get(str(v, n, "done"))
        if prepared is None or prepared is False:
            return

        # 检查是否收到2f+1个不同节点的匹配提交信息
        pre_prepare_log_for_message = self.status_current.get("log").get("pre_prepare").get(str([v, n]))
        commit_log_for_v_n = self.status_current.get("log").get("commit").get(str([v, n]))
        if pre_prepare_log_for_message is None:
            return

        commit_local = 0
        for msg in commit_log_for_v_n:
            if commit_log_for_v_n[msg][3] == pre_prepare_log_for_message[3]:
                commit_local += 1

        if commit_local > (self.node_sum*2)/3:
            # 已完成提交，将请求加入等待执行的堆
            heappush(self.status_current.get("op_to_execute"), (n, pre_prepare_log_for_message[5]))

    def check_message(self, message):
        # 检查
        v = message[1]
        n = message[2]
        i = message[4]
        # 首先检查视图编号是否一致
        if v != self.status_current.get("view"):
            return False

        # 接下来检查序号是否处于有效范围
        if n < self.seq_min or n > self.seq_max:
            return False

        # 检查是否被正确签名
        i_config = self.node_list.get(str(i))
        if i_config is None:
            return False
        else:
            key = i_config.get("key")
            message_to_sign = message[:5]
            msg_sign = sign(str(message_to_sign), key=key)
            if msg_sign != message[5][self.node_id]:
                return False

        return True

    def write_to_log(self, message, msg_type):
        v = message[1]
        n = message[2]
        i = message[4]
        msg_log = self.status_current.get("log").get(msg_type)
        msg_log_for_v_n = msg_log.get(str([v, n]))
        msg_log_for_v_n_done = msg_log.get(str([v, n, "done"]))
        if msg_log_for_v_n is None:
            msg_log[str([v, n])] = {str(i): message}
        else:
            msg_log_for_v_n[str(i)] = message

        if msg_log_for_v_n_done is None:
            msg_log[str([v, n, "done"])] = False
        pass

    # 检查点信息格式为<checkpoint,v,n,d,i,sign_MAC>,其中n为检查点序号，d为状态的摘要，i为节点序号
    def get_checkpoint(self, message):
        # 检查
        v = message[1]
        n = message[2]
        if self.check_message(message) is False:
            return
        else:
            # 将检查点消息写入消息日志
            self.write_to_log(message, "checkpoint")

        # 检查是否以完成正确性证明
        checkpoint_msg_list = self.status_current.get("log").get("checkpoint").get(str([v, n]))
        for i in self.status_checkpoint:
            num = 0
            for j in checkpoint_msg_list:
                if checkpoint_msg_list[j][3] == i[0]:
                    num += 1
            if num > (self.node_sum*2)/3:
                # 完成正确性证明，该检查点成为稳定检查点
                self.status_stable_checkpoint = i[1]
                self.status_checkpoint.remove(i)
                # 删除所有序号小于检查点的预准备，准备，提交消息
                pre_prepare_list = self.status_current.get("log").get("pre_prepare")
                for msg in pre_prepare_list:
                    if pre_prepare_list[msg][2] <= i[2]:
                        del pre_prepare_list[msg]

                prepare_list = self.status_current.get("log").get("prepare")


        pass

    def get_view_change(self, message):
        pass

    def get_new_view(self, message):
        pass

    def execute_op(self):
        op_list = self.status_current.get("op_to_execute")
        op = heappop(op_list)
        op_msg = op[1]
        if op_msg[2] == Request.read.value:
            result = self.read(op_msg)
        elif op_msg[2] == Request.write.value:
            result = self.write(op_msg)
        elif op_msg[2] == Request.empty.value:
            result = ""
        message = []
        message.append(MessageHead.reply.value)
        message.append(self.status_current.get("view"))
        message.append(self.get_timesatmp())
        message.append(op_msg[3])
        message.append(self.node_id)
        message.append(result)
        communication.send(msg=message, **self.client_list[op_msg[3]])

        # 检查是否到达检查点
        if op[0] % self.checkpoint_base == 0:
            # 到达检查点，将区块打包,写入区块链
            self.generate_block()
            # 生成检查点信息
            state_to_hash = str(self.status_current)
            dstate = get_hash(state_to_hash)
            checkpoint_msg = [MessageHead.checkpoint.value, self.status_current.get("view"), op[0], dstate,
                              self.node_id]
            msg_sign = []
            for i in self.node_list:
                msg_sign.append(sign(str(checkpoint_msg), self.node_list[i].get("key")))

            checkpoint_msg.append(msg_sign)
            # 广播检查点信息
            self.multicast(checkpoint_msg)
            # 将该检查点移入检查点列表
            checkpoint = copy.deepcopy(self.status_current)
            self.status_checkpoint.append((dstate, checkpoint, op[0]))
            # 进入下一个检查点阶段，更新序号有效范围
            self.seq_min = op[0]
            self.seq_max = self.seq_min + self.checkpoint_base
            # 对于主节点，为之前序号空间不够而缓存的消息生成预准备信息并发送
            for i in self.request_list:
                # 序号空间不足，不做操作
                if self.seq+1 > self.seq_max:
                    pass
                # 当前仍有可分配的序号，为消息分配序号，发送预准备信息，将该请求从缓存中删除
                else:
                    self.seq += 1
                    pre_prepare_msg = self.send_pre_prepare(request_msg=message, seq_number=self.seq)
                    # 将该预准备消息写入消息日志
                    pre_prepare_msg_dict = self.status_current["log"]["pre_prepare"]
                    pre_prepare_msg_dict[str([self.status_current.get("view"), self.seq])] = pre_prepare_msg
                    self.request_list.remove(i)

    def generate_block(self):
        pass

    def get_timesatmp(self):
        return 0


a = Node(client_list={"2": {"ip": "127.0.0.1", "port": "50000"}})

request_messageg = [MessageHead.request.value, 1, Request.read.value, "2", "zero"]
a.chose_handler(request_messageg)






