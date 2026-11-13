import base64
import json
import math
import mimetypes
import os
import re

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ----------------------------------------------------------------------
# Utilidades de módulo (NO métodos): el editor de forma puede ejecutarse
# con un WidgetItem del builder como "self", que no tiene métodos del plugin.
# ----------------------------------------------------------------------
def _num(v, default):
    try:
        n = float(str(v).strip())
        return n if math.isfinite(n) else default
    except (ValueError, TypeError):
        return default


def _truthy(v):
    return str(v).strip().lower() not in ("false", "0", "no", "off", "")


def _color(v, default):
    v = str(v).strip()
    return v if _HEX.match(v) else default


def _load_shape(props):
    """Lee la propiedad 'shape' (JSON [[x, y], ...]) y devuelve [(x, y), ...]."""
    try:
        data = json.loads(str((props or {}).get("shape", "[]")) or "[]")
    except (ValueError, TypeError):
        return []
    pts = []
    if isinstance(data, list):
        for p in data:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                x, y = _num(p[0], None), _num(p[1], None)
                if x is not None and y is not None:
                    pts.append((x, y))
    return pts


def _get_image_src(path):
    """Imagen local -> data URI Base64. Acepta también URLs y data URIs."""
    if not path:
        return ""
    path = str(path)
    if path.startswith(("http://", "https://", "data:")):
        return path
    if not os.path.isfile(path):
        if path.startswith("/"):
            return path
        print(f"RadarMap: imagen no encontrada: {path}")
        return ""
    mime, _ = mimetypes.guess_type(path)
    with open(path, "rb") as f:
        enc = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime or 'image/png'};base64,{enc}"


class RadarMap:
    # Todas las propiedades se guardan como string (igual que el resto de plugins)
    default_props = {
        "label": "Radar",
        "mode": "Polar",
        # Polar
        "max_range": "100",
        "range_unit": "m",
        "rings": "4",
        "spokes": "12",
        "sweep": "True",
        "sweep_ms": "4000",
        # Rectangular
        "plane_width": "200",
        "plane_height": "200",
        "grid_step": "50",
        "shape": "[]",
        "hide_outside_shape": "False",
        # Puntos / marcadores
        "point_color": "#22d3ee",
        "marker_type": "•",
        "marker_color": "#ffffff",
        "marker_char": "◆",
        "marker_image": "",
        "marker_size": "12",
        "blink_ms": "1200",
        "glow_size": "14",
        # Extras
        "trail_length": "0",
        "fade_s": "0",
        "show_labels": "True",
        "show_object_labels": "False",
        # Colores del mapa
        "bg_color": "#0b1220",
        "grid_color": "#1e4d5c",
        "shape_color": "#f59e0b",
    }

    _IMG_TYPES = [
        ("Imágenes", "*.png *.jpg *.jpeg *.gif *.webp *.svg"),
        ("Todos los archivos", "*.*"),
    ]

    custom_properties = [
        {"name": "label", "label": "Título:", "type": "text"},
        {"name": "mode", "label": "Modo:", "type": "select", "options": ["Polar", "Rectangular"]},
        {"name": "max_range", "label": "Alcance / radio (modo Polar):", "type": "text"},
        {"name": "range_unit", "label": "Unidad (m, km, ...):", "type": "text"},
        {"name": "rings", "label": "Anillos (modo Polar):", "type": "text"},
        {"name": "spokes", "label": "Líneas angulares, 0 = ninguna (Polar):", "type": "text"},
        {"name": "sweep", "label": "Barrido de radar (Polar):", "type": "boolean"},
        {"name": "sweep_ms", "label": "Duración de una vuelta (ms):", "type": "text"},
        {"name": "plane_width", "label": "Ancho del plano (Rectangular):", "type": "text"},
        {"name": "plane_height", "label": "Alto del plano (Rectangular):", "type": "text"},
        {"name": "grid_step", "label": "Paso de la cuadrícula:", "type": "text"},
        {
            "name": "shape",
            "label": "Forma del plano (Rectangular):",
            "type": "custom",
            "fname": "open_shape_editor",
            "btn_text": "Dibujar forma...",
        },
        {"name": "hide_outside_shape", "label": "Ocultar objetos fuera de la forma:", "type": "boolean"},
        {"name": "point_color", "label": "Color de los puntos (resplandor):", "type": "color"},
        {
            "name": "marker_type",
            "label": "Tipo de marcador:",
            "type": "select",
            "options": ["•", "×", "∆", "*", "Caracter", "Imagen"],
        },
        {"name": "marker_color", "label": "Color del marcador (no aplica a imagen):", "type": "color"},
        {"name": "marker_char", "label": "Carácter (si tipo = Caracter):", "type": "text"},
        {
            "name": "marker_image",
            "label": "Imagen (si tipo = Imagen):",
            "type": "file",
            "file_types": _IMG_TYPES,
        },
        {"name": "marker_size", "label": "Tamaño del marcador (px):", "type": "text"},
        {"name": "blink_ms", "label": "Parpadeo, periodo (ms, 0 = sin parpadeo):", "type": "text"},
        {"name": "glow_size", "label": "Resplandor (px, 0 = sin glow):", "type": "text"},
        {"name": "trail_length", "label": "Estela: posiciones previas (0 = ninguna):", "type": "text"},
        {"name": "fade_s", "label": "Desvanecer tras N s sin actualizar (0 = nunca):", "type": "text"},
        {"name": "show_labels", "label": "Mostrar escalas y ángulos:", "type": "boolean"},
        {"name": "show_object_labels", "label": "Mostrar nombre de cada objeto:", "type": "boolean"},
        {"name": "bg_color", "label": "Color de fondo:", "type": "color"},
        {"name": "grid_color", "label": "Color de la cuadrícula:", "type": "color"},
        {"name": "shape_color", "label": "Color de la forma:", "type": "color"},
    ]

    supported_events = ["on_click", "on_object_click"]

    value_help = {
        "soportado": True,
        "tipo": "Dict, lista de Dict o String JSON",
        "valores": "Objeto: {'id': str, 'angle': grados, 'range': distancia} o {'id': str, 'x': n, 'y': n}",
        "desc": "Coloca o mueve objetos en el radar. Cada objeto se identifica por su 'id' "
                "(si no lo mandas, es el objeto 'default'). Si el id ya existe se mueve; si no, se crea. "
                "Acepta coordenadas polares (angle/range) o rectangulares (x/y) en cualquier modo: "
                "el widget convierte. Ángulo: 0 = arriba (N), crece en sentido horario. "
                "El origen (0, 0) es el centro del mapa.",
        "ejemplos": [
            "ui.set_value('{id}', {'id': 'dron1', 'angle': 45, 'range': 30})",
            "ui.set_value('{id}', {'id': 'dron1', 'x': 10.5, 'y': -4})",
            "ui.set_value('{id}', [{'id': 'a', 'angle': 10, 'range': 20}, {'id': 'b', 'angle': 200, 'range': 55}])",
            "ui.set_value('{id}', {'id': 'a', 'angle': 90, 'range': 40, 'color': '#ef4444', 'label': 'Intruso'})",
            "ui.set_value('{id}', {'action': 'set', 'objects': [{'id': 'a', 'x': 1, 'y': 2}]})",
            "ui.set_value('{id}', {'action': 'remove', 'id': 'a'})",
            "ui.set_value('{id}', {'action': 'clear'})",
            "ui.set_property('{id}', 'mode', 'Rectangular')",
        ],
        "envia": "on_click -> {'x', 'y', 'angle', 'range'} del punto pulsado; "
                 "on_object_click -> {'id', 'x', 'y', 'angle', 'range'} del objeto pulsado",
        "notas": [
            "Claves opcionales por objeto: color (cambia glow y símbolo de ese objeto) y label.",
            "Lista o Dict suelto: agrega o actualiza. {'action': 'set', 'objects': [...]} reemplaza todos.",
            "Acciones: set, remove (con 'id') y clear.",
            "Objetos fuera del mapa (rango > alcance, o fuera del plano) no se dibujan, pero se conservan.",
            "Modo Rectangular: la forma dibujada es el contorno de la zona. 'Ocultar objetos fuera de la forma' filtra los de afuera.",
            "ui.set_property('{id}', 'mode' | 'max_range' | 'marker_type' | 'point_color' | 'blink_ms' | ...) cambia en vivo.",
            "ui.set_property('{id}', 'shape', '[[0,0],[50,0],[50,50]]') cambia la forma (JSON).",
            "Los objetos viven en el navegador: si recargas la página se pierden hasta el siguiente set_value.",
        ],
    }

    def __init__(self, width=380, height=380):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()

    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50),
            "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 380),
            "height": getattr(self, "height", 380),
            "props": getattr(self, "props", {}),
            "events": getattr(self, "events", {}),
        }

    # ------------------------------------------------------------------
    # Vista previa en el diseñador (Tk canvas)
    # ------------------------------------------------------------------
    def render_canvas(self, canvas, x, y):
        p = {**RadarMap.default_props, **(getattr(self, "props", None) or {})}
        w, h = self.width, self.height
        bg = _color(p["bg_color"], "#0b1220")
        grid = _color(p["grid_color"], "#1e4d5c")
        sc = _color(p["shape_color"], "#f59e0b")
        pc = _color(p["point_color"], "#22d3ee")

        items = [canvas.create_rectangle(x, y, x + w, y + h, fill=bg, outline="#334155", width=2)]

        title = str(p.get("label", "")).strip()
        top = 24 if title else 8
        if title:
            items.append(canvas.create_text(x + 10, y + 12, text=title, anchor="w",
                                            fill="#e2e8f0", font=("Segoe UI", 9, "bold")))

        ax0, ay0, ax1, ay1 = x + 10, y + top, x + w - 10, y + h - 10
        cx, cy = (ax0 + ax1) / 2.0, (ay0 + ay1) / 2.0

        if str(p["mode"]).strip().lower().startswith("pol"):
            r = max(6.0, min(ax1 - ax0, ay1 - ay0) / 2.0 - 2)
            rings = max(1, min(20, int(_num(p["rings"], 4))))
            for i in range(1, rings + 1):
                rr = r * i / rings
                items.append(canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=grid, width=1))
            spokes = max(0, min(72, int(_num(p["spokes"], 12))))
            for k in range(spokes):
                a = 2 * math.pi * k / spokes
                items.append(canvas.create_line(cx, cy, cx + math.sin(a) * r, cy - math.cos(a) * r, fill=grid))
            items.append(canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=pc, outline=""))
        else:
            pw = max(1e-6, _num(p["plane_width"], 200.0))
            ph = max(1e-6, _num(p["plane_height"], 200.0))
            s = min((ax1 - ax0) / pw, (ay1 - ay0) / ph)
            hx, hy = pw / 2.0 * s, ph / 2.0 * s
            step = _num(p["grid_step"], 50.0)
            if step > 0 and pw / step <= 200 and ph / step <= 200:
                nx, ny = int(pw / 2 / step), int(ph / 2 / step)
                for i in range(-nx, nx + 1):
                    gx = cx + i * step * s
                    items.append(canvas.create_line(gx, cy - hy, gx, cy + hy, fill=grid))
                for j in range(-ny, ny + 1):
                    gy = cy - j * step * s
                    items.append(canvas.create_line(cx - hx, gy, cx + hx, gy, fill=grid))
            items.append(canvas.create_rectangle(cx - hx, cy - hy, cx + hx, cy + hy, outline="#475569", width=2))
            pts = _load_shape(p)
            flat = []
            for px, py in pts:
                flat += [cx + px * s, cy - py * s]
            if len(pts) >= 3:
                items.append(canvas.create_polygon(*flat, outline=sc, fill="", width=2))
            elif len(pts) == 2:
                items.append(canvas.create_line(*flat, fill=sc, width=2))
            items.append(canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=pc, outline=""))
        return items

    # ------------------------------------------------------------------
    # Editor de forma (ventana nueva). Lo llama el botón "Dibujar forma...".
    # Solo usa self.props, así funciona con WidgetItem o con la clase del plugin.
    # ------------------------------------------------------------------
    def open_shape_editor(self, app):
        import tkinter as tk

        props = self.props
        pw = max(1e-6, _num(props.get("plane_width"), 200.0))
        ph = max(1e-6, _num(props.get("plane_height"), 200.0))
        step = _num(props.get("grid_step"), 50.0)
        if step <= 0:
            step = max(pw, ph) / 4.0
        snap_unit = step / 5.0
        points = [[px, py] for px, py in _load_shape(props)]

        CW, CH, M = 580, 580, 30
        scale = min((CW - 2 * M) / pw, (CH - 2 * M) / ph)
        cx, cy = CW / 2.0, CH / 2.0
        state = {"cursor": None}

        diag = tk.Toplevel(app.root)
        diag.title("Forma del plano")
        diag.config(bg="#1e293b")
        diag.transient(app.root)
        diag.grab_set()

        tk.Label(diag, text="Dibuja el contorno de la zona (el polígono se cierra solo)",
                 font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(pady=(10, 2))
        hint = "Clic: agregar recta  |  Clic derecho o Ctrl+Z: borrar la última"
        if str(props.get("mode", "")).strip().lower().startswith("pol"):
            hint += "\nModo actual: Polar. La forma solo se usa en modo Rectangular."
        tk.Label(diag, text=hint, fg="#94a3b8", bg="#1e293b", font=("Segoe UI", 9)).pack()

        cv = tk.Canvas(diag, width=CW, height=CH, bg="#0b1220", highlightthickness=0, cursor="crosshair")
        cv.pack(padx=12, pady=8)

        info = tk.Label(diag, text="", fg="#38bdf8", bg="#1e293b", font=("Consolas", 10))
        info.pack()

        snap_var = tk.BooleanVar(value=True)

        def to_px(wx, wy):
            return cx + wx * scale, cy - wy * scale

        def to_world(px, py):
            return (px - cx) / scale, -(py - cy) / scale

        def snapped(px, py):
            wx, wy = to_world(px, py)
            if snap_var.get():
                wx, wy = round(wx / snap_unit) * snap_unit, round(wy / snap_unit) * snap_unit
            wx = max(-pw / 2, min(pw / 2, wx))
            wy = max(-ph / 2, min(ph / 2, wy))
            return wx, wy

        def redraw():
            cv.delete("all")
            n = int(pw / 2 / step)
            m = int(ph / 2 / step)
            if n <= 200 and m <= 200:
                for i in range(-n, n + 1):
                    x0, y0 = to_px(i * step, -ph / 2)
                    x1, y1 = to_px(i * step, ph / 2)
                    cv.create_line(x0, y0, x1, y1, fill="#334155" if i else "#64748b")
                for j in range(-m, m + 1):
                    x0, y0 = to_px(-pw / 2, j * step)
                    x1, y1 = to_px(pw / 2, j * step)
                    cv.create_line(x0, y0, x1, y1, fill="#334155" if j else "#64748b")
            bx0, by0 = to_px(-pw / 2, ph / 2)
            bx1, by1 = to_px(pw / 2, -ph / 2)
            cv.create_rectangle(bx0, by0, bx1, by1, outline="#475569", width=2)

            flat = []
            for px, py in points:
                flat += list(to_px(px, py))
            if len(points) >= 3:
                cv.create_polygon(*flat, fill="#f59e0b", stipple="gray25", outline="")
                cv.create_line(*(flat[-2:] + flat[:2]), fill="#f59e0b", width=2, dash=(5, 4))
            if len(points) >= 2:
                cv.create_line(*flat, fill="#f59e0b", width=2)

            cur = state["cursor"]
            if cur and points:
                lx, ly = to_px(*points[-1])
                cv.create_line(lx, ly, *to_px(*cur), fill="#94a3b8", dash=(3, 3))
                if len(points) >= 2:
                    fx, fy = to_px(*points[0])
                    cv.create_line(*to_px(*cur), fx, fy, fill="#64748b", dash=(2, 4))

            for i, (px, py) in enumerate(points):
                sx, sy = to_px(px, py)
                col = "#22c55e" if i == 0 else ("#ef4444" if i == len(points) - 1 else "#f8fafc")
                cv.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill=col, outline="")
            if cur:
                sx, sy = to_px(*cur)
                cv.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, outline="#38bdf8")

            where = f"x={cur[0]:.1f}  y={cur[1]:.1f}   " if cur else ""
            info.config(text=f"{where}rectas: {max(0, len(points) - 1)}  vértices: {len(points)}")

        def on_move(e):
            state["cursor"] = snapped(e.x, e.y)
            redraw()

        def on_click(e):
            p = snapped(e.x, e.y)
            if points and abs(points[-1][0] - p[0]) < 1e-9 and abs(points[-1][1] - p[1]) < 1e-9:
                return
            points.append([p[0], p[1]])
            redraw()

        def undo(_e=None):
            if points:
                points.pop()
                redraw()

        def clear_all():
            points.clear()
            redraw()

        def accept():
            txt = json.dumps([[round(px, 4), round(py, 4)] for px, py in points])
            app.save_state()
            self.props["shape"] = txt
            cpv = getattr(app, "custom_prop_vars", None)
            if cpv and "shape" in cpv:
                cpv["shape"].set(txt)  # si no, update_prop_live lo pisa con el valor viejo
            app.update_prop_live()
            diag.destroy()

        cv.bind("<Motion>", on_move)
        cv.bind("<Button-1>", on_click)
        cv.bind("<Button-3>", undo)
        diag.bind("<Control-z>", undo)

        tk.Checkbutton(diag, text="Imán a cuadrícula (1/5 del paso)", variable=snap_var,
                       bg="#1e293b", fg="white", selectcolor="#0f172a",
                       activebackground="#1e293b", activeforeground="white").pack()

        bar = tk.Frame(diag, bg="#1e293b")
        bar.pack(fill=tk.X, padx=12, pady=10)
        tk.Button(bar, text="Borrar última recta", command=undo, bg="#334155", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="Borrar todo", command=clear_all, bg="#ef4444", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="Aceptar", command=accept, bg="#10b981", fg="white",
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="Cancelar", command=diag.destroy, bg="#334155", fg="white",
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=3)

        redraw()

    # ------------------------------------------------------------------
    # HTML del dashboard exportado
    # ------------------------------------------------------------------
    def render_html(self, w_id, props):
        p = {**RadarMap.default_props, **(props or {})}
        cfg = {k: str(v) for k, v in p.items()}
        cfg["id"] = str(w_id)
        cfg["marker_image"] = _get_image_src(p.get("marker_image", ""))
        cfg_json = json.dumps(cfg).replace("</", "<\\/")
        safe_id = re.sub(r"\W", "_", str(w_id))
        bg = _color(p.get("bg_color"), "#0b1220")
        # __CFG__ al final: el JSON del usuario no puede contener otros marcadores
        return (_HTML_TEMPLATE
                .replace("__SAFE__", safe_id)
                .replace("__BG__", bg)
                .replace("__CFG__", cfg_json))


_HTML_TEMPLATE = r'''
<div id="radar___SAFE__" style="width:100%;height:100%;box-sizing:border-box;display:flex;flex-direction:column;background:__BG__;border:1px solid #1e293b;border-radius:12px;overflow:hidden;">
  <div class="rd-title" style="display:none;padding:6px 10px 0 10px;font:700 12px ui-sans-serif,system-ui,sans-serif;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>
  <div style="position:relative;flex:1;min-height:0;">
    <canvas class="rd-cv" style="position:absolute;left:0;top:0;width:100%;height:100%;display:block;cursor:crosshair;"></canvas>
  </div>
</div>

<script>
(function () {
    const C = __CFG__;
    const root = document.getElementById("radar___SAFE__");
    if (!root) return;
    const titleEl = root.querySelector(".rd-title");
    const cv = root.querySelector(".rd-cv");
    const ctx = cv.getContext("2d");
    const objs = new Map();
    let W = 0, H = 0, dpr = 1;
    let shape = [];
    let img = null;

    const num = (v, d) => { const n = Number(v); return Number.isFinite(n) ? n : d; };
    const truthy = (v) => !["false", "0", "no", "off", ""].includes(String(v).trim().toLowerCase());
    const isPolar = () => String(C.mode).trim().toLowerCase().startsWith("pol");
    const round3 = (v) => Math.round(v * 1000) / 1000;
    const fmt = (v) => String(Math.round(v * 100) / 100);

    function kindOf() {
        const m = String(C.marker_type).trim().toLowerCase();
        if (m === "\u2022" || m === "dot" || m === "o" || m === "punto") return "dot";
        if (m === "\u00d7" || m === "x" || m === "cross" || m === "cruz") return "cross";
        if (m === "\u2206" || m === "\u25b3" || m === "triangle" || m === "triangulo") return "tri";
        if (m === "*" || m === "star" || m === "asterisco") return "star";
        if (m.startsWith("car") || m === "char") return "char";
        if (m.startsWith("im")) return "img";
        return "dot";
    }

    function parseShape() {
        shape = [];
        try {
            const a = JSON.parse(C.shape || "[]");
            if (Array.isArray(a)) {
                a.forEach(function (p) {
                    if (Array.isArray(p) && p.length >= 2) {
                        const x = Number(p[0]), y = Number(p[1]);
                        if (Number.isFinite(x) && Number.isFinite(y)) shape.push([x, y]);
                    }
                });
            }
        } catch (e) { shape = []; }
    }

    function inShape(x, y) {
        if (shape.length < 3) return true;
        let c = false;
        for (let i = 0, j = shape.length - 1; i < shape.length; j = i++) {
            const xi = shape[i][0], yi = shape[i][1], xj = shape[j][0], yj = shape[j][1];
            if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) c = !c;
        }
        return c;
    }

    function loadImage() {
        img = null;
        if (!C.marker_image) return;
        const im = new Image();
        im.onload = function () { img = im; };
        im.src = C.marker_image;
    }

    function paintTitle() {
        titleEl.textContent = C.label || "";
        titleEl.style.display = C.label ? "block" : "none";
    }

    function resize() {
        const r = cv.getBoundingClientRect();
        dpr = window.devicePixelRatio || 1;
        W = r.width; H = r.height;
        cv.width = Math.max(1, Math.round(W * dpr));
        cv.height = Math.max(1, Math.round(H * dpr));
    }

    // Todo se dibuja en coordenadas del mundo (x, y); origen en el centro.
    function geom() {
        const m = 28;
        if (isPolar()) {
            const R = Math.max(1e-9, num(C.max_range, 100));
            const s = Math.max(1, Math.min(W, H) / 2 - m) / R;
            return { polar: true, cx: W / 2, cy: H / 2, s: s, R: R,
                     inside: function (x, y) { return Math.hypot(x, y) <= R * 1.0001; } };
        }
        const pw = Math.max(1e-9, num(C.plane_width, 200));
        const ph = Math.max(1e-9, num(C.plane_height, 200));
        const s = Math.max(0.0001, Math.min((W - 2 * m) / pw, (H - 2 * m) / ph));
        return { polar: false, cx: W / 2, cy: H / 2, s: s, pw: pw, ph: ph,
                 inside: function (x, y) { return Math.abs(x) <= pw / 2 + 1e-9 && Math.abs(y) <= ph / 2 + 1e-9; } };
    }

    function drawGrid(g) {
        const gc = C.grid_color || "#1e4d5c";
        const labels = truthy(C.show_labels);
        const unit = C.range_unit ? " " + C.range_unit : "";
        ctx.save();
        ctx.font = "10px ui-sans-serif,system-ui,sans-serif";
        if (g.polar) {
            const R = g.R * g.s;
            ctx.fillStyle = "rgba(255,255,255,0.03)";
            ctx.beginPath(); ctx.arc(g.cx, g.cy, R, 0, Math.PI * 2); ctx.fill();
            ctx.strokeStyle = gc; ctx.lineWidth = 1;
            const rings = Math.max(1, Math.min(50, Math.floor(num(C.rings, 4))));
            for (let i = 1; i <= rings; i++) {
                ctx.beginPath(); ctx.arc(g.cx, g.cy, R * i / rings, 0, Math.PI * 2); ctx.stroke();
            }
            const spokes = Math.max(0, Math.min(360, Math.floor(num(C.spokes, 12))));
            for (let k = 0; k < spokes; k++) {
                const a = 2 * Math.PI * k / spokes;
                ctx.beginPath(); ctx.moveTo(g.cx, g.cy);
                ctx.lineTo(g.cx + Math.sin(a) * R, g.cy - Math.cos(a) * R); ctx.stroke();
            }
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.arc(g.cx, g.cy, R, 0, Math.PI * 2); ctx.stroke();
            if (labels) {
                ctx.fillStyle = "#94a3b8";
                ctx.textBaseline = "middle";
                ctx.textAlign = "center";
                for (let k = 0; k < spokes; k++) {
                    const a = 2 * Math.PI * k / spokes;
                    const deg = Math.round(360 * k / spokes * 10) / 10;
                    ctx.fillText(deg + "\u00b0", g.cx + Math.sin(a) * (R + 13), g.cy - Math.cos(a) * (R + 13));
                }
                ctx.textAlign = "left";
                for (let i = 1; i <= rings; i++) {
                    ctx.fillText(fmt(g.R * i / rings) + unit, g.cx + 4, g.cy - R * i / rings - 6);
                }
            }
        } else {
            const step = Math.max(1e-9, num(C.grid_step, 50));
            const hx = g.pw / 2, hy = g.ph / 2;
            const nx = Math.floor(hx / step + 1e-9), ny = Math.floor(hy / step + 1e-9);
            ctx.strokeStyle = gc;
            if (nx <= 200 && ny <= 200) {
                for (let i = -nx; i <= nx; i++) {
                    const x = g.cx + i * step * g.s;
                    ctx.lineWidth = i === 0 ? 1.6 : 1;
                    ctx.beginPath(); ctx.moveTo(x, g.cy - hy * g.s); ctx.lineTo(x, g.cy + hy * g.s); ctx.stroke();
                }
                for (let j = -ny; j <= ny; j++) {
                    const y = g.cy - j * step * g.s;
                    ctx.lineWidth = j === 0 ? 1.6 : 1;
                    ctx.beginPath(); ctx.moveTo(g.cx - hx * g.s, y); ctx.lineTo(g.cx + hx * g.s, y); ctx.stroke();
                }
                if (labels) {
                    ctx.fillStyle = "#94a3b8";
                    const skip = Math.max(1, Math.ceil(34 / (step * g.s)));
                    ctx.textBaseline = "middle"; ctx.textAlign = "center";
                    for (let i = -nx; i <= nx; i++) {
                        if (i % skip === 0) ctx.fillText(fmt(i * step), g.cx + i * step * g.s, g.cy + hy * g.s + 11);
                    }
                    ctx.textAlign = "right";
                    for (let j = -ny; j <= ny; j++) {
                        if (j % skip === 0) ctx.fillText(fmt(j * step), g.cx - hx * g.s - 6, g.cy - j * step * g.s);
                    }
                }
            }
            ctx.strokeStyle = "#475569"; ctx.lineWidth = 2;
            ctx.strokeRect(g.cx - hx * g.s, g.cy - hy * g.s, g.pw * g.s, g.ph * g.s);
        }
        ctx.restore();
    }

    function drawShape(g) {
        if (shape.length < 2) return;
        const sc = C.shape_color || "#f59e0b";
        ctx.save();
        ctx.beginPath();
        shape.forEach(function (p, i) {
            const x = g.cx + p[0] * g.s, y = g.cy - p[1] * g.s;
            if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        });
        if (shape.length >= 3) {
            ctx.closePath();
            ctx.globalAlpha = 0.12; ctx.fillStyle = sc; ctx.fill(); ctx.globalAlpha = 1;
        }
        ctx.strokeStyle = sc; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
        ctx.restore();
    }

    function drawSweep(g, now) {
        const ms = Math.max(200, num(C.sweep_ms, 4000));
        const head = ((now % ms) / ms) * 2 * Math.PI;      // 0 = N, sentido horario
        const col = C.point_color || "#22d3ee";
        const R = g.R * g.s, N = 36, d = Math.PI / 180 * 1.5;
        ctx.save();
        ctx.fillStyle = col;
        for (let k = 0; k < N; k++) {
            const a1 = head - k * d - Math.PI / 2, a0 = a1 - d;
            ctx.globalAlpha = 0.22 * (1 - k / N);
            ctx.beginPath(); ctx.moveTo(g.cx, g.cy); ctx.arc(g.cx, g.cy, R, a0, a1 + 0.002); ctx.closePath(); ctx.fill();
        }
        ctx.globalAlpha = 0.8; ctx.strokeStyle = col; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(g.cx, g.cy);
        ctx.lineTo(g.cx + Math.sin(head) * R, g.cy - Math.cos(head) * R); ctx.stroke();
        ctx.restore();
    }

    function drawMarker(kind, x, y, size, color, glowColor, alpha, glow) {
        const h = size / 2;
        const passes = glow > 0 ? 2 : 1;                   // dos pasadas = glow más intenso
        for (let pass = 0; pass < passes; pass++) {
            ctx.save();
            ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
            ctx.strokeStyle = color; ctx.fillStyle = color;
            ctx.lineWidth = Math.max(1.5, size / 5);
            ctx.lineCap = "round"; ctx.lineJoin = "round";
            if (glow > 0) { ctx.shadowColor = glowColor; ctx.shadowBlur = glow; }
            const dot = function () { ctx.beginPath(); ctx.arc(x, y, h, 0, Math.PI * 2); ctx.fill(); };
            if (kind === "img") {
                if (img && img.naturalWidth) {
                    const k = Math.min(size / img.naturalWidth, size / img.naturalHeight);
                    const iw = img.naturalWidth * k, ih = img.naturalHeight * k;
                    ctx.drawImage(img, x - iw / 2, y - ih / 2, iw, ih);
                } else { dot(); }
            } else if (kind === "char") {
                ctx.font = "700 " + Math.round(size * 1.4) + "px ui-sans-serif,system-ui,sans-serif";
                ctx.textAlign = "center"; ctx.textBaseline = "middle";
                ctx.fillText(C.marker_char || "\u25c6", x, y);
            } else if (kind === "cross") {
                ctx.beginPath();
                ctx.moveTo(x - h, y - h); ctx.lineTo(x + h, y + h);
                ctx.moveTo(x + h, y - h); ctx.lineTo(x - h, y + h);
                ctx.stroke();
            } else if (kind === "tri") {
                const r = h * 1.15;
                ctx.beginPath();
                ctx.moveTo(x, y - r);
                ctx.lineTo(x + r * 0.87, y + r * 0.5);
                ctx.lineTo(x - r * 0.87, y + r * 0.5);
                ctx.closePath(); ctx.stroke();
            } else if (kind === "star") {
                ctx.beginPath();
                for (let i = 0; i < 3; i++) {
                    const a = i * Math.PI / 3;
                    ctx.moveTo(x - Math.cos(a) * h, y - Math.sin(a) * h);
                    ctx.lineTo(x + Math.cos(a) * h, y + Math.sin(a) * h);
                }
                ctx.stroke();
            } else { dot(); }
            ctx.restore();
        }
    }

    function drawObjects(g, now) {
        const kind = kindOf();
        const size = Math.max(3, num(C.marker_size, 12));
        const period = num(C.blink_ms, 0);
        const pulse = period > 0 ? 0.5 + 0.5 * Math.cos(2 * Math.PI * now / period) : 1;
        const glowMax = Math.max(0, num(C.glow_size, 0));
        const fade = num(C.fade_s, 0);
        const objLabels = truthy(C.show_object_labels);
        const hide = truthy(C.hide_outside_shape) && !g.polar && shape.length >= 3;

        objs.forEach(function (ob, id) {
            let life = 1;
            if (fade > 0) {
                const age = (now - ob.seen) / 1000;
                if (age > fade) { objs.delete(id); return; }
                life = 1 - age / fade;
            }
            if (!g.inside(ob.x, ob.y)) return;
            if (hide && !inShape(ob.x, ob.y)) return;

            const glowCol = ob.color || C.point_color || "#22d3ee";
            const symCol = ob.color || C.marker_color || "#ffffff";
            const x = g.cx + ob.x * g.s, y = g.cy - ob.y * g.s;

            ctx.save();
            ctx.fillStyle = glowCol;
            ob.trail.forEach(function (p, i) {
                if (!g.inside(p.x, p.y)) return;
                ctx.globalAlpha = life * 0.5 * (i + 1) / (ob.trail.length + 1);
                ctx.beginPath();
                ctx.arc(g.cx + p.x * g.s, g.cy - p.y * g.s, 2.2, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.restore();

            drawMarker(kind, x, y, size, symCol, glowCol, life * (0.35 + 0.65 * pulse), glowMax * (0.35 + 0.65 * pulse));

            if (objLabels) {
                ctx.save();
                ctx.globalAlpha = life;
                ctx.fillStyle = glowCol;
                ctx.font = "10px ui-sans-serif,system-ui,sans-serif";
                ctx.textAlign = "left"; ctx.textBaseline = "middle";
                ctx.fillText(ob.label !== undefined ? ob.label : ob.id, x + size / 2 + 5, y);
                ctx.restore();
            }
        });
    }

    function frame() {
        if (!document.body.contains(root)) return;
        const r = cv.getBoundingClientRect();
        if (r.width !== W || r.height !== H) resize();
        if (W > 0 && H > 0) {
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, W, H);
            ctx.fillStyle = C.bg_color || "#0b1220";
            ctx.fillRect(0, 0, W, H);
            const now = performance.now();
            const g = geom();
            drawGrid(g);
            if (g.polar) { if (truthy(C.sweep)) drawSweep(g, now); } else { drawShape(g); }
            drawObjects(g, now);
        }
        requestAnimationFrame(frame);
    }

    // ---------------- datos que llegan desde Python ----------------
    function toXY(o) {
        const x = Number(o.x), y = Number(o.y);
        if (o.x !== undefined && o.y !== undefined && Number.isFinite(x) && Number.isFinite(y)) return { x: x, y: y };
        const a = Number(o.angle !== undefined ? o.angle : o.theta);
        const r = Number(o.range !== undefined ? o.range : (o.r !== undefined ? o.r : o.distance));
        if (Number.isFinite(a) && Number.isFinite(r)) {
            const rad = a * Math.PI / 180;
            return { x: r * Math.sin(rad), y: r * Math.cos(rad) };
        }
        return null;
    }

    function upsert(o) {
        if (!o || typeof o !== "object") return;
        const p = toXY(o);
        if (!p) return;
        const id = String(o.id !== undefined ? o.id : "default");
        let ob = objs.get(id);
        if (!ob) { ob = { id: id, trail: [] }; objs.set(id, ob); }
        if (ob.x !== undefined) ob.trail.push({ x: ob.x, y: ob.y });
        const n = Math.max(0, Math.floor(num(C.trail_length, 0)));
        while (ob.trail.length > n) ob.trail.shift();
        ob.x = p.x; ob.y = p.y;
        if (o.color) ob.color = String(o.color);
        if (o.label !== undefined) ob.label = String(o.label);
        ob.seen = performance.now();
    }

    function apply(val) {
        if (val === null || val === undefined) return;
        if (typeof val === "string") {
            try { val = JSON.parse(val); } catch (e) { return; }
        }
        if (Array.isArray(val)) { val.forEach(upsert); return; }
        if (typeof val !== "object") return;
        const act = String(val.action || "").toLowerCase();
        if (act === "clear") { objs.clear(); return; }
        if (act === "remove") { objs.delete(String(val.id !== undefined ? val.id : "default")); return; }
        if (act === "set") { objs.clear(); (val.objects || []).forEach(upsert); return; }
        if (Array.isArray(val.objects)) { val.objects.forEach(upsert); return; }
        upsert(val);
    }

    // ---------------- eventos hacia Python ----------------
    function emit(name, value) {
        if (typeof emitEvent === "function") emitEvent({ id: C.id }, name, value);
    }

    function posInfo(x, y) {
        let a = Math.atan2(x, y) * 180 / Math.PI;
        if (a < 0) a += 360;
        return { x: round3(x), y: round3(y), angle: round3(a), range: round3(Math.hypot(x, y)) };
    }

    cv.addEventListener("click", function (e) {
        const r = cv.getBoundingClientRect();
        const px = e.clientX - r.left, py = e.clientY - r.top;
        const g = geom();
        const wx = (px - g.cx) / g.s, wy = -(py - g.cy) / g.s;
        let best = null, bd = Infinity;
        objs.forEach(function (ob) {
            const d = Math.hypot(px - (g.cx + ob.x * g.s), py - (g.cy - ob.y * g.s));
            if (d < bd) { bd = d; best = ob; }
        });
        const tol = Math.max(10, num(C.marker_size, 12) / 2 + 6);
        if (best && bd <= tol) emit("on_object_click", Object.assign({ id: best.id }, posInfo(best.x, best.y)));
        if (g.inside(wx, wy)) emit("on_click", posInfo(wx, wy));
    });

    window.__widgets = window.__widgets || {};
    window.__widgets[C.id] = {
        update: apply,
        update_prop: function (prop, val) {
            C[prop] = String(val);
            if (prop === "shape") parseShape();
            else if (prop === "marker_image") loadImage();
            else if (prop === "label") paintTitle();
        },
        clear: function () { objs.clear(); }
    };

    parseShape();
    loadImage();
    paintTitle();
    requestAnimationFrame(frame);
})();
</script>
'''