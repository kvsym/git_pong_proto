import zenoh
import bridge_mgmt_pb2 as bridge_pb

cfg = zenoh.Config()
cfg.insert_json5("connect/endpoints", '["tcp/localhost:7447"]')
z = zenoh.open(cfg)

openq = z.declare_querier("backend/bridge_mgmt/open_bridge")
closeq = z.declare_querier("backend/bridge_mgmt/close_bridge")

req = bridge_pb.OpenBridgeRequest(outbound_topic="human/imu", message_type=bridge_pb.IMU)
rep_msg = bridge_pb.OpenBridgeReply()

reply = openq.get(payload=req.SerializeToString()).recv()
rep_msg.ParseFromString(reply.ok.payload.to_bytes())
print("OPEN:", rep_msg)

req2 = bridge_pb.CloseBridgeRequest(bridge_id=rep_msg.bridge_id)
rep2 = bridge_pb.CloseBridgeReply()

reply2 = closeq.get(payload=req2.SerializeToString()).recv()
rep2.ParseFromString(reply2.ok.payload.to_bytes())
print("CLOSE:", rep2)

z.close()