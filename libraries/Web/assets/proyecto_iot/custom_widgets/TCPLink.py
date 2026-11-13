import json
import re
import socket
import struct
import sys
import threading
import time
import traceback
import types

# ---------------------------------------------------------------------------
# Estado compartido. Vive en sys.modules para que los callbacks registrados
# desde tu código externo y el widget cargado por el AppBuilder usen el MISMO
# registro, aunque este archivo se importe con nombres distintos.
# ---------------------------------------------------------------------------
_S = sys.modules.get("_tcplink_shared")
if _S is None:
    _S = types.ModuleType("_tcplink_shared")
    _S.callbacks = {"on_packet": {}, "on_connect": {}, "on_disconnect": {}}
    _S.links = {}
    _S.lock = threading.RLock()
    _S.socketio = None
    _S.dispatcher = None
    sys.modules["_tcplink_shared"] = _S

_DEFAULTS = {
    "mode": "client", "host": "192.168.1.50", "port": 5000,
    "framing": "raw", "delimiter": "\\n", "frame_size": 16,
    "auto_reconnect": True, "parse_json": False, "link_name": ""
}
_MAX_BUF = 4 * 1024 * 1024


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "si", "sí", "on")
    return bool(v)


def _unescape(s):
    s = "" if s is None else str(s)
    return (s.replace("\\r", "\r").replace("\\n", "\n")
             .replace("\\t", "\t").replace("\\0", "\0"))


def _framing_key(v):
    s = str(v).lower()
    if "4" in s:
        return "length4"
    if "2" in s:
        return "length2"
    if "lín" in s or "lin" in s:
        return "line"
    if "fij" in s or "fixed" in s:
        return "fixed"
    return "raw"


def _norm(cfg):
    c = dict(_DEFAULTS)
    c.update({k: v for k, v in cfg.items() if k in _DEFAULTS and v is not None})
    c["mode"] = "server" if str(c["mode"]).lower().startswith(("serv", "listen")) else "client"
    c["host"] = str(c["host"]).strip() or "127.0.0.1"
    c["port"] = int(c["port"])
    if not 1 <= c["port"] <= 65535:
        raise ValueError("El puerto debe estar entre 1 y 65535.")
    c["framing"] = _framing_key(c["framing"])
    c["delimiter"] = _unescape(c["delimiter"]) or "\n"
    c["frame_size"] = max(1, int(c["frame_size"] or 16))
    c["auto_reconnect"] = _truthy(c["auto_reconnect"])
    c["parse_json"] = _truthy(c["parse_json"])
    c["link_name"] = str(c["link_name"] or "").strip()
    return c


class _Framer:
    """Convierte el flujo TCP en paquetes lógicos según el framing elegido."""

    def __init__(self, kind, delimiter, size):
        self.kind = kind
        self.delim = delimiter.encode("utf-8") or b"\n"
        self.size = size
        self.buf = bytearray()

    def feed(self, chunk):
        if self.kind == "raw":
            return [bytes(chunk)]
        self.buf += chunk
        out = []
        if self.kind == "line":
            while True:
                i = self.buf.find(self.delim)
                if i < 0:
                    break
                pkt = bytes(self.buf[:i])
                del self.buf[:i + len(self.delim)]
                if self.delim == b"\n" and pkt.endswith(b"\r"):
                    pkt = pkt[:-1]
                out.append(pkt)
        elif self.kind in ("length4", "length2"):
            n, fmt = (4, "!I") if self.kind == "length4" else (2, "!H")
            while len(self.buf) >= n:
                (ln,) = struct.unpack(fmt, bytes(self.buf[:n]))
                if ln > _MAX_BUF:
                    self.buf.clear()
                    break
                if len(self.buf) < n + ln:
                    break
                out.append(bytes(self.buf[n:n + ln]))
                del self.buf[:n + ln]
        elif self.kind == "fixed":
            while len(self.buf) >= self.size:
                out.append(bytes(self.buf[:self.size]))
                del self.buf[:self.size]
        if len(self.buf) > _MAX_BUF:
            self.buf.clear()
        return out


def _frame_out(link, data):
    cfg = link["cfg"]
    k = cfg["framing"]
    if k == "length4":
        return struct.pack("!I", len(data)) + data
    if k == "length2":
        return struct.pack("!H", len(data)) + data
    if k == "line":
        d = cfg["delimiter"].encode("utf-8")
        return data if data.endswith(d) else data + d
    if k == "fixed":
        return data[:cfg["frame_size"]].ljust(cfg["frame_size"], b"\0")
    return data


class Packet:
    """Lo que recibe tu callback en cada evento."""

    def __init__(self, link, data, peer, event="on_packet"):
        self.event = event
        self.widget_id = link["id"]
        self.name = link["cfg"].get("link_name") or link["id"]
        self.data = data                      # bytes
        self.peer = peer                      # (ip, puerto)
        self.ts = time.time()
        self.text = data.decode("utf-8", errors="replace")
        self.json = None
        if data and link["cfg"]["parse_json"]:
            try:
                self.json = json.loads(self.text)
            except ValueError:
                pass

    @property
    def hex(self):
        return self.data.hex(" ")

    def reply(self, data, frame=True):
        """Responde al mismo par que envió el paquete."""
        return TCPLink.send(self.widget_id, data, peer=self.peer, frame=frame)

    def __repr__(self):
        return f"<Packet {self.event} {self.name} {self.peer} {len(self.data)} B>"


def _emit(event, payload):
    sio = _S.socketio
    if sio is None:
        return
    try:
        sio.emit(event, payload)
    except Exception:
        pass


def _status(link, state=None, message=""):
    if state:
        link["state"] = state
    link["last_stats"] = time.monotonic()
    _emit("tcp_status", {
        "id": link["id"], "state": link["state"], "message": message,
        "mode": link["cfg"]["mode"], "peers": len(link["conns"]),
        "rx_packets": link["rx_packets"], "tx_packets": link["tx_packets"],
        "rx_bytes": link["rx_bytes"], "tx_bytes": link["tx_bytes"]
    })


def _ui_data(link, direction, payload, peer):
    now = time.monotonic()
    if direction == "tx" or now - link["last_ui"] >= 0.02:
        link["last_ui"] = now
        view = payload[:512]
        _emit("tcp_data", {
            "id": link["id"], "dir": direction, "size": len(payload),
            "text": view.decode("utf-8", errors="replace"), "hex": view.hex(" "),
            "peer": f"{peer[0]}:{peer[1]}", "ts": time.strftime("%H:%M:%S")
        })
    if now - link["last_stats"] >= 1.0:
        _status(link)


def _fire(kind, link, pkt):
    cbs = []
    with _S.lock:
        for key in (link["id"], link["cfg"].get("link_name"), "*"):
            if key:
                cbs.extend(_S.callbacks[kind].get(key, ()))
    for cb in cbs:
        try:
            cb(pkt)
        except Exception:
            print(f"[TCPLink] Error en callback {kind} de {link['id']}:")
            traceback.print_exc()
    disp = _S.dispatcher
    if disp:
        try:
            disp(link["id"], kind, pkt)
        except Exception:
            traceback.print_exc()


def _new_link(wid, cfg):
    return {
        "id": wid, "cfg": cfg, "stop": threading.Event(),
        "lock": threading.RLock(), "send_lock": threading.Lock(),
        "conns": [], "server": None, "running": True, "state": "disconnected",
        "rx_packets": 0, "tx_packets": 0, "rx_bytes": 0, "tx_bytes": 0,
        "last_ui": 0.0, "last_stats": 0.0
    }


def _resolve(ref):
    with _S.lock:
        link = _S.links.get(ref)
        if link:
            return link
        for link in _S.links.values():
            if link["cfg"].get("link_name") == ref:
                return link
    return None


def _serve_conn(link, sock, addr):
    cfg = link["cfg"]
    framer = _Framer(cfg["framing"], cfg["delimiter"], cfg["frame_size"])
    entry = (sock, addr)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    sock.settimeout(0.5)
    with link["lock"]:
        link["conns"].append(entry)
    _status(link, "connected", f"Conectado con {addr[0]}:{addr[1]}")
    _fire("on_connect", link, Packet(link, b"", addr, "on_connect"))
    try:
        while not link["stop"].is_set():
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            with link["lock"]:
                link["rx_bytes"] += len(chunk)
            for payload in framer.feed(chunk):
                with link["lock"]:
                    link["rx_packets"] += 1
                _ui_data(link, "rx", payload, addr)
                _fire("on_packet", link, Packet(link, payload, addr))
    finally:
        with link["lock"]:
            if entry in link["conns"]:
                link["conns"].remove(entry)
        try:
            sock.close()
        except OSError:
            pass
        _fire("on_disconnect", link, Packet(link, b"", addr, "on_disconnect"))
        if cfg["mode"] == "server" and not link["stop"].is_set():
            _status(link, "listening" if not link["conns"] else "connected", "Conexión cerrada")
        else:
            _status(link, "disconnected", "Conexión cerrada")


def _finish(link, message="Desconectado."):
    link["running"] = False
    with link["lock"]:
        conns = list(link["conns"])
    for sock, _ in conns:
        try:
            sock.close()
        except OSError:
            pass
    if link["state"] != "error":
        _status(link, "disconnected", message)
    else:
        _status(link)


def _client_loop(link):
    cfg = link["cfg"]
    while not link["stop"].is_set():
        _status(link, "connecting", f"Conectando a {cfg['host']}:{cfg['port']}...")
        try:
            sock = socket.create_connection((cfg["host"], cfg["port"]), timeout=5)
        except OSError as exc:
            _status(link, "error", f"No se pudo conectar: {exc}")
            if not cfg["auto_reconnect"]:
                break
            link["stop"].wait(2.0)
            continue
        try:
            addr = sock.getpeername()[:2]
        except OSError:
            addr = (cfg["host"], cfg["port"])
        _serve_conn(link, sock, addr)
        if not cfg["auto_reconnect"]:
            break
        link["stop"].wait(2.0)
    _finish(link)


def _server_loop(link):
    cfg = link["cfg"]
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", cfg["port"]))
        srv.listen(8)
        srv.settimeout(0.5)
    except OSError as exc:
        srv.close()
        _status(link, "error", f"No se pudo abrir el puerto {cfg['port']}: {exc}")
        _finish(link)
        return
    link["server"] = srv
    _status(link, "listening", f"Escuchando en el puerto {cfg['port']}")
    while not link["stop"].is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        _S.socketio.start_background_task(_serve_conn, link, conn, addr[:2])
    try:
        srv.close()
    except OSError:
        pass
    _finish(link)


_HTML = """
<div id="tcp_@@SAFE@@" class="tcp-widget">
  <div class="tcp-head"><span class="tcp-title"></span>
    <span class="tcp-status"><i class="tcp-dot"></i><b class="tcp-state">Desconectado</b></span></div>
  <div class="tcp-conn">
    <select class="tcp-mode"><option value="client">Cliente</option><option value="server">Servidor</option></select>
    <input class="tcp-host" type="text" spellcheck="false" placeholder="IP / host">
    <input class="tcp-port" type="number" min="1" max="65535">
    <button class="tcp-btn" type="button">Conectar</button>
  </div>
  <pre class="tcp-log"></pre>
  <div class="tcp-send">
    <input class="tcp-input" type="text" spellcheck="false" placeholder="Dato a enviar">
    <select class="tcp-fmt"><option>Texto</option><option>Hex</option></select>
    <button class="tcp-sendbtn" type="button">Enviar</button>
  </div>
  <div class="tcp-foot"><span class="tcp-counters"></span>
    <span><button class="tcp-view" type="button">Texto</button><button class="tcp-clear" type="button">Limpiar</button></span></div>
</div>
<style>
#tcp_@@SAFE@@ {width:100%;height:100%;display:flex;flex-direction:column;gap:6px;box-sizing:border-box;padding:10px;background:@@BG@@;border:1px solid rgba(255,255,255,.08);border-radius:14px;color:#e2e8f0;font-family:'Segoe UI',sans-serif;overflow:hidden;}
#tcp_@@SAFE@@ .tcp-head {display:flex;justify-content:space-between;align-items:center;flex-shrink:0;}
#tcp_@@SAFE@@ .tcp-title {font-size:13px;font-weight:700;color:#fff;}
#tcp_@@SAFE@@ .tcp-status {display:flex;align-items:center;gap:6px;font-size:11px;}
#tcp_@@SAFE@@ .tcp-dot {width:9px;height:9px;border-radius:50%;background:#64748b;display:inline-block;}
#tcp_@@SAFE@@ .tcp-conn, #tcp_@@SAFE@@ .tcp-send {display:flex;gap:6px;flex-shrink:0;}
#tcp_@@SAFE@@ input, #tcp_@@SAFE@@ select {min-width:0;box-sizing:border-box;padding:6px 8px;border:1px solid #475569;border-radius:6px;background:#020617;color:#f8fafc;font:12px 'Segoe UI',sans-serif;outline:none;}
#tcp_@@SAFE@@ input:focus, #tcp_@@SAFE@@ select:focus {border-color:#3b82f6;}
#tcp_@@SAFE@@ input:disabled, #tcp_@@SAFE@@ select:disabled {opacity:.55;cursor:not-allowed;}
#tcp_@@SAFE@@ .tcp-host, #tcp_@@SAFE@@ .tcp-input {flex:1;}
#tcp_@@SAFE@@ .tcp-port {width:70px;}
#tcp_@@SAFE@@ button {padding:6px 12px;border:0;border-radius:6px;background:#2563eb;color:#fff;font-size:11px;font-weight:700;cursor:pointer;white-space:nowrap;}
#tcp_@@SAFE@@ button:hover {filter:brightness(1.12);}
#tcp_@@SAFE@@ .tcp-btn.stop {background:#dc2626;}
#tcp_@@SAFE@@ .tcp-view, #tcp_@@SAFE@@ .tcp-clear {background:#1e293b;margin-left:4px;padding:3px 8px;font-size:10px;}
#tcp_@@SAFE@@ .tcp-log {flex:1;min-height:0;margin:0;padding:8px;overflow:auto;background:#020617;border-radius:8px;font:11px/1.45 Consolas,'Courier New',monospace;color:#cbd5e1;white-space:pre-wrap;word-break:break-all;}
#tcp_@@SAFE@@ .tcp-foot {display:flex;justify-content:space-between;align-items:center;font-size:10px;color:#94a3b8;flex-shrink:0;}
</style>
<script>
(function() {
  const cfg = @@CFG@@;
  const root = document.getElementById("tcp_" + cfg.safe);
  if (!root || root.dataset.init === "1") return;
  root.dataset.init = "1";
  const socket = window.dashboardSocket;
  const q = (s) => root.querySelector(s);
  const title = q(".tcp-title"), stateEl = q(".tcp-state"), dot = q(".tcp-dot");
  const modeSel = q(".tcp-mode"), hostIn = q(".tcp-host"), portIn = q(".tcp-port"), btn = q(".tcp-btn");
  const logEl = q(".tcp-log"), sendIn = q(".tcp-input"), fmtSel = q(".tcp-fmt"), sendBtn = q(".tcp-sendbtn");
  const counters = q(".tcp-counters"), viewBtn = q(".tcp-view"), clearBtn = q(".tcp-clear");

  title.textContent = cfg.label;
  modeSel.value = cfg.mode; hostIn.value = cfg.host; portIn.value = cfg.port; fmtSel.value = cfg.send_format;
  q(".tcp-conn").style.display = cfg.show_controls ? "flex" : "none";
  q(".tcp-send").style.display = cfg.show_controls ? "flex" : "none";
  logEl.style.display = cfg.show_log ? "block" : "none";
  let hexView = cfg.log_view === "hex", running = false;
  viewBtn.textContent = hexView ? "Hex" : "Texto";
  const entries = [];
  const COLORS = {connected: "#22c55e", listening: "#22c55e", connecting: "#f59e0b", error: "#ef4444", disconnected: "#64748b"};
  const LABELS = {connected: "Conectado", listening: "Escuchando", connecting: "Conectando...", error: "Error", disconnected: "Desconectado"};

  function syncMode() { hostIn.style.display = modeSel.value === "server" ? "none" : "block"; }
  function renderLog() {
    logEl.textContent = entries.map(e => {
      const arrow = e.dir === "rx" ? "RX <-" : e.dir === "tx" ? "TX ->" : "INFO";
      if (e.dir === "info") return "[" + e.ts + "] " + e.text;
      return "[" + e.ts + "] " + arrow + " " + e.peer + " (" + e.size + " B) " + (hexView ? e.hex : e.text);
    }).join("\\n");
    logEl.scrollTop = logEl.scrollHeight;
  }
  function pushEntry(e) {
    entries.push(e);
    while (entries.length > cfg.max_log_lines) entries.shift();
    renderLog();
  }
  function setStatus(d) {
    const st = d.state || "disconnected";
    running = ["connecting", "connected", "listening"].includes(st);
    dot.style.background = COLORS[st] || "#64748b";
    stateEl.textContent = LABELS[st] || st;
    stateEl.style.color = COLORS[st] || "#94a3b8";
    btn.textContent = running ? "Desconectar" : "Conectar";
    btn.classList.toggle("stop", running);
    modeSel.disabled = running; hostIn.disabled = running; portIn.disabled = running;
    if (d.mode) { modeSel.value = d.mode; syncMode(); }
    counters.textContent = "RX " + (d.rx_packets || 0) + " pkt / " + (d.rx_bytes || 0) + " B  |  TX " + (d.tx_packets || 0) + " pkt / " + (d.tx_bytes || 0) + " B" + (d.peers ? "  |  " + d.peers + " conexión(es)" : "");
    if (d.message) pushEntry({dir: "info", ts: new Date().toLocaleTimeString(), text: d.message});
  }
  function onStatus(d) { if (d && d.id === cfg.id) setStatus(d); }
  function onData(d) { if (d && d.id === cfg.id) pushEntry(d); }

  btn.addEventListener("click", function() {
    if (!socket) return;
    if (running) { socket.emit("tcplink_disconnect", {id: cfg.id}); return; }
    socket.emit("tcplink_connect", {
      id: cfg.id, mode: modeSel.value, host: hostIn.value.trim(), port: Number(portIn.value),
      framing: cfg.framing, delimiter: cfg.delimiter, frame_size: cfg.frame_size,
      auto_reconnect: cfg.auto_reconnect, parse_json: cfg.parse_json, link_name: cfg.link_name
    });
  });
  function doSend() {
    const v = sendIn.value;
    if (!socket || v === "") return;
    socket.emit("tcplink_send", {id: cfg.id, data: v, format: fmtSel.value, suffix: cfg.tx_suffix});
    sendIn.value = "";
  }
  sendBtn.addEventListener("click", doSend);
  sendIn.addEventListener("keydown", e => { if (e.key === "Enter") doSend(); });
  viewBtn.addEventListener("click", () => { hexView = !hexView; viewBtn.textContent = hexView ? "Hex" : "Texto"; renderLog(); });
  clearBtn.addEventListener("click", () => { entries.length = 0; renderLog(); });
  modeSel.addEventListener("change", syncMode);
  syncMode();

  if (socket && typeof socket.on === "function") {
    socket.on("tcp_status", onStatus);
    socket.on("tcp_data", onData);
    const ask = () => socket.emit("tcplink_state", {id: cfg.id});
    socket.on("connect", ask);
    if (socket.connected) ask();
  } else {
    stateEl.textContent = "Socket.IO no disponible";
  }

  window.__widgets = window.__widgets || {};
  window.__widgets[cfg.id] = {
    update: function(v) { if (v && typeof v === "object" && v.label !== undefined) { cfg.label = v.label; title.textContent = v.label; } },
    update_prop: function(p, v) { if (p === "label") { cfg.label = v; title.textContent = v; } },
    destroy: function() {
      if (socket && typeof socket.off === "function") { socket.off("tcp_status", onStatus); socket.off("tcp_data", onData); }
      delete window.__widgets[cfg.id];
    }
  };
})();
</script>
"""


class TCPLink:
    default_props = {
        "label": "TCP Link", "link_name": "tcp_01", "mode": "Cliente",
        "host": "192.168.1.50", "port": 5000, "framing": "Raw",
        "delimiter": "\\n", "frame_size": 16, "auto_connect": False,
        "auto_reconnect": True, "parse_json": False, "show_controls": True,
        "show_log": True, "log_view": "Texto", "max_log_lines": 200,
        "send_format": "Texto", "tx_suffix": "", "background": "#111827"
    }
    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "link_name", "label": "Nombre del enlace (para callbacks):", "type": "text"},
        {"name": "mode", "label": "Modo:", "type": "select", "options": ["Cliente", "Servidor"]},
        {"name": "host", "label": "Host / IP remota (modo cliente):", "type": "text"},
        {"name": "port", "label": "Puerto TCP:", "type": "number"},
        {"name": "framing", "label": "Separación de paquetes:", "type": "select",
         "options": ["Raw", "Línea", "Longitud 4 bytes", "Longitud 2 bytes", "Tamaño fijo"]},
        {"name": "delimiter", "label": "Delimitador (modo Línea):", "type": "text"},
        {"name": "frame_size", "label": "Tamaño (modo Tamaño fijo):", "type": "number"},
        {"name": "auto_connect", "label": "Conectar al iniciar el servidor:", "type": "boolean"},
        {"name": "auto_reconnect", "label": "Reconectar automáticamente:", "type": "boolean"},
        {"name": "parse_json", "label": "Intentar parsear JSON:", "type": "boolean"},
        {"name": "show_controls", "label": "Mostrar controles:", "type": "boolean"},
        {"name": "show_log", "label": "Mostrar registro:", "type": "boolean"},
        {"name": "log_view", "label": "Vista del registro:", "type": "select", "options": ["Texto", "Hex"]},
        {"name": "max_log_lines", "label": "Líneas máximas del registro:", "type": "number"},
        {"name": "send_format", "label": "Formato de envío:", "type": "select", "options": ["Texto", "Hex"]},
        {"name": "tx_suffix", "label": "Sufijo al enviar (ej. \\r\\n):", "type": "text"},
        {"name": "background", "label": "Color de fondo:", "type": "color"}
    ]
    # Se ejecutan en el SERVIDOR (callbacks de Python), ver TCPLink.on_packet(...)
    supported_events = ["on_packet", "on_connect", "on_disconnect"]

    # ------------------------------------------------------------------
    # API para tu código externo
    # ------------------------------------------------------------------
    @staticmethod
    def _register(kind, widget_id):
        def deco(fn):
            with _S.lock:
                _S.callbacks[kind].setdefault(str(widget_id), []).append(fn)
            return fn
        return deco

    @staticmethod
    def on_packet(widget_id="*"):
        """Decorador: se llama por cada paquete completo recibido."""
        return TCPLink._register("on_packet", widget_id)

    @staticmethod
    def on_connect(widget_id="*"):
        return TCPLink._register("on_connect", widget_id)

    @staticmethod
    def on_disconnect(widget_id="*"):
        return TCPLink._register("on_disconnect", widget_id)

    @staticmethod
    def set_dispatcher(fn):
        """fn(widget_id, event_name, packet): puente hacia tu sistema de eventos."""
        _S.dispatcher = fn

    @staticmethod
    def connect(widget_id, **cfg):
        if _S.socketio is None:
            raise RuntimeError("TCPLink.register_backend aún no se ha ejecutado.")
        wid = str(widget_id)
        link = _resolve(wid)
        if link and link["running"]:
            if not link["stop"].is_set():
                return link
            deadline = time.monotonic() + 2.0
            while link["running"] and time.monotonic() < deadline:
                time.sleep(0.05)
        with _S.lock:
            old = _S.links.get(wid)
            merged = {**(old["cfg"] if old else {}), **cfg}
            link = _new_link(wid, _norm(merged))
            _S.links[wid] = link
        loop = _server_loop if link["cfg"]["mode"] == "server" else _client_loop
        _S.socketio.start_background_task(loop, link)
        return link

    @staticmethod
    def disconnect(widget_id):
        link = _resolve(str(widget_id))
        if link:
            link["stop"].set()
            with link["lock"]:
                conns = list(link["conns"])
            for sock, _ in conns:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    @staticmethod
    def send(widget_id, data, peer=None, frame=True):
        """Envía datos. Con frame=True aplica el framing del enlace."""
        link = _resolve(str(widget_id))
        if link is None:
            return 0
        if isinstance(data, str):
            data = data.encode("utf-8")
        data = bytes(data)
        wire = _frame_out(link, data) if frame else data
        with link["lock"]:
            targets = [c for c in link["conns"]
                       if peer is None or tuple(c[1])[:2] == tuple(peer)[:2]]
        sent = []
        with link["send_lock"]:
            for sock, addr in targets:
                try:
                    sock.sendall(wire)
                    sent.append(addr)
                except OSError:
                    try:
                        sock.close()
                    except OSError:
                        pass
        if sent:
            with link["lock"]:
                link["tx_packets"] += len(sent)
                link["tx_bytes"] += len(wire) * len(sent)
            _ui_data(link, "tx", data, sent[0] if len(sent) == 1 else ("*", len(sent)))
        return len(sent)

    @staticmethod
    def is_connected(widget_id):
        link = _resolve(str(widget_id))
        return bool(link and link["conns"])

    # ------------------------------------------------------------------
    # Backend (lo invoca el AppBuilder)
    # ------------------------------------------------------------------
    @staticmethod
    def register_backend(app, socketio, project_data):
        _S.socketio = socketio

        def h_connect(data):
            data = data or {}
            wid = str(data.get("id", ""))
            try:
                TCPLink.connect(wid, **{k: v for k, v in data.items() if k != "id"})
            except (TypeError, ValueError) as exc:
                _emit("tcp_status", {"id": wid, "state": "error", "message": f"Configuración inválida: {exc}"})

        def h_disconnect(data):
            TCPLink.disconnect(str((data or {}).get("id", "")))

        def h_send(data):
            data = data or {}
            wid = str(data.get("id", ""))
            raw = str(data.get("data", ""))
            if "hex" in str(data.get("format", "")).lower():
                try:
                    payload = bytes.fromhex(raw.replace("0x", "").replace(" ", ""))
                except ValueError:
                    _emit("tcp_status", {"id": wid, "state": (_resolve(wid) or {"state": "disconnected"})["state"],
                                         "message": "Hex inválido"})
                    return
            else:
                payload = (raw + _unescape(data.get("suffix", ""))).encode("utf-8")
            if TCPLink.send(wid, payload) == 0:
                link = _resolve(wid)
                _emit("tcp_status", {"id": wid, "state": link["state"] if link else "disconnected",
                                     "message": "No hay una conexión activa para enviar."})

        def h_state(data):
            wid = str((data or {}).get("id", ""))
            link = _resolve(wid)
            if link:
                _status(link)
            else:
                _emit("tcp_status", {"id": wid, "state": "disconnected"})

        socketio.on_event("tcplink_connect", h_connect)
        socketio.on_event("tcplink_disconnect", h_disconnect)
        socketio.on_event("tcplink_send", h_send)
        socketio.on_event("tcplink_state", h_state)

        def autostart():
            socketio.sleep(1.0)  # da tiempo a que tus callbacks se registren
            try:
                pd = json.loads(project_data) if isinstance(project_data, str) else (project_data or {})
                widgets = pd.get("widgets", []) if isinstance(pd, dict) else []
            except Exception:
                widgets = []
            for w in widgets:
                if w.get("type") != "TCPLink":
                    continue
                props = {**TCPLink.default_props, **(w.get("props") or {})}
                if _truthy(props.get("auto_connect")):
                    try:
                        TCPLink.connect(w["id"], **props)
                    except Exception as exc:
                        print(f"[TCPLink] No se pudo autoconectar {w.get('id')}: {exc}")

        socketio.start_background_task(autostart)
        print("[TCPLink] Eventos registrados: tcplink_connect / tcplink_disconnect / tcplink_send / tcplink_state")

    # ------------------------------------------------------------------
    # Widget (editor + HTML)
    # ------------------------------------------------------------------
    def __init__(self, width=520, height=340):
        self.width, self.height = width, height
        self.props = self.default_props.copy()

    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50), "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 520), "height": getattr(self, "height", 340),
            "props": getattr(self, "props", {}), "events": getattr(self, "events", {})
        }

    def render_canvas(self, canvas, x, y):
        p = {**self.default_props, **self.props}
        items = [canvas.create_rectangle(x, y, x + self.width, y + self.height,
                                         fill=p["background"], outline="#1f2937", width=2)]
        items.append(canvas.create_text(x + 14, y + 16, anchor="w", text=p["label"],
                                        fill="#ffffff", font=("Segoe UI", 10, "bold")))
        items.append(canvas.create_text(x + self.width / 2, y + self.height / 2,
                                        text=f"TCP {str(p['mode']).upper()} | {p['host']}:{p['port']}",
                                        fill="#64748b", font=("Segoe UI", 12, "bold")))
        return items

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        try:
            port = int(p.get("port", 5000))
        except (TypeError, ValueError):
            port = 5000
        try:
            max_lines = max(10, int(p.get("max_log_lines", 200)))
        except (TypeError, ValueError):
            max_lines = 200
        try:
            frame_size = max(1, int(p.get("frame_size", 16)))
        except (TypeError, ValueError):
            frame_size = 16
        cfg = {
            "id": str(w_id), "safe": re.sub(r"\W", "_", str(w_id)),
            "label": str(p["label"]), "link_name": str(p.get("link_name") or ""),
            "mode": "server" if str(p["mode"]).lower().startswith("serv") else "client",
            "host": str(p["host"]), "port": port,
            "framing": str(p["framing"]), "delimiter": str(p["delimiter"]),
            "frame_size": frame_size,
            "auto_reconnect": _truthy(p["auto_reconnect"]),
            "parse_json": _truthy(p["parse_json"]),
            "show_controls": _truthy(p["show_controls"]),
            "show_log": _truthy(p["show_log"]),
            "log_view": "hex" if "hex" in str(p["log_view"]).lower() else "text",
            "max_log_lines": max_lines,
            "send_format": "Hex" if "hex" in str(p["send_format"]).lower() else "Texto",
            "tx_suffix": str(p.get("tx_suffix") or "")
        }
        cfg_json = json.dumps(cfg).replace("<", "\\u003c")
        return (_HTML.replace("@@SAFE@@", cfg["safe"])
                     .replace("@@BG@@", str(p["background"]))
                     .replace("@@CFG@@", cfg_json))
