import socket, struct, threading, time, cv2, numpy as np

PORT = 5000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
sock.bind(("0.0.0.0", PORT))

latest = None
lock = threading.Lock()             # MUTEX
new_frame_event = threading.Event() # Event flag

# Proceso receptor
def receiver():
    global latest
    cur_frame, chunks, done = -1, {}, False
    while True:
        # Recibir paquete
        packet, _ = sock.recvfrom(2048)
        if len(packet) <= 8:
            continue
        # Header
        frame_id, idx, total = struct.unpack("!IHH", packet[:8])

        # Eliminar paquetes de frames viejos si llego uno nuevo
        if frame_id < cur_frame:
            continue
        if frame_id > cur_frame:
            cur_frame, chunks, done = frame_id, {}, False
        if done:
            continue
        
        # Agregar paquete a frame
        chunks[idx] = packet[8:]
        
        # Paquete completo
        if len(chunks) == total:
            done = True
            jpg = b"".join(chunks[i] for i in range(total))

            # Notificar de paquete nuevo
            with lock:
                latest = (frame_id, jpg)
            new_frame_event.set()

# Thread del receptor
threading.Thread(target=receiver, daemon=True).start()

# Thread principal
print("Esperando video...")
fps, count, t0 = 0.0, 0, time.perf_counter()
while True:
    # Esperar a nuevo frame del hilo receptor
    new_frame_event.wait()
    new_frame_event.clear()
    with lock:
        frame_id, jpg = latest

    # Decodificar JPG
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        continue
    
    # Determinar FPS
    count += 1
    now = time.perf_counter()
    if now - t0 >= 1.0:
        fps = count / (now - t0)
        count, t0 = 0, now

    # Mostrar imagen
    cv2.putText(img, f"{frame_id}  {fps:.1f} FPS", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.imshow("rx", img)
    if cv2.waitKey(1) == ord('q'):
        break
