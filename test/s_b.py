from main.server import *

a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "hehe", "port_push": "40001"}
a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "hehe", "port_push": "40002"}
a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "hehe", "port_push": "40003"}
a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "hehe", "port_push": "40000"}
a_to_e = {"ip": "127.0.0.1", "port": "30004", "id": 4, "key": "hehe", "port_push": "40004"}
a_to_f = {"ip": "127.0.0.1", "port": "30005", "id": 5, "key": "hehe", "port_push": "40005"}
a_to_g = {"ip": "127.0.0.1", "port": "30006", "id": 6, "key": "hehe", "port_push": "40006"}
a_to_h = {"ip": "127.0.0.1", "port": "30007", "id": 7, "key": "hehe", "port_push": "40007"}
a_to_i = {"ip": "127.0.0.1", "port": "30008", "id": 8, "key": "hehe", "port_push": "40008"}
a_to_j = {"ip": "127.0.0.1", "port": "30009", "id": 9, "key": "hehe", "port_push": "40009"}
a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d, "4": a_to_e, "5": a_to_f, "6": a_to_g,
          "7": a_to_h, "8": a_to_i, "9": a_to_j}
client_config = {"ip": "127.0.0.1", "port": "23334"}
chain_client=Client(node_list=a_list, client_config=client_config, client_id=3, node_sum=10,timeout=20, test=False)
a = Server(config={"ip": "127.0.0.1", "port": "56667"},test=False,name="testB",chain_client=chain_client)
a.start()
