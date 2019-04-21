from client import Client
import socket
import threading
#from Crypto.PublicKey import DSA
#from Crypto.Signature import DSS
from Crypto.Signature import pkcs1_15 as DSS
from Crypto.PublicKey import RSA as DSA
import Crypto.Random as Random
from Crypto.Hash import SHA256
import time
from messgae_head import *
from Crypto.Cipher import PKCS1_OAEP
from crypto_algorithm import *
import hashlib

class Server:
    def __init__(self, name="testServer", chain_client=None, config=None, domain=None, test=False, challenge_str_len=16,
                 life_time=7776000, token_life=1800):
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
            self.key = DSA.construct(rsa_components=domain, consistency_check=True)
            self.pubkey = self.key.publickey()
        self.cred = []
        self.cred_location = None
        self.signer = DSS.new(rsa_key=self.key)
        self.challenge_str_len = challenge_str_len
        self.life_time = life_time
        self.token_life = token_life

    def start(self):
        self.chain_client.start_client()
        if self.test:
            print("starting register")
        self.register()
        if self.test:
            print("register successfully, cred location:", self.cred_location)
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
        # cred格式为[name,timestamp,public_key,sign]
        self.cred_location = eval(self.chain_client.execute_request(request_type=Request.write.value,
                                                                    request_data=str(self.cred)))
        if self.test:
            print([self.cred_location])

    # request格式为[head,data]
    def chose_handler(self, c):
        request = c.recv(4096).decode()
        request = eval(request)
        if self.test:
            print(request)
        if request[0] is Authentication.register.value:
            self.get_register(data=request[1], c=c)
            return
        elif request[0] is Authentication.authenticate.value:
            self.get_authenticate(data=request[1], c=c)
            return
        elif request[0] is Authentication.req_for_PublicKey.value:
            self.get_req_for_public_key(data=request[1], c=c)
            return
        elif request[0] is Authentication.login.value:
            self.get_login(data=request[1], c=c)
        else:
            c.send("wrong message".encode())
            c.close()
            return

    # 该请求格式为[cred_location,server_name]
    def get_req_for_public_key(self, data, c):
        correct, public_tup = self.get_server_public_key(cred_location=data[0], server_name=data[1])
        if correct is False:
            c.send("wrong msg".encode())
        else:
            c.send(public_tup[1])
        c.close()
        return

    def get_server_public_key(self, cred_location, server_name=None):
        cred = eval(self.chain_client.execute_request(request_data=cred_location, request_type=Request.read.value))
        # 先检验服务器name是否正确
        if server_name is not None and cred[0] != server_name:
            return False, None
        # 检验该证书的签名正确与否
        public_key_string = cred[2]
        public_key = DSA.import_key(public_key_string)
        verifier = DSS.new(rsa_key=public_key)
        sign = cred[-1]
        cred = cred[:-1]
        message_hash = SHA256.new(str(cred).encode())
        try:
            verifier.verify(msg_hash=message_hash, signature=sign)
            return True, (public_key, public_key_string)
        except ValueError:
            return False, None

    # data为[username,userPublicKey]
    def get_register(self, data, c):
        timestamp = time.time()
        data.append(timestamp)
        # 三个月的时间长度
        life_time = self.life_time
        data.append(timestamp+life_time)
        data.append(self.cred_location)
        # 签名，将信息写入链
        # 写入链的证书格式为[username,userPublicKey,timestamp,cred_life,server_cred_location,sign1]
        message_hash = SHA256.new(str(data).encode())
        signature = self.signer.sign(message_hash)
        data.append(signature)
        cred_location = eval(self.chain_client.execute_request(request_type=Request.write.value,
                                                          request_data=str(data)))
        # 签名，将证书返回给用户
        # 返回的证书格式为[cred_life,server_cred_location,cred_location,server_name,sign2]
        data = [timestamp+life_time, self.cred_location, cred_location, self.name]
        message_hash = SHA256.new(str(data).encode())
        signature = self.signer.sign(message_hash)
        data.append(signature)
        c.send(str(data).encode())
        return

    # 收到的authenticate请求格式为[cred_location]
    def get_authenticate(self, data, c):
        cred_location = data[0]
        # 取得链上的证书
        cred = eval(self.chain_client.execute_request(request_type=Request.read.value, request_data=cred_location))
        # 检查该证书是否有效
        timestamp = time.time()
        if cred[2] >= timestamp or timestamp >= cred[3]:
            c.send("fail".encode())
            c.close()
            return
        # 验证该证书的签名
        # 首先获取为该证书签名的服务器的公钥
        server_cred_location = cred[-2]
        correct, publickey_tup = self.get_server_public_key(cred_location=server_cred_location)
        if correct is False:
            c.send("fail".encode())
            c.close()
            return
        else:
            public_key = publickey_tup[0]
            # 验证该证书的签名是否正确
            verifier = DSS.new(rsa_key=public_key)
            sign = cred[-1]
            cred = cred[:-1]
            message_hash = SHA256.new(str(cred).encode())
            try:
                verifier.verify(msg_hash=message_hash, signature=sign)
                user_publickey = DSA.import_key(cred[1])
                # verifier_for_user = DSS.new(rsa_key=user_publickey)
                # 证书签名正确，进入挑战应答阶段
                self.challenge(user_pubkey=user_publickey, c=c, cred_location=cred_location)
                return
            except ValueError:
                c.send("fail".encode())
                c.close()
                return

    def challenge(self, user_pubkey, c, cred_location):
        if self.test:
            print("challenging")
        # 发送挑战
        challenge_str = Random.get_random_bytes(self.challenge_str_len)
        # message_hash = SHA256.new(challenge_str)
        cipher = PKCS1_OAEP.new(user_pubkey, randfunc=randombytes)
        encrypt_challenge = cipher.encrypt(challenge_str)
        try:
            c.send(encrypt_challenge)
            reply = c.recv(8192)
            # reply直接为挑战字符串
            # verifier.verify(msg_hash=message_hash, signature=reply)
            if reply != challenge_str:
                raise ValueError
            c.send("success".encode())
            # 通过签名验证,进入下一阶段，生成登陆用令牌
            verifier = DSS.new(rsa_key=user_pubkey)
            self.generate_token(c=c, verifier=verifier, challenge_str=challenge_str, reply=reply,
                                cred_location=cred_location)
            return
        except ValueError:
            c.send("fail".encode())
            c.close()
            return
        except ConnectionError:
            return

    # 生成令牌,用户发送的是[h(k1,server1),h(k2,server2),h(k3,server3)...,sign],最多不超过10个key
    def generate_token(self, c, verifier, challenge_str, reply, cred_location):
        message = c.recv(8192).decode()
        message = eval(message)
        keys = message[:-1]
        sign = message[-1]
        message_hash = SHA256.new(str(keys).encode())
        # 验证签名是否正确
        try:
            verifier.verify(msg_hash=message_hash, signature=sign)
            timestamp = time.time()
            # 验证签名正确，生成令牌
            # 令牌格式为[cred_location,server_cred_location,[h(k1,server1),h(k2,server2),h(k3,server3)...,timestamp,sign],token_life,sign]
            token = [cred_location, self.cred_location, message, timestamp+self.token_life]
            message_hash = SHA256.new(str(token).encode())
            sign = self.signer.sign(message_hash)
            token.append(sign)
            token_location = eval(self.chain_client.execute_request(request_type=Request.write.value,
                                                                    request_data=str(token)))
            c.send(str(token_location).encode())
            c.close()
            return
        except ValueError:
            c.send("fail".encode())
            c.close()
            return

    #用户发送的data是[token_location,Epks(ki,serveri),i]
    def get_login(self, data, c):
        if self.test:
            print("get login")
        token_location = data[0]
        token = eval(self.chain_client.execute_request(request_type=Request.read.value,
                                                       request_data=token_location))
        server_cred_location = token[1]
        cred_location = token[0]
        if self.test:
            print(server_cred_location)
        correct, publickey_tup = self.get_server_public_key(cred_location=server_cred_location)
        if correct is False:
            c.send("fail".encode())
            c.close()
            return
        else:
            server_publickey = publickey_tup[0]
            token_hash = SHA256.new(str(token[:-1]).encode())
            verifier = DSS.new(rsa_key=server_publickey)
            try:
                keys = token[2]
                # 验证token是否有效
                t = time.time()
                if time.time() >= token[-2] or t - keys[-2] >= self.token_life:
                    raise ValueError
                # 验证token的签名
                verifier.verify(msg_hash=token_hash, signature=token[-1])
                if self.test:
                    print("token sign correct")
                # 验证token中的key的签名
                cred = eval(self.chain_client.execute_request(request_type=Request.read.value,
                                                              request_data=cred_location))
                user_public_key_string = cred[1]
                user_public_key = DSA.import_key(user_public_key_string)
                verifier = DSS.new(rsa_key=user_public_key)
                if self.test:
                    print(keys)
                    print(user_public_key_string)
                keys_hash = SHA256.new(str(keys[:-1]).encode())
                verifier.verify(msg_hash=keys_hash, signature=keys[-1])
                if self.test:
                    print("keys sign correct")
                # 验证通过后，检验收到的密钥是否是token中的密钥
                cipher_for_server = PKCS1_OAEP.new(self.key)
                session_key = cipher_for_server.decrypt(data[1])
                # cipher_for_user = PKCS1_OAEP.new(user_public_key, randfunc=randombytes)

                # session_key_encryptd = cipher_for_user.encrypt(session_key)
                session_key_hashed = hashlib.sha1(session_key).hexdigest()
                i = data[2]
                session_key_received = keys[i]
                session_key_list = eval(session_key.decode())
                session_key = session_key_list[0]
                server_name = session_key_list[1]
                if self.test:
                    print(server_name)
                    print(session_key_hashed == session_key_received)
                    print(server_name == self.name)
                if session_key_hashed == session_key_received and server_name == self.name:
                    reply = "session key is "+session_key
                    c.send(reply.encode())
                else:
                    raise ValueError
            except ValueError:
                c.send("fail".encode())
                c.close()
                return


a = Server(config={"ip": "127.0.0.1", "port": "56666"},test=True)
a.start()
print("hello")