from main.pbft_node import Node

import copy

if __name__ == '__main__':
    a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "xx", "port_push": "40001"}
    a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "xx", "port_push": "40002"}
    a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "xx", "port_push": "40003"}
    a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "xx", "port_push": "40000"}
    a_to_e = {"ip": "127.0.0.1", "port": "30004", "id": 4, "key": "xx", "port_push": "40004"}
    a_to_f = {"ip": "127.0.0.1", "port": "30005", "id": 5, "key": "xx", "port_push": "40005"}
    a_to_g = {"ip": "127.0.0.1", "port": "30006", "id": 6, "key": "xx", "port_push": "40006"}
    a_to_h = {"ip": "127.0.0.1", "port": "30007", "id": 7, "key": "xx", "port_push": "40007"}
    a_to_i = {"ip": "127.0.0.1", "port": "30008", "id": 8, "key": "xx", "port_push": "40008"}
    a_to_j = {"ip": "127.0.0.1", "port": "30009", "id": 9, "key": "xx", "port_push": "40009"}
    a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d, "4": a_to_e, "5": a_to_f, "6": a_to_g,
              "7": a_to_h, "8": a_to_i, "9": a_to_j}

    # b_list = copy.deepcopy(a_list)
    # b_list["0"]["key"] = "ab"
    # b_list["1"]["key"] = "bb"
    # b_list["2"]["key"] = "bc"
    # b_list["3"]["key"] = "bd"
    #
    # c_list = copy.deepcopy(a_list)
    # c_list["0"]["key"] = "ac"
    # c_list["1"]["key"] = "bc"
    # c_list["2"]["key"] = "cc"
    # c_list["3"]["key"] = "cd"
    #
    # d_list = copy.deepcopy(a_list)
    # d_list["0"]["key"] = "ad"
    # d_list["1"]["key"] = "bd"
    # d_list["2"]["key"] = "cd"
    # d_list["3"]["key"] = "dd"

    client_list = {"2": {"ip": "127.0.0.1", "port": "23333", "key": "hehe"},
                   "3": {"ip": "127.0.0.1", "port": "23334", "key": "hehe"},
                   "4": {"ip": "127.0.0.1", "port": "23335", "key": "hehe"},
                   "5": {"ip": "127.0.0.1", "port": "23336", "key": "hehe"}}

    h = Node(node_id=7, node_list=a_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    # b = Node(node_id=1, node_list=b_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    # c = Node(node_id=2, node_list=c_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    # d = Node(node_id=3, node_list=d_list, client_list=client_list, timeout=10, checkpoint_base=3,test=True)
    h.start_node()
    #b.start_node()
    #c.start_node()
    #d.start_node()
    print("started")