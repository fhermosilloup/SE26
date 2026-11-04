import ipaddress
import json
import re
import socket
import threading

_HTML = """
<div id="audio_@@SAFE@@" class="aud-widget">
  <div class="aud-head"><span class="aud-title"></span><span class="aud-status"><i class="aud-dot"></i><b class="aud-state">Detenido</b></span></div>
  <div class="aud-row aud-rx">
    <label>Puerto de escucha<input class="aud-port" type="number" min="1" max="65535"></label>
    <label>IP del emisor (vacío = cualquiera)<input class="aud-sender" type="text" spellcheck="false"></label>
    <button class="aud-listen" type="button">Escuchar</button>
  </div>
  <div class="aud-row aud-tx">
    <label>IP destino<input class="aud-dip" type="text" spellcheck="false"></label>
    <label>Puerto destino<input class="aud-dport" type="number" min="1" max="65535"></label>
    <button class="aud-mic" type="button">Enviar micrófono</button>
  </div>
  <div class="aud-meter"><div class="aud-bar"></div></div>
  <div class="aud-row aud-vol"><span>Volumen</span><input class="aud-volume" type="range" min="0" max="100"></div>
  <div class="aud-foot"><span class="aud-rxstat"></span><span class="aud-txstat"></span></div>
</div>
<style>
#audio_@@SAFE@@ {width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;gap:8px;box-sizing:border-box;padding:10px;background:@@BG@@;border:1px solid rgba(255,255,255,.08);border-radius:14px;color:#e2e8f0;font-family:'Segoe UI',sans-serif;overflow:hidden;}
#audio_@@SAFE@@ .aud-head {display:flex;justify-content:space-between;align-items:center;}
#audio_@@SAFE@@ .aud-title {font-size:13px;font-weight:700;color:#fff;}
#audio_@@SAFE@@ .aud-status {display:flex;align-items:center;gap:6px;font-size:11px;}
#audio_@@SAFE@@ .aud-dot {width:9px;height:9px;border-radius:50%;background:#64748b;display:inline-block;}
#audio_@@SAFE@@ .aud-row {display:flex;align-items:flex-end;gap:6px;}
#audio_@@SAFE@@ label {display:flex;flex-direction:column;gap:3px;flex:1;min-width:0;font-size:10px;font-weight:600;color:#94a3b8;}
#audio_@@SAFE@@ input[type=text], #audio_@@SAFE@@ input[type=number] {min-width:0;box-sizing:border-box;padding:6px 8px;border:1px solid #475569;border-radius:6px;background:#020617;color:#f8fafc;font:12px 'Segoe UI',sans-serif;outline:none;}
#audio_@@SAFE@@ input:focus {border-color:#3b82f6;}
#audio_@@SAFE@@ input:disabled {opacity:.55;cursor:not-allowed;}
#audio_@@SAFE@@ button {padding:7px 12px;border:0;border-radius:6px;background:#16a34a;color:#fff;font-size:11px;font-weight:700;cursor:pointer;white-space:nowrap;}
#audio_@@SAFE@@ button:hover {filter:brightness(1.12);}
#audio_@@SAFE@@ button.on {background:#dc2626;}
#audio_@@SAFE@@ .aud-meter {height:10px;background:#020617;border:1px solid #334155;border-radius:6px;overflow:hidden;}
#audio_@@SAFE@@ .aud-bar {height:100%;width:0%;background:linear-gradient(to right,#22c55e,#eab308,#ef4444);transition:width .06s linear;}
#audio_@@SAFE@@ .aud-vol {align-items:center;font-size:10px;color:#94a3b8;}
#audio_@@SAFE@@ .aud-volume {flex:1;accent-color:#3b82f6;}
#audio_@@SAFE@@ .aud-foot {display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;}
</style>
<script>
(function() {
  const cfg = @@CFG@@;
  const root = document.getElementById("audio_" + cfg.safe);
  if (!root || root.dataset.init === "1") return;
  root.dataset.init = "1";
  const socket = window.dashboardSocket;
  const q = (s) => root.querySelector(s);
  const canRx = cfg.mode === "rx" || cfg.mode === "both";
  const canTx = cfg.mode === "tx" || cfg.mode === "both";
  const stateEl = q(".aud-state"), dot = q(".aud-dot"), bar = q(".aud-bar");
  const listenBtn = q(".aud-listen"), micBtn = q(".aud-mic");
  const portIn = q(".aud-port"), senderIn = q(".aud-sender"), dipIn = q(".aud-dip"), dportIn = q(".aud-dport"), volIn = q(".aud-volume");
  const rxStat = q(".aud-rxstat"), txStat = q(".aud-txstat");
  q(".aud-title").textContent = cfg.label;
  portIn.value = cfg.udp_port; senderIn.value = cfg.sender_ip; dipIn.value = cfg.dest_ip; dportIn.value = cfg.dest_port; volIn.value = cfg.volume;
  q(".aud-rx").style.display = (canRx && cfg.show_controls) ? "flex" : "none";
  q(".aud-tx").style.display = (canTx && cfg.show_controls) ? "flex" : "none";
  q(".aud-vol").style.display = canRx ? "flex" : "none";
  q(".aud-meter").style.display = cfg.show_meter ? "block" : "none";
  const COLORS = {listening: "#22c55e", sending: "#3b82f6", connecting: "#f59e0b", error: "#ef4444", stopped: "#64748b"};
  let level = 0;

  function setState(st, msg) {
    dot.style.background = COLORS[st] || "#64748b";
    stateEl.style.color = COLORS[st] || "#94a3b8";
    stateEl.textContent = msg;
  }

  // ---------------- Recepción: UDP -> navegador ----------------
  let actx = null, gain = null, analyser = null, nextTime = 0;
  let listening = false, connecting = false, rxPackets = 0, rxBytes = 0, dropped = 0;

  function ensureCtx() {
    if (!actx) {
      actx = new (window.AudioContext || window.webkitAudioContext)({latencyHint: "interactive"});
      gain = actx.createGain();
      gain.gain.value = volIn.value / 100;
      analyser = actx.createAnalyser();
      analyser.fftSize = 512;
      gain.connect(analyser);
      analyser.connect(actx.destination);
    }
    if (actx.state === "suspended") actx.resume();
  }

  function playPcm(ab) {
    const ch = cfg.channels;
    let f32;
    if (cfg.bits === 8) {
      const u8 = new Uint8Array(ab);
      f32 = new Float32Array(u8.length);
      for (let i = 0; i < u8.length; i++) f32[i] = (u8[i] - 128) / 128;
    } else {
      const n = ab.byteLength >> 1;
      const i16 = new Int16Array(ab, 0, n);
      f32 = new Float32Array(n);
      for (let i = 0; i < n; i++) f32[i] = i16[i] / 32768;
    }
    const frames = Math.floor(f32.length / ch);
    if (!frames) return;
    const abuf = actx.createBuffer(ch, frames, cfg.sample_rate);
    for (let c = 0; c < ch; c++) {
      const d = abuf.getChannelData(c);
      for (let i = 0; i < frames; i++) d[i] = f32[i * ch + c];
    }
    const jitter = cfg.jitter_ms / 1000;
    const now = actx.currentTime;
    if (nextTime < now + 0.01) nextTime = now + jitter;          // se vació el búfer: re-sincroniza
    else if (nextTime - now > jitter * 3 + 0.2) { dropped++; return; } // demasiado atrasado: descarta
    const src = actx.createBufferSource();
    src.buffer = abuf;
    src.connect(gain);
    src.start(nextTime);
    nextTime += abuf.duration;
  }

  function onChunk(meta, buf) {
    if (!listening || !meta || meta.audio_id !== cfg.id || !buf) return;
    const ab = (buf instanceof ArrayBuffer) ? buf
      : (buf.buffer ? buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) : null);
    if (!ab || !actx) return;
    rxPackets++; rxBytes += ab.byteLength;
    playPcm(ab);
  }

  function onStatus(d) {
    if (!d || d.id !== cfg.id) return;
    if (d.state === "listening") {
      listening = true; connecting = false;
      listenBtn.textContent = "Detener"; listenBtn.classList.add("on");
      portIn.disabled = true; senderIn.disabled = true;
      setState("listening", "Escuchando");
    } else if (d.state === "error") {
      listening = false; connecting = false;
      listenBtn.textContent = "Escuchar"; listenBtn.classList.remove("on");
      portIn.disabled = false; senderIn.disabled = false;
      setState("error", d.message || "Error");
    } else {
      listening = false; connecting = false;
      listenBtn.textContent = "Escuchar"; listenBtn.classList.remove("on");
      portIn.disabled = false; senderIn.disabled = false;
      setState("stopped", "Detenido");
    }
  }

  listenBtn.addEventListener("click", function() {
    if (!socket) return;
    if (listening) { socket.emit("udpaudio_stop", {id: cfg.id, udp_port: Number(portIn.value)}); return; }
    if (connecting) return;
    ensureCtx();                       // requiere un gesto del usuario
    nextTime = 0; connecting = true;
    setState("connecting", "Conectando...");
    socket.emit("udpaudio_listen", {id: cfg.id, udp_port: Number(portIn.value), sender_ip: senderIn.value.trim()});
  });
  volIn.addEventListener("input", () => { if (gain) gain.gain.value = volIn.value / 100; });

  // ---------------- Envío: micrófono -> UDP ----------------
  let micStream = null, micCtx = null, micNode = null, sending = false;
  let txPackets = 0, txBytes = 0;
  let pcm = [], acc = 0, cnt = 0, phase = 0, ratio = 1;
  const samplesPerPkt = Math.max(1, Math.round(cfg.sample_rate * cfg.packet_ms / 1000));

  function sendPacket(part) {
    const ch = cfg.channels;
    let out;
    if (cfg.bits === 8) {
      out = new Uint8Array(part.length * ch);
      for (let i = 0; i < part.length; i++) {
        const v = Math.max(0, Math.min(255, Math.round(part[i] * 127 + 128)));
        for (let c = 0; c < ch; c++) out[i * ch + c] = v;
      }
    } else {
      out = new Int16Array(part.length * ch);
      for (let i = 0; i < part.length; i++) {
        const x = Math.max(-1, Math.min(1, part[i]));
        const v = Math.round(x < 0 ? x * 32768 : x * 32767);
        for (let c = 0; c < ch; c++) out[i * ch + c] = v;
      }
    }
    socket.emit("udpaudio_tx", {id: cfg.id, dest_ip: dipIn.value.trim(), dest_port: Number(dportIn.value)}, out.buffer);
    txPackets++; txBytes += out.byteLength;
  }

  function onMic(input) {
    let sum = 0;
    for (let i = 0; i < input.length; i++) {
      const s = input[i];
      sum += s * s; acc += s; cnt++; phase += 1;
      if (phase >= ratio) { pcm.push(acc / cnt); acc = 0; cnt = 0; phase -= ratio; }   // promedio = filtro simple
    }
    level = Math.max(level, Math.sqrt(sum / input.length) * 2);
    while (pcm.length >= samplesPerPkt) sendPacket(pcm.splice(0, samplesPerPkt));
  }

  async function startMic() {
    if (!socket) return;
    if (!navigator.mediaDevices || !window.isSecureContext) {
      setState("error", "El micrófono requiere https o localhost");
      return;
    }
    try {
      micStream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
      micCtx = new (window.AudioContext || window.webkitAudioContext)();
      const code = "class C extends AudioWorkletProcessor{process(i){const c=i[0]&&i[0][0];if(c)this.port.postMessage(c.slice());return true;}}registerProcessor('cap',C);";
      const url = URL.createObjectURL(new Blob([code], {type: "application/javascript"}));
      await micCtx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      const src = micCtx.createMediaStreamSource(micStream);
      micNode = new AudioWorkletNode(micCtx, "cap");
      const mute = micCtx.createGain();
      mute.gain.value = 0;
      src.connect(micNode); micNode.connect(mute); mute.connect(micCtx.destination);
      ratio = Math.max(1, micCtx.sampleRate / cfg.sample_rate);   // el audio del micrófono debe ser >= sample_rate
      pcm = []; acc = 0; cnt = 0; phase = 0;
      micNode.port.onmessage = (e) => onMic(e.data);
      sending = true;
      micBtn.textContent = "Detener envío"; micBtn.classList.add("on");
      dipIn.disabled = true; dportIn.disabled = true;
      setState("sending", "Enviando");
    } catch (err) {
      setState("error", "Micrófono: " + (err && err.message ? err.message : err));
      stopMic();
    }
  }

  function stopMic() {
    sending = false;
    if (micNode) { micNode.port.onmessage = null; try { micNode.disconnect(); } catch (e) {} micNode = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    if (micCtx) { try { micCtx.close(); } catch (e) {} micCtx = null; }
    micBtn.textContent = "Enviar micrófono"; micBtn.classList.remove("on");
    dipIn.disabled = false; dportIn.disabled = false;
    if (!listening && stateEl.textContent === "Enviando") setState("stopped", "Detenido");
  }
  micBtn.addEventListener("click", () => { if (sending) stopMic(); else startMic(); });

  // ---------------- Medidor y estadísticas ----------------
  const timer = setInterval(function() {
    if (analyser && listening) {
      const data = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(data);
      let s = 0;
      for (let i = 0; i < data.length; i++) { const v = (data[i] - 128) / 128; s += v * v; }
      level = Math.max(level, Math.sqrt(s / data.length) * 2);
    }
    bar.style.width = Math.min(100, level * 100) + "%";
    level *= 0.7;
    rxStat.textContent = canRx ? "RX " + rxPackets + " pkt / " + (rxBytes / 1024).toFixed(1) + " KB" + (dropped ? " | descartados " + dropped : "") : "";
    txStat.textContent = canTx ? "TX " + txPackets + " pkt / " + (txBytes / 1024).toFixed(1) + " KB" : "";
  }, 100);

  if (socket && typeof socket.on === "function") {
    socket.on("audio_chunk", onChunk);
    socket.on("udp_audio_status", onStatus);
  } else {
    setState("error", "Socket.IO no disponible");
  }

  window.__widgets = window.__widgets || {};
  window.__widgets[cfg.id] = {
    update: function(v) { if (v && typeof v === "object" && v.label !== undefined) { cfg.label = v.label; q(".aud-title").textContent = v.label; } },
    update_prop: function(p, v) { if (p === "label") { cfg.label = v; q(".aud-title").textContent = v; } },
    destroy: function() {
      clearInterval(timer); stopMic();
      if (listening && socket) socket.emit("udpaudio_stop", {id: cfg.id, udp_port: Number(portIn.value)});
      if (socket && typeof socket.off === "function") { socket.off("audio_chunk", onChunk); socket.off("udp_audio_status", onStatus); }
      if (actx) { try { actx.close(); } catch (e) {} }
      delete window.__widgets[cfg.id];
    }
  };
})();
</script>
"""


class UDPAudioStream:
    default_props = {
        "label": "Audio", "mode": "Recibir", "udp_port": 6000, "sender_ip": "",
        "dest_ip": "192.168.1.50", "dest_port": 6001, "sample_rate": 16000,
        "channels": 1, "sample_format": "PCM 16-bit", "header_bytes": 0,
        "jitter_ms": 120, "packet_ms": 20, "volume": 100,
        "show_controls": True, "show_meter": True, "background": "#111827"
    }
    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "mode", "label": "Modo:", "type": "select", "options": ["Recibir", "Enviar", "Ambos"]},
        {"name": "udp_port", "label": "Puerto UDP de escucha:", "type": "number"},
        {"name": "sender_ip", "label": "IP del emisor (vacío = cualquiera):", "type": "text"},
        {"name": "dest_ip", "label": "IP destino (modo Enviar):", "type": "text"},
        {"name": "dest_port", "label": "Puerto destino (modo Enviar):", "type": "number"},
        {"name": "sample_rate", "label": "Frecuencia de muestreo (Hz):", "type": "number"},
        {"name": "channels", "label": "Canales:", "type": "select", "options": ["1", "2"]},
        {"name": "sample_format", "label": "Formato de muestra:", "type": "select", "options": ["PCM 16-bit", "PCM 8-bit"]},
        {"name": "header_bytes", "label": "Bytes de cabecera a descartar:", "type": "number"},
        {"name": "jitter_ms", "label": "Búfer de reproducción (ms):", "type": "number"},
        {"name": "packet_ms", "label": "Duración por paquete al enviar (ms):", "type": "number"},
        {"name": "volume", "label": "Volumen inicial (0-100):", "type": "number"},
        {"name": "show_controls", "label": "Mostrar controles:", "type": "boolean"},
        {"name": "show_meter", "label": "Mostrar medidor:", "type": "boolean"},
        {"name": "background", "label": "Color de fondo:", "type": "color"}
    ]
    supported_events = []

    @staticmethod
    def register_backend(app, socketio, project_data):
        lock = threading.RLock()
        listeners = {}                      # puerto UDP -> contexto
        tx = {"sock": None}

        def sid_of():
            from flask import request
            return request.sid

        def status(sid, wid, state, message=""):
            socketio.emit("udp_audio_status", {"id": wid, "state": state, "message": message}, to=sid)

        def receiver(ctx):
            port = ctx["port"]
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                udp.bind(("0.0.0.0", port))
                udp.settimeout(0.25)
            except OSError as exc:
                ctx["error"] = str(exc)
                ctx["ready"].set()
                udp.close()
                with lock:
                    if listeners.get(port) is ctx:
                        listeners.pop(port, None)
                return
            ctx["ready"].set()
            print(f"[UDPAudio] Escuchando en 0.0.0.0:{port}")
            meta = {"audio_id": ctx["wid"], "port": port}
            try:
                while not ctx["stop"].is_set():
                    try:
                        packet, addr = udp.recvfrom(65535)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if ctx["sender_ip"] and addr[0] != ctx["sender_ip"]:
                        continue
                    payload = packet[ctx["header"]:]
                    if len(payload) < 2:
                        continue
                    with lock:
                        recipients = list(ctx["clients"])
                    for sid in recipients:
                        try:
                            socketio.emit("audio_chunk", (meta, payload), to=sid)
                        except Exception as exc:
                            print(f"[UDPAudio] Error Socket.IO: {exc}")
            finally:
                udp.close()
                with lock:
                    if listeners.get(port) is ctx:
                        listeners.pop(port, None)
                print(f"[UDPAudio] Receptor detenido en UDP :{port}")

        def h_listen(data):
            sid = sid_of()
            data = data or {}
            wid = str(data.get("id", ""))
            try:
                port = int(data.get("udp_port", 6000))
                if not 1 <= port <= 65535:
                    raise ValueError("El puerto debe estar entre 1 y 65535.")
                sender_ip = str(data.get("sender_ip", "")).strip()
                if sender_ip:
                    ipaddress.ip_address(sender_ip)
            except (TypeError, ValueError) as exc:
                status(sid, wid, "error", f"Configuración inválida: {exc}")
                return
            header = 0
            for w in (project_data.get("widgets", []) if isinstance(project_data, dict) else []):
                if w.get("id") == wid:
                    try:
                        header = max(0, int((w.get("props") or {}).get("header_bytes", 0)))
                    except (TypeError, ValueError):
                        header = 0
            with lock:
                ctx = listeners.get(port)
                if ctx is not None and (ctx["wid"] != wid or ctx["sender_ip"] != sender_ip):
                    status(sid, wid, "error", f"El puerto UDP {port} ya lo usa otra configuración.")
                    return
                if ctx is None:
                    ctx = {"port": port, "wid": wid, "sender_ip": sender_ip, "header": header,
                           "clients": set(), "stop": threading.Event(),
                           "ready": threading.Event(), "error": None}
                    listeners[port] = ctx
                    socketio.start_background_task(receiver, ctx)
                ctx["clients"].add(sid)
            ctx["ready"].wait(timeout=2.0)
            if ctx.get("error"):
                with lock:
                    ctx["clients"].discard(sid)
                status(sid, wid, "error", f"No se pudo abrir el puerto UDP {port}: {ctx['error']}")
                return
            status(sid, wid, "listening", "Escuchando")

        def h_stop(data):
            sid = sid_of()
            data = data or {}
            wid = str(data.get("id", ""))
            try:
                port = int(data.get("udp_port", 0))
            except (TypeError, ValueError):
                port = 0
            with lock:
                ctx = listeners.get(port)
                if ctx:
                    ctx["clients"].discard(sid)
                    if not ctx["clients"]:
                        ctx["stop"].set()
            status(sid, wid, "stopped", "Detenido")

        def h_tx(meta, data=None):
            # Solo se permite enviar a direcciones de red local / loopback.
            try:
                if not isinstance(data, (bytes, bytearray, memoryview)):
                    return
                data = bytes(data)
                if not data or len(data) > 8192:
                    return
                ip = ipaddress.ip_address(str((meta or {}).get("dest_ip", "")).strip())
                port = int((meta or {}).get("dest_port"))
                if ip.version != 4 or not 1 <= port <= 65535:
                    return
                if not (ip.is_private or ip.is_loopback or ip.is_link_local):
                    return
                with lock:
                    if tx["sock"] is None:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        tx["sock"] = s
                    s = tx["sock"]
                s.sendto(data, (str(ip), port))
            except (TypeError, ValueError, OSError):
                pass

        socketio.on_event("udpaudio_listen", h_listen)
        socketio.on_event("udpaudio_stop", h_stop)
        socketio.on_event("udpaudio_tx", h_tx)
        print("[UDPAudio] Eventos registrados: udpaudio_listen / udpaudio_stop / udpaudio_tx")

    def __init__(self, width=420, height=230):
        self.width, self.height = width, height
        self.props = self.default_props.copy()

    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50), "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 420), "height": getattr(self, "height", 230),
            "props": getattr(self, "props", {}), "events": getattr(self, "events", {})
        }

    def render_canvas(self, canvas, x, y):
        p = {**self.default_props, **self.props}
        items = [canvas.create_rectangle(x, y, x + self.width, y + self.height,
                                         fill=p["background"], outline="#1f2937", width=2)]
        items.append(canvas.create_text(x + 14, y + 16, anchor="w", text=p["label"],
                                        fill="#ffffff", font=("Segoe UI", 10, "bold")))
        # Barras tipo ecualizador
        n, bw = 14, (self.width - 40) / 14
        for i in range(n):
            h = 10 + ((i * 37) % 9) * 6
            bx = x + 20 + i * bw
            items.append(canvas.create_rectangle(bx, y + self.height / 2 + 30 - h, bx + bw - 4,
                                                 y + self.height / 2 + 30, fill="#3b82f6", outline=""))
        items.append(canvas.create_text(x + self.width / 2, y + self.height - 16,
                                        text=f"UDP AUDIO | {p['mode']} :{p['udp_port']}",
                                        fill="#64748b", font=("Segoe UI", 10, "bold")))
        return items

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}

        def num(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(float(p.get(key, default)))))
            except (TypeError, ValueError):
                return default

        m = str(p["mode"]).lower()
        mode = "tx" if m.startswith("env") else ("both" if m.startswith("amb") else "rx")
        cfg = {
            "id": str(w_id), "safe": re.sub(r"\W", "_", str(w_id)), "label": str(p["label"]),
            "mode": mode, "udp_port": num("udp_port", 6000, 1, 65535),
            "sender_ip": str(p.get("sender_ip") or ""),
            "dest_ip": str(p.get("dest_ip") or ""), "dest_port": num("dest_port", 6001, 1, 65535),
            "sample_rate": num("sample_rate", 16000, 8000, 48000),
            "channels": 2 if str(p.get("channels")) == "2" else 1,
            "bits": 8 if "8" in str(p.get("sample_format")) else 16,
            "jitter_ms": num("jitter_ms", 120, 20, 2000),
            "packet_ms": num("packet_ms", 20, 5, 200),
            "volume": num("volume", 100, 0, 100),
            "show_controls": str(p.get("show_controls")).lower() not in ("false", "0", "no"),
            "show_meter": str(p.get("show_meter")).lower() not in ("false", "0", "no")
        }
        cfg_json = json.dumps(cfg).replace("<", "\\u003c")
        return (_HTML.replace("@@SAFE@@", cfg["safe"])
                     .replace("@@BG@@", str(p["background"]))
                     .replace("@@CFG@@", cfg_json))
