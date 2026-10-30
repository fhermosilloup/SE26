# Plantilla generada automáticamente para el widget personalizado: CustomSensor

class CustomSensor:
    def __init__(self, width=180, height=120):
        self.width = width
        self.height = height
        default_props = {
            "label": "CustomSensor"
        }
        supported_events = ["on_click"]

    def render_canvas(self, canvas, x, y):
        # Código para dibujar la representación en el canvas de Tkinter
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height, fill='#0f172a', outline='#38bdf8', width=2)
        txt = canvas.create_text(x + self.width/2, y + self.height/2, text='CustomSensor', fill='#38bdf8', font=('Segoe UI', 10, 'bold'))
        return [box, txt]

    def render_html(self, w_id, props):
        # Código HTML/Tailwind para la exportación Flask
        return f"<div class='bg-slate-900 border border-cyan-500 rounded-xl p-3 flex items-center justify-center shadow-xl w-full h-full text-cyan-400 font-bold'>{props.get('label', 'CustomSensor')}</div>"
