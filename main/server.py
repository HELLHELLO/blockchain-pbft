from client import Client
import socket
import threading
from Crypto.PublicKey import DSA
from Crypto.Signature import DSS
from Crypto.Hash import SHA256
import time
from messgae_head import *


class server:
    def __init__(self, name="testServer", chain_client=None, config=None, domain=None, test=False):
        self.test = test
        #if chain_client is not None:
        #    self.chain_client = chain_client
        #else:
        a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "hehe"}
        a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "hehe"}
        a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "hehe"}
        a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "hehe"}
        a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d}
        client_config = {"ip": "127.0.0.1", "port": "23333"}
        self.chain_client = Client(node_list=a_list, client_config=client_config, client_id=2, node_sum=4,
                                   timeout=20, test=True)
        self.config = config
        self.name = name
        if domain is None:
            self.key = DSA.generate(2048)
            self.pubkey = self.key.publickey()
        else:
            self.key = DSA.construct(tup=domain, consistency_check=True)
            self.pubkey = self.key.publickey()
        self.cred = []
        self.cred_location = None
        self.signer = DSS.new(key=self.key, mode="fips-186-3")

    def start(self):
        self.chain_client.start_client()
        if self.test:
            print("starting register")
        self.register()
        if self.test:
            print("register successfully, cred location:",self.cred_location)
        s = socket.socket()
        ip = self.config["ip"]
        port = int(self.config["port"])
        s.bind((ip, port))
        s.listen(10)
        while True:
            c, addr = s.accept()
            service = threading.Thread(target=self.chose_handler, args=(c,))
            service.start()

    def register(self):
        public_key = self.pubkey.export_key()
        timestamp = time.time()
        self.cred = [self.name, timestamp, public_key]
        message_hash = SHA256.new(str(self.cred).encode())
        signature = self.signer.sign(message_hash)
        self.cred.append(signature)
        self.cred_location = self.chain_client.execute_request(request_type=Request.write.value,
                                                               request_data=str(self.cred))

    # request格式为[head,data]
    def chose_handler(self, c):
        request = c.recv(1024).decode()
        request = eval(request)
        if request[0] is Authentication.register.value:
            self.get_register(data=request[1], c=c)
            return
        elif request[0] is Authentication.authenticate.value:
            self.get_authenticate(data=request[1], c=c)
            return
        else:
            c.send("wrong message")
            c.close()
            return

    # data为[username,userPublicKey]
    def get_register(self, data, c):
        timestamp = time.time()
        data.append(timestamp)
        # 签名，将信息写入链
        message_hash = SHA256.new(str(data).encode())
        signature = self.signer.sign(message_hash)
        data.append(signature)
        cred_location = self.chain_client.execute_request(request_type=Request.write.value,
                                                          request_data=str(data))
        # 签名，将证书返回给用户
        data[-1] = cred_location
        message_hash = SHA256.new(str(data).encode())
        signature = self.signer.sign(message_hash)
        data.append(signature)
        c.send(str(data).encode())
        return

    def get_authenticate(self,data,c):
        pass



print("hello")