import socket
import json

UDP_IP = "127.0.0.1"   # same IP as in simulator
UDP_PORT = 9000       # same port as in simulator

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"✅ Listening for telemetry on udp://{UDP_IP}:{UDP_PORT} ...\n")

while True:
    data, addr = sock.recvfrom(4096)
    try:
        telemetry = json.loads(data.decode())
        print("📡 Telemetry:", telemetry)
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON packet received")
