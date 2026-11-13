import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser, scrolledtext
import json
import zipfile
import io
import os
import importlib.util
import sys
import copy
import math
import re

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

CUSTOM_WIDGETS_DIR = "custom_widgets"

THEMES = {
    "light": {
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "fg": "#1e293b",
        "border": "#cbd5e1",
        "accent": "#2563eb",
        "canvas": "#ffffff",
        "select": "#f59e0b",  # Fucsia/Púrpura vibrante (destaca perfecto sobre blanco y gráficos azules)
        
    },
    "dark": {
        "bg": "#121212",
        "panel": "#1e1e1e",
        "fg": "#e1e4e8",
        "border": "#2d2d2d",
        "accent": "#38bdf8",
        "canvas": "#09090b",
        "select": "#f59e0b",  # Naranja ámbar original para modo oscuro
    },
    "wii": {
        "bg": "#e2e8f0",
        "panel": "#ffffff",
        "fg": "#334155",
        "border": "#cbd5e1",
        "accent": "#00a0e9",
        "canvas": "#f1f5f9",
        "select": "#9333ea",  # Morado brillante ideal para el estilo Wii
    },
}

WIDGET_EVENTS_MAP = {
    "Button": ["on_click"],
    "ToggleSwitch": ["on_value_change", "on_click"],
    "Slider": ["on_value_change"],
    "CheckBox": ["on_value_change", "on_click"],
    "TextBox": ["on_value_change", "on_update"],
    "NumberBox": ["on_value_change", "on_update"],
    "Label": ["on_click", "on_update"],
    "Keyboard": ["on_key_pressed"],
    "Knob": ["on_value_change"],
    "LED": ["on_update", "on_click"],
    "Gauge": ["on_update"],
    "Clock": ["on_update"],
    "Compass": ["on_update"],
    "SevenSegment": ["on_update"],
    "ProgressBar": ["on_update"]
}


# Ayuda de ui.set_value() por tipo de widget. {id} se reemplaza por el ID real del widget.
WIDGET_VALUE_HELP = {
    "LED": {
        "tipo": "Boolean",
        "valores": "True / False",
        "desc": "True enciende el LED con resplandor del color configurado. False lo apaga (gris).",
        "ejemplos": ["ui.set_value('{id}', True)", "ui.set_value('{id}', False)"],
        "envia": "on_click a True",
        "notas": ["Usa booleanos reales. El string \"False\" se interpreta como verdadero en JavaScript."],
    },
    "CheckBox": {
        "tipo": "Boolean",
        "valores": "True / False",
        "desc": "Marca (True) o desmarca (False) la casilla.",
        "ejemplos": ["ui.set_value('{id}', True)"],
        "envia": "on_click / on_value_change a bool",
        "notas": ["Usa booleanos reales, no strings."],
    },
    "ToggleSwitch": {
        "tipo": "Boolean",
        "valores": "True / False",
        "desc": "Pone el switch en ON (True) u OFF (False). Repinta color, knob y texto.",
        "ejemplos": ["ui.set_value('{id}', True)"],
        "envia": "on_click / on_value_change a bool",
        "notas": ["Usa booleanos reales, no strings."],
    },
    "Slider": {
        "tipo": "Number",
        "valores": "0 a 100",
        "desc": "Mueve el control deslizante a la posición indicada.",
        "ejemplos": ["ui.set_value('{id}', 75)"],
        "envia": "on_value_change a número",
        "notas": ["El slider del navegador tiene min=0 y max=100."],
    },
    "Knob": {
        "tipo": "Number",
        "valores": "0 a 100",
        "desc": "Gira la perilla de -135° (0) a +135° (100).",
        "ejemplos": ["ui.set_value('{id}', 50)"],
        "envia": "on_value_change a número",
        "notas": [],
    },
    "Gauge": {
        "tipo": "Number",
        "valores": "0 a 100 (se limita a ese rango)",
        "desc": "Tacómetro: rota la aguja de -120° a +120°. Circular: rellena el arco y muestra el número.",
        "ejemplos": ["ui.set_value('{id}', 80)"],
        "envia": "(solo on_update)",
        "notas": ["Valores fuera de 0-100 se recortan."],
    },
    "ProgressBar": {
        "tipo": "Number",
        "valores": "0 a 100",
        "desc": "Llena la barra y muestra el valor como porcentaje.",
        "ejemplos": ["ui.set_value('{id}', 60)"],
        "envia": "(solo on_update)",
        "notas": ["No se limita el rango: 150 se mostraría como 150%."],
    },
    "Compass": {
        "tipo": "Number",
        "valores": "0 a 360 (grados)",
        "desc": "Rota la aguja. 0 = N, 90 = E, 180 = S, 270 = W.",
        "ejemplos": ["ui.set_value('{id}', 270)"],
        "envia": "(solo on_update)",
        "notas": [],
    },
    "NumberBox": {
        "tipo": "Number",
        "valores": "Cualquier número",
        "desc": "Escribe el número en la caja de texto numérica.",
        "ejemplos": ["ui.set_value('{id}', 3.14)"],
        "envia": "on_value_change / on_update a número",
        "notas": [],
    },
    "TextBox": {
        "tipo": "String",
        "valores": "Cualquier texto",
        "desc": "Escribe el texto en la caja.",
        "ejemplos": ["ui.set_value('{id}', 'Hola')"],
        "envia": "on_value_change / on_update a string",
        "notas": [],
    },
    "Label": {
        "tipo": "String",
        "valores": "Cualquier texto",
        "desc": "Cambia el texto mostrado en la etiqueta.",
        "ejemplos": ["ui.set_value('{id}', 'Temperatura: 25 °C')"],
        "envia": "on_click a True",
        "notas": ["Para cambiar color o forma usa ui.set_property(...), no set_value."],
    },
    "SevenSegment": {
        "tipo": "Number o String de dígitos",
        "valores": "Dígitos 0-9",
        "desc": "Muestra el valor rellenando con ceros a la izquierda hasta el número de dígitos configurado. Si es más largo, conserva los últimos N dígitos.",
        "ejemplos": ["ui.set_value('{id}', 1234)", "ui.set_value('{id}', '0042')"],
        "envia": "(solo on_update)",
        "notas": ["Solo se dibujan 0-9. Cualquier otro carácter (-, .) se muestra como 0."],
    },
    "StatusBar": {
        "tipo": "Boolean o String",
        "valores": "True / 'online' / 'true' = Online. Cualquier otro = Offline",
        "desc": "Cambia el indicador entre Online (verde, pulsante) y Offline (rojo).",
        "ejemplos": ["ui.set_value('{id}', 'online')", "ui.set_value('{id}', False)"],
        "envia": "(ninguno)",
        "notas": [],
    },
    "Keyboard": {
        "soportado": False,
        "desc": "Solo emite eventos. Envía el texto de la tecla (ej. 'A', 'SPACE', 'ENTER') en on_key_pressed.",
        "envia": "on_key_pressed a string",
    },
    "Button": {
        "soportado": False,
        "desc": "Solo emite eventos. on_click envía True.",
        "envia": "on_click a True",
    },
    "Clock": {"soportado": False, "desc": "Se actualiza solo con la hora del navegador.", "envia": "(solo on_update)"},
    "VerticalContainer": {"soportado": False, "desc": "Contenedor de diseño. No recibe valores."},
    "HorizontalContainer": {"soportado": False, "desc": "Contenedor de diseño. No recibe valores."},
    "MatrixContainer": {"soportado": False, "desc": "Contenedor de diseño. No recibe valores."},
    "Tabs": {"soportado": False, "desc": "No recibe valores."},
}

APP_PY = r'''
#import eventlet
#eventlet.monkey_patch()
import os, json, traceback, importlib.util
from flask import Flask, render_template
from flask_socketio import SocketIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_DIR = os.path.join(BASE_DIR, 'events')
PROJECT_FILE = os.path.join(BASE_DIR, 'project.json')
APP_VERSION = 'diag-3'
print(f'[app] version={APP_VERSION} dir={BASE_DIR}')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = 'iot_secret'
#socketio = SocketIO(app, cors_allowed_origins='*')
socketio = SocketIO(app, async_mode="threading")

event_handlers = {}
_running = set()


class UIProxy:
    def __init__(self, sio):
        self.sio = sio
        self._listeners = {}
        self._values = {}
        
    def get(self, widget_id, default=None):
        """Último valor conocido del widget (o default si aún no hay)."""
        return self._values.get(widget_id, default)

    def set_property(self, widget_id, prop_name, value):
        try:
            with open(PROJECT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for w in data.get('widgets', []):
                if w['id'] == widget_id:
                    w['props'][prop_name] = value
            with open(PROJECT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception:
            traceback.print_exc()
        self.sio.emit('prop_update', {'id': widget_id, 'prop': prop_name, 'value': value})

    def set_value(self, widget_id, value):
        self._values[widget_id] = value
        self.sio.emit('update', {'id': widget_id, 'value': value})
        dispatch(widget_id, 'on_update', value)
    
    def on(self, widget_id, event, callback=None):
        def decorator(fn):
            key = (widget_id, event)
            if key not in self._listeners:
                self._listeners[key] = []
            if fn not in self._listeners[key]:
                self._listeners[key].append(fn)
            return fn

        if callable(callback):
            return decorator(callback)
        return decorator


ui_proxy = UIProxy(socketio)



def load_backend_plugins():
    """Carga hooks de backend de los plugins usados en project.json."""
    try:
        with open(PROJECT_FILE, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
    except Exception:
        print('[plugins] No se pudo leer project.json')
        traceback.print_exc()
        return

    plugin_dir = os.path.join(BASE_DIR, 'custom_widgets')
    if not os.path.isdir(plugin_dir):
        return

    used_types = sorted({
        str(w.get('type', '')).strip()
        for w in project_data.get('widgets', [])
        if w.get('type')
    })

    for widget_type in used_types:
        plugin_file = None
        for filename in os.listdir(plugin_dir):
            if filename.lower() == (widget_type + '.py').lower():
                plugin_file = os.path.join(plugin_dir, filename)
                break
        if not plugin_file:
            continue

        try:
            module_name = 'backend_plugin_' + widget_type.replace('-', '_')
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class = getattr(module, widget_type, None)
            if plugin_class is None:
                for attr_name in dir(module):
                    candidate = getattr(module, attr_name)
                    if isinstance(candidate, type) and attr_name.lower() == widget_type.lower():
                        plugin_class = candidate
                        break

            register = getattr(plugin_class, 'register_backend', None)
            if callable(register):
                print('[plugins] backend hook:', widget_type)
                register(app, socketio, project_data)
        except Exception:
            print('[plugins] ERROR cargando backend de', widget_type)
            traceback.print_exc()


def load_handlers():
    event_handlers.clear()
    if not os.path.isdir(EVENTS_DIR):
        print('[events] carpeta no encontrada:', EVENTS_DIR)
        return
    for fname in sorted(os.listdir(EVENTS_DIR)):
        if not fname.endswith('.py') or fname.startswith('__'):
            continue
        name = fname[:-3]
        try:
            spec = importlib.util.spec_from_file_location('events_' + name, os.path.join(EVENTS_DIR, fname))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            event_handlers[name] = mod
        except Exception:
            print('[events] ERROR cargando', fname)
            traceback.print_exc()
    print('[events] handlers cargados:', {k: [n for n in dir(v) if n.startswith('on_')] for k, v in event_handlers.items()})

# <-- NUEVO
def dispatch(widget_id, event_name, value):
    key = (widget_id, event_name)
    listeners = ui_proxy._listeners.get(key, [])
    
    mod = event_handlers.get(widget_id)
    fn = getattr(mod, event_name, None) if mod else None

    if not listeners and not callable(fn):
        return

    if key in _running:
        return
    _running.add(key)
    try:
        ctx = {'widget_id': widget_id, 'value': value, 'ui': ui_proxy, 'set_value': ui_proxy.set_value}
        
        # Ejecutar callbacks registrados con ui.on(...)
        for cb in list(listeners):
            try:
                cb(ctx)
            except Exception:
                traceback.print_exc()

        # 2. Ejecutar función del archivo en events/
        if callable(fn):
            fn(ctx)
    except Exception:
        traceback.print_exc()
    finally:
        _running.discard(key)



@app.route('/')
def index():
    with open(PROJECT_FILE, 'r', encoding='utf-8') as f:
        project_data = json.load(f)
    return render_template('dashboard.html', project=project_data)


@socketio.on('client_event')
def handle_client_event(data):
   #print('[client_event] recibido:', data)
   dispatch(data.get('id'), data.get('event_name'), data.get('value'))
@socketio.on('client_state')
def handle_client_state(data):
    ui_proxy._values[data.get('id')] = data.get('value')


load_handlers()
load_backend_plugins()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
'''

PROP_VARS = [
    "color", "clock_type", "gauge_model", "btn_style", "led_style",
    "seg_digits", "seg_color", "toggle_on_text", "toggle_off_text",
    "toggle_on_color", "toggle_off_color", "label_bg_color",
    "label_fg_color", "label_shape", "keyboard_rows","compass_heading", "knob_value", "prog_value", "tab_names",
]




class SlideButton(tk.Canvas):
    def __init__(self, master, variable=None, command=None, width=75, height=28, **kwargs):
        super().__init__(master, width=width, height=height, highlightthickness=0, bd=0, **kwargs)
        self.variable = variable
        self.command = command
        self.w_val = width
        self.h_val = height
        self.configure(bg=master.cget("bg"))
        
        # Determinar estado inicial
        if self.variable:
            val = self.variable.get()
            self.is_on = True if val in [True, "True", "true", "TRUE", 1, "1"] else False
            self.variable.trace_add("write", self._on_var_change)
        else:
            self.is_on = False
            
        # Vincular el clic directamente al canvas
        self.bind("<Button-1>", self.toggle)
        self.draw()

    def _on_var_change(self, *args):
        if not self.variable:
            return
        val = self.variable.get()
        new_state = True if val in [True, "True", "true", "TRUE", 1, "1"] else False
        if new_state != self.is_on:
            self.is_on = new_state
            self.draw()

    def toggle(self, event=None):
        self.is_on = not self.is_on
        if self.variable:
            # Forzar el texto exacto que esperan los widgets custom ("True" o "False")
            val_str = "True" if self.is_on else "False"
            self.variable.set(val_str)
        
        # Redibujar el botón gráficamente al instante
        self.draw()
        
        # Ejecutar la actualización de la app para que w.props recoja el nuevo valor
        if self.command:
            try:
                self.command()
            except TypeError:
                try:
                    self.command(None)
                except Exception:
                    pass

    def draw(self):
        self.delete("all")
        w = self.w_val
        h = self.h_val
        
        # Colores según el estado actual
        bg_color = "#10b981" if self.is_on else "#334155"
        knob_color = "#ffffff"
        
        # Dibujar contenedor redondeado
        self.create_rounded_rect(2, 2, w-2, h-2, radius=h-4, fill=bg_color, outline="")
        
        # Dibujar elementos internos según el estado
        if self.is_on:
            self.create_text(23, h/2, text="True", fill="#ffffff", font=("Segoe UI", 8, "bold"))
            self.create_oval(w - h + 2, 4, w - 6, h - 4, fill=knob_color, outline="")
        else:
            self.create_oval(4, 4, h - 2, h - 4, fill=knob_color, outline="")
            self.create_text(w - 23, h/2, text="False", fill="#ffffff", font=("Segoe UI", 8, "bold"))

    def create_rounded_rect(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
        
import tkinter as tk
from tkinter import ttk

class ScrollablePropContainer(tk.Frame):
    def __init__(self, parent, bg="#1e293b", **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        
        # Canvas principal
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Frame interno donde se empaquetarán todos los campos de propiedades
        self.inner_frame = tk.Frame(self.canvas, bg=bg)
        
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        # Crear la ventana dentro del canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        
        # Asegurar que el frame interno escale con el ancho del panel
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfig(self.canvas_window, width=event.width))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Posicionamiento en la interfaz
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Activar el scroll con la rueda del ratón (MouseWheel)
        self._bind_mouse_wheel(self.inner_frame)

    def _bind_mouse_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event):
        # Soporte multiplataforma para el desplazamiento de la rueda del ratón
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            # Para Linux (Button-4 y Button-5)
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    def clear(self):
        """Limpia todos los widgets hijos del contenedor interno."""
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
    
    def set_bg(self, bg):
        """Aplica el color de fondo a todas las capas del contenedor con scroll."""
        self.config(bg=bg)
        self.canvas.config(bg=bg)
        self.inner_frame.config(bg=bg)
            
            
            
            
            
            
            
            
            
class WidgetItem:
    def __init__(self, wid, wtype, x, y):
        self.id = wid
        self.type = wtype
        self.x = x
        self.y = y
        self.width = 380 if wtype == "Keyboard" else (350 if wtype in ["MatrixContainer"] else (300 if wtype in ["VerticalContainer", "HorizontalContainer"] else (180 if wtype == "SevenSegment" else (160 if wtype in ["Gauge", "Clock", "Compass", "Knob"] else (140 if wtype in ["ToggleSwitch", "Label"] else (220 if wtype == "ProgressBar" else 160))))))
        self.height = 200 if wtype == "Keyboard" else (250 if wtype in ["MatrixContainer"] else (200 if wtype in ["VerticalContainer", "HorizontalContainer"] else (140 if wtype == "Tabs" else (70 if wtype in ["SevenSegment", "ToggleSwitch"] else (50 if wtype == "Label" else (160 if wtype in ["Gauge", "Clock", "Compass", "Knob"] else (50 if wtype == "ProgressBar" else 100)))))))
        self.label = wtype
        self.color = "#ef4444" if wtype == "LED" else ("#10b981" if wtype == "Button" else "#3b82f6")
        
        self.events = {}
        self.clock_type = "Analogico" if wtype == "Clock" else ""
        self.gauge_model = "Tacometro Clasico" if wtype == "Gauge" else ""
        self.btn_style = "Neon Glow" if wtype == "Button" else ""
        self.led_style = "Neon Redondo" if wtype == "LED" else ""
        self.seg_digits = "4" if wtype == "SevenSegment" else ""
        self.seg_color = "#f97316" if wtype == "SevenSegment" else ""
        
        self.toggle_on_text = "ON"
        self.toggle_off_text = "OFF"
        self.toggle_on_color = "#22c55e"
        self.toggle_off_color = "#64748b"
        
        self.label_bg_color = "#1e293b"
        self.label_fg_color = "#f8fafc"
        self.label_shape = "Redondeada"
        
        self.keyboard_rows = "QWERTY" if wtype == "Keyboard" else ""
        self.compass_heading = "0 (N)" if wtype == "Compass" else ""
        self.knob_value = "50" if wtype == "Knob" else ""
        self.prog_value = "75" if wtype == "ProgressBar" else ""
        self.tab_names = "Tab 1, Tab 2, Tab 3" if wtype == "Tabs" else ""
        
        self.attached_widgets = []

    def to_dict(self):
        native = {
            "label": self.label, "color": self.color,
            "clock_type": self.clock_type, "gauge_model": self.gauge_model,
            "btn_style": self.btn_style, "led_style": self.led_style,
            "seg_digits": self.seg_digits, "seg_color": self.seg_color,
            "toggle_on_text": self.toggle_on_text, "toggle_off_text": self.toggle_off_text,
            "toggle_on_color": self.toggle_on_color, "toggle_off_color": self.toggle_off_color,
            "label_bg_color": self.label_bg_color, "label_fg_color": self.label_fg_color,
            "label_shape": self.label_shape,
            "keyboard_rows": self.keyboard_rows,
            "compass_heading": self.compass_heading, "knob_value": self.knob_value,
            "prog_value": self.prog_value, "tab_names": self.tab_names,
            "attached_widgets": self.attached_widgets,
        }
        # Las propiedades de plugins (img_release, etc.) ganan sobre las nativas
        custom = getattr(self, "props", None) or {}
        return {
            "id": self.id, "type": self.type, "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "props": {**native, **copy.deepcopy(custom)},
            "events": self.events,
        }

class IoTBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Dashboard Builder Pro")
        self.root.geometry("1400x850")
        
        self.current_theme = "dark"
        self.widgets = []
        self.selected = None
        self.editing_wid = None
        self.selected_widgets = [] 
        self.widget_counter = 0
        self.pending_type = None
        
        self.custom_widget_types = []
        self.load_custom_widgets_plugins()

        self.drag_data = {"item": None, "start_x": 0, "start_y": 0, "mode": "move"}
        self.selection_box = None
        self.sel_start_x = 0
        self.sel_start_y = 0
        self.resize_edge = None
        
        self.clipboard = []
        self.current_file_path = None
        self.undo_stack = []
        self.redo_stack = []
        self.widget_event_codes = {}

        self.setup_ui()
        self.apply_theme()
        
        
        # Shortcuts
        self.root.bind_all("<Control-s>", lambda e: self.save_project())
        self.root.bind_all("<Control-g>", lambda e: self.save_project())
        self.root.bind_all("<Control-o>", lambda e: self.load_project())
        self.root.bind_all("<Control-a>", lambda e: self.load_project())
        self.root.bind_all("<Control-e>", lambda e: self.export_flask_project())
        self.root.bind_all("<Control-z>", lambda e: self.undo_action())
        self.root.bind_all("<Control-y>", lambda e: self.redo_action())
        self.root.bind_all("<Control-n>", lambda e: self.new_project())
        self.root.bind_all("<Delete>", lambda e: self.safe_delete_selection())
        self.root.bind_all("<BackSpace>", lambda e: self.safe_delete_selection())
        self.root.bind_all("<Up>", self.navigate_widgets)
        self.root.bind_all("<Down>", self.navigate_widgets)
        self.root.bind_all("<Left>", self.navigate_widgets)
        self.root.bind_all("<Right>", self.navigate_widgets)
        
        self.unsaved_changes = False
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        if self.unsaved_changes:
            res = messagebox.askyesnocancel(
                "Guardar cambios",
                "Tienes cambios sin guardar. ¿Deseas guardarlos antes de salir?",
                parent=self.root
            )
            if res is True:  # Sí: intenta guardar y luego cierra
                # Llama a tu función de guardado (ej. self.save_project() o self.save_file())
                # Asegúrate de que esta función devuelva True si se guardó con éxito o maneje el archivo
                self.save_project() 
                self.root.destroy()
            elif res is False:  # No: cierra directamente sin guardar
                self.root.destroy()
            # Si es Cancelar (None), la aplicación no hace nada y se mantiene abierta
        else:
            self.root.destroy()
    
    def safe_delete_selection(self, event=None):
        # Ignora si son elementos del ui
        try:
            focused = self.root.focus_get()
            if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
                return
        except Exception:
            return
            
        self.delete_selection()
    
    def scroll_to_widget(self, w):
        """Desplaza automáticamente el canvas para hacer visible el widget w si está fuera de la vista."""
        canvas_h = self.canvas.winfo_height()
        canvas_w = self.canvas.winfo_width()
        total_h = 3000.0  # Coincide con el scrollregion=(0, 0, 3000, 3000) del canvas
        total_w = 3000.0

        y_view = self.canvas.yview()
        x_view = self.canvas.xview()

        current_top_y = y_view[0] * total_h
        current_bottom_y = y_view[1] * total_h

        current_left_x = x_view[0] * total_w
        current_right_x = x_view[1] * total_w

        margin = 40  # Margen de seguridad en píxeles

        # Verificación vertical
        target_y_fraction = None
        if w.y < current_top_y + margin:
            target_y_fraction = max(0.0, (w.y - margin) / total_h)
        elif w.y + w.height > current_bottom_y - margin:
            target_y_fraction = max(0.0, (w.y + w.height + margin - canvas_h) / total_h)

        if target_y_fraction is not None:
            self.canvas.yview_moveto(target_y_fraction)

        # Verificación horizontal
        target_x_fraction = None
        if w.x < current_left_x + margin:
            target_x_fraction = max(0.0, (w.x - margin) / total_w)
        elif w.x + w.width > current_right_x - margin:
            target_x_fraction = max(0.0, (w.x + w.width + margin - canvas_w) / total_w)

        if target_x_fraction is not None:
            self.canvas.xview_moveto(target_x_fraction)
            
    def navigate_widgets(self, event):
        try:
            focused = self.root.focus_get()
            # Añadimos tk.Listbox para que si la lista tiene el foco, las flechas funcionen en ella
            if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, tk.Listbox)):
                return
        except Exception:
            return

        # Si no hay widget seleccionado o solo hay uno, no hace nada
        if not self.selected or len(self.widgets) <= 1:
            return

        curr = self.selected
        curr_cx = curr.x + curr.width / 2
        curr_cy = curr.y + curr.height / 2

        direction = event.keysym  # 'Up', 'Down', 'Left', 'Right'
        best_candidate = None
        min_score = float("inf")

        for w in self.widgets:
            if w.id == curr.id:
                continue

            w_cx = w.x + w.width / 2
            w_cy = w.y + w.height / 2

            dx = w_cx - curr_cx
            dy = w_cy - curr_cy

            # Filtra por dirección y calcula la puntuación ponderada
            # (se le da doble peso al eje secundario para favorecer alineación directa)
            if direction == "Up" and dy < -5:
                score = abs(dy) + 2.0 * abs(dx)
            elif direction == "Down" and dy > 5:
                score = abs(dy) + 2.0 * abs(dx)
            elif direction == "Left" and dx < -5:
                score = abs(dx) + 2.0 * abs(dy)
            elif direction == "Right" and dx > 5:
                score = abs(dx) + 2.0 * abs(dy)
            else:
                continue

            if score < min_score:
                min_score = score
                best_candidate = w

        # Selecciona el candidato más cercano en esa dirección
        if best_candidate:
            self.selected_widgets = [best_candidate]
            self.select_widget(best_candidate)
            self.scroll_to_widget(best_candidate)
    
    def remove_event_function(self, wid, ev):
        code = self.widget_event_codes.get(wid)
        if code is None:
            return
        code = re.sub(rf"^def {re.escape(ev)}\(.*?(?=^def |\Z)", "", code, flags=re.S | re.M)
        if re.search(r"^def \w+\(", code, flags=re.M):
            self.widget_event_codes[wid] = code.rstrip() + "\n"
        else:
            del self.widget_event_codes[wid]
    
    
    def event_template(self, ev):
        return (
            f"def {ev}(context):\n"
            f"    widget_id = context.get('widget_id')\n"
            f"    value = context.get('value')\n"
            f"    ui = context.get('ui')\n"
            f"    # Ej Modify Properties: ui.set_property('label_0', 'label', 'Texto nuevo')\n"
            f"    # Ej Set Values: ui.set_value('led_0', True)\n"
            f"    print('Evento {ev} de ' + str(widget_id) + ' valor: ' + str(value))\n"
        )

    def ensure_event_functions(self, w):
        code = self.widget_event_codes.get(w.id, f"# Controlador para el widget: {w.id}\n\n")
        for ev in w.events:
            if f"def {ev}(" not in code:
                code += "\n" + self.event_template(ev)
        if w.events:
            self.widget_event_codes[w.id] = code

    def migrate_legacy_events(self, w):
        valid = WIDGET_EVENTS_MAP.get(w.type, ["on_click", "on_update"])

        # Solo eventos válidos para este tipo; onClick / on_action / "" se descartan
        w.events = {ev: ev for ev in w.events if ev in valid}

        # Sin eventos válidos, sin script
        if not w.events:
            self.widget_event_codes.pop(w.id, None)
            return

        code = self.widget_event_codes.get(w.id, f"# Controlador para el widget: {w.id}\n\n")
        code = code.replace(">OBJECT_NAME>", w.id).replace("OBJECT_NAME", w.id)

        # Renombrar funciones legacy a los eventos válidos que aún no tienen función
        missing = [ev for ev in w.events if f"def {ev}(" not in code]

        def repl(m):
            if m.group(1) in valid or not missing:
                return m.group(0)
            return f"def {missing.pop(0)}(context)"

        code = re.sub(r"def (\w+)\(context\)", repl, code)
        first_ev = next(iter(w.events))
        code = re.sub(r"'(onClick|onChange|onValueChange|onUpdate)'", f"'{first_ev}'", code)

        self.widget_event_codes[w.id] = code.rstrip() + "\n"

    def repair_all_events(self):
        ids = {w.id for w in self.widgets}
        for wid in list(self.widget_event_codes):
            if wid not in ids:
                del self.widget_event_codes[wid]
        for w in self.widgets:
            self.migrate_legacy_events(w)
            self.ensure_event_functions(w)
        self.refresh_scripts_list()
        
    def sync_vars_from_widget(self, w):
        if not w:
            return
            
        # Lista de propiedades estándar que intentamos sincronizar con las variables de la UI
        # Puedes adaptar o añadir los nombres de variables que maneje tu inspector
        standard_props = ['label', 'color', 'clock_type', 'gauge_model', 'btn_style', 
                          'led_style', 'seg_digits', 'seg_color', 'toggle_on_text', 
                          'toggle_off_text', 'toggle_on_color', 'toggle_off_color', 
                          'label_bg_color', 'label_fg_color', 'label_shape', 
                          'keyboard_rows', 'compass_heading', 'knob_value', 'prog_value', 'tab_names']

        for p in standard_props:
            var_name = f"var_{p}"
            if hasattr(self, var_name):
                ui_var = getattr(self, var_name)
                
                # 1. Intentar obtener el valor del atributo directo del widget
                val = getattr(w, p, None)
                
                # 2. Si no lo tiene directamente, buscar en w.props
                if val is None and hasattr(w, 'props') and isinstance(w.props, dict):
                    val = w.props.get(p, None)
                    
                # 3. Si aún no existe, buscar en default_props de la clase del widget
                if val is None and hasattr(w, 'default_props') and isinstance(w.default_props, dict):
                    val = w.default_props.get(p, "")
                
                # Asignar a la variable de Tkinter de forma segura si encontramos un valor
                if val is not None:
                    try:
                        ui_var.set(val)
                    except Exception:
                        pass

    def sync_widget_from_vars(self, w):
        for p in PROP_VARS:
            var = getattr(self, f"var_{p}", None)
            if var is not None:
                setattr(w, p, var.get())

    def load_custom_widgets_plugins(self):
        self.custom_widget_types.clear()
        
        # Diccionario para almacenar las clases de los plugins y sus metadatos
        if not hasattr(self, 'custom_widget_classes'):
            self.custom_widget_classes = {}

        if not os.path.exists(CUSTOM_WIDGETS_DIR): 
            os.makedirs(CUSTOM_WIDGETS_DIR)

        for file in os.listdir(CUSTOM_WIDGETS_DIR):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                path = os.path.join(CUSTOM_WIDGETS_DIR, file)
                try:
                    # Carga dinámica del módulo del plugin
                    spec = importlib.util.spec_from_file_location(module_name, path)
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)

                    # Buscar la clase principal dentro del archivo (ej. Radiobutton, Scrolllist, etc.)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if isinstance(attr, type) and attr_name.lower() == module_name.lower():
                            widget_class = attr
                            # print("Widget.name=",widget_class.__name__)
                            # Definir o recuperar propiedades por defecto desde la clase del plugin
                            # Si el plugin define un atributo de clase 'default_props', lo usamos; si no, creamos uno base.
                            if not hasattr(widget_class, 'default_props'):
                                widget_class.default_props = {"label": widget_class.__name__}
                            # else:
                                # print("Widget.props: ", widget_class.default_props)
                            
                            # 2. Definir o recuperar eventos soportados desde la clase del plugin
                            # Si el plugin define 'supported_events', lo usamos; si no, asignamos por defecto.
                            if not hasattr(widget_class, 'supported_events'):
                                widget_class.supported_events = ["on_click"]
                            # else:
                                # print("Widget.events: ", widget_class.supported_events)

                            # Registrar el tipo de widget en el builder
                            w_type_name = widget_class.__name__
                            self.custom_widget_types.append(w_type_name)
                            self.custom_widget_classes[w_type_name] = widget_class

                            # Sincronizar automáticamente con el mapa global de eventos del builder
                            WIDGET_EVENTS_MAP[w_type_name] = widget_class.supported_events
                            # Registrar la ayuda de set_value del plugin
                            help_info = getattr(widget_class, "value_help", None)
                            if callable(help_info):  # también acepta un staticmethod/classmethod
                                try:
                                    help_info = help_info()
                                except Exception as ex:
                                    print(f"[Error] value_help de {w_type_name}: {ex}")
                                    help_info = None
                            if isinstance(help_info, dict):
                                WIDGET_VALUE_HELP[w_type_name] = help_info
                            else:
                                WIDGET_VALUE_HELP.pop(w_type_name, None)
                            break

                except Exception as e:
                    print(f"[Error] Cargando plugin {file}: {e}")

    def save_state(self):
        self.undo_stack.append([copy.deepcopy(w.to_dict()) for w in self.widgets])
        self.redo_stack.clear()
        self.unsaved_changes = True

    def undo_action(self):
        if not self.undo_stack: return
        self.redo_stack.append([copy.deepcopy(w.to_dict()) for w in self.widgets])
        self.load_widgets_from_state(self.undo_stack.pop())
        self.unsaved_changes = True

    def redo_action(self):
        if not self.redo_stack: return
        self.undo_stack.append([copy.deepcopy(w.to_dict()) for w in self.widgets])
        self.load_widgets_from_state(self.redo_stack.pop())

    def load_widgets_from_state(self, state_list):
        self.widgets.clear()
        self.canvas.delete("all")
        self.widget_counter = 0
        self.selected_widgets.clear()

        for item in state_list:
            w_type = item.get("type", "Button")
            w_id = item.get("id", f"w_{self.widget_counter}")

            # Maneja plugins y widgets nativos, y restaura todas sus propiedades
            w = self._build_widget_from_dict({**item, "id": w_id, "type": w_type})

            self.widgets.append(w)
            self.draw_widget(w)
            self.widget_counter += 1

        self.select_widget(None)
        self.refresh_scripts_list()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')  # 'clam' permite mayor personalización de colores en widgets ttk
        t = THEMES[self.current_theme]
        # Combobox
        style.map('TCombobox',  fieldbackground=[('readonly', t["bg"])], selectbackground=[('readonly', t["accent"])], foreground=[('readonly', t["fg"])])
        style.configure('TCombobox',  fieldbackground=t["bg"],  background=t["panel"],  foreground=t["fg"], arrowcolor=t["accent"])
        # Barras de desplazamiento (Scrollbars) vertical y horizontal
        style.configure('TScrollbar', background=t["panel"],  troughcolor=t["bg"],  bordercolor=t["border"],  arrowcolor=t["fg"])
        
        self.toolbar = tk.Frame(self.root, height=50)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.lbl_title = tk.Label(self.toolbar, text="IoT Dashboard Builder Pro", font=("Segoe UI", 12, "bold"))
        self.lbl_title.pack(side=tk.LEFT, padx=15)
        
        self.theme_var = tk.StringVar(value=self.current_theme)
        self.theme_menu = ttk.Combobox(self.toolbar, textvariable=self.theme_var, values=["light", "dark", "wii"], state="readonly", width=10)
        self.theme_menu.pack(side=tk.LEFT, padx=10)
        self.theme_menu.bind("<<ComboboxSelected>>", self.change_theme_event)
        
        tk.Button(self.toolbar, text="Nuevo", command=self.new_project, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="Guardar", command=self.save_project, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="Abrir", command=self.load_project, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar, text="Nuevo Widget", command=self.open_new_widget_dialog, bg="#8b5cf6", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=10)
        self.btn_export = tk.Button(self.toolbar, text="Exportar Flask", command=self.export_flask_project, bg="#10b981", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2")
        self.btn_export.pack(side=tk.RIGHT, padx=15, pady=8)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.tab_designer = tk.Frame(self.notebook)
        self.tab_code = tk.Frame(self.notebook)
        self.notebook.add(self.tab_designer, text="Disenador Visual")
        self.notebook.add(self.tab_code, text="Editor de Codigo de Eventos")

        self.left_panel = tk.Frame(self.tab_designer, width=240)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.lbl_lib = tk.Label(self.left_panel, text="Biblioteca de Widgets", font=("Segoe UI", 10, "bold"))
        self.lbl_lib.pack(pady=10)
        
        t_init = THEMES[self.current_theme]
        self.canvas_lib = tk.Canvas(self.left_panel, highlightthickness=0, bg=t_init["panel"])
        self.scrollbar_lib = ttk.Scrollbar(self.left_panel, orient="vertical", command=self.canvas_lib.yview)
        self.lib_inner = tk.Frame(self.canvas_lib, bg=t_init["panel"])
        self.lib_inner.bind("<Configure>", lambda e: self.canvas_lib.configure(scrollregion=self.canvas_lib.bbox("all")))
        self.canvas_lib.create_window((0, 0), window=self.lib_inner, anchor="nw")
        self.canvas_lib.configure(yscrollcommand=self.scrollbar_lib.set)
        self.canvas_lib.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar_lib.pack(side=tk.RIGHT, fill=tk.Y)

        categories = {
            "Controles": ["Button", "ToggleSwitch", "Slider", "CheckBox", "TextBox", "NumberBox", "Keyboard", "Knob"],
            "Indicadores": ["LED", "Gauge", "SevenSegment", "StatusBar", "Clock", "Compass", "ProgressBar"],
            "Containers": ["VerticalContainer", "HorizontalContainer", "MatrixContainer", "Tabs"],
            "Texto y Visualizacion": ["Label"],
            "Plugins": self.custom_widget_types
        }

        for cat, items in categories.items():
            if not items: continue
            tk.Label(self.lib_inner, text=f"- {cat}", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill=tk.X, padx=5, pady=(5, 2))
            for item in items:
                b = tk.Button(self.lib_inner, text=f"    {item}", anchor="w", relief=tk.FLAT, cursor="hand2")
                b.pack(fill=tk.X, padx=15, pady=1)
                b.bind("<Button-1>", lambda e, wtype=item: self.set_pending(wtype))

        self.right_panel = tk.Frame(self.tab_designer, width=280)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.lbl_insp = tk.Label(self.right_panel, text="Inspector de Propiedades", font=("Segoe UI", 10, "bold"))
        self.lbl_insp.pack(pady=10)

        self.var_id, self.var_label = tk.StringVar(), tk.StringVar()
        self.var_x, self.var_y, self.var_w, self.var_h = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.var_color, self.var_clock_type, self.var_gauge_model = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.var_btn_style, self.var_led_style, self.var_seg_digits, self.var_seg_color = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        
        self.var_toggle_on_text, self.var_toggle_off_text = tk.StringVar(), tk.StringVar()
        self.var_toggle_on_color, self.var_toggle_off_color = tk.StringVar(), tk.StringVar()
        
        self.var_label_bg_color, self.var_label_fg_color, self.var_label_shape = tk.StringVar(), tk.StringVar(), tk.StringVar()

        self.var_keyboard_rows = tk.StringVar()
        self.var_compass_heading = tk.StringVar()
        self.var_knob_value, self.var_prog_value, self.var_tab_names = tk.StringVar(), tk.StringVar(), tk.StringVar()

        # Crear el contenedor con scroll en el panel derecho
        self.prop_scroll = ScrollablePropContainer(self.right_panel, bg=t_init["panel"])
        self.prop_scroll.pack(fill=tk.BOTH, expand=True, padx=10)
        self.prop_container = self.prop_scroll.inner_frame
        self.build_inspector_fields()

        self.canvas_container = tk.Frame(self.tab_designer)
        self.canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_container, scrollregion=(0, 0, 3000, 3000), cursor="cross", highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self.canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self.canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_hover)

        self.code_paned = tk.PanedWindow(self.tab_code, orient=tk.HORIZONTAL, bg="#1e1e1e")
        self.code_paned.pack(fill=tk.BOTH, expand=True)

        self.scripts_frame = tk.Frame(self.code_paned, width=200)
        self.code_paned.add(self.scripts_frame, minsize=150)

        # Guarda la referencia en self.lbl_scripts_title
        self.lbl_scripts_title = tk.Label(self.scripts_frame, text="Scripts de Eventos Activos", font=("Segoe UI", 9, "bold"))
        self.lbl_scripts_title.pack(pady=10)
        
        self.scripts_listbox = tk.Listbox(self.scripts_frame, font=("Consolas", 10), relief=tk.FLAT, highlightthickness=0)
        self.scripts_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.scripts_listbox.bind("<Double-1>", self.load_script_from_list)

        self.editor_frame = tk.Frame(self.code_paned)
        self.code_paned.add(self.editor_frame, stretch="always")

        # Guarda la referencia en self.code_toolbar
        self.code_toolbar = tk.Frame(self.editor_frame, height=40)
        self.code_toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        self.lbl_code_title = tk.Label(self.code_toolbar, text="(Ningun archivo abierto)", font=("Segoe UI", 10, "bold"))
        self.lbl_code_title.pack(side=tk.LEFT)
        
        tk.Button(self.code_toolbar, text="Guardar Cambios de Codigo", command=self.save_widget_code_tab, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

        # Configuración del editor de código estilo Python
        self.code_editor = scrolledtext.ScrolledText(
            self.editor_frame,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            highlightthickness=0,
        )
        self.code_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.code_editor.insert(tk.END, "# Selecciona un archivo en la lista de la izquierda o un widget en el disenador\n")

        # Definir los colores (tags) para la sintaxis de Python
        self.code_editor.tag_config("keyword", foreground="#c586c0")  # Morado
        self.code_editor.tag_config("string", foreground="#ce9178")  # Naranja/Marrón
        self.code_editor.tag_config(
            "comment", foreground="#6a9955"
        )  # Verde comentario
        self.code_editor.tag_config(
            "number", foreground="#b5cea8"
        )  # Verde claro números

        # Vincular eventos de escritura, resaltado y auto-tabulación
        self.code_editor.bind("<KeyRelease>", self.on_code_key_release)
        self.code_editor.bind("<Return>", self.handle_auto_indent)
    
    def mark_unsaved(self, event=None):
        self.unsaved_changes = True
    
    def on_code_key_release(self, event=None):
        """Marca como no guardado y aplica colorización de sintaxis."""
        self.mark_unsaved()
        self.syntax_highlight()

    def syntax_highlight(self, event=None):
        """Aplica colores a palabras clave, strings, comentarios y números en tiempo real."""
        # Limpiar etiquetas anteriores
        for tag in ["keyword", "string", "comment", "number"]:
            self.code_editor.tag_remove(tag, "1.0", tk.END)

        text_content = self.code_editor.get("1.0", tk.END)

        # Expresiones regulares para tokens de Python
        patterns = [
            ("comment", r"#.*"),
            ("string", r"(\'[^\']*\'|\"[^\"]*\")"),
            (
                "keyword",
                r"\b(def|class|if|elif|else|for|while|return|import|from|as|in|not|and|or|True|False|None|try|except|finally|with|lambda|global|nonlocal|pass|break|continue|raise|assert|del|yield|async|await)\b",
            ),
            ("number", r"\b\d+(\.\d+)?\b"),
        ]

        for tag_name, pattern in patterns:
            for match in re.finditer(pattern, text_content):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                self.code_editor.tag_add(tag_name, start_idx, end_idx)

    def handle_auto_indent(self, event):
        """Maneja la auto-tabulación al presionar Enter, detectando bloques con ':'."""
        cursor_pos = self.code_editor.index(tk.INSERT)
        line_num = cursor_pos.split(".")[0]
        line_start = f"{line_num}.0"
        current_line = self.code_editor.get(line_start, cursor_pos)

        # Detectar la indentación (espacios o tabs) de la línea actual
        indent = ""
        for char in current_line:
            if char in " \t":
                indent += char
            else:
                break

        # Si la línea termina en dos puntos (:), agregar 4 espacios extra de tabulación
        if current_line.strip().endswith(":"):
            indent += "    "

        # Insertar salto de línea seguido de la indentación calculada
        self.code_editor.insert(tk.INSERT, "\n" + indent)

        # Disparar marcado de cambios y resaltado
        self.on_code_key_release()

        return "break"  # Previene el comportamiento por defecto de la tecla Enter en Tkinter
        
    def refresh_widget_library(self):
        """Limpia y vuelve a cargar los elementos de la biblioteca lateral."""
        for child in self.lib_inner.winfo_children():
            child.destroy()

        categories = {
            "Controles": [
                "Button",
                "ToggleSwitch",
                "Slider",
                "CheckBox",
                "TextBox",
                "NumberBox",
                "Keyboard",
                "Knob",
            ],
            "Indicadores": [
                "LED",
                "Gauge",
                "SevenSegment",
                "StatusBar",
                "Clock",
                "Compass",
                "ProgressBar",
            ],
            "Containers": [
                "VerticalContainer",
                "HorizontalContainer",
                "MatrixContainer",
                "Tabs",
            ],
            "Texto y Visualizacion": ["Label"],
            "Plugins": self.custom_widget_types,
        }

        t = THEMES[self.current_theme]
        for cat, items in categories.items():
            if not items:
                continue
            lbl = tk.Label(
                self.lib_inner,
                text=f"- {cat}",
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                bg=t["panel"],
                fg=t["accent"],
            )
            lbl.pack(fill=tk.X, padx=5, pady=(5, 2))
            for item in items:
                b = tk.Button(
                    self.lib_inner,
                    text=f"    {item}",
                    anchor="w",
                    relief=tk.FLAT,
                    cursor="hand2",
                    bg=t["panel"],
                    fg=t["fg"],
                    activebackground=t["border"],
                    activeforeground=t["fg"],
                )
                b.pack(fill=tk.X, padx=15, pady=1)
                b.bind("<Button-1>", lambda e, wtype=item: self.set_pending(wtype))
    
    def open_new_widget_dialog(self):
        diag = tk.Toplevel(self.root)
        diag.title("Nuevo Widget Personalizado")
        diag.geometry("400x320")
        diag.config(bg="#1e293b")
        diag.grab_set()

        tk.Label(
            diag,
            text="Crear Nuevo Widget Python",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg="#1e293b",
        ).pack(pady=10)
        form_frame = tk.Frame(diag, bg="#1e293b")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        tk.Label(
            form_frame,
            text="Nombre del Widget:",
            fg="#cbd5e1",
            bg="#1e293b",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W)
        e_name = tk.Entry(
            form_frame,
            bg="#334155",
            fg="white",
            insertbackground="white",
            font=("Segoe UI", 10),
        )
        e_name.pack(fill=tk.X, pady=5)
        e_name.insert(0, "CustomSensor")

        tk.Label(
            form_frame,
            text="Ancho por defecto (px):",
            fg="#cbd5e1",
            bg="#1e293b",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W)
        e_w = tk.Entry(
            form_frame,
            bg="#334155",
            fg="white",
            insertbackground="white",
            font=("Segoe UI", 10),
        )
        e_w.pack(fill=tk.X, pady=5)
        e_w.insert(0, "180")

        tk.Label(
            form_frame,
            text="Alto por defecto (px):",
            fg="#cbd5e1",
            bg="#1e293b",
            font=("Segoe UI", 9),
        ).pack(anchor=tk.W)
        e_h = tk.Entry(
            form_frame,
            bg="#334155",
            fg="white",
            insertbackground="white",
            font=("Segoe UI", 10),
        )
        e_h.pack(fill=tk.X, pady=5)
        e_h.insert(0, "120")

        def generate_template():
            wname = e_name.get().strip()
            if not wname:
                return
            try:
                width, height = int(e_w.get()), int(e_h.get())
            except ValueError:
                width, height = 180, 120

            filename = os.path.join(CUSTOM_WIDGETS_DIR, f"{wname.lower()}.py")
            template_code = '''import json
import re

class __NAME__:
    default_props = {
        "label": "__NAME__",
        "color": "#38bdf8",
    }

    # Tipos: text, color, boolean, select (con "options"), file, table, custom
    custom_properties = [
        {"name": "label", "label": "Etiqueta:", "type": "text"},
        {"name": "color", "label": "Color:", "type": "color"},
    ]

    # Eventos que el widget puede emitir (clic derecho > Connect)
    supported_events = ["on_click"]

    # Ayuda de clic derecho > Valores / Ayuda...
    # Claves: soportado, tipo, valores, desc, ejemplos, envia, notas. {id} = ID real del widget.
    value_help = {
        "soportado": True,
        "tipo": "String",
        "valores": "Cualquier texto",
        "desc": "Cambia el texto mostrado en el widget.",
        "ejemplos": ["ui.set_value('{id}', 'Hola')"],
        "envia": "on_click -> True",
        "notas": [
            "ui.set_property('{id}', 'color', '#ef4444') cambia el color.",
        ],
    }

    def __init__(self, width=__W__, height=__H__):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()

    def to_dict(self):
        return {
            "id": getattr(self, "id", "w_0"),
            "type": getattr(self, "type", self.__class__.__name__),
            "x": getattr(self, "x", 50),
            "y": getattr(self, "y", 50),
            "width": getattr(self, "width", 300),
            "height": getattr(self, "height", 150),
            "props": getattr(self, "props", {}),
            "events": getattr(self, "events", {}),
        }

    def render_canvas(self, canvas, x, y):
        color = str(self.props.get("color", self.default_props["color"]))
        label = str(self.props.get("label", "__NAME__"))
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height,
                                    fill="#0f172a", outline=color, width=2)
        txt = canvas.create_text(x + self.width / 2, y + self.height / 2,
                                text=label, fill=color, font=("Segoe UI", 10, "bold"))
        return [box, txt]

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        safe_id = re.sub(r"\\W", "_", str(w_id))
        cfg = json.dumps({
            "id": str(w_id),
            "label": str(p.get("label", "__NAME__")),
            "color": str(p.get("color", "#38bdf8")),
        })

        return f"""
<div id="w_{safe_id}"
    class="w-full h-full flex items-center justify-center rounded-xl font-bold cursor-pointer select-none"
    style="background:#0f172a; border:1px solid; overflow:hidden;"></div>

<script>
(function() {{
    const cfg = {cfg};
    const el = document.getElementById("w_{safe_id}");

    function paint() {{
        el.textContent = cfg.label;
        el.style.color = cfg.color;
        el.style.borderColor = cfg.color;
    }}
    paint();

    // Registro para ui.set_value / ui.set_property desde Python
    window.__widgets = window.__widgets || {{}};
    window.__widgets[cfg.id] = {{
        update: function(val) {{ cfg.label = String(val); paint(); }},
        update_prop: function(prop, val) {{
            if (prop === "label" || prop === "color") {{
                cfg[prop] = String(val);
                paint();
            }}
        }}
    }};

    el.addEventListener("click", () => emitEvent({{id: cfg.id}}, "on_click", true));
}})();
</script>
"""
'''
            template_code = (template_code
                             .replace("__NAME__", wname)
                             .replace("__W__", str(width))
                             .replace("__H__", str(height)))
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(template_code)
                messagebox.showinfo("Exito", f"Widget creado en:\n{filename}")
                diag.destroy()

                self.load_custom_widgets_plugins()
                self.refresh_widget_library()
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        tk.Button(
            diag,
            text="Crear Plantilla",
            command=generate_template,
            bg="#10b981",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
        ).pack(pady=15)

    def pick_color_var(self, str_var):
        color_code = colorchooser.askcolor(title="Seleccionar Color", color=str_var.get())
        if color_code[1]:
            self.save_state()
            str_var.set(color_code[1])
            self.update_prop_live()
    
    def open_table_editor(self, w):
        diag = tk.Toplevel(self.root)
        diag.title("Editor Visual de Tabla")
        diag.geometry("600x450")
        diag.config(bg="#1e293b")
        diag.grab_set()

        tk.Label(
            diag,
            text="Editor de Filas y Columnas",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg="#1e293b",
        ).pack(pady=10)

        container = tk.Frame(diag, bg="#1e293b")
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        canvas = tk.Canvas(container, bg="#0f172a", highlightthickness=0)
        scrollbar_y = ttk.Scrollbar(
            container, orient="vertical", command=canvas.yview
        )
        scrollbar_x = ttk.Scrollbar(
            container, orient="horizontal", command=canvas.xview
        )
        grid_frame = tk.Frame(canvas, bg="#0f172a")

        grid_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        canvas.configure(
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Parsear datos actuales de w.props
        cols_str = w.props.get("scroll_cols", "Col 1, Col 2")
        rows_str = w.props.get("scroll_rows", "1, 2 | A, B")

        headers = [h.strip() for h in cols_str.split(",")]
        col_blocks = [b.strip() for b in rows_str.split("|")]

        data_matrix = []
        num_cols = len(headers)
        max_rows = 1
        parsed_cols = []
        for block in col_blocks:
            items = [i.strip() for i in block.split(",")]
            parsed_cols.append(items)
            if len(items) > max_rows:
                max_rows = len(items)

        for r in range(max_rows):
            row_vals = []
            for c in range(num_cols):
                val = ""
                if c < len(parsed_cols) and r < len(parsed_cols[c]):
                    val = parsed_cols[c][r]
                row_vals.append(val)
            data_matrix.append(row_vals)

        entries_grid = []
        selected_row = 0  # Índice de fila seleccionado en data_matrix
        selected_col = 0  # Índice de columna seleccionado en headers

        def set_active(r, c):
            nonlocal selected_row, selected_col
            selected_col = c
            if r > 0:
                selected_row = r - 1  # Ajusta para omitir la fila de encabezados

        def rebuild_grid():
            nonlocal entries_grid
            for widget in grid_frame.winfo_children():
                widget.destroy()
            entries_grid = []

            # Fila 0: Encabezados
            header_entries = []
            for c, h_text in enumerate(headers):
                e = tk.Entry(
                    grid_frame,
                    font=("Segoe UI", 9, "bold"),
                    bg="#334155",
                    fg="#38bdf8",
                    justify="center",
                )
                e.insert(0, h_text)
                e.grid(row=0, column=c, padx=2, pady=2, sticky="nsew")
                e.bind(
                    "<FocusIn>",
                    lambda event, row_idx=0, col_idx=c: set_active(
                        row_idx, col_idx
                    ),
                )
                header_entries.append(e)
            entries_grid.append(header_entries)

            # Filas de datos
            for r, row_data in enumerate(data_matrix):
                row_entries = []
                for c, val in enumerate(row_data):
                    e = tk.Entry(
                        grid_frame,
                        font=("Segoe UI", 9),
                        bg="#1e293b",
                        fg="white",
                    )
                    e.insert(0, val)
                    e.grid(row=r + 1, column=c, padx=2, pady=2, sticky="nsew")
                    e.bind(
                        "<FocusIn>",
                        lambda event, row_idx=r + 1, col_idx=c: set_active(
                            row_idx, col_idx
                        ),
                    )
                    row_entries.append(e)
                entries_grid.append(row_entries)

        rebuild_grid()

        btn_frame = tk.Frame(diag, bg="#1e293b")
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        def add_row():
            update_matrix_from_entries()
            data_matrix.append(["" for _ in range(len(headers))])
            rebuild_grid()

        def remove_row():
            nonlocal selected_row
            update_matrix_from_entries()
            if len(data_matrix) > 1:
                if selected_row < 0 or selected_row >= len(data_matrix):
                    selected_row = len(data_matrix) - 1
                # Elimina exactamente la fila seleccionada
                data_matrix.pop(selected_row)
                if selected_row >= len(data_matrix):
                    selected_row = len(data_matrix) - 1
                rebuild_grid()
            else:
                messagebox.showwarning(
                    "Aviso", "Debe mantener al menos una fila.", parent=diag
                )

        def add_col():
            update_matrix_from_entries()
            headers.append(f"Col {len(headers)+1}")
            for row in data_matrix:
                row.append("")
            rebuild_grid()

        def remove_col():
            nonlocal selected_col
            update_matrix_from_entries()
            if len(headers) > 1:
                if selected_col < 0 or selected_col >= len(headers):
                    selected_col = len(headers) - 1
                # Elimina la columna seleccionada de los encabezados y de cada fila
                headers.pop(selected_col)
                for row in data_matrix:
                    if selected_col < len(row):
                        row.pop(selected_col)
                if selected_col >= len(headers):
                    selected_col = len(headers) - 1
                rebuild_grid()
            else:
                messagebox.showwarning(
                    "Aviso", "Debe mantener al menos una columna.", parent=diag
                )

        def update_matrix_from_entries():
            nonlocal headers, data_matrix
            headers = [
                entries_grid[0][c].get().strip()
                for c in range(len(entries_grid[0]))
            ]
            new_matrix = []
            for r in range(1, len(entries_grid)):
                row_vals = [
                    entries_grid[r][c].get().strip()
                    for c in range(len(entries_grid[r]))
                ]
                new_matrix.append(row_vals)
            data_matrix[:] = new_matrix

        tk.Button(
            btn_frame,
            text="+ Fila",
            command=add_row,
            bg="#334155",
            fg="white",
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_frame,
            text="- Fila",
            command=remove_row,
            bg="#334155",
            fg="white",
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_frame,
            text="+ Columna",
            command=add_col,
            bg="#334155",
            fg="white",
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=10)
        tk.Button(
            btn_frame,
            text="- Columna",
            command=remove_col,
            bg="#334155",
            fg="white",
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=2)

        def save_and_close():
            update_matrix_from_entries()
            new_cols_str = ", ".join(headers)
            cols_data_blocks = []
            for c in range(len(headers)):
                col_items = [
                    data_matrix[r][c]
                    for r in range(len(data_matrix))
                    if c < len(data_matrix[r])
                ]
                cols_data_blocks.append(", ".join(col_items))
            new_rows_str = " | ".join(cols_data_blocks)

            self.save_state()
            w.props["scroll_cols"] = new_cols_str
            w.props["scroll_rows"] = new_rows_str

            if hasattr(self, "custom_prop_vars"):
                if "scroll_rows" in self.custom_prop_vars:
                    self.custom_prop_vars["scroll_rows"].set(new_rows_str)

            self.update_prop_live()
            diag.destroy()

        tk.Button(
            diag,
            text="Guardar Cambios",
            command=save_and_close,
            bg="#10b981",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
        ).pack(side=tk.BOTTOM, pady=10)
    
    
    
    def build_inspector_fields(self):
        for widget in self.prop_container.winfo_children(): widget.destroy()

        t = THEMES[self.current_theme]
        def add_field(label_text, textvariable, callback=None, readonly=False):
            lbl = tk.Label(self.prop_container, text=label_text, font=("Segoe UI", 9), bg=t["panel"], fg=t["fg"])
            lbl.pack(anchor=tk.W, pady=(5, 0))
            ent = tk.Entry(
                self.prop_container, 
                textvariable=textvariable, 
                bg=t["bg"], 
                fg=t["fg"], 
                insertbackground=t["fg"], 
                relief=tk.FLAT,
                readonlybackground=t["bg"]  # <--- Esto fuerza el fondo oscuro/claro en modo readonly
            )
            if readonly:
                ent.config(state='readonly')
            ent.pack(fill=tk.X, pady=2)
            if callback and not readonly: 
                ent.bind("<KeyRelease>", callback)
            return ent

        add_field("ID unico:", self.var_id, readonly=True)
        if self.prop_container.winfo_children(): self.prop_container.winfo_children()[-1].config(state='readonly')
        add_field("Etiqueta / Titulo:", self.var_label, self.update_prop_live)
        add_field("Posicion X:", self.var_x, self.update_prop_live)
        add_field("Posicion Y:", self.var_y, self.update_prop_live)
        add_field("Ancho (W):", self.var_w, self.update_prop_live)
        add_field("Alto (H):", self.var_h, self.update_prop_live)
        
        if not self.selected:
            return
        w_cls = None
        if hasattr(self, 'custom_widget_classes'):
            # print(self.selected.type, ".selected")
            for k, cls in self.custom_widget_classes.items():
                if k.lower() == self.selected.type.lower():
                    w_cls = cls
                    break
        
        # Inbuild widgets
        if self.selected.type == "ToggleSwitch":
            add_field("Texto ON:", self.var_toggle_on_text, self.update_prop_live)
            add_field("Texto OFF:", self.var_toggle_off_text, self.update_prop_live)
            
            lbl = tk.Label(self.prop_container, text="Color ON:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            fr1 = tk.Frame(self.prop_container)
            fr1.pack(fill=tk.X, pady=2)
            ent1 = tk.Entry(fr1, textvariable=self.var_toggle_on_color)
            ent1.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent1.bind("<KeyRelease>", self.update_prop_live)
            tk.Button(fr1, text="Elegir", command=lambda: self.pick_color_var(self.var_toggle_on_color)).pack(side=tk.RIGHT, padx=5)

            lbl = tk.Label(self.prop_container, text="Color OFF:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            fr2 = tk.Frame(self.prop_container)
            fr2.pack(fill=tk.X, pady=2)
            ent2 = tk.Entry(fr2, textvariable=self.var_toggle_off_color)
            ent2.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent2.bind("<KeyRelease>", self.update_prop_live)
            tk.Button(fr2, text="Elegir", command=lambda: self.pick_color_var(self.var_toggle_off_color)).pack(side=tk.RIGHT, padx=5)

        if self.selected.type == "Label":
            lbl = tk.Label(self.prop_container, text="Forma Envoltura:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            cb_shape = ttk.Combobox(self.prop_container, textvariable=self.var_label_shape, values=["Ninguna", "Rectangular", "Redondeada"], state="readonly")
            cb_shape.pack(fill=tk.X, pady=2)
            cb_shape.bind("<<ComboboxSelected>>", self.update_prop_live)

            lbl = tk.Label(self.prop_container, text="Color de Fondo:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            fr1 = tk.Frame(self.prop_container)
            fr1.pack(fill=tk.X, pady=2)
            ent1 = tk.Entry(fr1, textvariable=self.var_label_bg_color)
            ent1.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent1.bind("<KeyRelease>", self.update_prop_live)
            tk.Button(fr1, text="Elegir", command=lambda: self.pick_color_var(self.var_label_bg_color)).pack(side=tk.RIGHT, padx=5)

            lbl = tk.Label(self.prop_container, text="Color de Texto:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            fr2 = tk.Frame(self.prop_container)
            fr2.pack(fill=tk.X, pady=2)
            ent2 = tk.Entry(fr2, textvariable=self.var_label_fg_color)
            ent2.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent2.bind("<KeyRelease>", self.update_prop_live)
            tk.Button(fr2, text="Elegir", command=lambda: self.pick_color_var(self.var_label_fg_color)).pack(side=tk.RIGHT, padx=5)

        if self.selected.type == "Compass":
            add_field("Rumbo Inicial:", self.var_compass_heading, self.update_prop_live)
        if self.selected.type == "Knob":
            add_field("Valor Inicial:", self.var_knob_value, self.update_prop_live)

        if self.selected.type in ["LED", "Button", "Gauge", "ProgressBar", "Knob", "VerticalContainer", "HorizontalContainer", "MatrixContainer", "Compass"]:
            lbl = tk.Label(self.prop_container, text="Color Principal / Borde:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            fr = tk.Frame(self.prop_container, bg=t["panel"])
            fr.pack(fill=tk.X, pady=2)
            ent = tk.Entry(fr, textvariable=self.var_color)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent.bind("<KeyRelease>", self.update_prop_live)
            tk.Button(fr, text="Elegir", command=lambda: self.pick_color_var(self.var_color)).pack(side=tk.RIGHT, padx=5)

        if self.selected.type == "Gauge":
            lbl = tk.Label(self.prop_container, text="Modelo de Gauge:", font=("Segoe UI", 9))
            lbl.pack(anchor=tk.W, pady=(5, 0))
            self.cb_gauge = ttk.Combobox(self.prop_container, textvariable=self.var_gauge_model, values=["Tacometro Clasico", "Circular (Stamina / Progreso)"], state="readonly")
            self.cb_gauge.pack(fill=tk.X, pady=2)
            self.cb_gauge.bind("<<ComboboxSelected>>", self.update_prop_live)

        if self.selected.type == "SevenSegment":
            add_field("Numero de Digitos (ej. 2, 3, 4):", self.var_seg_digits, self.update_prop_live)
        
        # Custom Widgets
        if w_cls:
            if not hasattr(self.selected, "props") or not isinstance(self.selected.props, dict):
                self.selected.props = {}

            if hasattr(w_cls, "default_props"):
                for dp_k, dp_v in w_cls.default_props.items():
                    if dp_k not in self.selected.props:
                        self.selected.props[dp_k] = dp_v

            self.custom_prop_vars = {}
            custom_props = getattr(w_cls, "custom_properties", None)

            if not custom_props and hasattr(w_cls, "default_props"):
                custom_props = [
                    {
                        "name": k,
                        "label": f"{k.replace('_', ' ').title()}:",
                        "type": "color" if "color" in k.lower() else "text",
                    }
                    for k, v in w_cls.default_props.items()
                    if k != "label"
                ]

            if custom_props:
                for p_info in custom_props:
                    p_name = p_info["name"]
                    p_label = p_info.get("label", p_name)
                    p_type = str(p_info.get("type", "text")).lower()

                    val = self.selected.props.get(
                        p_name,
                        getattr(w_cls, "default_props", {}).get(p_name, ""),
                    )
                    var = tk.StringVar(value=str(val))
                    self.custom_prop_vars[p_name] = var

                    # Selector de Color (Color Picker)
                    if p_type == "color":
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))

                        fr = tk.Frame(self.prop_container, bg=t["panel"])
                        fr.pack(fill=tk.X, pady=2)

                        # Validar si el valor inicial es un color Hex válido (#RGB o #RRGGBB)
                        init_val = str(val).strip()
                        init_color = (
                            init_val
                            if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", init_val)
                            else "#3b82f6"
                        )

                        color_box = tk.Frame(
                            fr,
                            width=18,
                            height=18,
                            bg=init_color,
                            highlightthickness=1,
                            highlightbackground="#475569",
                        )
                        color_box.pack(side=tk.LEFT, padx=(0, 6))

                        ent = tk.Entry(fr, textvariable=var)
                        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)

                        def on_color_key(e, cb=color_box, v=var):
                            color_str = v.get().strip()
                            # Solo actualiza la vista previa si es un Hex completo de 3 o 6 dígitos
                            if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color_str):
                                try:
                                    cb.config(bg=color_str)
                                except tk.TclError:
                                    pass
                            self.update_prop_live()

                        ent.bind("<KeyRelease>", on_color_key)

                        def open_picker(target_var, preview_frame):
                            c_code = colorchooser.askcolor(
                                title=f"Seleccionar {p_label}",
                                color=target_var.get(),
                            )
                            if c_code[1]:
                                self.save_state()
                                target_var.set(c_code[1])
                                preview_frame.config(bg=c_code[1])
                                self.update_prop_live()

                        tk.Button(
                            fr,
                            text="Elegir",
                            command=lambda v=var, cb=color_box: open_picker(
                                v, cb
                            ),
                        ).pack(side=tk.RIGHT, padx=5)

                    # Selector de Archivo (File Dialog)
                    elif p_type in ["file", "filepath", "file_path", "path"]:
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))

                        fr = tk.Frame(self.prop_container, bg=t["panel"])
                        fr.pack(fill=tk.X, pady=2)

                        ent = tk.Entry(fr, textvariable=var)
                        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        ent.bind("<KeyRelease>", self.update_prop_live)

                        def open_file_dialog(target_var, spec):
                            # Permite definir filtros opcionales en custom_properties o usa 'Todos los archivos' por defecto
                            ftypes = spec.get(
                                "file_types", [("Todos los archivos", "*.*")]
                            )
                            selected_file = filedialog.askopenfilename(
                                title=f"Seleccionar {p_label}",
                                filetypes=ftypes,
                            )
                            if selected_file:
                                self.save_state()
                                target_var.set(selected_file)
                                self.update_prop_live()

                        tk.Button(
                            fr,
                            text="Examinar",
                            command=lambda v=var, spec=p_info: open_file_dialog(
                                v, spec
                            ),
                        ).pack(side=tk.RIGHT, padx=5)

                    # Desplegable de Selección (Select / Options)
                    elif p_type in ["select", "choice", "combobox"]:
                        options = p_info.get(
                            "options", ["Opción 1", "Opción 2"]
                        )
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))
                        cb = ttk.Combobox(
                            self.prop_container,
                            textvariable=var,
                            values=options,
                            state="readonly",
                        )
                        cb.pack(fill=tk.X, pady=2)
                        cb.bind(
                            "<<ComboboxSelected>>", self.update_prop_live
                        )

                    # Booleano (True/False)
                    elif p_type in ["boolean", "bool"]:
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                            bg=t["panel"],
                            fg=t["fg"]
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))
                        
                        # Pasar directamente el método como comando
                        slide_btn = SlideButton(
                            self.prop_container,
                            variable=var,
                            command=self.update_prop_live
                        )
                        slide_btn.pack(anchor=tk.W, pady=2)
                    # Editor Visual de Tabla (Table / Grid Editor)
                    elif p_type in ["table", "grid", "matrix"]:
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))

                        fr = tk.Frame(self.prop_container, bg=t["panel"])
                        fr.pack(fill=tk.X, pady=2)

                        # Muestra un resumen o botón para abrir la ventana modal
                        tk.Button(
                            fr,
                            text="Editar Tabla",
                            command=lambda w=self.selected: self.open_table_editor(w),
                            bg="#2563eb",
                            fg="white",
                            font=("Segoe UI", 9, "bold"),
                            relief=tk.FLAT,
                            cursor="hand2",
                        ).pack(fill=tk.X, expand=True, pady=2)
                    
                    elif p_type == "custom":
                        lbl = tk.Label(
                            self.prop_container,
                            text=p_label,
                            font=("Segoe UI", 9),
                            bg=t["panel"],
                            fg=t["fg"]
                        )
                        lbl.pack(anchor=tk.W, pady=(5, 0))

                        fr = tk.Frame(self.prop_container, bg=t["panel"])
                        fr.pack(fill=tk.X, pady=2)

                        fname = p_info.get("fname", "open_custom_editor")

                        def call_custom_editor(w=self.selected, fn=fname):
                            if w and hasattr(w, fn):
                                getattr(w, fn)(self)
                            elif w:
                                messagebox.showerror("Error", f"El método '{fn}' no está definido en el widget.")

                        tk.Button(
                            fr,
                            text=p_info.get("btn_text", "Configurar"),
                            command=call_custom_editor,
                            bg=t.get("accent", "#2563eb"),
                            fg="white",
                            font=("Segoe UI", 9, "bold"),
                            relief=tk.FLAT,
                            cursor="hand2"
                        ).pack(fill=tk.X, expand=True, pady=2, ipady=3)
                    else:
                        add_field(p_label, var, self.update_prop_live)
        # Aplica el tema oscuro/claro a todos los elementos hijos del inspector automáticamente
        def style_inspector_children(parent):
            for child in parent.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.config(bg=t["panel"], fg=t["fg"])
                    elif isinstance(child, tk.Entry):
                        child.config(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
                    elif isinstance(child, tk.Button):
                        child.config(bg=t["border"], fg=t["fg"], activebackground=t["accent"], activeforeground=t["fg"])
                    elif isinstance(child, tk.Frame):
                        child.config(bg=t["panel"])
                        style_inspector_children(child) # Entra recursivamente en los sub-marcos (como los de color)
                except Exception:
                    pass
        style_inspector_children(self.prop_container)

    def apply_theme(self):
        t = THEMES[self.current_theme]
        
        # 1. Definir e inicializar style aquí mismo
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar Combobox dinámico
        style.configure('TCombobox', 
                        fieldbackground=t["bg"], 
                        background=t["panel"], 
                        foreground=t["fg"],
                        arrowcolor=t["accent"])
        style.map('TCombobox', 
                  fieldbackground=[('readonly', t["bg"])],
                  selectbackground=[('readonly', t["accent"])],
                  foreground=[('readonly', t["fg"])])
                  
        # Configurar Scrollbars dinámicas
        style.configure('TScrollbar', 
                        background=t["panel"], 
                        troughcolor=t["bg"], 
                        bordercolor=t["border"], 
                        arrowcolor=t["fg"])
        style.map('TScrollbar',
                  background=[('active', t["accent"]), ('pressed', t["accent"])],
                  troughcolor=[('active', t["bg"]), ('pressed', t["bg"])])
                        
        # Configurar Notebook y Pestañas dinámicas
        style.configure('TNotebook', background=t["panel"], bordercolor=t["border"])
        style.configure('TNotebook.Tab', background=t["panel"], foreground=t["fg"], padding=[10, 5])
        style.map('TNotebook.Tab', 
                  background=[('selected', t["bg"]), ('active', t["border"])],
                  foreground=[('selected', t["accent"]), ('active', t["fg"])])
        
        # Ventana principal y paneles contenedores principales
        self.root.config(bg=t["bg"])
        self.toolbar.config(bg=t["panel"])
        self.left_panel.config(bg=t["panel"])
        self.lib_inner.config(bg=t["panel"])
        self.canvas_lib.config(bg=t["panel"])
        self.right_panel.config(bg=t["panel"])
        self.prop_container.config(bg=t["panel"])
        if hasattr(self, "prop_scroll"):
            self.prop_scroll.set_bg(t["panel"])
        self.canvas.config(bg=t["canvas"])
        
        # Etiquetas principales de los paneles
        if hasattr(self, "lbl_title"): self.lbl_title.config(bg=t["panel"], fg=t["fg"])
        if hasattr(self, "lbl_lib"): self.lbl_lib.config(bg=t["panel"], fg=t["fg"])
        if hasattr(self, "lbl_insp"): self.lbl_insp.config(bg=t["panel"], fg=t["fg"])
        
        # Editor de código (ScrolledText) y pestañas
        if hasattr(self, "code_paned"):
            self.code_paned.config(bg=t["border"])
        if hasattr(self, "scripts_frame"):
            self.scripts_frame.config(bg=t["panel"])
        if hasattr(self, "lbl_scripts_title"):
            self.lbl_scripts_title.config(bg=t["panel"], fg=t["fg"])
        if hasattr(self, "editor_frame"):
            self.editor_frame.config(bg=t["panel"])
        if hasattr(self, "code_toolbar"):
            self.code_toolbar.config(bg=t["panel"])
        if hasattr(self, "lbl_code_title"):
            self.lbl_code_title.config(bg=t["panel"], fg=t["accent"])
            
        if hasattr(self, "code_editor"):
            self.code_editor.config(
                bg=t["panel"],  # Fondo acorde al panel del tema activo
                fg=t["fg"], 
                insertbackground=t["accent"]
            )
            
        if hasattr(self, "scripts_listbox"):
            self.scripts_listbox.config(
                bg=t["panel"],
                fg=t["fg"],
                selectbackground=t["accent"],
                selectforeground="#ffffff",
                highlightthickness=0,
                bd=0
            )

        # Componentes dentro de la biblioteca de widgets (izquierda)
        for widget in self.lib_inner.winfo_children():
            try:
                if isinstance(widget, tk.Button):
                    widget.config(bg=t["panel"], fg=t["fg"], activebackground=t["border"], activeforeground=t["fg"], relief=tk.FLAT)
                elif isinstance(widget, tk.Label):
                    # Si la etiqueta tiene guion "-", actúa como categoría (ej: "- Controles")
                    is_category = "-" in widget.cget("text")
                    widget.config(bg=t["panel"], fg=t["accent"] if is_category else t["fg"])
            except Exception:
                pass

        # Inspector de propiedades (elementos dinámicos)
        t = THEMES[self.current_theme]
        def style_inspector(parent):
            for child in parent.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.config(bg=t["panel"], fg=t["fg"])
                    elif isinstance(child, tk.Entry):
                        try:
                            child.config(
                                bg=t["bg"], 
                                fg=t["fg"], 
                                insertbackground=t["fg"], 
                                readonlybackground=t["bg"]  # <--- Agrega esto
                            )
                        except Exception:
                            pass
                    elif isinstance(child, tk.Frame):
                        child.config(bg=t["panel"])
                        style_inspector(child) # Entra en los sub-marcos (color pickers, etc.)
                except Exception:
                    pass
        style_inspector(self.prop_container)
        
        
        

    def change_theme_event(self, event):
        self.current_theme = self.theme_var.get()
        self.apply_theme()

    def set_pending(self, wtype):
        self.pending_type = wtype
        self.root.config(cursor="target")

    def get_parent_container(self, widget_id):
        for w in self.widgets:
            if w.type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"]:
                if widget_id in w.attached_widgets:
                    return w
        return None

    def on_mouse_hover(self, event):
        canvas_x, canvas_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.drag_data.get("item"): return 
        self.resize_edge = None
        cursor = "cross"
        if self.selected:
            w = self.selected
            margin = 10
            if w.x <= canvas_x <= w.x + w.width and w.y <= canvas_y <= w.y + w.height:
                near_l, near_r = canvas_x <= w.x + margin, canvas_x >= w.x + w.width - margin
                near_t, near_b = canvas_y <= w.y + margin, canvas_y >= w.y + w.height - margin
                if near_t and near_l: self.resize_edge, cursor = "nw", "sizing"
                elif near_t and near_r: self.resize_edge, cursor = "ne", "sizing"
                elif near_b and near_l: self.resize_edge, cursor = "sw", "sizing"
                elif near_b and near_r: self.resize_edge, cursor = "se", "sizing"
                elif near_t: self.resize_edge, cursor = "n", "sb_v_double_arrow"
                elif near_b: self.resize_edge, cursor = "s", "sb_v_double_arrow"
                elif near_l: self.resize_edge, cursor = "w", "sb_h_double_arrow"
                elif near_r: self.resize_edge, cursor = "e", "sb_h_double_arrow"
                else: self.resize_edge, cursor = "move", "fleur"
            else: cursor = "cross"
        self.canvas.config(cursor=cursor)

    def on_canvas_click(self, event):
        canvas_x, canvas_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        
        if self.pending_type:
            self.save_state()
            wid = f"{self.pending_type.lower()}_{self.widget_counter}"
            self.widget_counter += 1
            w = WidgetItem(wid, self.pending_type, int(canvas_x), int(canvas_y))
            
            # <--- NUEVO
            # Inicializa props con default_props del plugin
            if hasattr(self, 'custom_widget_classes'):
                for k, cls in self.custom_widget_classes.items():
                    if k.lower() == self.pending_type.lower():
                        if hasattr(cls, 'default_props'):
                            w.props = copy.deepcopy(cls.default_props)
                        break
            
            self.widgets.append(w)
            self.draw_widget(w)
            self.select_widget(w)
            self.pending_type = None
            self.root.config(cursor="")
            return

        if self.selected and getattr(self, "resize_edge", None):
            w = self.selected
            if w.x <= canvas_x <= w.x + w.width and w.y <= canvas_y <= w.y + w.height:
                self.save_state() 
                self.drag_data["item"] = w
                self.drag_data["mode"] = self.resize_edge
                self.drag_data["start_x"] = canvas_x
                self.drag_data["start_y"] = canvas_y
                self.drag_data["start_w"] = w.width
                self.drag_data["start_h"] = w.height
                self.drag_data["start_x_pos"] = w.x
                self.drag_data["start_y_pos"] = w.y
                if w not in self.selected_widgets: self.selected_widgets = [w]
                return

        item = self.canvas.find_withtag("current")
        if item:
            tags = self.canvas.gettags(item[0])
            for tag in tags:
                if tag.startswith("wid_"):
                    wid = tag.split("wid_")[1]
                    for w in self.widgets:
                        if w.id == wid:
                            if w not in self.selected_widgets: self.selected_widgets = [w]
                            self.select_widget(w)
                            self.save_state()
                            self.drag_data["item"] = w
                            self.drag_data["mode"] = "move"
                            self.drag_data["start_x"] = canvas_x
                            self.drag_data["start_y"] = canvas_y
                            return
        else:
            self.selected_widgets.clear()
            self.select_widget(None)
            self.sel_start_x, self.sel_start_y = canvas_x, canvas_y
            if self.selection_box: self.canvas.delete(self.selection_box)
            self.selection_box = self.canvas.create_rectangle(self.sel_start_x, self.sel_start_y, self.sel_start_x, self.sel_start_y, outline="#3b82f6", width=2, dash=(2, 2), fill="#3b82f6", stipple="gray25")
            self.drag_data["item"] = None

    def on_canvas_drag(self, event):
        canvas_x, canvas_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        if self.drag_data.get("item"):
            dx = canvas_x - self.drag_data["start_x"]
            dy = canvas_y - self.drag_data["start_y"]
            mode = self.drag_data.get("mode", "move")
            
            if mode != "move":
                w = self.drag_data["item"]
                new_w, new_h = self.drag_data["start_w"], self.drag_data["start_h"]
                new_x, new_y = self.drag_data["start_x_pos"], self.drag_data["start_y_pos"]
                
                if "e" in mode: new_w += dx
                if "w" in mode: new_w -= dx; new_x += dx
                if "s" in mode: new_h += dy
                if "n" in mode: new_h -= dy; new_y += dy
                
                if new_w < 30: 
                    new_w = 30
                    if "w" in mode: new_x = self.drag_data["start_x_pos"] + (self.drag_data["start_w"] - 30)
                if new_h < 30: 
                    new_h = 30
                    if "n" in mode: new_y = self.drag_data["start_y_pos"] + (self.drag_data["start_h"] - 30)
                    
                w.x, w.y, w.width, w.height = int(new_x), int(new_y), int(new_w), int(new_h)
                
                self.canvas.delete(f"wid_{w.id}")
                self.draw_widget(w)
                self.canvas.itemconfig(f"bg_{w.id}", outline="#f59e0b", width=2)
                
                if w.type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"]: self.update_container_layout(w)
                else:
                    p = self.get_parent_container(w.id)
                    if p: self.update_container_layout(p)
                
                self.var_x.set(w.x); self.var_y.set(w.y)
                self.var_w.set(w.width); self.var_h.set(w.height)
                
            else:
                moving_set = self.selected_widgets if len(self.selected_widgets) > 1 else [self.drag_data["item"]]
                # Actualizar el punto de referencia ANTES de mover
                self.drag_data["start_x"] = canvas_x
                self.drag_data["start_y"] = canvas_y

                for w in moving_set:
                    self.canvas.move(f"wid_{w.id}", dx, dy)
                    w.x += int(dx)
                    w.y += int(dy)
                    self.move_attached_children(w, dx, dy)

                if self.selected:
                    self.var_x.set(self.selected.x)
                    self.var_y.set(self.selected.y)
                
        elif self.selection_box:
            self.canvas.coords(self.selection_box, self.sel_start_x, self.sel_start_y, canvas_x, canvas_y)

    def move_attached_children(self, container_w, dx, dy):
        attached = getattr(container_w, "attached_widgets", None)
        if not attached:
            return
        for child_id in attached:
            child = next((cw for cw in self.widgets if cw.id == child_id), None)
            if child and child not in self.selected_widgets:
                self.canvas.move(f"wid_{child.id}", dx, dy)
                child.x += int(dx)
                child.y += int(dy)
                self.move_attached_children(child, dx, dy)

    def on_canvas_release(self, event):
        if self.drag_data.get("item"):
            dragged = self.drag_data["item"]
            mode = self.drag_data.get("mode", "move")
            
            if mode == "move":
                parent = self.get_parent_container(dragged.id)
                if parent:
                    cx = dragged.x + dragged.width/2
                    cy = dragged.y + dragged.height/2
                    target_id = None
                    for sib_id in parent.attached_widgets:
                        if sib_id == dragged.id: continue
                        sib = next((sw for sw in self.widgets if sw.id == sib_id), None)
                        if sib and sib.x <= cx <= sib.x + sib.width and sib.y <= cy <= sib.y + sib.height:
                            target_id = sib_id
                            break
                    if target_id:
                        idx_d = parent.attached_widgets.index(dragged.id)
                        idx_t = parent.attached_widgets.index(target_id)
                        parent.attached_widgets[idx_d], parent.attached_widgets[idx_t] = parent.attached_widgets[idx_t], parent.attached_widgets[idx_d]
                    
                    self.update_container_layout(parent)
            
            self.drag_data["item"] = None

        if self.selection_box:
            box_coords = self.canvas.coords(self.selection_box)
            self.canvas.delete(self.selection_box)
            self.selection_box = None
            if len(box_coords) == 4:
                x1, y1, x2, y2 = box_coords
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)
                if (max_x - min_x) < 5 and (max_y - min_y) < 5: return
                self.selected_widgets.clear()
                for w in self.widgets:
                    if not (w.x + w.width < min_x or w.x > max_x or w.y + w.height < min_y or w.y > max_y):
                        self.selected_widgets.append(w)
                if self.selected_widgets:
                    for w in self.widgets:
                        t = THEMES[self.current_theme]
                        if w in self.selected_widgets: self.canvas.itemconfig(f"bg_{w.id}", outline="#3b82f6", width=2)
                        else: self.canvas.itemconfig(f"bg_{w.id}", outline=w.color if w.type in ["VerticalContainer","HorizontalContainer","MatrixContainer"] else t["border"], width=2 if w.type in ["VerticalContainer","HorizontalContainer","MatrixContainer"] else 1)
                    self.selected = None
                    self.build_inspector_fields()

    def on_right_click(self, event):
        item = self.canvas.find_withtag("current")
        target_w = None
        if item:
            tags = self.canvas.gettags(item[0])
            for tag in tags:
                if tag.startswith("wid_"):
                    wid = tag.split("wid_")[1]
                    for w in self.widgets:
                        if w.id == wid:
                            target_w = w
                            if w not in self.selected_widgets: self.selected_widgets = [w]
                            self.select_widget(w)
                            break

        if target_w:
            menu = tk.Menu(self.root, tearoff=0)
            parent = self.get_parent_container(target_w.id)
            if parent:
                menu.add_command(label="Liberar de Container (Detach)", command=lambda tw=target_w, p=parent: self.detach_widget(tw, p))
                menu.add_separator()
            elif target_w.type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"]:
                menu.add_command(label="Acoplar Widget (Attach)...", command=lambda tw=target_w: self.open_attach_dialog(tw))
                menu.add_separator()
            
            menu.add_command(label="Eventos", command=lambda tw=target_w: self.open_connect_dialog(tw))
            menu.add_command(label="Ayuda", command=lambda tw=target_w: self.open_values_help(tw))
            menu.add_separator()
            menu.add_command(label="Duplicar", command=self.duplicate_selection)
            menu.add_command(label="Borrar", command=self.delete_selection)
            menu.tk_popup(event.x_root, event.y_root)
    
    
    def open_values_help(self, w):
        t = THEMES[self.current_theme]
        info = WIDGET_VALUE_HELP.get(w.type)
        cls = getattr(self, "custom_widget_classes", {}).get(w.type)

        if info is None:
            info = {
                "desc": "Este widget personalizado no declara ayuda. Agrega un atributo de clase "
                        "`value_help` al plugin para verla aquí.",
            }

        diag = tk.Toplevel(self.root)
        diag.title(f"Valores - {w.id}")
        diag.geometry("560x480")
        diag.config(bg=t["panel"])
        diag.transient(self.root)

        tk.Label(diag, text=f"{w.type}  ({w.id})", font=("Segoe UI", 12, "bold"),
                 bg=t["panel"], fg=t["accent"]).pack(anchor=tk.W, padx=15, pady=(12, 0))
        tk.Label(diag, text="Ayuda de ui.set_value()", font=("Segoe UI", 9),
                 bg=t["panel"], fg=t["fg"]).pack(anchor=tk.W, padx=15, pady=(0, 8))

        txt = scrolledtext.ScrolledText(diag, wrap=tk.WORD, font=("Consolas", 10),
                                        bg=t["bg"], fg=t["fg"], relief=tk.FLAT,
                                        highlightthickness=0, padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        txt.tag_config("h", foreground=t["accent"], font=("Consolas", 10, "bold"))
        txt.tag_config("code", foreground="#10b981")
        txt.tag_config("warn", foreground="#f59e0b")

        def section(title, body, tag=None):
            txt.insert(tk.END, title + "\n", "h")
            txt.insert(tk.END, body + "\n\n", tag or ())

        examples = [e.replace("{id}", w.id) for e in info.get("ejemplos", [])]

        if info.get("soportado") is False:
            section("Soporte", "Este widget NO acepta ui.set_value().", "warn")
        if info.get("tipo"):
            section("Tipo de dato", info["tipo"])
        if info.get("valores"):
            section("Valores válidos", info["valores"])
        if info.get("desc"):
            section("Descripción", info["desc"])
        if examples:
            section("Ejemplos", "\n".join(examples), "code")
        if info.get("envia"):
            section("Eventos que emite (navegador a Python)", info["envia"])

        evs = WIDGET_EVENTS_MAP.get(w.type)
        if evs:
            section("Eventos disponibles para Connect", ", ".join(evs))

        if info.get("notas"):
            section("Notas", "\n".join("- " + n for n in info["notas"]), "warn")

        txt.config(state=tk.DISABLED)

        def copy_examples():
            if examples:
                diag.clipboard_clear()
                diag.clipboard_append("\n".join(examples))

        btns = tk.Frame(diag, bg=t["panel"])
        btns.pack(fill=tk.X, padx=15, pady=10)
        if examples:
            tk.Button(btns, text="Copiar ejemplo", command=copy_examples, bg="#2563eb", fg="white",
                      font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)
        tk.Button(btns, text="Cerrar", command=diag.destroy, bg=t["border"], fg=t["fg"],
                  font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)
    
    
    def detach_widget(self, child, parent):
        self.save_state()
        if child.id in parent.attached_widgets:
            parent.attached_widgets.remove(child.id)
            child.width = 120
            child.height = 60
            child.x = parent.x - 30
            child.y = parent.y - 30
            self.canvas.delete(f"wid_{child.id}")
            self.draw_widget(child)
            self.update_container_layout(parent)
            messagebox.showinfo("Detached", f"El widget {child.id} ha sido liberado exitosamente.")

    def open_attach_dialog(self, container_w):
        diag = tk.Toplevel(self.root)
        diag.title(f"Attach a {container_w.id}")
        diag.geometry("380x250")
        diag.config(bg="#1e293b")
        diag.grab_set()

        tk.Label(diag, text=f"Acoplar Widget al Contenedor", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(pady=10)
        available_widgets = [w.id for w in self.widgets if w.id != container_w.id and w.type not in ["VerticalContainer", "HorizontalContainer", "MatrixContainer", "Tabs"] and not self.get_parent_container(w.id)]
        
        if not available_widgets:
            tk.Label(diag, text="No hay widgets sueltos disponibles.", fg="#ef4444", bg="#1e293b", font=("Segoe UI", 9)).pack(pady=15)
            return

        cb_widget = ttk.Combobox(diag, values=available_widgets, state="readonly", width=25)
        cb_widget.pack(pady=10)
        cb_widget.set(available_widgets[0])

        def do_attach():
            selected_id = cb_widget.get()
            if selected_id and selected_id not in container_w.attached_widgets:
                self.save_state()
                container_w.attached_widgets.append(selected_id)
                self.update_container_layout(container_w)
                diag.destroy()

        tk.Button(diag, text="Acoplar", command=do_attach, bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2").pack(pady=15)

    def update_container_layout(self, container):
        self.canvas.delete(f"wid_{container.id}")
        self.draw_widget(container)
        self.canvas.tag_lower(f"wid_{container.id}")
        if self.selected == container: self.canvas.itemconfig(f"bg_{container.id}", outline="#f59e0b", width=2)
            
        children = [w for w in self.widgets if w.id in container.attached_widgets]
        if not children: return
            
        pad_x, pad_y, spacing = 12, 35, 8
        usable_w = container.width - (pad_x * 2)
        usable_h = container.height - pad_y - 12
        n = len(children)
        
        if container.type == "VerticalContainer":
            item_h = max(20, (usable_h - (n - 1) * spacing) / n)
            item_w = usable_w
            cur_y = container.y + pad_y
            for child in children:
                child.x, child.y = container.x + pad_x, int(cur_y)
                child.width, child.height = int(item_w), int(item_h)
                cur_y += item_h + spacing
                
        elif container.type == "HorizontalContainer":
            item_w = max(20, (usable_w - (n - 1) * spacing) / n)
            item_h = usable_h
            cur_x = container.x + pad_x
            for child in children:
                child.x, child.y = int(cur_x), container.y + pad_y
                child.width, child.height = int(item_w), int(item_h)
                cur_x += item_w + spacing
                
        elif container.type == "MatrixContainer":
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            item_w = max(20, (usable_w - (cols - 1) * spacing) / cols)
            item_h = max(20, (usable_h - (rows - 1) * spacing) / rows)
            
            for i, child in enumerate(children):
                r, c = i // cols, i % cols
                child.x = int(container.x + pad_x + c * (item_w + spacing))
                child.y = int(container.y + pad_y + r * (item_h + spacing))
                child.width, child.height = int(item_w), int(item_h)

        for child in children:
            self.canvas.delete(f"wid_{child.id}")
            self.draw_widget(child)
            self.canvas.tag_raise(f"wid_{child.id}")
            if self.selected == child:
                self.canvas.itemconfig(f"bg_{child.id}", outline="#f59e0b", width=2)
                self.var_x.set(child.x); self.var_y.set(child.y)
                self.var_w.set(child.width); self.var_h.set(child.height)
    def show_widget_code(self, w):
        if w.id in self.widget_event_codes:
            self.editing_wid = w.id
            self.lbl_code_title.config(text=f"Editando archivo: events/{w.id}.py")
            self.code_editor.delete("1.0", tk.END)
            self.code_editor.insert(tk.END, self.widget_event_codes[w.id])
        else:
            self.editing_wid = None
            self.lbl_code_title.config(text="Ningun archivo creado para este widget")
            self.code_editor.delete("1.0", tk.END)
            self.code_editor.insert(tk.END, f"# Conecta un evento (clic derecho > Conectar) para crear events/{w.id}.py\n")
    
    def open_connect_dialog(self, w):
        diag = tk.Toplevel(self.root)
        diag.title(f"Connect - {w.id}")
        diag.geometry("420x300")
        diag.config(bg="#1e293b")
        diag.transient(self.root)
        diag.focus_force()

        tk.Label(diag, text=f"Gestor de Eventos ({w.type})", font=("Segoe UI", 11, "bold"),
                 fg="white", bg="#1e293b").pack(pady=10)

        valid_events = WIDGET_EVENTS_MAP.get(w.type, ["on_update", "on_click"])
        cb_events = ttk.Combobox(diag, values=valid_events, state="readonly", width=30)
        cb_events.pack(pady=10)
        cb_events.set(valid_events[0])

        btn_action = tk.Button(diag, text="Connect", bg="#10b981", fg="white",
                               font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", width=15)
        btn_action.pack(pady=10)

        lbl_state = tk.Label(diag, text="", fg="#94a3b8", bg="#1e293b", font=("Segoe UI", 9),
                             wraplength=380, justify="center")
        lbl_state.pack(pady=5)

        def refresh():
            if cb_events.get() in w.events:
                btn_action.config(text="Remove", bg="#ef4444")
            else:
                btn_action.config(text="Connect", bg="#10b981")
            #lbl_state.config(text="Conectados: " + (", ".join(w.events) if w.events else "ninguno"))

        def toggle():
            ev = cb_events.get()
            print(f"[connect] clic en {w.id} / {ev} / eventos antes: {list(w.events)}")
            try:
                if self.editing_wid and self.editing_wid in self.widget_event_codes:
                    self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)

                if ev in w.events:
                    del w.events[ev]
                    self.remove_event_function(w.id, ev)
                else:
                    w.events[ev] = ev
                    self.ensure_event_functions(w)

                self.refresh_scripts_list()
                self.show_widget_code(w)
                print(f"[connect] eventos despues: {list(w.events)}")
            except Exception as ex:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Error", f"{type(ex).__name__}: {ex}", parent=diag)
            finally:
                refresh()

        btn_action.config(command=toggle)
        cb_events.bind("<<ComboboxSelected>>", lambda e: refresh())
        #tk.Button(diag, text="Cerrar", command=diag.destroy, bg="#334155", fg="white", relief=tk.FLAT, cursor="hand2", width=10).pack(pady=8)
        refresh()

    def draw_widget(self, w):
        t = THEMES[self.current_theme]
        tag, bg_tag = f"wid_{w.id}", f"bg_{w.id}"
        
        if w.type == "Button":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "ToggleSwitch":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "Label":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 10, "bold"), tags=(tag,))
        elif w.type == "LED":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "Slider":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "CheckBox":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type in ["TextBox", "NumberBox"]:
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x+w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9), tags=(tag,))
        elif w.type == "StatusBar":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "Keyboard":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "Clock":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            cx, cy = w.x + w.width/2, w.y + w.height/2
            if w.clock_type == "Analogico":
                self.canvas.create_text(cx, cy, text="AnalogClock", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
            else:
                self.canvas.create_text(cx, cy, text="DigitalClock", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "Gauge":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            cx, cy = w.x + w.width/2, w.y + w.height/2
            if w.gauge_model == "Tacometro Clasico":
                self.canvas.create_text(cx, cy, text=f"GaugeManometer", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
            else:
                self.canvas.create_text(cx, cy, text=f"GaugeCircular", fill="#FFFFFF", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "ProgressBar":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", outline=t["border"], width=1, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "Tabs":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=t_names[0], fill="#ffffff", font=("Segoe UI", 8, "bold"), tags=(tag,))
        elif w.type == "Compass":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "Knob":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "SevenSegment":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", width=2, tags=(tag, bg_tag))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "VerticalContainer":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", outline=w.color if w.color else "#334155", width=2, tags=(tag, bg_tag))
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+28, fill="#234764", outline="", tags=(tag,))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "HorizontalContainer":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", outline=w.color if w.color else "#334155", width=2, tags=(tag, bg_tag))
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+28, fill="#234764", outline="", tags=(tag,))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        elif w.type == "MatrixContainer":
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="#234764", outline=w.color if w.color else "#334155", width=2, tags=(tag, bg_tag))
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+28, fill="#234764", outline="", tags=(tag,))
            self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"{w.type}", fill="#FFFFFF", font=("Segoe UI", 9, "bold"), tags=(tag,))
        
        elif w.type in self.custom_widget_types or (hasattr(self, 'custom_widget_classes') and w.type in self.custom_widget_classes):
            try:
                # Busca la clase del plugin de forma segura
                widget_class = self.custom_widget_classes.get(w.type)
                if not widget_class:
                    for k, cls in self.custom_widget_classes.items():
                        if k.lower() == w.type.lower():
                            widget_class = cls
                            break
                
                if widget_class:
                    instance = widget_class(w.width, w.height)
                    if hasattr(w, 'props') and w.props and hasattr(instance, 'default_props'):
                        for k, v in w.props.items():
                            instance.default_props[k] = v
                            
                    # Ejecuta el render_canvas del plugin primero
                    if hasattr(instance, "render_canvas"):
                        ids = instance.render_canvas(self.canvas, w.x, w.y)
                        if isinstance(ids, list):
                            for el in ids: 
                                self.canvas.itemconfig(el, tags=(tag,))
                else:
                    self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text=f"No class for {w.type}", fill="#ef4444", tags=(tag,))
            except Exception as e:
                print(f"Error render canvas {w.type}: {e}")
                self.canvas.create_text(w.x + w.width/2, w.y + w.height/2, text="Error Plugin", fill="#ef4444", tags=(tag,))
            
            # Dibuja el marco de selección encima de todo lo demás
            is_selected = (self.selected == w or w in self.selected_widgets)
            border_color = t["select"] if is_selected else t["border"]
            border_width = 4 if is_selected else 1
            self.canvas.create_rectangle(w.x, w.y, w.x+w.width, w.y+w.height, fill="", outline=border_color, width=border_width, tags=(tag, bg_tag), dash=(4, 4))

    def refresh_scripts_list(self):
        self.scripts_listbox.delete(0, tk.END)
        for wid in self.widget_event_codes.keys():
            self.scripts_listbox.insert(tk.END, f"{wid}.py")

    def load_script_from_list(self, event):
        if self.editing_wid and self.editing_wid in self.widget_event_codes:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)
            
        selection = self.scripts_listbox.curselection()
        if selection:
            filename = self.scripts_listbox.get(selection[0])
            wid = filename.replace(".py", "")
            self.editing_wid = wid
            
            self.lbl_code_title.config(text=f"Editando archivo: events/{filename}")
            self.code_editor.delete("1.0", tk.END)
            self.code_editor.insert(tk.END, self.widget_event_codes.get(wid, ""))
            self.syntax_highlight()

    def select_widget(self, w):
        if self.editing_wid and self.editing_wid in self.widget_event_codes:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)

        self.selected = w
        self.selected_widgets = [w] if w else []
        self.canvas.focus_set()
        t = THEMES[self.current_theme]
        for widget in self.widgets:
            w_id = getattr(widget, 'id', '')
            w_type = getattr(widget, 'type', '')
            w_color = getattr(widget, 'color', '#3b82f6')
            
            self.canvas.itemconfig(  
                f"bg_{w_id}",  
                outline=(w_color if w_type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"] else t["border"]),
                width=(2 if w_type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"] else 1),
                dash="",  # Remueve el punteado de los widgets no seleccionados
            )
            
        if w:
            w_id = getattr(w, 'id', '')
            # Cambia el color del borde a naranja y aplica la línea punteada
            self.canvas.itemconfig(f"bg_{w_id}", outline=t["select"], width=3, dash=(4, 4))
            self.var_id.set(w_id)
            
            # Obtener la etiqueta de forma segura (Nativos usan w.label, Plugins usan w.props['label'])
            label_val = getattr(w, 'label', None)
            if label_val is None and hasattr(w, 'props') and isinstance(w.props, dict):
                label_val = w.props.get('label', getattr(w, 'type', 'Widget'))
            self.var_label.set(label_val or "")

            self.var_x.set(getattr(w, 'x', 0))
            self.var_y.set(getattr(w, 'y', 0))
            self.var_w.set(getattr(w, 'width', 100))
            self.var_h.set(getattr(w, 'height', 100))

            self.sync_vars_from_widget(w)

            if w_id in self.widget_event_codes:
                self.editing_wid = w_id
                self.lbl_code_title.config(
                    text=f"Editando archivo: events/{w_id}.py"
                )
                self.code_editor.delete("1.0", tk.END)
                self.code_editor.insert(tk.END, self.widget_event_codes[w_id])
            else:
                self.editing_wid = None
                self.lbl_code_title.config(
                    text="Ningun archivo creado para este widget"
                )
                self.code_editor.delete("1.0", tk.END)
                self.code_editor.insert(
                    tk.END,
                    f"# Selecciona 'Connect' via Clic-Derecho en '{w_id}' para crear su archivo de eventos.\n",
                )
        else:
            self.var_id.set("")
            self.editing_wid = None
            self.lbl_code_title.config(
                text="(Ningun widget seleccionado ni archivo abierto)"
            )
            self.code_editor.delete("1.0", tk.END)

        self.build_inspector_fields()

    def update_prop_live(self, event=None):
        w = self.selected
        if not w:
            return
        
        self.unsaved_changes = True
        
        # 1. Asegurar que el widget tenga un diccionario de propiedades
        if not hasattr(w, 'props') or not isinstance(w.props, dict):
            w.props = getattr(w, 'default_props', {}).copy()
            
        # 2. Capturar todas las variables personalizadas del inspector
        if hasattr(self, 'custom_prop_vars') and self.custom_prop_vars:
            for p_name, p_var in self.custom_prop_vars.items():
                val = p_var.get()
                # Normalizar si viene de un SlideButton booleano o string
                if isinstance(val, bool):
                    w.props[p_name] = "True" if val else "False"
                else:
                    w.props[p_name] = str(val)

        # 3. Capturar la etiqueta principal si el inspector la tiene
        if hasattr(self, 'var_label'):
            label_val = self.var_label.get()
            w.props['label'] = label_val
            if hasattr(w, 'label'):
                w.label = label_val

        try:
            x, y = int(self.var_x.get()), int(self.var_y.get())
            ww, hh = int(self.var_w.get()), int(self.var_h.get())
        except ValueError:
            return
        
        # Actualizar coordenadas y dimensiones en la instancia
        w.x, w.y, w.width, w.height = x, y, ww, hh

        # Sincronizar colores u otros elementos estándar si aplican
        if hasattr(self, 'sync_widget_from_vars'):
            old_color = getattr(w, 'color', '#3b82f6')
            self.sync_widget_from_vars(w)
            if hasattr(w, 'color') and not w.color:
                w.color = old_color

        # 4. GUARDAR EL ESTADO DESPUÉS DE ACTUALIZAR TODAS LAS PROPS
        self.save_state()

        if hasattr(w, 'type') and w.type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"]:
            self.update_container_layout(w)
        else:
            parent = self.get_parent_container(getattr(w, 'id', ''))
            if parent:
                self.update_container_layout(parent)
            else:
                self.canvas.delete(f"wid_{getattr(w, 'id', '')}")
                self.draw_widget(w)
                try:
                    self.canvas.itemconfig(f"bg_{getattr(w, 'id', '')}", outline="#f59e0b", width=2)
                except Exception:
                    pass



    def _build_widget_from_dict(self, item):
        """Crea un widget (nativo o plugin) a partir de un dict de to_dict()."""
        w_type = item.get("type", "Button")
        props = item.get("props", {})

        target_cls = None
        for k, cls in getattr(self, "custom_widget_classes", {}).items():
            if k.lower() == w_type.lower():
                target_cls = cls
                break

        if target_cls:
            w = target_cls()
            w.id, w.type = item["id"], w_type
            w.x, w.y = item.get("x", 50), item.get("y", 50)
            w.width = item.get("width", getattr(w, "width", 300))
            w.height = item.get("height", getattr(w, "height", 150))
            defaults = copy.deepcopy(getattr(w, "default_props", {}))
            w.props = {**defaults, **copy.deepcopy(props)}
        else:
            w = WidgetItem(item["id"], w_type, item.get("x", 50), item.get("y", 50))
            w.width = item.get("width", 140)
            w.height = item.get("height", 50)
            for p in ["label", "color"] + PROP_VARS:
                if p in props:
                    setattr(w, p, props[p])
            w.attached_widgets = list(props.get("attached_widgets", []))
            w.props = copy.deepcopy(props)

        w.events = copy.deepcopy(item.get("events", {}))
        return w

    def duplicate_selection(self, event=None):
        # Si viene del atajo, no actuar cuando se está escribiendo en un campo
        if event is not None:
            try:
                if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, tk.Listbox)):
                    return
            except Exception:
                return

        sources = list(self.selected_widgets) or ([self.selected] if self.selected else [])
        if not sources:
            return

        # Sincronizar el código del editor antes de copiarlo
        if self.editing_wid and self.editing_wid in self.widget_event_codes:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)

        # Incluir los hijos de los contenedores seleccionados
        ordered = []
        def collect(w):
            if w in ordered:
                return
            ordered.append(w)
            for cid in (getattr(w, "attached_widgets", None) or []):
                child = next((c for c in self.widgets if c.id == cid), None)
                if child:
                    collect(child)
        for w in sources:
            collect(w)

        self.save_state()
        OFFSET = 30

        # IDs nuevos únicos
        used = {w.id for w in self.widgets}
        id_map = {}
        for w in ordered:
            while True:
                new_id = f"{w.type.lower()}_{self.widget_counter}"
                self.widget_counter += 1
                if new_id not in used:
                    break
            used.add(new_id)
            id_map[w.id] = new_id

        new_widgets = []
        for w in ordered:
            item = copy.deepcopy(w.to_dict())
            item["id"] = id_map[w.id]
            item["x"] = item.get("x", 0) + OFFSET
            item["y"] = item.get("y", 0) + OFFSET
            props = item.setdefault("props", {})
            props["attached_widgets"] = [id_map[c] for c in props.get("attached_widgets", []) if c in id_map]

            nw = self._build_widget_from_dict(item)
            self.widgets.append(nw)
            self.draw_widget(nw)
            new_widgets.append(nw)

            # Duplicar también el script de eventos
            code = self.widget_event_codes.get(w.id)
            if code is not None and nw.events:
                self.widget_event_codes[nw.id] = code.replace(
                    f"# Controlador para el widget: {w.id}",
                    f"# Controlador para el widget: {nw.id}",
                )

        # Reacomodar contenedores (dibuja a los hijos encima)
        for nw in new_widgets:
            if nw.type in ["VerticalContainer", "HorizontalContainer", "MatrixContainer"]:
                self.update_container_layout(nw)

        # Seleccionar las copias de lo que el usuario había seleccionado
        tops = [next(nw for nw, ow in zip(new_widgets, ordered) if ow is s) for s in sources]
        if len(tops) == 1:
            self.select_widget(tops[0])
        else:
            self.select_widget(None)
            self.selected_widgets = tops
            for nw in tops:
                self.canvas.itemconfig(f"bg_{nw.id}", outline="#3b82f6", width=2)
        self.scroll_to_widget(tops[-1])

        self.refresh_scripts_list()
        self.unsaved_changes = True



    def delete_selection(self):
        if self.selected_widgets:
            self.save_state()
            self.unsaved_changes = True
            for w in self.selected_widgets:
                parent = self.get_parent_container(w.id)
                if parent and w.id in parent.attached_widgets:
                    parent.attached_widgets.remove(w.id)
                    self.update_container_layout(parent)
                    
                self.canvas.delete(f"wid_{w.id}")
                if w.id in self.widget_event_codes: 
                    del self.widget_event_codes[w.id]
                if w in self.widgets: self.widgets.remove(w)
            self.selected_widgets.clear()
            self.select_widget(None)
            self.refresh_scripts_list()

    def save_widget_code_tab(self):
        if self.editing_wid:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)
            messagebox.showinfo("Guardado Local", f"Codigo del archivo events/{self.editing_wid}.py sincronizado.")
        else:
            messagebox.showwarning("Atencion", "No hay ningun archivo activo en el editor.")
    
    def new_project(self):
        # Preguntar si hay cambios sin guardar
        if self.unsaved_changes:
            res = messagebox.askyesnocancel(
                "Nuevo proyecto",
                "Tienes cambios sin guardar. ¿Deseas guardarlos antes de crear un proyecto nuevo?",
                parent=self.root
            )
            if res is None:      # Cancelar
                return
            if res is True:      # Sí: guardar primero
                self.save_project()
                # Si sigue habiendo cambios, el usuario canceló el diálogo de guardado
                if self.unsaved_changes:
                    return

        # Limpiar el estado del proyecto
        self.widgets.clear()
        self.canvas.delete("all")
        self.selected = None
        self.selected_widgets = []
        self.widget_counter = 0
        self.widget_event_codes = {}
        self.editing_wid = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_file_path = None
        self.pending_type = None
        self.root.config(cursor="")
        self.drag_data = {"item": None, "start_x": 0, "start_y": 0, "mode": "move"}
        self.selection_box = None

        # Refrescar la interfaz (limpia inspector y editor de código)
        self.select_widget(None)
        self.refresh_scripts_list()
        self.unsaved_changes = False
    
    def save_project(self):
        if self.editing_wid and self.editing_wid in self.widget_event_codes:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)

        if not self.current_file_path:
            filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
            if not filepath: return
            self.current_file_path = filepath
        
        project_data = {
            "version": "4.5",
            "theme": self.current_theme,
            "widgets": [w.to_dict() for w in self.widgets], # <-- ¡Funciona para todos por igual!
            "event_codes": self.widget_event_codes
        }
        
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
            messagebox.showinfo("Exito", "Proyecto guardado.")
            self.unsaved_changes = False
        except Exception as e: 
            messagebox.showerror("Error", str(e))

    def load_project(self):
        if self.unsaved_changes:
            res = messagebox.askyesnocancel(
                "Guardar cambios",
                "Tienes cambios sin guardar. ¿Deseas guardarlos antes de cerrar el proyecto?",
                parent=self.root
            )
            if res is True:  # Sí: intenta guardar y luego cierra
                self.save_project() 
        
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            self.current_file_path = filepath
            
            # Usar 'or' previene que si 'theme' es nulo en el JSON, falle la lectura
            self.current_theme = data.get("theme") or "dark"
            self.theme_var.set(self.current_theme)
            
            # Cargar datos y widgets primero
            self.widget_event_codes = data.get("event_codes", {})
            self.load_widgets_from_state(data.get("widgets", []))
            self.repair_all_events()
            self.refresh_scripts_list()
            
            # Aplicar el tema al final para sincronizar el canvas, inspector y colores limpios
            self.apply_theme()
            
            self.unsaved_changes = False
        except Exception as e: 
            messagebox.showerror("Error", str(e))

    def export_flask_project(self):
        if self.editing_wid and self.editing_wid in self.widget_event_codes:
            self.widget_event_codes[self.editing_wid] = self.code_editor.get("1.0", tk.END)
        self.repair_all_events()

        initial_name = "iot_dashboard_pro.zip"
        if getattr(self, "current_file_path", None):
            base_name = os.path.basename(self.current_file_path)
            file_root, _ = os.path.splitext(base_name)
            initial_name = f"{file_root}.zip"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".zip", 
            filetypes=[("ZIP files", "*.zip")], 
            initialfile=initial_name
        )
        if not filepath: 
            return

        # Procesamos los widgets para incluir el HTML de los plugins personalizados de forma directa
        processed_widgets = []
        for w in self.widgets:
            w_dict = w.to_dict() if hasattr(w, 'to_dict') else {
                "id": w.id, "type": w.type, "x": w.x, "y": w.y,
                "width": w.width, "height": w.height,
                "props": getattr(w, 'props', {}),
                "events": getattr(w, 'events', {})
            }

            props = w_dict.get('props', {})

            # Extracción limpia y directa del render_html del plugin
            try:
                if hasattr(self, 'custom_widget_classes'):
                    target_cls = None
                    for k, cls in self.custom_widget_classes.items():
                        if k.lower() == w.type.lower():
                            target_cls = cls
                            break

                    if target_cls:
                        instance = target_cls()
                        
                        # FIX: Asignar las propiedades actuales del widget a la instancia del plugin
                        if hasattr(instance, "props"):
                            instance.props = props.copy()
                        else:
                            setattr(instance, 'props', props.copy())

                        if hasattr(instance, "render_html"):
                            w_dict['custom_html'] = instance.render_html(w.id, props)
            except Exception as e:
                print(f"Error generando custom_html para plugin {w.type}: {e}")

            processed_widgets.append(w_dict)

        project_data = {
            "version": "4.5",
            "theme": self.current_theme,
            "widgets": processed_widgets,
            "custom_widget_types": self.custom_widget_types
        }

        # FIX 1: el JSON va dentro de un <script>. Si contiene "</script>" (los custom_html lo traen)
        # el navegador cierra el bloque ahí y el resto del código se imprime como texto.
        # Escapamos "<", ">" y "&" como \uXXXX: es válido en JSON y en JavaScript.
        project_json = (json.dumps(project_data)
                        .replace('<', '\\u003c')
                        .replace('>', '\\u003e')
                        .replace('&', '\\u0026'))

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('app.py', APP_PY)
            zf.writestr('project.json', json.dumps(project_data, indent=4))
            zf.writestr('requirements.txt', "Flask==3.0.0\nFlask-SocketIO==5.3.6\nsimple-websocket==1.0.0\n")
            zf.writestr('events/__init__.py', "# Paquete de eventos\n")

            for wid, code in self.widget_event_codes.items():
                if code.strip():
                    zf.writestr(f'events/{wid}.py', code)

            if os.path.exists(CUSTOM_WIDGETS_DIR):
                for file in os.listdir(CUSTOM_WIDGETS_DIR):
                    if file.endswith(".py"):
                        with open(os.path.join(CUSTOM_WIDGETS_DIR, file), "r", encoding="utf-8") as pf:
                            zf.writestr(f"custom_widgets/{file}", pf.read())

            if os.path.exists("seg.png"):
                with open("seg.png", "rb") as sf:
                    zf.writestr('static/seg.png', sf.read())
            html_code = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>IoT Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
       .seg-digit { width: 35px; height: 60px; background-image: url('static/seg.png'); background-size: 500% 200%; display: inline-block; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen m-0 p-0 overflow-auto">
    <div id="canvas" class="relative w-[3000px] h-[3000px]"></div>
    <script>
        const socket = io();
        window.dashboardSocket = socket;
        socket.on('connect', () => console.log('socket conectado'));
        socket.on('connect_error', e => console.error('socket error', e));

        // Registro para widgets personalizados: cada uno puede hacer
        // window.__widgets[id] = { update(val){...}, update_prop(prop, val){...} }
        window.__widgets = window.__widgets || {};

        // FIX 3: los custom widgets llaman emitEvent({id: '...'}, ...) con un objeto parcial.
        // Aquí lo resolvemos contra el widget real del proyecto para que tenga "events".
        function emitEvent(w, evName, value) {
            if (!w) return;
            if (!w.events) {
                const full = project.widgets.find(x => x.id === w.id);
                if (full) w = full;
            }
            const wired = !!(w.events && w.events[evName]);
            console.log('[emit]', w.id, evName, value, wired ? '' : '(no conectado)');
            if (wired) socket.emit('client_event', {id: w.id, event_name: evName, value: value});
        }

        const project = """ + project_json + """;
        const canvas = document.getElementById('canvas');
        const activeCharts = {};

        function getDigitPos(ch) {
            if (ch === '0') return { col: 4, row: 1 };
            let n = parseInt(ch);
            if (!isNaN(n) && n >= 1 && n <= 5) return { col: n - 1, row: 0 };
            if (!isNaN(n) && n >= 6 && n <= 9) return { col: n - 6, row: 1 };
            return { col: 4, row: 1 };
        }

        function gaugeIsCircular(props) {
            return String((props && props.gauge_model) || '').toLowerCase().startsWith('circ');
        }

        function updateSegmentDisplay(elId, valStr, segDigits) {
            const container = document.getElementById(elId);
            if(!container) return;
            container.innerHTML = '';
            let nDigits = parseInt(segDigits) || 4;
            let str = String(valStr).padStart(nDigits, '0');
            if (str.length > nDigits) str = str.slice(-nDigits);
            for(let i=0; i<str.length; i++) {
                let char = str[i];
                let span = document.createElement('span');
                span.className = 'seg-digit';
                let pos = getDigitPos(char);
                span.style.backgroundPosition = `${pos.col * 25}% ${pos.row * 100}%`;
                container.appendChild(span);
            }
        }
        
        
        
        
        
        
        project.widgets.forEach(w => {
            const wrapper = document.createElement('div');
            wrapper.className = 'absolute flex flex-col items-center justify-center';
            wrapper.style.left = w.x + 'px'; wrapper.style.top = w.y + 'px';
            wrapper.style.width = w.width + 'px'; wrapper.style.height = w.height + 'px';
            wrapper.id = w.id;
            
            
            
            
            //
            // GENERATE HTML
            //
            let innerHTML = ''; let props = w.props || {}; let events = w.events || {};
            if (w.type === 'Button') {
                let color = props.color || '#3b82f6';
                innerHTML += `<button id="el_${w.id}" class="w-full h-full font-bold rounded-xl text-white shadow-xl flex items-center justify-center cursor-pointer active:scale-95 transition-transform" style="background-color: ${color};">${props.label || 'Boton'}</button>`;
            } else if (w.type === 'ToggleSwitch') {
                let onColor = props.toggle_on_color || '#22c55e';
                let offColor = props.toggle_off_color || '#64748b';
                let onTxt = props.toggle_on_text || 'ON';
                let offTxt = props.toggle_off_text || 'OFF';

                innerHTML += `
                    <div class="w-full h-full flex items-center justify-center">
                        <label class="relative inline-flex items-center cursor-pointer select-none">
                            <input type="checkbox" id="el_${w.id}" class="sr-only peer">

                            <div id="ts_bg_${w.id}"
                                 class="w-16 h-8 rounded-full transition-colors duration-300 relative flex items-center"
                                 style="background-color: ${offColor};">

                                <span id="ts_txt_${w.id}"
                                      class="absolute right-2 text-[10px] font-bold text-white">
                                    ${offTxt}
                                </span>

                                <div id="ts_knob_${w.id}"
                                     class="absolute top-1 left-1 bg-white w-6 h-6 rounded-full transition-transform duration-300 shadow">
                                </div>
                            </div>
                        </label>
                    </div>`;
            }else if (w.type === 'Label') {
                let shape = props.label_shape || 'Redondeada';
                let bg = shape === 'Ninguna' ? 'transparent' : (props.label_bg_color || '#1e293b');
                let radius = shape === 'Redondeada' ? '12px' : '0px';
                innerHTML += `<div id="el_${w.id}" class="w-full h-full flex items-center justify-center font-bold text-base transition-all p-2" style="background-color: ${bg}; color: ${props.label_fg_color || '#f8fafc'}; border-radius: ${radius};">${props.label || 'Texto'}</div>`;
            }else if (w.type === 'LED') {
                let color = props.color || '#ef4444';
                innerHTML += `<div id="el_${w.id}" class="w-10 h-10 rounded-full transition-all duration-300 cursor-pointer" style="background-color: #334155; box-shadow: none;"></div><span class="text-xs mt-2 text-slate-400">${props.label}</span>`;
            } else if (w.type === 'Slider') {
                innerHTML += `<input id="el_${w.id}" type="range" min="0" max="100" value="50" class="w-full accent-blue-500 cursor-pointer"><span class="text-xs mt-2 text-slate-400">${props.label}</span>`;
            } else if (w.type === 'CheckBox') {
                innerHTML += `<label class="flex items-center gap-2 cursor-pointer font-semibold text-sm"><input id="el_${w.id}" type="checkbox" class="w-5 h-5 accent-blue-600 rounded cursor-pointer"> ${props.label}</label>`;
            } else if (w.type === 'TextBox' || w.type === 'NumberBox') {
                innerHTML += `<input id="el_${w.id}" type="${w.type === 'NumberBox' ? 'number' : 'text'}" placeholder="${props.label}" class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors">`;
            } else if (w.type === 'Knob') {
                innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg relative select-none">
                                <span class="absolute left-4 text-xs font-bold text-slate-400">0</span>
                                <span class="absolute right-2 text-xs font-bold text-slate-400">100</span>
                                <div id="knob_body_${w.id}" class="w-20 h-20 rounded-full bg-slate-700 border-4 border-slate-800 shadow-[0_4px_10px_rgba(0,0,0,0.5)] flex items-center justify-center cursor-pointer relative transition-transform" style="transform: rotate(-135deg);">
                                    <div class="w-2 h-2 bg-blue-500 rounded-full absolute top-2 shadow-[0_0_5px_#3b82f6]"></div>
                                </div><span class="text-xs mt-4 text-slate-400 uppercase tracking-wider font-bold">${props.label}</span></div>`;
            } else if (w.type === 'Gauge') {
                if (!gaugeIsCircular(props)) {
                    innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg relative p-2">
                                    <svg viewBox="-60 -60 120 120" class="w-full h-full drop-shadow-xl">
                                        <circle cx="0" cy="0" r="52" fill="#000000"/>
                                        <circle cx="0" cy="0" r="46" fill="#ffffff"/>
                                        <line x1="-36.4" y1="21" x2="-42.4" y2="24.5" stroke="#000" stroke-width="2.5"/>
                                        <line x1="-42" y1="0" x2="-46" y2="0" stroke="#000" stroke-width="1.5"/>
                                        <line x1="-36.4" y1="-21" x2="-42.4" y2="-24.5" stroke="#000" stroke-width="2.5"/>
                                        <line x1="-21" y1="-36.4" x2="-24.5" y2="-42.4" stroke="#000" stroke-width="1.5"/>
                                        <line x1="0" y1="-42" x2="0" y2="-46" stroke="#000" stroke-width="2.5"/>
                                        <line x1="21" y1="-36.4" x2="24.5" y2="-42.4" stroke="#000" stroke-width="1.5"/>
                                        <line x1="36.4" y1="-21" x2="42.4" y2="-24.5" stroke="#000" stroke-width="2.5"/>
                                        <line x1="42" y1="0" x2="46" y2="0" stroke="#000" stroke-width="1.5"/>
                                        <line x1="36.4" y1="21" x2="42.4" y2="24.5" stroke="#000" stroke-width="2.5"/>
                                        <text x="-26" y="22" font-size="11" font-weight="bold" font-family="sans-serif" text-anchor="middle" fill="#000000">0</text>
                                        <text x="-28" y="-12" font-size="11" font-weight="bold" font-family="sans-serif" text-anchor="middle" fill="#000000">25</text>
                                        <text x="0" y="-30" font-size="11" font-weight="bold" font-family="sans-serif" text-anchor="middle" fill="#000000">50</text>
                                        <text x="28" y="-12" font-size="11" font-weight="bold" font-family="sans-serif" text-anchor="middle" fill="#000000">75</text>
                                        <text x="26" y="22" font-size="11" font-weight="bold" font-family="sans-serif" text-anchor="middle" fill="#000000">100</text>
                                        <g id="gauge_needle_${w.id}" style="transform: rotate(-120deg); transform-origin: 0px 0px; transition: transform 0.3s ease;">
                                            <polygon points="-2.5,0 2.5,0 1,-38 -1,-38" fill="#2563eb"/>
                                        </g>
                                        <circle cx="0" cy="0" r="8" fill="#2563eb"/>
                                    </svg><span class="text-xs mt-1 font-bold text-slate-400">${props.label}</span></div>`;
                } else {
                    innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg relative p-2">
                                    <svg viewBox="0 0 100 60" class="w-full h-full drop-shadow-xl">
                                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#334155" stroke-width="10" stroke-linecap="round"/>
                                        <path id="gauge_arc_${w.id}" d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="${props.color || '#3b82f6'}" stroke-width="10" stroke-linecap="round" stroke-dasharray="125.6" stroke-dashoffset="30"/>
                                    </svg>
                                    <div class="absolute inset-0 flex flex-col items-center justify-center mt-4">
                                        <span id="gauge_val_${w.id}" class="text-xl font-bold text-white">75</span>
                                        <span class="text-[10px] text-slate-400 uppercase tracking-widest">${props.label}</span>
                                    </div>
                                 </div>`;
                }
            } else if (w.type === 'Compass') {
                innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg"><div class="relative w-24 h-24 rounded-full border-4 border-slate-600 bg-slate-800 flex items-center justify-center shadow-inner"><div class="absolute text-red-500 font-bold text-xs top-1">N</div><div class="absolute text-slate-400 font-bold text-xs bottom-1">S</div><div class="absolute text-slate-400 font-bold text-xs right-1">E</div><div class="absolute text-slate-400 font-bold text-xs left-1">W</div><div id="compass_needle_${w.id}" class="w-1 h-16 relative flex flex-col items-center transition-transform" style="transform: rotate(0deg);"><div class="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-b-[32px] border-b-red-500"></div><div class="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[32px] border-t-white"></div><div class="w-3 h-3 rounded-full bg-slate-300 absolute top-[29px] -left-[4px] shadow"></div></div></div><span class="text-[10px] mt-2 text-slate-400 uppercase font-bold">${props.label}</span></div>`;
            } else if (w.type === 'Clock') {
                if(props.clock_type === 'Analogico'){
                    innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg p-2">
                                    <svg viewBox="-50 -50 100 100" class="w-full h-full drop-shadow-xl">
                                        <circle cx="0" cy="0" r="45" fill="white" stroke="#334155" stroke-width="4"/>
                                        <line id="hour_wid_${w.id}" x1="0" y1="0" x2="0" y2="-20" stroke="black" stroke-width="4" stroke-linecap="round" style="transform: rotate(0deg);"/>
                                        <line id="min_wid_${w.id}" x1="0" y1="0" x2="0" y2="-30" stroke="black" stroke-width="2" stroke-linecap="round" style="transform: rotate(0deg);"/>
                                        <line id="sec_wid_${w.id}" x1="0" y1="0" x2="0" y2="-35" stroke="red" stroke-width="1" stroke-linecap="round" style="transform: rotate(0deg);"/>
                                        <circle cx="0" cy="0" r="2" fill="black"/>
                                    </svg><span class="text-xs mt-1 font-bold text-slate-400">${props.label}</span></div>`;
                } else {
                    innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg p-2"><div id="clock_${w.id}" class="font-mono text-3xl font-bold text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]">12:00:00</div><span class="text-xs mt-2 text-slate-500 uppercase tracking-widest font-bold">${props.label || 'Reloj'}</span></div>`;
                }
            } else if (w.type === 'SevenSegment') {
                innerHTML += `<div class="bg-slate-900 border border-slate-700 rounded p-3 w-full h-full flex items-center justify-center cursor-pointer hover:bg-slate-800"><div id="seg_${w.id}" class="flex gap-1 items-center justify-center"></div></div>`;
            } else if (w.type === 'ProgressBar') {
                let c = props.color || '#3b82f6';
                innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col justify-center shadow-lg p-4"><div class="flex justify-between items-end mb-2"><span class="text-xs font-bold text-slate-300">${props.label}</span><span id="prog_val_${w.id}" class="text-sm font-bold" style="color:${c}">${props.prog_value || 50}%</span></div><div class="w-full h-4 bg-slate-800 rounded-full overflow-hidden shadow-inner border border-slate-700"><div id="prog_bar_${w.id}" class="h-full transition-all duration-300" style="width: ${props.prog_value || 50}%; background-color: ${c};"></div></div></div>`;
            } else if (w.type === 'Keyboard') {
                innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center shadow-lg p-2 gap-1.5 select-none">
                                <div class="flex gap-1 justify-center w-full">${['1','2','3','4','5','6','7','8','9','0'].map(k=>`<button class="flex-1 py-2 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 rounded text-white font-bold text-xs shadow">${k}</button>`).join('')}</div>
                                <div class="flex gap-1 justify-center w-full">${['Q','W','E','R','T','Y','U','I','O','P'].map(k=>`<button class="flex-1 py-2 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 rounded text-white font-bold text-xs shadow">${k}</button>`).join('')}</div>
                                <div class="flex gap-1 justify-center w-full px-2">${['A','S','D','F','G','H','J','K','L'].map(k=>`<button class="flex-1 py-2 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 rounded text-white font-bold text-xs shadow">${k}</button>`).join('')}</div>
                                <div class="flex gap-1 justify-center w-full">${['Z','X','C','V','B','N','M'].map(k=>`<button class="flex-1 py-2 bg-slate-800 hover:bg-slate-700 active:bg-blue-600 rounded text-white font-bold text-xs shadow">${k}</button>`).join('')}</div>
                                <div class="flex gap-1 justify-center w-full"><button class="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 active:bg-blue-600 rounded text-white font-bold text-xs shadow">SPACE</button><button class="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 rounded text-white font-bold text-xs shadow">ENTER</button></div>
                              </div>`;
            } else if (w.type === 'StatusBar') {
                innerHTML += `<div class="w-full h-full bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center shadow-lg p-4"><div class="flex items-center gap-2"><div id="status_dot_${w.id}" class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div><span id="status_text_${w.id}" class="text-emerald-400 font-mono text-sm">Online</span></div></div>`;
            } else if(w.type === 'HorizontalContainer') {
                innerHTML += `<div id="el_${w.id}" class="bg-transparent border border-slate-700 rounded p-3 w-full h-full flex items-center justify-center cursor-pointer"></div>`;
            }  else if(w.type === 'VerticalContainer') {
                innerHTML += `<div id="el_${w.id}" class="bg-transparent border border-slate-700 rounded p-3 w-full h-full flex items-center justify-center cursor-pointer"></div>`;
            }  else if(w.type === 'MatrixContainer') {
                innerHTML += `<div id="el_${w.id}" class="bg-transparent border border-slate-700 rounded p-3 w-full h-full flex items-center justify-center cursor-pointer"></div>`;
            } else if (w.custom_html) {
                innerHTML += w.custom_html;
            } else {
                innerHTML += `<div id="el_${w.id}" class="bg-slate-900 border border-slate-700 rounded p-3 w-full h-full flex items-center justify-center text-slate-300 text-xs font-bold cursor-pointer hover:bg-slate-800">${props.label || w.type}</div>`;
            }
            wrapper.innerHTML = innerHTML;
            canvas.appendChild(wrapper);
            // FIX 2: innerHTML no ejecuta los <script>. Los agregamos despues de appendChild
            // para que document.getElementById ya encuentre los elementos del widget.
            if (w.custom_html) {
                wrapper.querySelectorAll('script').forEach(old => {
                    const s = document.createElement('script');
                    s.textContent = old.textContent;
                    old.replaceWith(s);
                });
            }







            //
            // EVEN HANDLER
            //
            if (w.type === 'SevenSegment') { updateSegmentDisplay(`seg_${w.id}`, '1234', props.seg_digits); }
            if (w.type === 'ToggleSwitch') {
                const chk = document.getElementById(`el_${w.id}`);
                const bg = document.getElementById(`ts_bg_${w.id}`);
                const knob = document.getElementById(`ts_knob_${w.id}`);
                const txt = document.getElementById(`ts_txt_${w.id}`);

                const paint = (on) => {
                    bg.style.backgroundColor = on
                        ? (props.toggle_on_color || '#22c55e')
                        : (props.toggle_off_color || '#64748b');

                    knob.style.transform = on
                        ? 'translateX(32px)'
                        : 'translateX(0px)';

                    txt.innerText = on
                        ? (props.toggle_on_text || 'ON')
                        : (props.toggle_off_text || 'OFF');

                    // OFF permanece a la derecha; ON pasa a la izquierda
                    txt.classList.toggle('left-2', on);
                    txt.classList.toggle('right-2', !on);
                };

                if (chk) {
                    chk._paint = paint;

                    chk.addEventListener('click', e =>
                        emitEvent(w, 'on_click', e.target.checked)
                    );

                    chk.addEventListener('change', e => {
                        paint(e.target.checked);
                        emitEvent(w, 'on_value_change', e.target.checked);
                    });
                }
            }

            // FIX 4: los custom widgets gestionan sus propios eventos; no les ponemos el on_click genérico
            const el = document.getElementById(`el_${w.id}`);
            if (el && w.type !== 'ToggleSwitch' && !w.custom_html) {
                if (w.type === 'Slider') {
                    el.addEventListener('input', e => emitEvent(w, 'on_value_change', Number(e.target.value)));
                } else if (w.type === 'NumberBox') {
                    el.addEventListener('input', e => emitEvent(w, 'on_value_change', Number(e.target.value)));
                    el.addEventListener('change', e => emitEvent(w, 'on_update', Number(e.target.value)));
                } else if (w.type === 'TextBox') {
                    el.addEventListener('input', e => emitEvent(w, 'on_value_change', e.target.value));
                    el.addEventListener('change', e => emitEvent(w, 'on_update', e.target.value));
                } else if (w.type === 'CheckBox') {
                    el.addEventListener('click', e => emitEvent(w, 'on_click', e.target.checked));
                    el.addEventListener('change', e => emitEvent(w, 'on_value_change', e.target.checked));
                } else {
                    el.addEventListener('click', () => emitEvent(w, 'on_click', true));
                }
            }
            if (w.type === 'Knob') {
                let knobBody = document.getElementById(`knob_body_${w.id}`);
                let isDragging = false, lastVal = null;
                knobBody.addEventListener('mousedown', (e) => { isDragging = true; e.preventDefault(); });
                window.addEventListener('mouseup', () => { isDragging = false; });
                window.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    let rect = knobBody.getBoundingClientRect();
                    let cx = rect.left + rect.width/2, cy = rect.top + rect.height/2;
                    let normAngle = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI + 90;
                    if (normAngle > 180) normAngle -= 360;
                    normAngle = Math.max(-135, Math.min(135, normAngle));
                    let val = Math.round(((normAngle + 135) / 270) * 100);
                    knobBody.style.transform = `rotate(${normAngle}deg)`;
                    if (val !== lastVal) { lastVal = val; emitEvent(w, 'on_value_change', val); }
                });
            }
            if (w.type === 'Keyboard') {
                wrapper.querySelectorAll('button').forEach(btn => {
                    btn.addEventListener('click', e => emitEvent(w, 'on_key_pressed', e.target.innerText));
                });
            }
        });

        setInterval(() => {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
            const h = now.getHours() % 12; const m = now.getMinutes(); const s = now.getSeconds();
            project.widgets.forEach(w => {
                if (w.type === 'Clock') {
                    if (w.props.clock_type === 'Analogico') {
                        const hLine = document.getElementById(`hour_wid_${w.id}`);
                        const mLine = document.getElementById(`min_wid_${w.id}`);
                        const sLine = document.getElementById(`sec_wid_${w.id}`);
                        if(hLine) hLine.style.transform = `rotate(${(h + m/60) * 30}deg)`;
                        if(mLine) mLine.style.transform = `rotate(${m * 6}deg)`;
                        if(sLine) sLine.style.transform = `rotate(${s * 6}deg)`;
                    } else {
                        const el = document.getElementById(`clock_${w.id}`);
                        if (el) el.innerText = timeStr;
                    }
                }
            });
        }, 1000);
        
        
        
        
        
        //
        // SOCKET UPDATE
        //
        socket.on('update', function(data) {
            const wid = data.id; const val = data.value;
            const w = project.widgets.find(x => x.id === wid);
            if (!w) return;

            // Custom widgets: si registraron un manejador, se lo delegamos
            if (window.__widgets[wid] && typeof window.__widgets[wid].update === 'function') {
                window.__widgets[wid].update(val);
                return;
            }

            const el = document.getElementById(`el_${wid}`);

            if (w.type === 'Slider' || w.type === 'NumberBox' || w.type === 'TextBox') { if (el) el.value = val; }
            else if (w.type === 'Label') { if (el) el.innerText = val; }
            else if (w.type === 'CheckBox') { if (el) el.checked = Boolean(val); }
            else if (w.type === 'ToggleSwitch') {
                const chk = document.getElementById(`el_${wid}`);
                if (chk) { chk.checked = Boolean(val); if (chk._paint) chk._paint(chk.checked); }
            }
            else if (w.type === 'SevenSegment') { updateSegmentDisplay(`seg_${wid}`, val, w.props.seg_digits); }
            else if (w.type === 'Gauge') {
                if (!gaugeIsCircular(w.props)) {
                    const gn = document.getElementById(`gauge_needle_${wid}`);
                    if(gn){ let deg = -120 + (Math.max(0, Math.min(100, val)) * 2.4); gn.style.transform = `rotate(${deg}deg)`; }
                } else {
                    const gv = document.getElementById(`gauge_val_${wid}`);
                    const ga = document.getElementById(`gauge_arc_${wid}`);
                    if (gv) gv.innerText = val;
                    if (ga) {
                        let pct = Math.max(0, Math.min(100, val));
                        let offset = 125.6 - (125.6 * pct / 100);
                        ga.style.strokeDashoffset = offset;
                    }
                }
            }
            else if (w.type === 'ProgressBar') {
                const pb = document.getElementById(`prog_bar_${wid}`); const pv = document.getElementById(`prog_val_${wid}`);
                if (pb) pb.style.width = val + '%';
                if (pv) pv.innerText = val + '%';
            }
            else if (w.type === 'StatusBar') {
                const st = document.getElementById(`status_text_${wid}`);
                const dot = document.getElementById(`status_dot_${wid}`);
                const isOnline = String(val).toLowerCase() === 'online' || val === true || String(val).toLowerCase() === 'true';
                
                if (st) {
                    st.innerText = isOnline ? 'Online' : 'Offline';
                    st.className = isOnline ? "text-emerald-400 font-mono text-sm" : "text-rose-400 font-mono text-sm";
                }
                if (dot) {
                    dot.className = isOnline ? "w-3 h-3 rounded-full bg-emerald-500 animate-pulse" : "w-3 h-3 rounded-full bg-rose-500";
                }
            }
            else if (w.type === 'Compass') { const cn = document.getElementById(`compass_needle_${wid}`); if (cn) cn.style.transform = `rotate(${val}deg)`; }
            // FIX 5: typo "degisComposite" en el CSS de rotación del Knob
            else if (w.type === 'Knob') { const kn = document.getElementById(`knob_body_${wid}`); if (kn) { let ang = -135 + (val * 2.7); kn.style.transform = `rotate(${ang}deg)`; } }
            else if (w.type === 'LED') {
                if (el) {
                    const color = w.props.color || '#ef4444';
                    const isOn = Boolean(val);
                    
                    if (isOn) {
                        // ENCENDIDO: Aplica el color base y un resplandor (glow) envolvente
                        el.style.backgroundColor = color;
                        el.style.boxShadow = `0 0 15px ${color}, 0 0 30px ${color}`;
                    } else {
                        // APAGADO: Color gris oscuro y se remueve por completo el resplandor
                        el.style.backgroundColor = '#334155';
                        el.style.boxShadow = 'none';
                    }
                }
            }
        });
        
        
        //
        // SOCKET PROPERTIES UPDATE
        //
        socket.on('prop_update', function(data) {
            const wid = data.id; const prop = data.prop; const val = data.value;
            const wrapper = document.getElementById(wid);
            const w = project.widgets.find(x => x.id === wid);
            if (!w || !wrapper) return;
            w.props[prop] = val;

            // FIX 6: en custom widgets, no tocar el DOM genérico (borraba el primer div del widget)
            if (w.custom_html) {
                if (window.__widgets[wid] && typeof window.__widgets[wid].update_prop === 'function') {
                    window.__widgets[wid].update_prop(prop, val);
                }
                return;
            }

            if (prop === 'label') {
                const lblEl = wrapper.querySelector('span, button, div');
                if (lblEl) lblEl.innerText = val;
            } else if (prop === 'color') {
                const el = document.getElementById(`el_${wid}`);
                if (el) el.style.backgroundColor = val;
            }
        });
    </script>
</body>
</html>
"""
            zf.writestr('templates/dashboard.html', html_code)

        # Verificación del ZIP generado
        report = []
        with zipfile.ZipFile(io.BytesIO(memory_file.getvalue())) as zr:
            for n in zr.namelist():
                if n.startswith('events/') and not n.endswith('__init__.py'):
                    defs = re.findall(r"^def (\w+)\(", zr.read(n).decode('utf-8'), flags=re.M)
                    report.append(f"{n}: {', '.join(defs) or 'SIN FUNCIONES'}")
        conectados = {w.id: list(w.events) for w in self.widgets if w.events}
        print("[export] conectados:", conectados)
        print("[export] archivos:", report)

        with open(filepath, "wb") as f: f.write(memory_file.getvalue())
        
        if messagebox.askyesno("Extraer proyecto", "¿Deseas extraer el archivo ZIP exportado?"):    
            # Definimos la carpeta de destino (por ejemplo, una carpeta con el mismo nombre del ZIP sin la extensión)
            extract_folder = os.path.splitext(filepath)[0]
            
            # Comprobar si ya existe el proyecto/carpeta extraída
            proceder_extraccion = True
            if os.path.exists(extract_folder):
                # 3. Preguntar si desea sustituirlo
                reemplazar = messagebox.askyesno(
                    "Proyecto existente", 
                    f"Ya existe una carpeta o archivo con el nombre '{os.path.basename(extract_folder)}'.\n¿Deseas sustituirlo?"
                )
                if not reemplazar:
                    proceder_extraccion = False

            # 4. Extraer si el usuario aceptó
            if proceder_extraccion:
                try:
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)
                    messagebox.showinfo("Éxito", f"Proyecto extraído correctamente en:\n{extract_folder}")
                except Exception as e:
                    messagebox.showerror("Error de extracción", f"No se pudo extraer el archivo:\n{str(e)}")
        # messagebox.showinfo("Exito", f"Exportado en:\n{filepath}\n\n" + ("\n".join(report) or "Sin scripts de eventos"))

if __name__ == '__main__':
    root = tk.Tk()
    app = IoTBuilderApp(root)
    root.mainloop()
