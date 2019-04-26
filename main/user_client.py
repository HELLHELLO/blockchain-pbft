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
print("注册开始：",time.time())
s = socket.socket()
s.connect(("127.0.0.1", 56666))
register_data = [client_name, client_public_key_str]
register_msg = [Authentication.register.value, register_data]
s.send(str(register_msg).encode())
reply = s.recv(8192).decode()
s.close()
print("注册结束：",time.time())
print("公钥：",client_public_key_str)
print(reply)
print(len(reply))
cred = eval(reply)
server_cred_location = cred[1]
# 获取服务器公钥
server_name = "testB"
req_for_public_key = [(1,1), server_name]
req_for_public_key_msg = [Authentication.req_for_PublicKey.value, req_for_public_key]
c = socket.socket()
c.connect(("127.0.0.1", 56666))
c.send(str(req_for_public_key_msg).encode())
server_public_key_str = c.recv(8192)
server_public_key = RSA.importKey(server_public_key_str)
# 认证
cred_location = cred[2]
print("认证开始：",time.time())
authenticate_data = [cred_location]
authenticate_msg = [Authentication.authenticate.value, authenticate_data]
s = socket.socket()
s.connect(("127.0.0.1", 56666))
s.send(str(authenticate_msg).encode())
challenge = s.recv(1024)
print("挑战：",challenge)
# message_hash = SHA256.new(challenge)
decrypr = PKCS1_OAEP.new(client_key, randfunc=randombytes)
sign = decrypr.decrypt(challenge)
s.send(sign)
challenge_result = s.recv(1024).decode()
print(challenge_result)
print("认证结束：",time.time())
# 生成会话密钥
print("令牌生成开始：",time.time())
session_key = str(("test", server_name))
session_key2 = str(("testb", "testB"))
# cipher = PKCS1_OAEP.new(client_public_key, randfunc=randombytes)
encrypt_session_key = hashlib.sha1(session_key.encode()).hexdigest()#cipher.encrypt(session_key.encode())
encrypt_session_key2 = hashlib.sha1(session_key2.encode()).hexdigest()
keys = [encrypt_session_key, encrypt_session_key2, time.time()]
hash_key = SHA256.new(str(keys).encode())
signer = pkcs1_15.new(client_key)
sign = signer.sign(hash_key)
keys.append(sign)
str_keys = str(keys)
print("keys len:", len(str_keys))
s.send(str(str_keys).encode())
token_location = eval(s.recv(1024).decode())
s.close()
print("令牌生成结束：",time.time())
print(token_location)
# 登录
print("登录开始：",time.time())
cipher_server = PKCS1_OAEP.new(server_public_key)
encrypt_session_key = cipher_server.encrypt(session_key2.encode())
login_message = [token_location, encrypt_session_key, 1]
login_req = [Authentication.login.value, login_message]
s = socket.socket()
s.connect(("127.0.0.1", 56667))
s.send(str(login_req).encode())
reply = s.recv(1024).decode()
print("登录结束：",time.time())
print(reply)
print(client_public_key_str)
print(keys)

