import enum
from crypto_algorithm import *
import communication
import copy
from heapq import *
import threading
import time


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

    def __init__(self, view=0, node_id=0, node_list=None, checkpoint_base=50, seq_space=100, client_list=None, timeout=5
                 ):

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
        # 稳定检查点信息中为{checkpoint:(状态摘要，块链状态，检查点序号),proof:证明}
        dstate = get_hash(str(self.status_current["chain"]))
        self.status_stable_checkpoint = {"checkpoint": (dstate, copy.deepcopy(self.status_current.get("chain")), 0),
                                         "proof": {}}
        self.status_checkpoint = []

        # 是否处于视图更改阶段
        self.view_changing = False
        # 定时器，同时保存启动该定时器的请求摘要
        self.timer_state = {"timer": None, "dreq": None}
        # 定时器超时时间
        self.timeout = timeout

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
        # 以这种方式来保存：{request的hash值：reply的内容}以及{c:reply}，当发现收到的request的hash值在该dict中有对应的value时，直接取出对应的value作为reply
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

    # 定时器超时后调用该函数，进行视图更改
    # 视图更改信息格式为<view_change,v+1,s,C,P,i,sign_MAC>,v+1为下一个视图，n为稳定检查点序号
    # C是稳定检查点的证明，P是P是一个包含了对于每一个i已准备的消息序号大于n的消息的Pm集合的集合。
    # Pm集合中包括一个有效的预准备消息（不包含对应的客户端信息），2f个对应的来自不同备份的有效的准备信息。
    # i是节点id
    def change_view(self, view):
        # 启动定时器时的视图与当前视图不一致，不进行操作
        if view != self.status_current.get("view"):
            return

        # 定时器在当前视图中超时，执行视图更改
        self.view_changing = True
        n = self.status_stable_checkpoint.get("checkpoint")[2]
        C = self.status_stable_checkpoint.get("proof")
        v = self.status_current.get("view")
        P = []
        pre_prepare_msg_list = self.status_current.get("log").get("pre_prepare")
        prepare_msg_list = self.status_current.get("log").get("prepare")
        for i in pre_prepare_msg_list:
            done = list(eval(i))
            done.append("done")
            if pre_prepare_msg_list[i][2] > n and prepare_msg_list.get(done) is True:
                Pm = {"pre_prepare": pre_prepare_msg_list[i], "prepare": prepare_msg_list[i]}
                P.append(Pm)

        view_change_msg = [MessageHead.view_change.value, v+1, n, C, P, self.node_id]
        msg_sign = []
        for i in self.node_list:
            msg_sign.append(sign(str(view_change_msg), self.node_list[i].get("key")))

        view_change_msg.append(msg_sign)
        # 发送
        self.multicast(view_change_msg)
        # 自身视图+1
        self.status_current["view"] += 1
        # 重置计时器
        self.timer_state["timer"] = None
        self.timer_state["dreq"] = None

    def read(self, request):
        return request

    def write(self, request):
        return request

    def multicast(self, message, send_to_self=True):
        for i in self.node_list:
            if i != str(self.node_id):
                communication.send(msg=message, **self.node_list[i])
        # 是否发送给自身
        if send_to_self:
            communication.send(msg=message, **self.node_list[str(self.node_id)])

    def chose_handler(self, message):
        if message[0] is MessageHead.request.value and not self.view_changing:
            self.get_request(message)
        elif message[0] is MessageHead.pre_prepare.value and not self.view_changing:
            self.get_pre_prepare(message)
        elif message[0] is MessageHead.prepare.value and not self.view_changing:
            self.get_prepare(message)
        elif message[0] is MessageHead.commit.value and not self.view_changing:
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
            view = self.status_current["view"]
            if self.node_id == (view % self.node_sum):
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
                    pre_prepare_msg_dict[str([view, self.seq])] = pre_prepare_msg

            else:
                # 是备份节点，将请求转发至主节点
                p = self.status_current["view"] % self.node_sum
                communication.send(msg=message, **self.node_list[str(p)])
                # 之后启动计时器，以及可能进行的视图更改
                # 若已有启动的计时器，则先取消该计时器
                if self.timer_state["timer"] is not None:
                    self.timer_state["timer"].cancel()
                timer = threading.Timer(float(self.timeout), self.change_view, [view])
                self.timer_state["timer"] = timer
                timer.start()
                self.timer_state["dreq"] = message_hash

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
            self.status_current.get("log").get("commit")[(str([v, n, "done"]))] = True
            if pre_prepare_log_for_message[5] is not "":
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

    def write_to_log(self, message, msg_type, v=None, n=None, i=None):
        if v is None:
            v = message[1]
        if n is None:
            n = message[2]
        if i is None:
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
        checkpoint_list = copy.deepcopy(self.status_checkpoint)
        for i in self.status_checkpoint:
            if i[2] != n:
                continue
            num = 0
            for j in checkpoint_msg_list:
                if checkpoint_msg_list[j][3] == i[0]:
                    num += 1
            if num > (self.node_sum*2)/3:
                # 完成正确性证明，该检查点成为稳定检查点,保存该检查点信息以及正确性证明
                checkpoint_proof = copy.deepcopy(checkpoint_msg_list)
                stable_checkpoint = copy.deepcopy(i)
                self.status_stable_checkpoint = {"checkpoint": stable_checkpoint, "proof": checkpoint_proof}
                checkpoint_list.remove(i)
                # 删除所有更早的检查点状态
                for checkpoint in self.status_checkpoint:
                    if checkpoint[2] <= i[2]:
                        checkpoint_list.remove(checkpoint)
                # 删除所有序号小于等于检查点的预准备，准备，提交消息,新视图信息,视图更改信息
                pre_prepare_list = self.status_current.get("log").get("pre_prepare")
                keys = list(pre_prepare_list.keys())
                for msg in keys:
                    if pre_prepare_list[msg][2] <= i[2]:
                        pre_prepare_list.pop(msg)

                prepare_list = self.status_current.get("log").get("prepare")
                keys = list(prepare_list.keys())
                for msg_list in keys:
                    if prepare_list[msg_list] is not True and prepare_list[msg_list] is not False and \
                            len(prepare_list[msg_list]) > 0:
                        if prepare_list[msg_list][0][2] <= i[2]:
                            prepare_list.pop(msg_list)

                commit_list = self.status_current.get("log").get("commit")
                keys = list(commit_list.keys())
                for msg_list in keys:
                    if commit_list[msg_list] is not True and commit_list[msg_list] is not False and \
                            len(commit_list[msg_list]) > 0:
                        if commit_list[msg_list][0][2] <= i[2]:
                            commit_list.pop(msg_list)

                new_view_list = self.status_current.get("log").get("new_view")
                keys = list(new_view_list.keys())
                for new_view in keys:
                    v, view_n = list(eval(new_view))
                    if view_n < i[2]:
                        new_view_list.pop(new_view)

                view_change_list = self.status_current.get("log").get("view_change")
                keys = list(view_change_list.keys())
                for view_change in keys:
                    v, change_n = list(eval(view_change))
                    if v < self.status_current["view"]:
                        view_change_list.pop(view_change)

                # 更新序号有效范围
                self.seq_min = n
                self.seq_max = self.seq_min + self.checkpoint_base
                # 对于主节点，为之前序号空间不够而缓存的消息生成预准备信息并发送
                # request_list_copy = copy.deepcopy(self.request_list)
                wait_for_del = []
                for request_msg in self.request_list:
                    # 序号空间不足，不做操作
                    if self.seq + 1 > self.seq_max:
                        break
                    # 当前仍有可分配的序号，为消息分配序号，发送预准备信息，将该请求从缓存中删除
                    else:
                        self.seq += 1
                        pre_prepare_msg = self.send_pre_prepare(request_msg=request_msg, seq_number=self.seq)
                        # 将该预准备消息写入消息日志
                        pre_prepare_msg_dict = self.status_current["log"]["pre_prepare"]
                        pre_prepare_msg_dict[str([self.status_current.get("view"), self.seq])] = pre_prepare_msg
                        wait_for_del.append(request_msg)
                        # request_list_copy.remove(request_msg)
                # self.request_list = request_list_copy
                for request_msg in wait_for_del:
                    self.request_list.remove(request_msg)
                break
        self.status_checkpoint = checkpoint_list

        # 删除之前的检查点信息
        checkpoint_msg_list = self.status_current.get("log").get("checkpoint")
        keys = list(checkpoint_msg_list.keys())
        for key in keys:
            if len(checkpoint_msg_list[key]) > 0:
                if checkpoint_msg_list[key][0][2] < n:
                    checkpoint_msg_list.pop(key)

    # 视图更改信息格式为<view_change,v+1,n,C,P,i,sign_MAC>,v+1为下一个视图，n为稳定检查点的序号
    # C是稳定检查点的证明，P是P是一个包含了对于每一个i已准备的消息序号大于n的消息的Pm集合的集合。
    # Pm集合中包括一个有效的预准备消息（不包含对应的客户端信息），2f个对应的来自不同备份的有效的准备信息。
    # i是节点id
    def get_view_change(self, message):
        # 检查该消息是否有效
        # 先检查该消息的签名
        i = message[5]
        C = message[3]
        v = message[1]
        # 不同节点所发送的稳定检查点可能不一致，因此n不应作为索引，将n同一设为0
        n = 0
        i_config = self.node_list.get(str(i))
        if i_config is None:
            return
        else:
            key = i_config.get("key")
            message_to_sign = message[:6]
            msg_sign = sign(str(message_to_sign), key=key)
            if msg_sign != message[6][self.node_id]:
                return
        # 检查是否有足够的证明
        if len(C) <= (self.node_sum * 2) / 3:
            return
        # 通过证明后，写入消息日志
        self.write_to_log(message=message, msg_type="view_change", v=v, n=n, i=i)

        # 检查这个视图更改信息要转到的视图中，自己是否是主节点，不是就不干事,
        if v % self.node_sum != self.node_id:
            pass
        else:
            # 检查是否已经收到足够的视图更改信息,且要转到的视图比现在视图更新：
            if v > self.status_current["view"]:
                view_change_list = self.status_current.get("log").get("view_change").get(str([v, n]))
                if len(view_change_list) > (self.node_sum*2)/3:
                    # 已收到足够的视图更改信息，生成新视图信息并发送
                    new_view_msg, min_s = self.send_new_view(v)
                    self.write_to_log(message=new_view_msg, msg_type="new_view", v=v, n=min_s, i=self.node_id)

    # 从其他节点获取检查点
    def ask_for_checkpoint(self, node_id):
        return

    # 生成新视图信息并发送，生成的新视图信息被写入消息日志
    # 新视图信息格式为<new_view,v+1,V,O>,其中，
    # V为节点(v+1 mod r)所收到的视图更改信息的集合，
    # O是预准备信息的集合，通过如下过程生成
    # 主节点在集合V中选取最新的稳定检查点，取其序号作为最小序号min-s，max-s，并取v中的准备信息中最大的序号作为序号最大值。
    # 主节点为新视图v+1中的每一个大于min-s小于max-s的序号n生成一条新的预准备信息，这里有两种情况：
    # 在某些视图更改信息中的P中，至少存在一个集合拥有一个序号n，
    #   在该情况，主节点产生一条新的信息<pre-prepare,v+1,n,d>xp，
    #   其中d是V中具有最高视图编号的视图更改信息中的预准备信息中的请求的摘要。
    # 没有上述集合，
    #   在该情况下，主节点创建一条新的预准备信息<pre-prepare,v+1,n,dnull>xp，其中dnull是对于特殊的空操作的摘要。
    def send_new_view(self, v):
        # 先生成V
        n = 0
        V = self.status_current.get("log").get("view_change").get(str([v, n]))
        # 生成O
        # 选取最新的稳定检查点

        O, min_s, msg_i = self.generate_O(V, v)
        for msg in O:
            self.write_to_log(msg, "pre_prepare")
        # 生成O之后的操作,更新自身的检查点
        self.update_checkpoint(V=V, msg_i=msg_i, min_s=min_s)

        # 更新序号有效范围
        self.seq_min = min_s
        self.seq_max = self.seq_min + self.checkpoint_base
        # 更新视图v
        self.status_current["view"] = v

        # 发送new_view信息
        new_view = [MessageHead.new_view.value, v, V, O]
        msg_sign = []
        for i in self.node_list:
            msg_sign.append(sign(str(new_view), self.node_list[i].get("key")))
        new_view.append(msg_sign)
        self.multicast(message=new_view, send_to_self=True)
        return new_view, min_s

    # 在视图更改过程中更新检查点
    def update_checkpoint(self, V, msg_i, min_s):
        if self.status_stable_checkpoint.get("checkpoint") is None or min_s > \
                self.status_stable_checkpoint.get("checkpoint"):
            # 如果该稳定检查点序号比当前的自己的稳定检查点序号更新，首先检查未稳定的检查点是否是该序号
            checkpoint_list = copy.deepcopy(self.status_checkpoint)
            found_checkpoint = False
            for unstable_checkpoint in self.status_checkpoint:
                # 如果该检查点已在未稳定检查点中,将该检查点转变为稳定检查点
                if unstable_checkpoint[2] == min_s:
                    self.status_stable_checkpoint = {"checkpoint": unstable_checkpoint, "proof": V[msg_i][3]}
                    found_checkpoint = True
                    checkpoint_list.remove(unstable_checkpoint)
                    break
            # 如果自身没有该检查点，从其他节点获取
            if found_checkpoint is False:
                new_checkpoint = self.ask_for_checkpoint(msg_i)
                self.status_stable_checkpoint = {"checkpoint": new_checkpoint, "proof": V[msg_i][3]}
            # 删除所有更早的检查点状态
            for checkpoint in self.status_checkpoint:
                if checkpoint[2] <= min_s:
                    checkpoint_list.remove(checkpoint)
            # 删除所有序号小于等于检查点的预准备，准备，提交消息
                pre_prepare_list = self.status_current.get("log").get("pre_prepare")
                keys = list(pre_prepare_list.keys())
                for msg in keys:
                    if pre_prepare_list[msg][2] <= min_s:
                        pre_prepare_list.pop(msg)

                prepare_list = self.status_current.get("log").get("prepare")
                keys = list(prepare_list.keys())
                for msg_list in keys:
                    if len(prepare_list[msg_list]) > 0:
                        if prepare_list[msg_list][0][2] <= min_s:
                            prepare_list.pop(msg_list)

                commit_list = self.status_current.get("log").get("commit")
                keys = list(commit_list.keys())
                for msg_list in keys:
                    if len(commit_list[msg_list]) > 0:
                        if commit_list[msg_list][0][2] <= min_s:
                            commit_list.pop(msg_list)

                checkpoint_msg_list = self.status_current.get("log").get("checkpoint")
                keys = list(checkpoint_msg_list.keys())
                for key in keys:
                    if checkpoint_msg_list[key][0][2] < min_s:
                        checkpoint_msg_list.pop(key)
            self.status_checkpoint = checkpoint_list

    def generate_O(self, V, v):
        # 生成O
        # 选取最新的稳定检查点
        # 生成min-s
        min_s = 0
        msg_i = "0"
        for i in V:
            # 稳定检查点信息中为{checkpoint:(状态摘要，块链状态，检查点序号),proof:证明}
            if min_s <= V[i][2]:
                min_s = V[i][2]
                msg_i = i

        # 生成max-s
        max_s = min_s
        for view_change_msg in V:
            P = V[view_change_msg][4]
            for Pm in P:
                if max_s < Pm["pre_prepare"][2]:
                    max_s = Pm["pre_prepare"][2]

        # 为之前已经committed的信息进行排序
        new_pre_prepare_msg_list = []
        for n in range(min_s + 1, max_s + 1):
            found = False
            found_msg = None
            found_v = 0
            for view_change_msg in V:
                P = V[view_change_msg][4]
                for Pm in P:
                    # 两种情况
                    # 1.有一些消息需要重新执行三相协议
                    if Pm["pre_prepare"][2] == n:
                        found = True
                        if found_v < Pm["pre_prepare"][1]:
                            found_msg = Pm["pre_prepare"]
                            found_v = found_msg[1]
            # 两种情况
            # 1.找到了之前已被分配该序号的消息
            if found is True:
                new_message = found_msg[:-2]
                new_message[1] = v
                msg_sign = []
                for i in self.node_list:
                    msg_sign.append(sign(str(new_message), self.node_list[i].get("key")))
                new_message.append(msg_sign)
                new_message.append(found_msg[-1])
                new_pre_prepare_msg_list.append(new_message)
            else:
                # 2.没有这样的消息，生成空操作替代
                new_message = [MessageHead.pre_prepare.value, v, n,
                               get_hash(str(Request.empty.value))]
                # 进行签名，这里用MAC
                msg_sign = []
                for i in self.node_list:
                    msg_sign.append(sign(str(new_message), self.node_list[i].get("key")))
                new_message.append(msg_sign)
                new_message.append("")
                new_pre_prepare_msg_list.append(new_message)
        O = new_pre_prepare_msg_list
        return O, min_s, msg_i

    def get_new_view(self, message):
        # 先取出信息中的视图编号
        v = message[1]
        # 主节点编号
        p = v % self.node_sum
        to_sign = message[:-1]
        # 检查签名
        i_config = self.node_list.get(str(p))
        if i_config is None:
            return
        else:
            key = i_config.get("key")
            msg_sign = sign(str(to_sign), key=key)
            if msg_sign != message[-1][self.node_id]:
                return

        V = message[2]
        if len(V) < (self.node_sum*2)/3:
            return

        # 检查O是否正确
        O, min_s, msg_i = self.generate_O(V, v)
        if str(O) != str(message[3]):
            return
        self.write_to_log(message=message, msg_type="new_view", v=v, n=min_s, i=p)
        # 通过检测，将O中消息写入日志
        for msg in O:
            self.write_to_log(msg, "pre_prepare")

        self.update_checkpoint(V=V, msg_i=msg_i, min_s=min_s)
        # 更新序号有效范围
        self.seq_min = min_s
        self.seq_max = self.seq_min + self.checkpoint_base
        # 更新视图v
        self.status_current["view"] = v

        # 为O中的每一条信息发送相应的prepare
        for pre_prepare in O:
            self.send_prepare_or_commit(v=v, n=pre_prepare[2], d=pre_prepare[3], i=self.node_id)

    def execute_op(self):
        op_list = self.status_current.get("op_to_execute")
        op = heappop(op_list)
        op_msg = op[1]

        # 如果有对于该请求的计时器，则停止计时
        dreq = get_hash(str(op_msg))
        if self.timer_state["dreq"] == dreq and self.timer_state["timer"] is not None:
            self.timer_state["timer"].cancel()
            self.timer_state["dreq"] = None
            self.timer_state["timer"] = None

        # 如果发现该请求的时间戳早于最后一次对该客户端的回复，不执行该请求
        request_t = op_msg[1]
        reply_t = self.latest_reply.get(str(op_msg[3]))[2]
        if self.compare_timestamp(request_t, reply_t):
            return

        result = ""
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
            # 当前服务状态为chain的状态
            state_to_hash = str(self.status_current.get("chain"))
            dstate = get_hash(state_to_hash)
            checkpoint_msg = [MessageHead.checkpoint.value, self.status_current.get("view"), op[0], dstate,
                              self.node_id]
            msg_sign = []
            for i in self.node_list:
                msg_sign.append(sign(str(checkpoint_msg), self.node_list[i].get("key")))

            checkpoint_msg.append(msg_sign)
            # 广播检查点信息
            self.multicast(checkpoint_msg, send_to_self=True)
            # 将该检查点移入检查点列表
            # 检查点即为服务状态，也即区块链状态
            checkpoint = copy.deepcopy(self.status_current.get("chain"))
            self.status_checkpoint.append((dstate, checkpoint, op[0]))

    def generate_block(self):
        pass

    def get_timesatmp(self):
        return

a = Node(client_list={"2": {"ip": "127.0.0.1", "port": "50000"}})

request_messageg = [MessageHead.request.value, 1, Request.read.value, "2", "zero"]
a.chose_handler(request_messageg)






