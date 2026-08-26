import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, copy, subprocess, sys, os
from PIL import Image, ImageTk, ImageDraw

VALID_GPIOS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]

COMPONENT_SPECS = {
    "LED": ("led_off.png", (19, 30)),
    "Button": ("button_pressed.png", (30, 30)),
    "Toggle Switch": ("toggle-switch.png", (40, 20)),
    "Buzzer": ("buzzer_off.png", (50, 33)),
    "Motor": ("motor.png", (60, 60)),
    "Servo": ("servo_base.png", (75, 27)),
    "Distance Sensor": ("distance_sensor.png", (83, 50)),
    "Light Sensor": ("light_sensor.png", (33, 33)),
    "Motion Sensor": ("motion_sensor_off.png", (80, 60)),
    "Potentiometer": (None, (150, 20)),
    "LCD": (None, (160, 50)),
}

COMPONENTS = {
    "LED": ("leds", {"pin": 21}),
    "Button": ("buttons", {"pin": 11}),
    "Toggle Switch": ("toggles", {"pin": 15, "off_label": "backward", "on_label": "forward", "is_on": False}),
    "Buzzer": ("buzzers", {"pin": 16, "frequency": 440}),
    "Motor": ("motors", {"forward_pin": 22, "backward_pin": 23}),
    "Servo": ("servos", {"pin": 24, "min_angle": -90, "max_angle": 90, "initial_angle": 0}),
    "Distance Sensor": ("distance_sensors", {"trigger_pin": 17, "echo_pin": 18, "min_distance": 0, "max_distance": 30}),
    "Light Sensor": ("light_sensors", {"pin": 8}),
    "Motion Sensor": ("motion_sensors", {"pin": 27, "detection_radius": 50, "delay_duration": 5, "block_duration": 3}),
    "Potentiometer": ("potentiometers", {"channel": 0}),
    "LCD": ("lcds", {"pins": [2, 3, 4, 5, 6, 7], "columns": 16, "lines": 2}),
}

class Designer:
    def __init__(self, root):
        self.root = root
        self.root.title("TkGPIO Circuit Designer")
        self.components = []
        self.selected = None
        self.next_id = 1
        self.canvas_w, self.canvas_h = 300, 300
        self.drag_offset = (0, 0)
        self.entries = {}
        self.loaded_images = {}
        self.palette_icons = {}
        self.pinout_photo = None
        self.pinout_scale = 1.0
        self.pinout_selected = False

        self.load_component_images()
        self.load_pinout_image()
        self.build_ui()
        self.draw_grid()

        # Ajuste automático del tamaño de ventana
        self.auto_fit_window()

    def remove_background(self, pil_img, bg_color=(255, 255, 255), tolerance=25):
        img = pil_img.convert("RGBA")
        datas = img.getdata()
        new_data = []
        r_bg, g_bg, b_bg = bg_color
        for r, g, b, a in datas:
            if abs(r - r_bg) <= tolerance and abs(g - g_bg) <= tolerance and abs(b - b_bg) <= tolerance:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
        return img

    def load_component_images(self):
        for comp_type, (filename, size) in COMPONENT_SPECS.items():
            w, h = size
            if filename and os.path.exists(filename):
                try:
                    pil_img = Image.open(filename)
                    pil_img = self.remove_background(pil_img, bg_color=(255, 255, 255), tolerance=25)
                    
                    canvas_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
                    self.loaded_images[comp_type] = {"img": ImageTk.PhotoImage(canvas_img), "w": w, "h": h}
                    
                    ratio = 36.0 / h
                    icon_w = max(16, int(w * ratio))
                    icon_img = pil_img.resize((icon_w, 36), Image.Resampling.LANCZOS)
                    self.palette_icons[comp_type] = ImageTk.PhotoImage(icon_img)
                except Exception as e:
                    print(f"Error al cargar {filename}: {e}")
                    self.loaded_images[comp_type] = {"img": None, "w": w, "h": h}
                    self.palette_icons[comp_type] = None
            else:
                self.loaded_images[comp_type] = {"img": None, "w": w, "h": h}
                synthetic = Image.new("RGBA", (50, 36), (255, 255, 255, 0))
                draw = ImageDraw.Draw(synthetic)
                if comp_type == "LCD":
                    draw.rectangle([2, 6, 48, 30], fill="#82E007", outline="#111", width=2)
                    draw.text((12, 10), "LCD", fill="black")
                elif comp_type == "Potentiometer":
                    draw.rectangle([4, 15, 46, 21], fill="#e0e0e0", outline="#666", width=1)
                    draw.rectangle([20, 10, 30, 26], fill="#888", outline="#333", width=1)
                else:
                    draw.rectangle([4, 4, 46, 32], fill="#ccc", outline="#555", width=1)
                self.palette_icons[comp_type] = ImageTk.PhotoImage(synthetic)

    def load_pinout_image(self):
        if os.path.exists("pinout.png"):
            try:
                self.pinout_base_img = Image.open("pinout.png")
                orig_w, orig_h = self.pinout_base_img.size
                target_w = min(460, orig_w)
                self.pinout_scale = target_w / orig_w
                new_w = int(orig_w * self.pinout_scale)
                new_h = int(orig_h * self.pinout_scale)
                
                img = self.pinout_base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self.pinout_photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error al cargar pinout.png: {e}")
                self.pinout_base_img = None
                self.pinout_photo = None
        else:
            self.pinout_base_img = None
            self.pinout_photo = None

    def toggle_pinout_select(self, event=None):
        self.pinout_selected = not self.pinout_selected
        if self.pinout_selected:
            self.select(None)
            self.lbl_pinout.config(bd=2, relief="solid", highlightbackground="#007acc", highlightcolor="#007acc", highlightthickness=2)
            self.status.config(text=f"Pinout seleccionado | Zoom: {int(self.pinout_scale * 100)}% (Usa la rueda del ratón para ampliar/reducir)")
        else:
            self.lbl_pinout.config(bd=1, relief="solid", highlightthickness=0)
            self.update_status()

    def on_pinout_zoom(self, event):
        if not self.pinout_selected or not self.pinout_base_img:
            return

        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            new_scale = self.pinout_scale * 1.10
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            new_scale = self.pinout_scale * 0.90
        else:
            return

        self.pinout_scale = max(0.3, min(3.0, new_scale))
        orig_w, orig_h = self.pinout_base_img.size
        new_w = max(80, int(orig_w * self.pinout_scale))
        new_h = max(80, int(orig_h * self.pinout_scale))

        resized = self.pinout_base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.pinout_photo = ImageTk.PhotoImage(resized)
        self.lbl_pinout.config(image=self.pinout_photo)
        self.status.config(text=f"Pinout seleccionado | Zoom: {int(self.pinout_scale * 100)}% ({new_w}×{new_h} px)")

    def get_comp_bounds(self, comp_type):
        info = self.loaded_images.get(comp_type, {"w": 40, "h": 40})
        return max(10, info["w"] // 2), max(10, info["h"] // 2)

    def build_ui(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        for text, cmd in [
            ("Nuevo", self.new_project), ("Abrir JSON", self.open_json),
            ("Guardar JSON", self.save_json), ("▶ Simular", self.simulate),
            ("Exportar Python", self.export_python), ("⌨ Atajos", self.show_shortcuts)]:
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=2)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)

        # 1. Panel Izquierdo: Componentes (Fijo a la izquierda)
        left_frame = ttk.LabelFrame(body, text="Componentes", padding=6, width=170)
        left_frame.pack(side="left", fill="y", padx=3, pady=2)
        left_frame.pack_propagate(False)

        self.pal_canvas = tk.Canvas(left_frame, highlightthickness=0, bg="#fbfbfb")
        pal_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.pal_canvas.yview)
        self.pal_container = tk.Frame(self.pal_canvas, bg="#fbfbfb")

        self.pal_container.bind(
            "<Configure>",
            lambda e: self.pal_canvas.configure(scrollregion=self.pal_canvas.bbox("all"))
        )
        self.pal_canvas.create_window((0, 0), window=self.pal_container, anchor="nw", width=145)
        self.pal_canvas.configure(yscrollcommand=pal_scroll.set)

        self.pal_canvas.pack(side="left", fill="both", expand=True)
        pal_scroll.pack(side="right", fill="y")

        self.pal_canvas.bind("<MouseWheel>", self.on_palette_mousewheel)
        self.pal_canvas.bind("<Button-4>", self.on_palette_mousewheel)
        self.pal_canvas.bind("<Button-5>", self.on_palette_mousewheel)
        self.pal_container.bind("<MouseWheel>", self.on_palette_mousewheel)
        self.pal_container.bind("<Button-4>", self.on_palette_mousewheel)
        self.pal_container.bind("<Button-5>", self.on_palette_mousewheel)

        for name in COMPONENTS:
            self.create_palette_card(self.pal_container, name)

        # 2. Panel Derecho: Propiedades (Acoplado a la derecha para no deformarse)
        self.right = ttk.LabelFrame(body, text="Propiedades", padding=10, width=280)
        self.right.pack(side="right", fill="y", padx=3, pady=2)
        self.right.pack_propagate(False)

        self.props_container = ttk.Frame(self.right)
        self.props_container.pack(fill="x", expand=False)
        self.btn_apply = ttk.Button(self.right, text="Aplicar", command=self.apply_properties)

        box = ttk.LabelFrame(self.right, text="Canvas", padding=6)
        box.pack(side="bottom", fill="x", pady=8)
        self.wvar = tk.StringVar(value=str(self.canvas_w))
        self.hvar = tk.StringVar(value=str(self.canvas_h))
        ttk.Label(box, text="Ancho").grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.wvar, width=8).grid(row=0, column=1, pady=2)
        ttk.Label(box, text="Alto").grid(row=1, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.hvar, width=8).grid(row=1, column=1, pady=2)
        ttk.Button(box, text="Aplicar", command=self.resize_canvas).grid(row=2, column=0, columnspan=2, pady=5)

        # 3. Panel Central: Notebook (Llena todo el espacio intermedio)
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(side="left", fill="both", expand=True, padx=3, pady=2)

        # Pestaña 1: Diagrama con scroll interno independiente
        tab_diagram = ttk.Frame(self.notebook)
        self.notebook.add(tab_diagram, text="  Diagrama  ")

        self.diag_scroll_canvas = tk.Canvas(tab_diagram, highlightthickness=0, bg="#f0f0f0")
        diag_vbar = ttk.Scrollbar(tab_diagram, orient="vertical", command=self.diag_scroll_canvas.yview)
        diag_hbar = ttk.Scrollbar(tab_diagram, orient="horizontal", command=self.diag_scroll_canvas.xview)
        
        self.diag_content = tk.Frame(self.diag_scroll_canvas, bg="#f0f0f0", padx=10, pady=10)
        self.diag_content.bind(
            "<Configure>",
            lambda e: self.diag_scroll_canvas.configure(scrollregion=self.diag_scroll_canvas.bbox("all"))
        )
        self.diag_scroll_canvas.create_window((0, 0), window=self.diag_content, anchor="nw")
        self.diag_scroll_canvas.configure(xscrollcommand=diag_hbar.set, yscrollcommand=diag_vbar.set)

        self.diag_scroll_canvas.pack(side="left", fill="both", expand=True)
        diag_vbar.pack(side="right", fill="y")
        diag_hbar.pack(side="bottom", fill="x")

        # Workspace
        workspace_box = ttk.LabelFrame(self.diag_content, text="Área de Diseño", padding=6)
        workspace_box.pack(side="top", anchor="nw", pady=(0, 10))

        self.canvas = tk.Canvas(
            workspace_box, bg="white", highlightthickness=1, highlightbackground="#666",
            width=self.canvas_w, height=self.canvas_h
        )
        self.canvas.pack(side="top", anchor="nw")

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Pinout debajo del Workspace
        pinout_box = ttk.LabelFrame(self.diag_content, text="Referencia GPIO Pinout (Clic para Zoom)", padding=8)
        pinout_box.pack(side="top", anchor="nw", fill="x", pady=5)

        if self.pinout_photo:
            self.lbl_pinout = tk.Label(pinout_box, image=self.pinout_photo, bg="white", bd=1, relief="solid", cursor="hand2")
            self.lbl_pinout.pack(anchor="center", pady=4)
            self.lbl_pinout.bind("<Button-1>", self.toggle_pinout_select)
            self.lbl_pinout.bind("<MouseWheel>", self.on_pinout_zoom)
            self.lbl_pinout.bind("<Button-4>", self.on_pinout_zoom)
            self.lbl_pinout.bind("<Button-5>", self.on_pinout_zoom)
        else:
            self.lbl_pinout = tk.Label(
                pinout_box, text="Coloca el archivo 'pinout.png' junto a la aplicación para ver el diagrama de pines.",
                font=("Arial", 9, "italic"), fg="#666", bg="white", padx=20, pady=15, relief="groove"
            )
            self.lbl_pinout.pack(fill="x", pady=4)

        # Pestaña 2: JSON Config
        tab_json = ttk.Frame(self.notebook)
        self.notebook.add(tab_json, text="  JSON Config  ")

        json_scroll = ttk.Scrollbar(tab_json, orient="vertical")
        json_scroll.pack(side="right", fill="y")
        self.json_text = tk.Text(
            tab_json, wrap="none", font=("Consolas", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white", yscrollcommand=json_scroll.set
        )
        self.json_text.pack(fill="both", expand=True)
        json_scroll.config(command=self.json_text.yview)

        # Pestaña 3: Python
        tab_python = ttk.Frame(self.notebook)
        self.notebook.add(tab_python, text="  Python  ")

        py_scroll = ttk.Scrollbar(tab_python, orient="vertical")
        py_scroll.pack(side="right", fill="y")
        self.py_text = tk.Text(
            tab_python, wrap="none", font=("Consolas", 10),
            bg="#1e1e1e", fg="#9cdcfe", insertbackground="white", yscrollcommand=py_scroll.set
        )
        self.py_text.pack(fill="both", expand=True)
        py_scroll.config(command=self.py_text.yview)

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.status = ttk.Label(self.root, relief="sunken", anchor="w")
        self.status.pack(fill="x")

        # Atajos de Teclado
        self.root.bind_all("<Delete>", self.on_key_delete)
        self.root.bind_all("<BackSpace>", self.on_key_delete)
        self.root.bind_all("<Key-c>", self.on_key_copy)
        self.root.bind_all("<Key-C>", self.on_key_copy)
        self.root.bind_all("<Control-c>", self.on_key_copy)
        self.root.bind_all("<Control-C>", self.on_key_copy)
        self.root.bind_all("<Escape>", lambda e: self.select(None))
        self.root.bind_all("<Up>", lambda e: self.on_nudge(0, -10))
        self.root.bind_all("<Down>", lambda e: self.on_nudge(0, 10))
        self.root.bind_all("<Left>", lambda e: self.on_nudge(-10, 0))
        self.root.bind_all("<Right>", lambda e: self.on_nudge(10, 0))
        self.root.bind_all("<Control-s>", lambda e: self.save_json())
        self.root.bind_all("<Control-S>", lambda e: self.save_json())
        self.root.bind_all("<Control-o>", lambda e: self.open_json())
        self.root.bind_all("<Control-O>", lambda e: self.open_json())
        self.root.bind_all("<Control-e>", lambda e: self.export_python())
        self.root.bind_all("<Control-E>", lambda e: self.export_python())
        self.root.bind_all("<Control-n>", lambda e: self.new_project())
        self.root.bind_all("<Control-N>", lambda e: self.new_project())
        self.root.bind_all("<F5>", lambda e: self.simulate())
    
    def auto_fit_window(self):
        """Calcula el ancho necesario para eliminar huecos sin exceder el monitor."""
        self.root.update_idletasks()

        pinout_w = self.pinout_photo.width() if self.pinout_photo else 450
        middle_needed_w = max(self.canvas_w + 50, pinout_w + 50, 400)
        
        # 170 (Izquierda) + middle_needed_w (Centro) + 280 (Derecha) + márgenes
        needed_w = 170 + middle_needed_w + 280 + 35
        
        pinout_h = self.pinout_photo.height() if self.pinout_photo else 200
        needed_h = max(self.canvas_h + pinout_h + 230, 750)

        # Límite de seguridad según la pantalla
        screen_w = self.root.winfo_screenwidth() - 60
        screen_h = self.root.winfo_screenheight() - 80

        final_w = min(needed_w, screen_w)
        final_h = min(needed_h, screen_h)

        self.root.geometry(f"{final_w}x{final_h}")
        self.diag_scroll_canvas.configure(scrollregion=self.diag_scroll_canvas.bbox("all"))
        
    def on_palette_mousewheel(self, event):
        if event.num == 4:
            self.pal_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.pal_canvas.yview_scroll(1, "units")
        elif event.delta:
            self.pal_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_palette_card(self, parent, name):
        card = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid", cursor="hand2")
        card.pack(fill="x", padx=4, pady=3)

        icon_img = self.palette_icons.get(name)
        lbl_icon = tk.Label(card, image=icon_img, bg="#ffffff", cursor="hand2") if icon_img else None
        if lbl_icon:
            lbl_icon.pack(pady=(4, 1))

        lbl_name = tk.Label(card, text=name, font=("Arial", 9, "bold"), bg="#ffffff", fg="#2c3e50", cursor="hand2")
        lbl_name.pack(pady=(0, 4))

        widgets = [card, lbl_name]
        if lbl_icon:
            widgets.append(lbl_icon)

        def on_enter(e):
            card.config(bg="#e8f0fe", highlightthickness=1, highlightbackground="#709cd9", highlightcolor="#709cd9")
            lbl_name.config(bg="#e8f0fe", fg="#1967d2")
            if lbl_icon: lbl_icon.config(bg="#e8f0fe")

        def on_leave(e):
            card.config(bg="#ffffff", highlightthickness=0)
            lbl_name.config(bg="#ffffff", fg="#2c3e50")
            if lbl_icon: lbl_icon.config(bg="#ffffff")

        def on_click(e):
            self.add_component(name)

        for w in widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
            w.bind("<MouseWheel>", self.on_palette_mousewheel)
            w.bind("<Button-4>", self.on_palette_mousewheel)
            w.bind("<Button-5>", self.on_palette_mousewheel)

    def update_json_view(self):
        cfg = self.configuration()
        formatted_json = json.dumps(cfg, indent=4)
        self.json_text.config(state="normal")
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", formatted_json)
        self.json_text.config(state="disabled")

    def update_python_view(self):
        code = self.generated_code()
        self.py_text.config(state="normal")
        self.py_text.delete("1.0", "end")
        self.py_text.insert("1.0", code)
        self.py_text.config(state="disabled")

    def on_tab_changed(self, event):
        selected_tab = self.notebook.index(self.notebook.select())
        if selected_tab == 1:
            self.update_json_view()
        elif selected_tab == 2:
            self.update_python_view()

    def show_shortcuts(self):
        shortcuts_text = (
            "Edición de componentes:\n"
            "  • Supr / Backspace : Eliminar componente seleccionado\n"
            "  • C / Ctrl + C       : Duplicar componente seleccionado\n"
            "  • Flechas (↑ ↓ ← →) : Mover elemento en pasos de 10px\n"
            "  • Esc               : Deseleccionar componente\n\n"
            "Acciones de proyecto:\n"
            "  • Ctrl + N          : Nuevo proyecto\n"
            "  • Ctrl + O          : Abrir archivo JSON\n"
            "  • Ctrl + S          : Guardar proyecto JSON\n"
            "  • Ctrl + E          : Exportar código Python (.py)\n"
            "  • F5                : Ejecutar simulación"
        )
        messagebox.showinfo("Atajos de Teclado", shortcuts_text)

    def get_used_gpios(self, exclude_component=None):
        used = set()
        for c in self.components:
            if exclude_component and c is exclude_component:
                continue
            for k in ("pin", "trigger_pin", "echo_pin", "forward_pin", "backward_pin"):
                if isinstance(c.get(k), int):
                    used.add(c[k])
            if isinstance(c.get("pins"), list):
                used.update([p for p in c["pins"] if isinstance(p, int)])
        return used

    def get_next_available_gpios(self, count=1, exclude_component=None):
        used = self.get_used_gpios(exclude_component)
        available = [p for p in VALID_GPIOS if p not in used]
        if len(available) < count:
            return None
        return available[:count]

    def get_next_type_index(self, typ):
        used_numbers = set()
        for c in self.components:
            if c["type"] == typ:
                parts = c.get("name", "").rsplit(" ", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    used_numbers.add(int(parts[1]))
        idx = 1
        while idx in used_numbers:
            idx += 1
        return idx

    def rebuild_property_fields(self):
        for widget in self.props_container.winfo_children():
            widget.destroy()
        self.entries.clear()

        if not self.selected:
            self.btn_apply.pack_forget()
            lbl = ttk.Label(self.props_container, text="Ningún componente\nseleccionado", justify="center", foreground="#777")
            lbl.pack(pady=20)
            return

        ignored_keys = {"id", "tag"}
        ordered_keys = ["type", "name"] + [k for k in self.selected.keys() if k not in ("type", "name", "x", "y") and k not in ignored_keys] + ["x", "y"]

        for key in ordered_keys:
            row = ttk.Frame(self.props_container)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=key, width=13, anchor="w").pack(side="left")
            e = ttk.Entry(row)
            e.pack(side="left", fill="x", expand=True)

            val = self.selected.get(key, "")
            e.insert(0, str(val))
            if key == "type":
                e.config(state="readonly")

            self.entries[key] = e

        self.btn_apply.pack(fill="x", pady=10)

    def draw_grid(self):
        self.canvas.delete("grid")
        self.canvas.config(scrollregion=(0, 0, self.canvas_w, self.canvas_h))
        
        for x in range(0, self.canvas_w, 20): 
            self.canvas.create_line(x, 0, x, self.canvas_h, fill="#eeeeee", tags="grid")
        for y in range(0, self.canvas_h, 20): 
            self.canvas.create_line(0, y, self.canvas_w, y, fill="#eeeeee", tags="grid")
            
        self.canvas.tag_lower("grid")
        self.redraw()

    def redraw(self):
        self.canvas.delete("component", "selection")
        for c in self.components:
            x, y = c["x"], c["y"]
            tag = c["tag"]
            typ = c["type"]
            img_data = self.loaded_images.get(typ)

            if img_data and img_data["img"]:
                self.canvas.create_image(x, y, image=img_data["img"], tags=("component", tag))
            elif typ == "LCD":
                self.canvas.create_rectangle(x-80, y-25, x+80, y+25, fill="#82E007", outline="#222", width=2, tags=("component", tag))
                self.canvas.create_text(x, y, text=c.get("name", "LCD"), fill="black", font=("Arial", 9, "bold"), tags=("component", tag))
            elif typ == "Potentiometer":
                self.canvas.create_rectangle(x-75, y-8, x+75, y+8, fill="#e0e0e0", outline="#666", tags=("component", tag))
                self.canvas.create_rectangle(x-10, y-12, x+10, y+12, fill="#888", outline="#333", tags=("component", tag))
            else:
                w, h = self.get_comp_bounds(typ)
                self.canvas.create_rectangle(x-w, y-h, x+w, y+h, fill="#bbb", outline="#333", tags=("component", tag))

        if self.selected:
            c = self.selected
            half_w, half_h = self.get_comp_bounds(c["type"])
            self.canvas.create_rectangle(c["x"] - half_w - 3, c["y"] - half_h - 3,
                                         c["x"] + half_w + 3, c["y"] + half_h + 3,
                                         outline="#007acc", width=2, dash=(4, 2), tags="selection")

    def add_component(self, typ):
        cat, defaults = COMPONENTS[typ]
        c_defaults = copy.deepcopy(defaults)

        if "pin" in c_defaults:
            free = self.get_next_available_gpios(1)
            if not free:
                messagebox.showerror("Error", "No hay pines GPIO disponibles.")
                return
            c_defaults["pin"] = free[0]
        elif "forward_pin" in c_defaults:
            free = self.get_next_available_gpios(2)
            if not free:
                messagebox.showerror("Error", "No hay suficientes pines GPIO libres para el Motor.")
                return
            c_defaults["forward_pin"], c_defaults["backward_pin"] = free[0], free[1]
        elif "trigger_pin" in c_defaults:
            free = self.get_next_available_gpios(2)
            if not free:
                messagebox.showerror("Error", "No hay suficientes pines GPIO libres para el Sensor.")
                return
            c_defaults["trigger_pin"], c_defaults["echo_pin"] = free[0], free[1]
        elif "pins" in c_defaults:
            needed = len(c_defaults["pins"])
            free = self.get_next_available_gpios(needed)
            if not free:
                messagebox.showerror("Error", f"No hay suficientes pines GPIO libres para la LCD ({needed} requeridos).")
                return
            c_defaults["pins"] = free

        i = self.next_id
        self.next_id += 1
        type_idx = self.get_next_type_index(typ)
        half_w, half_h = self.get_comp_bounds(typ)

        c = {
            "id": f"{typ.lower().replace(' ', '_')}_{type_idx}",
            "type": typ,
            "name": f"{typ} {type_idx}",
            "x": half_w,
            "y": half_h,
            "tag": f"component_{i}"
        }
        c.update(c_defaults)
        self.components.append(c)
        self.select(c)

    def find_at(self, x, y):
        for c in reversed(self.components):
            half_w, half_h = self.get_comp_bounds(c["type"])
            if abs(c["x"] - x) <= half_w and abs(c["y"] - y) <= half_h:
                return c
        return None

    def on_press(self, e):
        canvas_x = self.canvas.canvasx(e.x)
        canvas_y = self.canvas.canvasy(e.y)
        c = self.find_at(canvas_x, canvas_y)
        self.select(c)
        if c:
            self.drag_offset = (canvas_x - c["x"], canvas_y - c["y"])

    def on_drag(self, e):
        if not self.selected: return
        half_w, half_h = self.get_comp_bounds(self.selected["type"])
        canvas_x = self.canvas.canvasx(e.x)
        canvas_y = self.canvas.canvasy(e.y)
        
        target_x = round((canvas_x - self.drag_offset[0]) / 10) * 10
        target_y = round((canvas_y - self.drag_offset[1]) / 10) * 10

        self.selected["x"] = max(half_w, min(self.canvas_w - half_w, target_x))
        self.selected["y"] = max(half_h, min(self.canvas_h - half_h, target_y))
        
        self.redraw()
        self.update_status()

    def on_release(self, e):
        self.sync_entry_positions()

    def sync_entry_positions(self):
        if self.selected:
            if "x" in self.entries:
                self.entries["x"].delete(0, "end")
                self.entries["x"].insert(0, str(self.selected["x"]))
            if "y" in self.entries:
                self.entries["y"].delete(0, "end")
                self.entries["y"].insert(0, str(self.selected["y"]))

    def select(self, c):
        if c and self.pinout_selected:
            self.pinout_selected = False
            if hasattr(self, "lbl_pinout"):
                self.lbl_pinout.config(bd=1, relief="solid", highlightthickness=0)

        self.selected = c
        self.rebuild_property_fields()
        self.redraw()
        self.update_status()

    def on_nudge(self, dx, dy):
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, (tk.Entry, ttk.Entry, tk.Text)):
            return

        if self.selected:
            half_w, half_h = self.get_comp_bounds(self.selected["type"])
            new_x = self.selected["x"] + dx
            self.selected["x"] = max(half_w, min(self.canvas_w - half_w, new_x))
            
            new_y = self.selected["y"] + dy
            self.selected["y"] = max(half_h, min(self.canvas_h - half_h, new_y))

            self.redraw()
            self.sync_entry_positions()
            self.update_status()

    def on_key_delete(self, event):
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.delete_selected()

    def on_key_copy(self, event):
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.duplicate()

    def apply_properties(self):
        if not self.selected: return
        numeric = {"pin", "trigger_pin", "echo_pin", "forward_pin", "backward_pin",
                   "channel", "min_angle", "max_angle", "initial_angle", "frequency",
                   "min_distance", "max_distance", "detection_radius", "delay_duration",
                   "block_duration", "columns", "lines", "x", "y"}
        booleans = {"is_on"}
        gpio_fields = {"pin", "trigger_pin", "echo_pin", "forward_pin", "backward_pin"}

        temp_values = {}
        for k, e in self.entries.items():
            if k == "type" or k not in self.selected: continue
            raw_val = e.get().strip()

            if k in numeric:
                try: v = int(raw_val)
                except ValueError:
                    messagebox.showerror("Error", f"'{k}' debe ser un número entero.")
                    return
            elif k in booleans:
                v = raw_val.lower() in ("true", "1", "yes", "t", "si")
            elif k == "pins":
                try:
                    cleaned = raw_val.replace("[", "").replace("]", "")
                    v = [int(p.strip()) for p in cleaned.split(",") if p.strip()]
                except ValueError:
                    messagebox.showerror("Error", "'pins' debe ser una lista separada por comas.")
                    return
            else:
                v = raw_val

            temp_values[k] = v

        used_by_others = self.get_used_gpios(exclude_component=self.selected)
        assigned_in_this = []

        for k, v in temp_values.items():
            if k in gpio_fields:
                if v not in VALID_GPIOS:
                    messagebox.showerror("Error GPIO", f"El GPIO {v} no es válido. Opciones permitidas: {VALID_GPIOS}")
                    return
                if v in used_by_others or v in assigned_in_this:
                    messagebox.showerror("Conflicto GPIO", f"El GPIO {v} ya está siendo utilizado.")
                    return
                assigned_in_this.append(v)
            elif k == "pins":
                for p in v:
                    if p not in VALID_GPIOS:
                        messagebox.showerror("Error GPIO", f"El pin {p} de la LCD no es válido.")
                        return
                    if p in used_by_others or p in assigned_in_this:
                        messagebox.showerror("Conflicto GPIO", f"El pin {p} de la LCD ya está en uso.")
                        return
                    assigned_in_this.append(p)

        for k, v in temp_values.items():
            self.selected[k] = v

        self.redraw()
        self.update_status()

    def duplicate(self):
        if not self.selected: return
        c = copy.deepcopy(self.selected)
        
        if "pin" in c:
            free = self.get_next_available_gpios(1)
            if not free:
                messagebox.showerror("Error", "No hay pines GPIO disponibles.")
                return
            c["pin"] = free[0]
        elif "forward_pin" in c:
            free = self.get_next_available_gpios(2)
            if not free:
                messagebox.showerror("Error", "No hay suficientes pines GPIO disponibles.")
                return
            c["forward_pin"], c["backward_pin"] = free[0], free[1]
        elif "trigger_pin" in c:
            free = self.get_next_available_gpios(2)
            if not free:
                messagebox.showerror("Error", "No hay suficientes pines GPIO disponibles.")
                return
            c["trigger_pin"], c["echo_pin"] = free[0], free[1]
        elif "pins" in c:
            needed = len(c["pins"])
            free = self.get_next_available_gpios(needed)
            if not free:
                messagebox.showerror("Error", f"No hay suficientes pines GPIO libres ({needed} requeridos).")
                return
            c["pins"] = free

        i = self.next_id
        self.next_id += 1
        c["id"] = f"{c['type'].lower().replace(' ', '_')}_{i}"
        c["tag"] = f"component_{i}"
        c["name"] = c["name"] + " copy"
        
        half_w, half_h = self.get_comp_bounds(c["type"])
        c["x"] = min(self.canvas_w - half_w, c["x"] + 20)
        c["y"] = min(self.canvas_h - half_h, c["y"] + 20)
        
        self.components.append(c)
        self.select(c)

    def delete_selected(self):
        if self.selected:
            self.components.remove(self.selected)
            self.select(None)

    def clear(self):
        self.components = []
        self.select(None)

    def resize_canvas(self):
        try:
            self.canvas_w = int(self.wvar.get())
            self.canvas_h = int(self.hvar.get())
            self.canvas.config(width=self.canvas_w, height=self.canvas_h)
            self.draw_grid()
            self.auto_fit_window()  # Reajustar ventana principal
        except ValueError:
            messagebox.showerror("Error", "Las dimensiones deben ser enteros.")
    
    def new_project(self):
        if self.components and not messagebox.askyesno("Nuevo Proyecto", "¿Deseas crear un nuevo proyecto? Se limpiará el lienzo actual."):
            return
        self.clear()
        self.canvas_w, self.canvas_h = 800, 500
        self.wvar.set("800")
        self.hvar.set("500")
        self.canvas.config(width=self.canvas_w, height=self.canvas_h)
        self.draw_grid()
        self.auto_fit_window()

    def open_json(self):
        p = filedialog.askopenfilename(filetypes=[("Proyecto TkGPIO", "*.json")])
        if not p: return
        try:
            with open(p, encoding="utf-8") as f: d = json.load(f)
            self.canvas_w = d["canvas"]["width"]
            self.canvas_h = d["canvas"]["height"]
            self.wvar.set(str(self.canvas_w))
            self.hvar.set(str(self.canvas_h))
            self.canvas.config(width=self.canvas_w, height=self.canvas_h)
            
            self.components = []
            for c in d.get("components", []):
                c["tag"] = f"component_{self.next_id}"
                self.next_id += 1
                self.components.append(c)
            self.select(None)
            self.draw_grid()
            self.auto_fit_window()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def project_data(self):
        return {
            "version": 1,
            "canvas": {"width": self.canvas_w, "height": self.canvas_h},
            "components": [{k: v for k, v in c.items() if k != "tag"} for c in self.components]
        }

    def save_json(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Proyecto TkGPIO", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.project_data(), f, indent=4)
            self.status.config(text=f"Guardado: {p}")

    def configuration(self):
        cfg = {"width": self.canvas_w, "height": self.canvas_h}
        potentiometers = []

        for c in self.components:
            cat, _ = COMPONENTS[c["type"]]
            item = {k: v for k, v in c.items() if k not in ("id", "type", "tag")}
            
            if cat == "potentiometers":
                potentiometers.append(item)
            else:
                cfg.setdefault(cat, []).append(item)

        if potentiometers:
            cfg["adc"] = {
                "mcp_chip": 3008,
                "potentiometers": potentiometers
            }
        return cfg

    def format_configuration(self, cfg):
        lines = [
            "configuration = {",
            f"    'width': {cfg.get('width', 800)},",
            f"    'height': {cfg.get('height', 500)},"
        ]
        
        categories = [k for k in cfg.keys() if k not in ("width", "height")]
        for idx, cat in enumerate(categories):
            val = cfg[cat]
            if cat == "adc":
                lines.append("\n    'adc': {")
                lines.append(f"        'mcp_chip': {val['mcp_chip']},")
                lines.append("        'potentiometers': [")
                for p_idx, pot in enumerate(val["potentiometers"]):
                    lines.append("            {")
                    fields = [f"                '{k}': {repr(v)}" for k, v in pot.items()]
                    lines.append(",\n".join(fields))
                    lines.append("            }" + ("," if p_idx < len(val["potentiometers"]) - 1 else ""))
                lines.append("        ]")
                lines.append("    }" + ("," if idx < len(categories) - 1 else ""))
            else:
                lines.append(f"\n    '{cat}': [")
                for item_idx, item in enumerate(val):
                    lines.append("        {")
                    fields = [f"            '{k}': {repr(v)}" for k, v in item.items()]
                    lines.append(",\n".join(fields))
                    lines.append("        }" + ("," if item_idx < len(val) - 1 else ""))
                lines.append("    ]" + ("," if idx < len(categories) - 1 else ""))

        lines.append("}")
        return "\n".join(lines)

    def generate_main_template(self):
        """Construye el cuerpo de main() importando e inicializando los elementos."""
        type_mapping = {
            "LED": ("LED", "led"),
            "Button": ("Button", "btn"),
            "Toggle Switch": ("Button", "switch"),
            "Buzzer": ("Buzzer", "bzr"),
            "Motor": ("Motor", "motor"),
            "Servo": ("Servo", "servo"),
            "Distance Sensor": ("DistanceSensor", "sensor_dist"),
            "Light Sensor": ("LightSensor", "sensor_luz"),
            "Motion Sensor": ("MotionSensor", "sensor_mov"),
            "Potentiometer": ("MCP3008", "pot"),
        }

        needed_imports = set()
        instances = []
        type_counters = {}

        for c in self.components:
            typ = c["type"]
            if typ in type_mapping:
                cls_name, prefix = type_mapping[typ]
                needed_imports.add(cls_name)
                
                type_counters[typ] = type_counters.get(typ, 0) + 1
                var_name = f"{prefix}{type_counters[typ]}"

                if typ in ("LED", "Button", "Toggle Switch", "Buzzer", "Light Sensor", "Motion Sensor"):
                    pin = c.get("pin", 0)
                    instances.append(f"    {var_name} = {cls_name}({pin})")
                elif typ == "Motor":
                    fwd = c.get("forward_pin", 0)
                    bwd = c.get("backward_pin", 0)
                    instances.append(f"    {var_name} = Motor(forward={fwd}, backward={bwd})")
                elif typ == "Servo":
                    pin = c.get("pin", 0)
                    instances.append(f"    {var_name} = Servo({pin})")
                elif typ == "Distance Sensor":
                    trig = c.get("trigger_pin", 0)
                    echo = c.get("echo_pin", 0)
                    instances.append(f"    {var_name} = DistanceSensor(echo={echo}, trigger={trig})")
                elif typ == "Potentiometer":
                    ch = c.get("channel", 0)
                    instances.append(f"    {var_name} = MCP3008(channel={ch})")

        if not needed_imports:
            imports_line = "    # No hay componentes con pines GPIO directos"
        else:
            ordered_imports = sorted(list(needed_imports))
            imports_line = f"    from gpiozero import {', '.join(ordered_imports)}"

        instances_str = "\n".join(instances) if instances else "    pass"

        return f"""@circuit.run
def main():
    # Escribe aquí el código del alumno.
{imports_line}
    from time import sleep

{instances_str}

    while True:
        sleep(0.1)"""

    def generated_code(self):
        cfg_str = self.format_configuration(self.configuration())
        main_str = self.generate_main_template()
        return f"""from tkgpio import TkCircuit

{cfg_str}

circuit = TkCircuit(configuration)

{main_str}

if __name__ == "__main__":
    main()
"""

    def export_python(self):
        p = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python", "*.py")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.generated_code())
            self.status.config(text=f"Exportado: {p}")

    def simulate(self):
        p = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python", "*.py")], title="Guardar simulación")
        if not p: return
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.generated_code())
        try:
            subprocess.Popen([sys.executable, p])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_status(self):
        pins = []
        for c in self.components:
            for k in ("pin", "trigger_pin", "echo_pin", "forward_pin", "backward_pin"):
                if isinstance(c.get(k), int):
                    pins.append(c[k])
            if isinstance(c.get("pins"), list):
                pins.extend(c["pins"])
        self.status.config(text=f"Componentes: {len(self.components)} | GPIOs: {sorted(set(pins))} | Canvas: {self.canvas_w}×{self.canvas_h}")

if __name__ == "__main__":
    root = tk.Tk()
    Designer(root)
    root.mainloop()
