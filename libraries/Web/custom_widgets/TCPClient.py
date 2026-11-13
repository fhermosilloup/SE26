import codecs
import json
import re
import socket
import threading
import time
import traceback

_FRAMING = {"raw": None, "lf": b"\n", "crlf": b"\r\n"}
_SUFFIX = {"none": b"", "lf": b"\n", "crlf": b"\r\n"}


def _truthy(v):
    return str(v).strip().lower() not in ("false", "0", "no", "off", "")


def _to_int(v, default, minimum=None):
    try:
        n = int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default
    return max(minimum, n) if minimum is not None else n


class TCPClient:
    default_props = {
        "label": "TCP Client",
        "host": "127.0.0.1",
        "port": "5000",
        "autoconnect": "True",
        "auto_reconnect": "True",
        "reconnect_ms": "3000",
        "connect_timeout_s": "5",
        "framing": "raw",
        "data_format": "text",
        "encoding": "utf-8",
        "send_suffix": "none",
        "show_controls": "True",
    }

    custom_properties = [
        {"name": "label", "label": "Título:", "type": "text"},
        {"name": "host", "label": "Host / IP del servidor:", "type": "text"},
        {"name": "port", "label": "Puerto:", "type": "text"},
        {"name": "autoconnect", "label": "Conectar al iniciar:", "type": "boolean"},
        {"name": "auto_reconnect", "label": "Reconectar automáticamente:", "type": "boolean"},
        {"name": "reconnect_ms", "label": "Espera para reconectar (ms):", "type": "text"},
        {"name": "connect_timeout_s", "label": "Timeout de conexión (s):", "type": "text"},
        {
            "name": "framing",
            "label": "Separación de paquetes (raw / lf / crlf):",
            "type": "select",
            "options": ["raw", "lf", "crlf"],
        },
        {
            "name": "data_format",
            "label": "Formato del paquete recibido:",
            "type": "select",
            "options": ["text", "hex", "bytes"],
        },
        {"name": "encoding", "label": "Codificación de texto:", "type": "text"},
        {
            "name": "send_suffix",
            "label": "Terminador al enviar texto:",
            "type": "select",
            "options": ["none", "lf", "crlf"],
        },
        {"name": "show_controls", "label": "Mostrar botón Conectar:", "type": "boolean"},
    ]

    # El builder los registra en WIDGET_EVENTS_MAP (clic derecho > Connect)
    supported_events = ["on_packet", "on_connect", "on_disconnect"]

    value_help = {
        "soportado": True,
        "tipo": "String, bytes o Dict",
        "valores": "'texto' | b'bytes' | {'action': 'send' | 'connect' | 'disconnect' | 'status', ...}",
        "desc": "Cliente TCP que corre en el servidor (app.py). Un String o bytes se envía "
                "tal cual al servidor TCP. Con un Dict puedes conectar, desconectar o enviar "
                "datos en hexadecimal.",
        "ejemplos": [
            "ui.set_value('{id}', 'hola')",
            "ui.set_value('{id}', b'\\x01\\x02\\x03')",
            "ui.set_value('{id}', {'action': 'send', 'data': 'PING'})",
            "ui.set_value('{id}', {'action': 'send', 'hex': '48 65 6c 6c 6f'})",
            "ui.set_value('{id}', {'action': 'connect'})",
            "ui.set_value('{id}', {'action': 'connect', 'host': '192.168.1.10', 'port': 5000})",
            "ui.set_value('{id}', {'action': 'disconnect'})",
        ],
        "envia": "on_packet -> str o bytes (según 'Formato del paquete'); "
                 "on_connect -> {'host', 'port'}; "
                 "on_disconnect -> {'host', 'port', 'reason'}",
        "notas": [
            "Ejemplo: def on_packet(context): data = context['value']; context['ui'].set_value('label_0', data)",
            "Los eventos solo llegan a Python si los conectas (clic derecho > Connect).",
            "Separación 'raw': cada lectura del socket es un paquete. 'lf' o 'crlf': un paquete por línea, sin el terminador.",
            "Formato 'text' entrega str, 'hex' entrega un str como '48 65 6c', 'bytes' entrega bytes.",
            "'Terminador al enviar texto' se agrega a los str; los bytes y 'hex' se envían sin cambios.",
            "Hay una sola conexión por widget en el servidor, compartida por todas las pestañas del navegador.",
            "El botón Conectar del dashboard solo conecta o desconecta; no puede cambiar host ni puerto.",
        ],
    }

    def __init__(self, width=260, height=170):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()

    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50),
            "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 260),
            "height": getattr(self, "height", 170),
            "props": getattr(self, "props", {}),
            "events": getattr(self, "events", {}),
        }

    def render_canvas(self, canvas, x, y):
        label = str(self.props.get("label", "TCP Client"))
        addr = f"{self.props.get('host', '')}:{self.props.get('port', '')}"
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height,
                                      fill="#234764", outline="#334155", width=2)
        dot = canvas.create_oval(x + 10, y + 10, x + 20, y + 20, fill="#ef4444", outline="")
        title = canvas.create_text(x + 28, y + 15, text=label, anchor="w",
                                   fill="#ffffff", font=("Segoe UI", 10, "bold"))
        sub = canvas.create_text(x + self.width / 2, y + self.height / 2, text=addr,
                                 fill="#38bdf8", font=("Consolas", 10))
        return [box, dot, title, sub]

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        safe_id = re.sub(r"\W", "_", str(w_id))
        cfg = json.dumps({
            "id": str(w_id),
            "label": str(p.get("label", "TCP Client")),
            "host": str(p.get("host", "")),
            "port": str(p.get("port", "")),
            "show_controls": _truthy(p.get("show_controls", "True")),
        })

        return f"""
<div id="tcp_{safe_id}" style="width:100%;height:100%;box-sizing:border-box;display:flex;flex-direction:column;gap:6px;padding:10px;background:#0f172a;border:1px solid #1e293b;border-radius:12px;color:#e2e8f0;font-family:ui-sans-serif,system-ui,sans-serif;overflow:hidden;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span class="tcp-dot" style="width:10px;height:10px;border-radius:50%;background:#ef4444;flex:none;"></span>
    <span class="tcp-label" style="font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></span>
    <span class="tcp-state" style="margin-left:auto;font-size:11px;color:#94a3b8;white-space:nowrap;"></span>
  </div>
  <div class="tcp-addr" style="font-family:ui-monospace,monospace;font-size:11px;color:#38bdf8;"></div>
  <div class="tcp-stats" style="font-size:11px;color:#94a3b8;"></div>
  <div class="tcp-last" style="flex:1;min-height:0;font-family:ui-monospace,monospace;font-size:11px;color:#cbd5e1;background:#020617;border-radius:6px;padding:4px 6px;overflow:hidden;word-break:break-all;"></div>
  <button class="tcp-btn" style="border:0;border-radius:8px;padding:6px 10px;font-size:12px;font-weight:700;color:#fff;cursor:pointer;"></button>
</div>

<script>
(function() {{
    const cfg = {cfg};
    const root = document.getElementById("tcp_{safe_id}");
    const dot = root.querySelector(".tcp-dot");
    const lbl = root.querySelector(".tcp-label");
    const stEl = root.querySelector(".tcp-state");
    const addr = root.querySelector(".tcp-addr");
    const stats = root.querySelector(".tcp-stats");
    const last = root.querySelector(".tcp-last");
    const btn = root.querySelector(".tcp-btn");
    const sock = window.dashboardSocket;

    let state = {{ connected: false, running: false, host: cfg.host, port: cfg.port,
                  rx: 0, tx: 0, last: "", error: "" }};

    function paint(s) {{
        if (s) Object.assign(state, s);
        const connected = !!state.connected, running = !!state.running;
        lbl.textContent = cfg.label;
        dot.style.background = connected ? "#22c55e" : (running ? "#f59e0b" : "#ef4444");
        stEl.textContent = connected ? "Conectado" : (running ? "Conectando..." : "Desconectado");
        addr.textContent = (state.host || cfg.host) + ":" + (state.port || cfg.port);
        stats.textContent = "RX " + (state.rx || 0) + " B  |  TX " + (state.tx || 0) + " B";
        last.textContent = (!connected && state.error) ? ("Error: " + state.error) : (state.last || "(sin datos)");
        btn.textContent = running ? "Desconectar" : "Conectar";
        btn.style.background = running ? "#475569" : "#2563eb";
        btn.style.display = cfg.show_controls ? "block" : "none";
    }}
    paint();

    if (sock) {{
        sock.on("tcp_status", function(d) {{ if (d && d.id === cfg.id) paint(d); }});
        const ask = function() {{ sock.emit("tcp_status_request", {{ id: cfg.id }}); }};
        sock.on("connect", ask);
        if (sock.connected) ask();
    }}

    btn.addEventListener("click", function() {{
        if (!sock) return;
        sock.emit("client_event", {{
            id: cfg.id,
            event_name: "on_tcp_cmd",
            value: {{ action: state.running ? "disconnect" : "connect" }}
        }});
    }});

    window.__widgets = window.__widgets || {{}};
    window.__widgets[cfg.id] = {{
        update: function(val) {{ /* el estado llega por 'tcp_status' */ }},
        update_prop: function(prop, val) {{
            if (prop === "label") {{ cfg.label = String(val); paint(); }}
        }}
    }};
}})();
</script>
"""

    # ------------------------------------------------------------------
    # Backend: lo llama app.py -> load_backend_plugins()
    # ------------------------------------------------------------------
    @staticmethod
    def register_backend(app, socketio, project_data):
        ui = app.config.get("UI_PROXY")
        dispatch = app.config.get("DISPATCH")
        if ui is None or dispatch is None:
            # Respaldo: app.py se ejecuta como __main__ y ya tiene ui_proxy y dispatch
            import sys
            main = sys.modules.get("__main__")
            ui = getattr(main, "ui_proxy", None)
            dispatch = getattr(main, "dispatch", None)
        if ui is None or dispatch is None:
            print("[TCPClient] No se encontró ui_proxy/dispatch. Ejecuta app.py directamente "
                  "(python app.py) o agrega app.config['UI_PROXY'] y ['DISPATCH'] en app.py.")
            return
        print("[TCPClient] backend cargado")

        conns = {}
        for w in project_data.get("widgets", []):
            if str(w.get("type", "")).lower() != "tcpclient":
                continue
            wid = w["id"]
            conn = _TCPConnection(wid, w.get("props"), socketio, dispatch)
            conns[wid] = conn

            def on_update(ctx, c=conn):
                c.handle_value(ctx.get("value"))

            def on_cmd(ctx, c=conn):
                v = ctx.get("value")
                action = v.get("action") if isinstance(v, dict) else v
                if action == "connect":
                    c.connect()
                elif action == "disconnect":
                    c.disconnect()

            ui.on(wid, "on_update", on_update)   # ui.set_value(id, ...) desde Python
            ui.on(wid, "on_tcp_cmd", on_cmd)     # botón del dashboard
            if conn.autoconnect:
                conn.connect()

        @socketio.on("tcp_status_request")
        def _status_request(data):
            c = conns.get((data or {}).get("id"))
            if c:
                c.send_status()


class _TCPConnection:
    def __init__(self, wid, props, socketio, dispatch):
        p = {**TCPClient.default_props, **(props or {})}
        self.wid = wid
        self.socketio = socketio
        self.dispatch = dispatch

        self.host = str(p["host"]).strip() or "127.0.0.1"
        self.port = _to_int(p["port"], 5000, 1)
        self.autoconnect = _truthy(p["autoconnect"])
        self.auto_reconnect = _truthy(p["auto_reconnect"])
        self.reconnect_s = _to_int(p["reconnect_ms"], 3000, 100) / 1000.0
        try:
            self.timeout = max(0.5, float(p["connect_timeout_s"]))
        except (ValueError, TypeError):
            self.timeout = 5.0
        self.delim = _FRAMING.get(str(p["framing"]).strip().lower())
        self.data_format = str(p["data_format"]).strip().lower()
        self.suffix = _SUFFIX.get(str(p["send_suffix"]).strip().lower(), b"")
        enc = str(p["encoding"]).strip() or "utf-8"
        try:
            codecs.lookup(enc)
        except LookupError:
            enc = "utf-8"
        self.encoding = enc

        self._sock = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._nlock = threading.Lock()
        self._timer_pending = False
        self._last_notify = 0.0

        self.connected = False
        self.rx = 0
        self.tx = 0
        self.last = ""
        self.error = ""

    # ---------------- estado ----------------
    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def status(self):
        return {
            "id": self.wid, "connected": self.connected, "running": self.running,
            "host": self.host, "port": self.port, "rx": self.rx, "tx": self.tx,
            "last": self.last, "error": self.error,
        }

    def send_status(self):
        self.socketio.emit("tcp_status", self.status())

    def _notify(self, force=False):
        now = time.time()
        with self._nlock:
            if not force and now - self._last_notify < 0.25:
                if not self._timer_pending:
                    self._timer_pending = True
                    t = threading.Timer(0.25, self._flush)
                    t.daemon = True
                    t.start()
                return
            self._last_notify = now
        self.send_status()

    def _flush(self):
        with self._nlock:
            self._timer_pending = False
            self._last_notify = time.time()
        self.send_status()

    def _emit_event(self, name, value):
        try:
            self.dispatch(self.wid, name, value)
        except Exception:
            traceback.print_exc()

    # ---------------- conexión ----------------
    def connect(self, host=None, port=None):
        if host:
            self.host = str(host).strip()
        if port:
            self.port = _to_int(port, self.port, 1)
        if self.running:
            return
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(self._stop,), daemon=True)
        self._thread.start()
        self._notify(force=True)

    def disconnect(self):
        self._stop.set()
        with self._lock:
            sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        self._notify(force=True)

    def _run(self, stop):
        while not stop.is_set():
            sock = None
            was_connected = False
            reason = ""
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                sock.settimeout(1.0)
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError:
                    pass
                with self._lock:
                    if stop.is_set():
                        raise OSError("cancelado")
                    self._sock = sock
                    self.connected = True
                    self.error = ""
                was_connected = True
                self._notify(force=True)
                self._emit_event("on_connect", {"host": self.host, "port": self.port})
                reason = self._read_loop(sock, stop)
            except Exception as ex:
                reason = str(ex) or ex.__class__.__name__
                self.error = reason
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                with self._lock:
                    if self._sock is sock:
                        self._sock = None
                        self.connected = False

            if was_connected:
                self._emit_event("on_disconnect",
                                 {"host": self.host, "port": self.port, "reason": reason})
            self._notify(force=True)

            if stop.is_set() or not self.auto_reconnect:
                break
            stop.wait(self.reconnect_s)

        self._notify(force=True)

    def _read_loop(self, sock, stop):
        buf = b""
        while not stop.is_set():
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as ex:
                return "desconectado por el usuario" if stop.is_set() else str(ex)
            if not chunk:
                return "cerrado por el servidor"

            if self.delim is None:
                self._on_data(chunk)
                continue

            buf += chunk
            while True:
                i = buf.find(self.delim)
                if i < 0:
                    break
                pkt, buf = buf[:i], buf[i + len(self.delim):]
                self._on_data(pkt)
            if len(buf) > 1_000_000:  # sin terminador: evita crecer sin límite
                self._on_data(buf)
                buf = b""
        return "desconectado por el usuario"

    def _on_data(self, data):
        self.rx += len(data)
        if self.data_format == "text":
            txt = data.decode(self.encoding, "replace")
            value = txt
        elif self.data_format == "hex":
            txt = data.hex(" ")
            value = txt
        else:
            txt = data.hex(" ")
            value = data
        self.last = txt[:200]
        self._notify()
        self._emit_event("on_packet", value)

    # ---------------- envío ----------------
    def send(self, data):
        if isinstance(data, (bytes, bytearray, memoryview)):
            payload = bytes(data)
        else:
            payload = str(data).encode(self.encoding, "replace") + self.suffix
        with self._lock:
            sock = self._sock
            if sock is None:
                print(f"[TCPClient {self.wid}] No conectado: no se envió el dato.")
                return False
            try:
                sock.sendall(payload)
            except OSError as ex:
                print(f"[TCPClient {self.wid}] Error al enviar: {ex}")
                return False
        self.tx += len(payload)
        self._notify()
        return True

    def handle_value(self, value):
        if value is None:
            return
        if not isinstance(value, dict):
            self.send(value)
            return

        action = str(value.get("action", "send")).strip().lower()
        if action == "connect":
            self.connect(value.get("host"), value.get("port"))
        elif action in ("disconnect", "close"):
            self.disconnect()
        elif action == "status":
            self.send_status()
        elif action == "send":
            if "hex" in value:
                try:
                    self.send(bytes.fromhex(str(value["hex"])))
                except ValueError:
                    print(f"[TCPClient {self.wid}] 'hex' inválido: {value['hex']!r}")
            elif "data" in value:
                self.send(value["data"])