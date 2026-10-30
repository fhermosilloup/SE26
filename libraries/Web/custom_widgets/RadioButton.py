class RadioButton:
    # Atributos de clase correctos para que el cargador los lea automáticamente
    default_props = {
        "label": "Option 1",
        "group": "group_1"
    }
    supported_events = ["on_click"]

    def __init__(self, width=160, height=60):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        #print("RadioButton.RenderCanvas")
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height, fill='#0f172a', outline='#334155', width=1)
        outer_circle = canvas.create_oval(x + 15, y + self.height/2 - 10, x + 35, y + self.height/2 + 10, outline='#3b82f6', width=2)
        inner_circle = canvas.create_oval(x + 21, y + self.height/2 - 4, x + 29, y + self.height/2 + 4, fill='#3b82f6', outline='')
        txt = canvas.create_text(x + 48, y + self.height/2, text=self.default_props["label"], fill='#f8fafc', font=('Segoe UI', 10, 'bold'), anchor='w')
        return [box, outer_circle, inner_circle, txt]

    def render_html(self, w_id, props):
        print("RadioButton.renderHTML()")
        label = props.get('label', self.default_props["label"])
        group = props.get('group', self.default_props["group"])
        
        # Nota: Usamos llaves dobles {{ y }} en el JS para escapar correctamente la f-string de Python
        return f"""
        <div id="el_{w_id}" class="bg-slate-900 border border-slate-800 rounded-xl p-3 flex items-center gap-3 shadow-xl w-full h-full cursor-pointer select-none" onclick="const r = document.getElementById('radio_{w_id}'); if(r) {{ r.checked = true; emitEvent({{id: '{w_id}'}}, 'on_click', true); }}">
            <div class="w-6 h-6 rounded-full border-2 border-blue-500 flex items-center justify-center relative">
                <input type="radio" id="radio_{w_id}" name="{group}" class="sr-only peer">
                <div class="w-3 h-3 rounded-full bg-blue-500 opacity-0 peer-checked:opacity-100 transition-opacity"></div>
            </div>
            <span class="text-slate-100 font-bold text-sm">{label}</span>
        </div>
        """