import socket, struct, cv2, time

# Socket
IP_DESTINO = "192.168.1.6"
PORT = 5000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sockdest = (IP_DESTINO, PORT)

# Configurar cámara
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # datos crudos de cámara: JPEG
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)                            # opencv entrega datos crudos de la cámara

# Packet parameters
CHUNK_SIZE = 1400
frame_id = 0
print("Streaming...")
while True:
    # Leer imagen raw
    ret, frame = cap.read()
    if not ret:
        break
    
    # Empaquetar
    data = frame.tobytes()
    chunks = [data[i:i+CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]
    total_packets = len(chunks)
    
    # Send Frame: frame_id, packet_id, total_packets
    for packet_id, packet in enumerate(chunks):
        header = struct.pack("!IHH", frame_id, packet_id, total_packets)
        sock.sendto(header + packet, sockdest)
    frame_id = (frame_id + 1) & 0xFFFFFFFF

