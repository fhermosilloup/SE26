
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
   print('[client_event] recibido:', data)
   dispatch(data.get('id'), data.get('event_name'), data.get('value'))
@socketio.on('client_state')
def handle_client_state(data):
    ui_proxy._values[data.get('id')] = data.get('value')


load_handlers()
load_backend_plugins()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
