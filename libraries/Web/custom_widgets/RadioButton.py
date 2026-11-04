class RadioButton:
    # Atributos de clase por defecto
    default_props = {
        "label": "Option 1",
        "group": "group_1"
    }
    
    supported_events = ["on_click"]

    def __init__(self, width=160, height=60):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()
    
    def to_dict(self):
        return {
            "id": getattr(self, 'id', "w_0"),
            "type": getattr(self, 'type', self.__class__.__name__),
            "x": getattr(self, 'x', 50),
            "y": getattr(self, 'y', 50),
            "width": getattr(self, 'width', getattr(self, 'default_props', {}).get('width', 300)),
            "height": getattr(self, 'height', getattr(self, 'default_props', {}).get('height', 150)),
            "props": getattr(self, 'props', {}),
            "events": getattr(self, 'events', {})
        }
        
    def render_canvas(self, canvas, x, y):
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height, fill='#234764', outline='#334155', width=1)
        txt = canvas.create_text(x + self.width/2, y + self.height/2, text="RadioButton", fill='#ffffff', font=('Segoe UI', 10, 'bold'))
        return [box, txt]

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        
        label = p.get('label', "Valor por defecto")
        group = p.get('group', "")
        
        # Nota: Usamos llaves dobles {{ y }} en el JS para escapar correctamente la f-string de Python
        return f"""
                <div id="el_{w_id}" class="p-3 flex items-center gap-3 w-full h-full cursor-pointer select-none" onclick="const r = document.getElementById('radio_{w_id}'); if(r) {{ r.checked = true; emitEvent({{id: '{w_id}'}}, 'on_click', true); }}">
                    <div class="w-6 h-6 rounded-full border-2 border-blue-500 flex items-center justify-center relative">
                        <input type="radio" id="radio_{w_id}" name="{group}" class="sr-only peer">
                        <div class="w-3 h-3 rounded-full bg-blue-500 opacity-0 peer-checked:opacity-100 transition-opacity"></div>
                    </div>
                    <span class="text-slate-100 font-bold text-sm">{label}</span>
                </div>
                """