from Crypto.Signature import pkcs1_15
from Crypto.PublicKey import RSA
import Crypto.Random as Random
from Crypto.Hash import SHA256
import time
from messgae_head import *
from Crypto.Cipher import PKCS1_OAEP
import socket
import threading
from crypto_algorithm import *
# 客户端信息
client_key = RSA.generate(1024)
client_public_key = client_key.publickey()
client_public_key_str = client_public_key.exportKey()
client_name = "testClient"
# 注册
s = socket.socket()
s.connect(("127.0.0.1", 56666))
register_data = [client_name, client_public_key_str]
register_msg = [Authentication.register.value, register_data]
s.send(str(register_msg).encode())
reply = s.recv(8192).decode()
s.close()
print(reply)
print(len(reply))
cred = eval(reply)
server_cred_location = cred[1]
# 获取服务器公钥
server_name = "testServer"
req_for_public_key = [server_cred_location, server_name]
req_for_public_key_msg = [Authentication.req_for_PublicKey.value, req_for_public_key]
c = socket.socket()
c.connect(("127.0.0.1", 56666))
c.send(str(req_for_public_key_msg).encode())
server_public_key_str = c.recv(8192)
server_public_key = RSA.importKey(server_public_key_str)
# 认证
cred_location = cred[2]
authenticate_data = [cred_location]
authenticate_msg = [Authentication.authenticate.value, authenticate_data]
s = socket.socket()
s.connect(("127.0.0.1", 56666))
s.send(str(authenticate_msg).encode())
challenge = s.recv(1024)
print(challenge)
# message_hash = SHA256.new(challenge)
decrypr = PKCS1_OAEP.new(client_key, randfunc=randombytes)
sign = decrypr.decrypt(challenge)
s.send(sign)
challenge_result = s.recv(1024).decode()
print(challenge_result)
# 生成会话密钥
session_key = str(("test", server_name))
# cipher = PKCS1_OAEP.new(client_public_key, randfunc=randombytes)
encrypt_session_key = hashlib.sha1(session_key.encode()).hexdigest()#cipher.encrypt(session_key.encode())
print(encrypt_session_key)
keys = [encrypt_session_key, time.time()]
hash_key = SHA256.new(str(keys).encode())
signer = pkcs1_15.new(client_key)
sign = signer.sign(hash_key)
keys.append(sign)
str_keys = str(keys)
print("keys len:", len(str_keys))
s.send(str(str_keys).encode())
token_location = eval(s.recv(1024).decode())
s.close()
print(token_location)
# 登录
cipher_server = PKCS1_OAEP.new(server_public_key)
encrypt_session_key = cipher_server.encrypt(session_key.encode())
login_message = [token_location, encrypt_session_key, 0]
login_req = [Authentication.login.value, login_message]
s = socket.socket()
s.connect(("127.0.0.1", 56666))
s.send(str(login_req).encode())
reply = s.recv(1024).decode()
print(reply)
print(client_public_key_str)
print(keys)

