import hashlib
import hmac

# 计算一段字符串的hash值
# 暂定
def get_hash(string):
    string = str(string)
    return hashlib.sha1(string.encode()).hexdigest()


# 计算签名
# 暂定
def sign(string, key):
    string = str(string).encode()
    key = str(key).encode()
    return hmac.new(key=key, msg=string, digestmod=hashlib.sha1).hexdigest()
    # return hashlib.sha1((string+key).encode()).hexdigest()


def randombytes(hlen):
    a = b''
    for i in range(hlen):
        a = a + b'1'
    return a
