

# 计算一段字符串的hash值
# 暂定
def get_hash(string):
    return hash(string)


# 计算签名
# 暂定
def sign(string, key):
    return hash(string+key)
