from main.pbft_node import Node

import copy

if __name__ == '__main__':
    a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "ab", "port_push": "40001"}
    a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "ac", "port_push": "40002"}
    a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "ad", "port_push": "40003"}
    a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "aa", "port_push": "40000"}
    a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d}

    b_list = copy.deepcopy(a_list)
    b_list["0"]["key"] = "ab"
    b_list["1"]["key"] = "bb"
    b_list["2"]["key"] = "bc"
    b_list["3"]["key"] = "bd"

    c_list = copy.deepcopy(a_list)
    c_list["0"]["key"] = "ac"
    c_list["1"]["key"] = "bc"
    c_list["2"]["key"] = "cc"
    c_list["3"]["key"] = "cd"

    d_list = copy.deepcopy(a_list)
    d_list["0"]["key"] = "ad"
    d_list["1"]["key"] = "bd"
    d_list["2"]["key"] = "cd"
    d_list["3"]["key"] = "dd"

    client_list = {"2": {"ip": "127.0.0.1", "port": "23333", "key": "hehe"}}
    a = Node(node_id=0, node_list=a_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    b = Node(node_id=1, node_list=b_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    c = Node(node_id=2, node_list=c_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    d = Node(node_id=3, node_list=d_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    #a.start_node()
    b.start_node()
    #c.start_node()
    #d.start_node()
    print("started")