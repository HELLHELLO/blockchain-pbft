from main.server import *


a_to_b = {"ip": "127.0.0.1", "port": "30001", "id": 1, "key": "hehe"}
a_to_c = {"ip": "127.0.0.1", "port": "30002", "id": 2, "key": "hehe"}
a_to_d = {"ip": "127.0.0.1", "port": "30003", "id": 3, "key": "hehe"}
a_to_a = {"ip": "127.0.0.1", "port": "30000", "id": 0, "key": "hehe"}
a_list = {"0": a_to_a, "1": a_to_b, "2": a_to_c, "3": a_to_d}
client_config = {"ip": "127.0.0.1", "port": "23333"}
chain_client=Client(node_list=a_list, client_config=client_config, client_id=2, node_sum=4,timeout=20, test=False)
a = Server(config={"ip": "127.0.0.1", "port": "56666"},test=True,name="testA",chain_client=chain_client)
a.start()