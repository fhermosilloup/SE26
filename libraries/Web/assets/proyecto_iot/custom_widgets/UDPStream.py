import ipaddress
import json
import socket
import struct
import threading
import time

class UDPVideoStream:
    default_props = {
        "label": "Camera", "stream_id": "camera_01", "udp_port": 5000,
        "sender_ip": "192.168.1.100", "background": "#0f172a",
        "object_fit": "Contain", "show_header": True, "show_status": True,
        "show_timestamp": True, "show_fps": True, "show_controls": True,
        "placeholder": "Esperando video..."
    }
    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "stream_id", "label": "ID de la cámara:", "type": "text"},
        {"name": "udp_port", "label": "Puerto UDP predeterminado:", "type": "number"},
        {"name": "sender_ip", "label": "IP del emisor predeterminada:", "type": "text"},
        {"name": "background", "label": "Color de fondo:", "type": "color"},
        {"name": "object_fit", "label": "Ajuste de imagen:", "type": "select", "options": ["Contain", "Cover", "Fill"]},
        {"name": "show_header", "label": "Mostrar encabezado:", "type": "boolean"},
        {"name": "show_status", "label": "Mostrar estado:", "type": "boolean"},
        {"name": "show_timestamp", "label": "Mostrar timestamp:", "type": "boolean"},
        {"name": "show_fps", "label": "Mostrar FPS:", "type": "boolean"},
        {"name": "show_controls", "label": "Mostrar controles:", "type": "boolean"},
        {"name": "placeholder", "label": "Mensaje sin señal:", "type": "text"}
    ]
    supported_events = ["on_video_click"]
    # El estado se crea por instancia de servidor al registrar el plugin.
    @staticmethod
    def register_backend(app, socketio, project_data):
        lock = threading.RLock()
        streams = {}  # (port, sender_ip, stream_id) -> contexto
        by_port = {}  # port -> clave activa; el protocolo no lleva stream_id
        def send_status(sid, ok, message, **extra):
            payload = {"ok": ok, "message": message, **extra}
            socketio.emit("udp_stream_status", payload, to=sid)
        def receiver(ctx):
            port = ctx["port"]
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                udp.bind(("0.0.0.0", port))
                udp.settimeout(0.25)
                ctx["socket"] = udp
                print(f"[UDPStream] Receptor activo en 0.0.0.0:{port}; emisor permitido: {ctx['sender_ip']}")
            except OSError as exc:
                ctx["error"] = str(exc)
                ctx["ready"].set()
                udp.close()
                with lock:
                    key = ctx["key"]
                    if streams.get(key) is ctx:
                        streams.pop(key, None)
                        by_port.pop(port, None)
                return
            ctx["ready"].set()
            pending = {}
            last_emitted = None
            HEADER_SIZE = 8
            MAX_PACKETS = 4096
            MAX_FRAME_BYTES = 8 * 1024 * 1024
            MAX_PENDING = 12
            FRAME_TTL = 2.0
            def newer(candidate, previous):
                delta = (candidate - previous) & 0xFFFFFFFF
                return 0 < delta < 0x80000000
            try:
                while not ctx["stop"].is_set():
                    now = time.monotonic()
                    try:
                        packet, addr = udp.recvfrom(65535)
                        #print(f"[UDPStream] Recibido desde :{addr} el paquete de {len(packet)}")
                    except socket.timeout:
                        packet = None
                        addr = None
                    except OSError:
                        break
                    # Filtrado por IP de origen configurada en el widget.
                    if packet and addr and addr[0] != ctx["sender_ip"]:
                        continue
                    for fid in list(pending):
                        if now - pending[fid]["created"] > FRAME_TTL:
                            del pending[fid]
                    while len(pending) > MAX_PENDING:
                        oldest = min(pending, key=lambda k: pending[k]["created"])
                        del pending[oldest]
                    if not packet or len(packet) <= HEADER_SIZE:
                        continue
                    try:
                        frame_id, packet_id, total = struct.unpack("!IHH", packet[:HEADER_SIZE])
                    except struct.error:
                        continue
                    if total < 1 or total > MAX_PACKETS or packet_id >= total:
                        continue
                    part = packet[HEADER_SIZE:]
                    frame = pending.get(frame_id)
                    if frame is None:
                        frame = {"total": total, "parts": {}, "size": 0, "created": now}
                        pending[frame_id] = frame
                    if frame["total"] != total:
                        del pending[frame_id]
                        continue
                    if packet_id in frame["parts"]:
                        continue
                    frame["parts"][packet_id] = part
                    frame["size"] += len(part)
                    if frame["size"] > MAX_FRAME_BYTES:
                        del pending[frame_id]
                        continue
                    if len(frame["parts"]) != total:
                        continue
                    jpeg = b"".join(frame["parts"][i] for i in range(total))
                    del pending[frame_id]
                    
                    # print(f"[UDPStream] Frame completo: {frame_id}, " f"paquetes={total}, bytes={len(jpeg)}")
                    if len(jpeg) < 4 or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
                        print("[UDPStream] JPEG demasiado pequeño")
                        continue
                    if not jpeg.startswith(b"\xff\xd8"):
                        print("[UDPStream] JPEG sin marcador SOI")
                        continue
                    if not jpeg.endswith(b"\xff\xd9"):
                        print("[UDPStream] JPEG sin marcador EOI")
                        continue
                    
                    if last_emitted is not None and not newer(frame_id, last_emitted):
                        continue
                    last_emitted = frame_id
                    with lock:
                        recipients = list(ctx["clients"])
                    metadata = {"stream_id": ctx["stream_id"], "frame_id": frame_id}
                    for sid in recipients:
                        try:
                            socketio.emit("video_frame", (metadata, jpeg), to=sid )
                        except Exception as exc:
                            print(f"[UDPStream] Error Socket.IO: {exc}")
            finally:
                udp.close()
                with lock:
                    key = ctx["key"]
                    if streams.get(key) is ctx:
                        streams.pop(key, None)
                        by_port.pop(port, None)
                print(f"[UDPStream] Receptor detenido en UDP :{port}")
        def connect_udp_stream(data):
            from flask import request
            sid = request.sid
            print(f"[UDPStream] Cliente conectado al stream: {sid}")
            data = data or {}
            try:
                port = int(data.get("udp_port", 5000))
                if not 1 <= port <= 65535:
                    raise ValueError("El puerto debe estar entre 1 y 65535.")
                sender_ip = str(data.get("sender_ip", "")).strip()
                ipaddress.ip_address(sender_ip)
                stream_id = str(data.get("stream_id") or "camera_01").strip()
                if not stream_id:
                    raise ValueError("El ID de cámara está vacío.")
            except (TypeError, ValueError) as exc:
                send_status(sid, False, f"Configuración inválida: {exc}")
                return
            key = (port, sender_ip, stream_id)
            with lock:
                active_key = by_port.get(port)
                if active_key is not None and active_key != key:
                    send_status(sid, False,
                                f"El puerto UDP {port} ya está siendo utilizado por otra configuración.")
                    return
                ctx = streams.get(key)
                if ctx is None:
                    ctx = {
                        "key": key, "port": port, "sender_ip": sender_ip,
                        "stream_id": stream_id, "clients": set(),
                        "stop": threading.Event(), "ready": threading.Event(),
                        "socket": None, "error": None
                    }
                    streams[key] = ctx
                    by_port[port] = key
                    # threading.Thread(target=receiver, args=(ctx,), name=f"UDPStream-{port}", daemon=True).start()
                    socketio.start_background_task(receiver, ctx)
                ctx["clients"].add(sid)
            
            # Espera breve para confirmar que bind() fue posible.
            ctx["ready"].wait(timeout=2.0)
            if ctx.get("error"):
                with lock:
                    ctx["clients"].discard(sid)
                send_status(sid, False, f"No se pudo abrir el puerto UDP {port}: {ctx['error']}")
                return
            send_status(sid, True, "Conectado. Esperando paquetes UDP...", stream_id=stream_id, sender_ip=sender_ip, udp_port=port)
            
        def disconnect_udp_stream(data):
            from flask import request
            sid = request.sid
            data = data or {}
            try:
                port = int(data.get("udp_port", 0))
                sender_ip = str(data.get("sender_ip", "")).strip()
                stream_id = str(data.get("stream_id") or "camera_01").strip()
            except (TypeError, ValueError):
                send_status(sid, False, "No se pudo identificar la conexión UDP.")
                return
            key = (port, sender_ip, stream_id)
            with lock:
                ctx = streams.get(key)
                if ctx:
                    ctx["clients"].discard(sid)
                    if not ctx["clients"]:
                        # recvfrom tiene timeout de 250 ms; el hilo cerrará el socket.
                        ctx["stop"].set()
            send_status(sid, True, "Desconectado.", stream_id=stream_id, udp_port=port)
        socketio.on_event("udpstream_connect", connect_udp_stream)
        socketio.on_event("udpstream_disconnect", disconnect_udp_stream)
        print("[UDPStream] Eventos dinámicos registrados: udpstream_connect / udpstream_disconnect")
        
    def __init__(self, width=520, height=320):
        self.width, self.height = width, height
        self.props = self.default_props.copy()
        
    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50), "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 520), "height": getattr(self, "height", 320),
            "props": getattr(self, "props", {}), "events": getattr(self, "events", {})
        }
    
    def render_canvas(self, canvas, x, y):
        p = {**self.default_props, **self.props}
        items = [canvas.create_rectangle(x, y, x+self.width, y+self.height,
                                         fill=p["background"], outline="#334155", width=2)]
        if p["show_header"]:
            items.append(canvas.create_text(x+self.width/2, y+18, text=p["label"],
                                            fill="#ffffff", font=("Segoe UI", 10, "bold")))
        items.append(canvas.create_text(x+self.width/2, y+self.height/2,
                                        text=f"UDP VIDEO | :{p['udp_port']}",
                                        fill="#64748b", font=("Segoe UI", 13, "bold")))
        return items
    
    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        try:
            port = int(p.get("udp_port", 5000))
        except (TypeError, ValueError):
            port = 5000
        if not 1 <= port <= 65535:
            port = 5000
        cfg = {
            "id": w_id, "label": str(p["label"]), "stream_id": str(p["stream_id"]),
            "udp_port": port, "sender_ip": str(p.get("sender_ip", "192.168.1.100")),
            "background": p["background"], "object_fit": str(p["object_fit"]).lower(),
            "show_header": bool(p["show_header"]), "show_status": bool(p["show_status"]),
            "show_timestamp": bool(p["show_timestamp"]), "show_fps": bool(p["show_fps"]),
            "show_controls": bool(p["show_controls"]), "placeholder": str(p["placeholder"])
        }
        cfg_json = json.dumps(cfg).replace("<", "\\u003c")
        return f"""
<div id="video_{w_id}" class="video-widget">
  <div class="video-connection">
    <div class="video-config">
      <label>IP del emisor
        <input class="video-ip-input" type="text" spellcheck="false" autocomplete="off">
      </label>
      <label>Puerto UDP
        <input class="video-port-input" type="number" min="1" max="65535" step="1">
      </label>
    </div>
    <button class="video-connect-btn" type="button">Conectar</button>
  </div>
  <div class="video-header"><span class="video-title"></span><span class="video-status">● Desconectado</span></div>
  <div class="video-container"><img class="video-frame" draggable="false"><div class="video-placeholder"></div></div>
  <div class="video-footer"><span class="video-fps"></span><span class="video-timestamp"></span></div>
</div>
<style>
#video_{w_id} {{width:100%;height:100%;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box;background:{p['background']};border-radius:10px;color:white;font-family:'Segoe UI',sans-serif;}}
#video_{w_id} .video-connection {{display:flex;align-items:flex-end;justify-content:space-between;gap:9px;padding:9px 10px;flex-shrink:0;background:rgba(15,23,42,.65);}}
#video_{w_id} .video-config {{display:flex;align-items:flex-end;gap:8px;flex:1;min-width:0;}}
#video_{w_id} .video-config label {{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1;color:#cbd5e1;font-size:10px;font-weight:600;}}
#video_{w_id} .video-config input {{width:100%;min-width:0;box-sizing:border-box;padding:7px 8px;border:1px solid #475569;border-radius:5px;background:#020617;color:#f8fafc;font:12px 'Segoe UI',sans-serif;outline:none;}}
#video_{w_id} .video-config input:focus {{border-color:#3b82f6;}}
#video_{w_id} .video-config input:disabled {{opacity:.55;cursor:not-allowed;}}
#video_{w_id} .video-connect-btn {{padding:8px 14px;border:0;border-radius:5px;background:#16a34a;color:white;font-size:11px;font-weight:700;cursor:pointer;white-space:nowrap;min-width:92px;}}
#video_{w_id} .video-connect-btn:hover {{background:#15803d;}}
#video_{w_id} .video-connect-btn.disconnect {{background:#dc2626;}}
#video_{w_id} .video-connect-btn.disconnect:hover {{background:#b91c1c;}}
#video_{w_id} .video-connect-btn:disabled {{opacity:.6;cursor:wait;}}
#video_{w_id} .video-header {{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;min-height:28px;flex-shrink:0;}}
#video_{w_id} .video-title {{font-size:13px;font-weight:600;}}
#video_{w_id} .video-status {{font-size:11px;color:#f59e0b;white-space:nowrap;}}
#video_{w_id} .video-container {{position:relative;flex:1;min-height:0;overflow:hidden;background:#020617;display:flex;align-items:center;justify-content:center;}}
#video_{w_id} .video-frame {{width:100%;height:100%;object-fit:{p['object_fit'].lower()};display:none;}}
#video_{w_id} .video-placeholder {{position:absolute;color:#64748b;font-size:13px;text-align:center;padding:12px;pointer-events:none;}}
#video_{w_id} .video-footer {{display:flex;justify-content:space-between;padding:5px 10px;font-size:10px;color:#94a3b8;flex-shrink:0;}}
@media (max-width:420px) {{ #video_{w_id} .video-connection {{align-items:stretch;flex-direction:column;}} #video_{w_id} .video-connect-btn {{width:100%;}}}}
</style>
<script>
console.log("[UDPStream] Script cargado");
(function() {{
  const cfg = {cfg_json};
  const root = document.getElementById("video_" + cfg.id);
  if (!root || root.dataset.initialized === "1") return;
  root.dataset.initialized = "1";
  const socket = window.dashboardSocket;
  
  
  console.log("[UDPStream] Inicializando widget:", cfg.stream_id);
  console.log("[UDPStream] dashboardSocket:", window.dashboardSocket);
  
  const btn = root.querySelector(".video-connect-btn");
  const status = root.querySelector(".video-status");
  const img = root.querySelector(".video-frame");
  const placeholder = root.querySelector(".video-placeholder");
  const fpsLabel = root.querySelector(".video-fps");
  const timestamp = root.querySelector(".video-timestamp");
  const title = root.querySelector(".video-title");
  const ipInput = root.querySelector(".video-ip-input");
  const portInput = root.querySelector(".video-port-input");
  title.textContent = cfg.label || "";
  ipInput.value = cfg.sender_ip || "";
  portInput.value = String(cfg.udp_port || 5000);
  placeholder.textContent = cfg.placeholder || "Esperando video...";
  root.querySelector(".video-connection").style.display = cfg.show_controls ? "flex" : "none";
  root.querySelector(".video-header").style.display = cfg.show_header ? "flex" : "none";
  status.style.display = cfg.show_status ? "inline" : "none";
  root.querySelector(".video-footer").style.display = (cfg.show_fps || cfg.show_timestamp) ? "flex" : "none";
  fpsLabel.style.display = cfg.show_fps ? "inline" : "none";
  timestamp.style.display = cfg.show_timestamp ? "inline" : "none";
  let connected = false, connecting = false, gotFrame = false, destroyed = false, lastUrl = null;
  let activeConfig = null, frameCount = 0, fpsStart = performance.now(), frameTimer = null, waitTimer = null;
  function setStatus(msg, color) {{ status.textContent = msg; status.style.color = color; }}
  function clearFrame() {{
    img.style.display = "none"; placeholder.style.display = "block";
    if (lastUrl) {{ URL.revokeObjectURL(lastUrl); lastUrl = null; }}
    img.removeAttribute("src");
  }}
  function setInputsLocked(locked) {{ ipInput.disabled = locked; portInput.disabled = locked; }}
  function showFrame(data) {{
    if (!data || destroyed) return;
    const blob = data instanceof Blob ? data : new Blob([data], {{type:"image/jpeg"}});
    const url = URL.createObjectURL(blob), previous = lastUrl; lastUrl = url;
    img.onload = function() {{
      if (destroyed) {{ URL.revokeObjectURL(url); return; }}
      img.style.display = "block"; placeholder.style.display = "none";
      if (previous) URL.revokeObjectURL(previous);
    }};
    img.onerror = function() {{ if (lastUrl === url) lastUrl = null; URL.revokeObjectURL(url); }};
    img.src = url;
    const now = performance.now(); frameCount++;
    if (now - fpsStart >= 1000) {{
      fpsLabel.textContent = (frameCount * 1000 / (now - fpsStart)).toFixed(1) + " FPS";
      frameCount = 0; fpsStart = now;
    }}
    if (cfg.show_timestamp) timestamp.textContent = new Date().toLocaleTimeString();
  }}
  function handleFrame(data, frame) {{
    console.log("[UDPStream] Evento recibido:", data);
    console.log("[UDPStream] Tipo de frame:", typeof frame);
    console.log("[UDPStream] Constructor:", frame?.constructor?.name);
    console.log("[UDPStream] Tamaño:", frame?.byteLength ?? frame?.length);
    if (!connected || !data || !activeConfig ||
        data.stream_id !== cfg.stream_id) {{
        console.warn("[UDPStream] Frame descartado por configuración");
        return;
    }}
    const jpeg = frame || data.frame;
    if (!jpeg) {{
        console.warn("[UDPStream] No llegó el JPEG");
        return;
    }}
    console.log("[UDPStream] JPEG recibido correctamente");
    gotFrame = true;
    clearTimeout(waitTimer);
    setStatus("● En vivo", "#22c55e");
    showFrame(jpeg);
    clearTimeout(frameTimer);
    frameTimer = setTimeout(function() {{
        if (connected) {{
            setStatus("● Sin señal UDP", "#ef4444");
            clearFrame();
        }}
    }}, 5000);
}}
  function handleStatus(data) {{
    if (!data) return;
    if (data.stream_id && data.stream_id !== cfg.stream_id) return;
    if (connecting && !data.ok) {{
      connecting = false; btn.disabled = false; setInputsLocked(false);
      btn.textContent = "Conectar"; btn.classList.remove("disconnect");
      setStatus("● " + (data.message || "Error de conexión"), "#ef4444");
      return;
    }}
    if (connecting && data.ok) {{
      connecting = false; connected = true; btn.disabled = false;
      btn.textContent = "Desconectar"; btn.classList.add("disconnect"); setInputsLocked(true);
      setStatus("● " + (data.message || "Conectado"), "#f59e0b");
      gotFrame = false;
      waitTimer = setTimeout(function() {{ if (connected && !gotFrame) setStatus("● Sin paquetes UDP", "#f59e0b"); }}, 8000);
      return;
    }}
    if (data.message === "Desconectado.") {{
      connected = false; connecting = false; btn.disabled = false;
      btn.textContent = "Conectar"; btn.classList.remove("disconnect"); setInputsLocked(false);
      clearTimeout(waitTimer); clearTimeout(frameTimer); clearFrame();
      setStatus("● Desconectado", "#94a3b8");
    }}
  }}
  function connect() {{
    if (!socket || typeof socket.emit !== "function") {{ setStatus("● Socket.IO no disponible", "#ef4444"); return; }}
    const ip = ipInput.value.trim();
    const port = Number(portInput.value);
    if (!ip) {{ setStatus("● Introduce la IP del emisor", "#ef4444"); ipInput.focus(); return; }}
    if (!Number.isInteger(port) || port < 1 || port > 65535) {{ setStatus("● Puerto inválido (1–65535)", "#ef4444"); portInput.focus(); return; }}
    activeConfig = {{sender_ip:ip, udp_port:port, stream_id:cfg.stream_id}};
    connecting = true; btn.disabled = true; setStatus("● Conectando...", "#f59e0b");
    socket.emit("udpstream_connect", activeConfig);
  }}
  function disconnect() {{
    if (!socket || typeof socket.emit !== "function" || !activeConfig) return;
    btn.disabled = true; setStatus("● Desconectando...", "#f59e0b");
    socket.emit("udpstream_disconnect", activeConfig);
  }}
  if (socket && typeof socket.on === "function") {{
    console.log("[UDPStream] Registrando listeners");
    console.log("[UDPStream] Socket ID:", socket.id);
    console.log("[UDPStream] Estado inicial:", socket.connected);
    socket.on("connect", function() {{
        console.log("[UDPStream] Conectado:", socket.id);
    }});
    socket.on("disconnect", function(reason) {{
        console.warn("[UDPStream] Desconectado:", reason);
    }});
    socket.on("video_frame", function(data, frame) {{
        console.log("[UDPStream] Evento video_frame recibido");
        handleFrame(data, frame);
    }});
    socket.on("udp_stream_status", function(data) {{
        console.log("[UDPStream] Evento udp_stream_status recibido:", data);
        handleStatus(data);
    }});
    socket.on("video_frame_test", function(data) {{
        console.log("[UDPStream] Evento de prueba recibido:", data);
    }});
}} else {{
    console.error("[UDPStream] dashboardSocket no disponible");
}}
  btn.addEventListener("click", function() {{ if (connected) disconnect(); else if (!connecting) connect(); }});
  root.querySelector(".video-container").addEventListener("click", function() {{
    if (typeof emitEvent === "function") emitEvent({{id:cfg.id,events:{{on_video_click:true}}}}, "on_video_click", {{stream_id:cfg.stream_id,udp_port:activeConfig ? activeConfig.udp_port : Number(portInput.value)}});
  }});
  window.__widgets = window.__widgets || {{}};
  window.__widgets[cfg.id] = {{
    update: function(v) {{
      if (!v || typeof v !== "object") return;
      if (v.label !== undefined) {{ cfg.label = v.label; title.textContent = v.label; }}
      if (v.stream_id !== undefined && v.stream_id !== cfg.stream_id && !connected && !connecting) cfg.stream_id = v.stream_id;
    }},
    destroy: function() {{
      destroyed = true;
      if (connected && activeConfig && socket) socket.emit("udpstream_disconnect", activeConfig);
      connected = false; clearTimeout(waitTimer); clearTimeout(frameTimer);
      if (socket && typeof socket.off === "function") {{ socket.off("video_frame", handleFrame); socket.off("udp_stream_status", handleStatus); }}
      clearFrame(); delete window.__widgets[cfg.id];
    }}
  }};
}})();
</script>
""" 