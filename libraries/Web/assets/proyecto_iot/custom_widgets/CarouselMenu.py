import os
import json
import base64
import mimetypes
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class CarouselMenu:

    default_props = {
        "label": "Menú Carrusel",
        "width": 520,
        "height": 280,
        "background": "#1e293b",
        "show_card_bg": "True",
        "card_bg": "#334155",
        "card_hover": "#475569",
        "accent_color": "#38bdf8",
        "text_color": "#ffffff",
        "indicator_style": "Dots",
        "items": json.dumps([
            {"title": "Sensor Temp", "subtitle": "DHT22 Activo", "value": "24.5°C", "image": ""},
            {"title": "Motor Paso", "subtitle": "Velocidad Media", "value": "1200 RPM", "image": ""},
            {"title": "Relay 1", "subtitle": "Control Bomba", "value": "ON", "image": ""}
        ])
    }

    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "background", "label": "Color de fondo:", "type": "color"},
        {"name": "show_card_bg", "label": "Mostrar fondo de tarjeta:", "type": "boolean"},
        {"name": "card_bg", "label": "Color de tarjeta:", "type": "color"},
        {"name": "card_hover", "label": "Color Hover tarjeta:", "type": "color"},
        {"name": "accent_color", "label": "Color de acento:", "type": "color"},
        {"name": "text_color", "label": "Color de texto:", "type": "color"},
        {
            "name": "indicator_style",
            "label": "Estilo de indicadores:",
            "type": "select",
            "options": ["Dots", "Lines"]
        },
        {
            "name": "items",
            "label": "Elementos del Carrusel (Matrix):",
            "btn_text": "Configurar Tarjetas",
            "type": "custom",
            "fname": "open_carousel_editor"
        }
    ]

    supported_events = ["on_item_click", "on_slide_change"]

    def __init__(self, width=520, height=280):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()

    def _get_image_src(self, path):
        if not path:
            return ""
        path = str(path)
        if path.startswith(("http://", "https://", "data:", "/")):
            return path
        if not os.path.isfile(path):
            return ""
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "image/png"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    def to_dict(self):
        return {
            "id": getattr(self, 'id', "w_0"),
            "type": getattr(self, 'type', self.__class__.__name__),
            "x": getattr(self, 'x', 50),
            "y": getattr(self, 'y', 50),
            "width": getattr(self, 'width', getattr(self, 'default_props', {}).get('width', 520)),
            "height": getattr(self, 'height', getattr(self, 'default_props', {}).get('height', 280)),
            "props": getattr(self, 'props', {}),
            "events": getattr(self, 'events', {})
        }

    def render_canvas(self, canvas, x, y):
        p = getattr(self, 'props', self.default_props)
        lbl = p.get("label", "Menú Carrusel")
        return [
            canvas.create_rectangle(
                x, y,
                x + self.width,
                y + self.height,
                fill="#234764",
                outline="#334155",
                width=2
            ),
            canvas.create_text(
                x + self.width / 2,
                y + 16,
                text=lbl,
                fill="#ffffff",
                font=("Segoe UI", 11, "bold")
            )
        ]

    def open_carousel_editor(self, app_builder=None):
        t = getattr(app_builder, "theme", {
            "bg": "#0f172a",
            "panel": "#1e293b",
            "card": "#334155",
            "fg": "white",
            "accent": "#38bdf8",
            "border": "#334155"
        })

        editor = tk.Toplevel()
        editor.title("Editor de Menú Carrusel (WildCards)")
        editor.geometry("720x540")
        editor.config(bg=t.get("bg", "#0f172a"))
        editor.transient()
        editor.grab_set()

        raw_items = self.props.get("items", self.default_props["items"])
        if isinstance(raw_items, str):
            try:
                items = json.loads(raw_items)
            except Exception:
                items = []
        else:
            items = list(raw_items)

        main_frame = tk.Frame(editor, bg=t.get("bg", "#0f172a"))
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        left_frame = tk.Frame(main_frame, bg=t.get("panel", "#1e293b"), bd=1, relief=tk.SOLID)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10), ipadx=10)

        tk.Label(left_frame, text="Tarjetas (Wildcards)", bg=t.get("panel", "#1e293b"), fg=t.get("fg", "white"), font=("Segoe UI", 10, "bold")).pack(pady=8)

        listbox_frame = tk.Frame(left_frame, bg=t.get("panel", "#1e293b"))
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        item_listbox = tk.Listbox(
            listbox_frame,
            bg=t.get("card", "#334155"),
            fg=t.get("fg", "white"),
            font=("Segoe UI", 10),
            selectbackground=t.get("accent", "#38bdf8"),
            selectforeground="#0f172a",
            yscrollcommand=scrollbar.set,
            bd=0,
            highlightthickness=0,
            width=22
        )
        item_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=item_listbox.yview)

        def refresh_listbox(select_idx=None):
            item_listbox.delete(0, tk.END)
            for idx, it in enumerate(items):
                t_str = it.get("title", f"Tarjeta {idx+1}")
                item_listbox.insert(tk.END, f"{idx + 1}. {t_str}")
            if select_idx is not None and 0 <= select_idx < len(items):
                item_listbox.selection_set(select_idx)
                item_listbox.see(select_idx)

        right_frame = tk.Frame(main_frame, bg=t.get("panel", "#1e293b"), bd=1, relief=tk.SOLID)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right_frame, text="Propiedades de la Tarjeta", bg=t.get("panel", "#1e293b"), fg=t.get("fg", "white"), font=("Segoe UI", 10, "bold")).pack(pady=8)

        form_container = tk.Frame(right_frame, bg=t.get("panel", "#1e293b"))
        form_container.pack(fill=tk.X, padx=15, pady=5)

        title_var = tk.StringVar()
        subtitle_var = tk.StringVar()
        value_var = tk.StringVar()
        img_var = tk.StringVar()

        current_selected_idx = [None]

        def update_preview(*args):
            prev_title.config(text=title_var.get() or "Título")
            prev_subtitle.config(text=subtitle_var.get() or "Subtítulo")
            prev_value.config(text=value_var.get() or "0.0")

            path = img_var.get().strip()
            if path and os.path.isfile(path) and HAS_PIL:
                try:
                    pil_img = Image.open(path)
                    pil_img.thumbnail((45, 45))
                    editor._preview_img = ImageTk.PhotoImage(pil_img)
                    prev_img_lbl.config(image=editor._preview_img, text="")
                except Exception:
                    editor._preview_img = None
                    prev_img_lbl.config(image="", text="[ Error de imagen ]")
            else:
                editor._preview_img = None
                prev_img_lbl.config(image="", text="[ Imagen / Ícono ]")

            idx = current_selected_idx[0]
            if idx is not None and 0 <= idx < len(items):
                items[idx] = {
                    "title": title_var.get(),
                    "subtitle": subtitle_var.get(),
                    "value": value_var.get(),
                    "image": img_var.get()
                }
                curr_sel = item_listbox.curselection()
                t_str = title_var.get() or f"Tarjeta {idx+1}"
                item_listbox.delete(idx)
                item_listbox.insert(idx, f"{idx + 1}. {t_str}")
                if curr_sel:
                    item_listbox.selection_set(idx)

        title_var.trace_add("write", update_preview)
        subtitle_var.trace_add("write", update_preview)
        value_var.trace_add("write", update_preview)
        img_var.trace_add("write", update_preview)

        tk.Label(form_container, text="Título:", bg=t.get("panel", "#1e293b"), fg="#94a3b8", anchor="w").pack(fill=tk.X)
        tk.Entry(form_container, textvariable=title_var, bg=t.get("card", "#334155"), fg=t.get("fg", "white"), insertbackground="white", font=("Segoe UI", 10), bd=0).pack(fill=tk.X, pady=(0, 5), ipady=3)

        tk.Label(form_container, text="Subtítulo:", bg=t.get("panel", "#1e293b"), fg="#94a3b8", anchor="w").pack(fill=tk.X)
        tk.Entry(form_container, textvariable=subtitle_var, bg=t.get("card", "#334155"), fg=t.get("fg", "white"), insertbackground="white", font=("Segoe UI", 10), bd=0).pack(fill=tk.X, pady=(0, 5), ipady=3)

        tk.Label(form_container, text="Medición / Valor:", bg=t.get("panel", "#1e293b"), fg="#94a3b8", anchor="w").pack(fill=tk.X)
        tk.Entry(form_container, textvariable=value_var, bg=t.get("card", "#334155"), fg=t.get("fg", "white"), insertbackground="white", font=("Segoe UI", 10), bd=0).pack(fill=tk.X, pady=(0, 5), ipady=3)

        tk.Label(form_container, text="Imagen / Ícono (Ruta):", bg=t.get("panel", "#1e293b"), fg="#94a3b8", anchor="w").pack(fill=tk.X)
        img_frame = tk.Frame(form_container, bg=t.get("panel", "#1e293b"))
        img_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Entry(img_frame, textvariable=img_var, bg=t.get("card", "#334155"), fg=t.get("fg", "white"), insertbackground="white", font=("Segoe UI", 9), bd=0).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

        def browse_image():
            file_path = filedialog.askopenfilename(title="Seleccionar Imagen", filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.svg *.webp"), ("Todos", "*.*")])
            if file_path:
                img_var.set(file_path)

        tk.Button(img_frame, text="📁", command=browse_image, bg=t.get("accent", "#38bdf8"), fg="#0f172a", font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2").pack(side=tk.RIGHT, padx=(5, 0))

        preview_outer = tk.Frame(right_frame, bg=t.get("panel", "#1e293b"))
        preview_outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 8))

        tk.Label(preview_outer, text="Vista Previa de Tarjeta:", bg=t.get("panel", "#1e293b"), fg="#94a3b8", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 2))

        card_preview = tk.Frame(preview_outer, bg=t.get("card", "#334155"), bd=1, relief=tk.SOLID, highlightbackground="#475569")
        card_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        prev_title = tk.Label(card_preview, text="", bg=t.get("card", "#334155"), fg=t.get("fg", "white"), font=("Segoe UI", 11, "bold"))
        prev_title.pack(pady=(6, 0))

        prev_subtitle = tk.Label(card_preview, text="", bg=t.get("card", "#334155"), fg="#94a3b8", font=("Segoe UI", 9))
        prev_subtitle.pack()

        prev_img_lbl = tk.Label(card_preview, text="[ Imagen / Ícono ]", bg=t.get("card", "#334155"), fg="#64748b", font=("Segoe UI", 8, "italic"))
        prev_img_lbl.pack(expand=True)

        prev_value = tk.Label(card_preview, text="", bg=t.get("card", "#334155"), fg=t.get("accent", "#38bdf8"), font=("Segoe UI", 13, "bold"))
        prev_value.pack(pady=(0, 6))

        def load_item_to_form(idx):
            if idx < 0 or idx >= len(items):
                return
            current_selected_idx[0] = idx
            it = items[idx]
            title_var.set(it.get("title", ""))
            subtitle_var.set(it.get("subtitle", ""))
            value_var.set(it.get("value", ""))
            img_var.set(it.get("image", ""))
            update_preview()

        def on_list_select(event):
            selection = item_listbox.curselection()
            if selection:
                load_item_to_form(selection[0])

        item_listbox.bind("<<ListboxSelect>>", on_list_select)

        btn_control_frame = tk.Frame(left_frame, bg=t.get("panel", "#1e293b"))
        btn_control_frame.pack(fill=tk.X, padx=10, pady=10)

        def add_item():
            new_it = {"title": "Nuevo Sensor", "subtitle": "Estado OK", "value": "0.0", "image": ""}
            items.append(new_it)
            refresh_listbox(len(items) - 1)
            load_item_to_form(len(items) - 1)

        def delete_item():
            idx = current_selected_idx[0]
            if idx is not None and 0 <= idx < len(items):
                items.pop(idx)
                new_idx = max(0, idx - 1)
                refresh_listbox(new_idx if items else None)
                if items:
                    load_item_to_form(new_idx)
                else:
                    current_selected_idx[0] = None
                    title_var.set("")
                    subtitle_var.set("")
                    value_var.set("")
                    img_var.set("")

        def move_up():
            idx = current_selected_idx[0]
            if idx is not None and idx > 0:
                items[idx], items[idx - 1] = items[idx - 1], items[idx]
                refresh_listbox(idx - 1)
                load_item_to_form(idx - 1)

        def move_down():
            idx = current_selected_idx[0]
            if idx is not None and idx < len(items) - 1:
                items[idx], items[idx + 1] = items[idx + 1], items[idx]
                refresh_listbox(idx + 1)
                load_item_to_form(idx + 1)

        tk.Button(btn_control_frame, text="+ Añadir", command=add_item, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2").grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        tk.Button(btn_control_frame, text="- Eliminar", command=delete_item, bg="#dc2626", fg="white", font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2").grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        tk.Button(btn_control_frame, text="▲ Subir", command=move_up, bg="#475569", fg="white", font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2").grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        tk.Button(btn_control_frame, text="▼ Bajar", command=move_down, bg="#475569", fg="white", font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2").grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        btn_control_frame.columnconfigure(0, weight=1)
        btn_control_frame.columnconfigure(1, weight=1)

        def apply_changes():
            update_preview()
            self.props["items"] = json.dumps(items)
            if app_builder and hasattr(app_builder, "refresh_canvas"):
                app_builder.refresh_canvas()
            editor.destroy()

        tk.Button(
            right_frame,
            text="Guardar Cambios",
            command=apply_changes,
            bg="#16a34a",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            cursor="hand2"
        ).pack(fill=tk.X, padx=15, pady=(0, 10), ipady=4)

        if items:
            refresh_listbox(0)
            load_item_to_form(0)

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}

        items_data = p.get("items", [])
        if isinstance(items_data, str):
            try:
                items_data = json.loads(items_data)
            except Exception:
                items_data = []

        processed_items = []
        for item in items_data:
            it_copy = item.copy()
            it_copy["image_src"] = self._get_image_src(item.get("image", ""))
            processed_items.append(it_copy)

        show_bg = str(p.get("show_card_bg", "True")).strip().lower() not in ("false", "0", "no", "off")

        cfg = {
            "id": w_id,
            "items": processed_items,
            "indicator_style": p.get("indicator_style", "Dots"),
            "show_card_bg": show_bg
        }

        config_json = json.dumps(cfg)

        return f"""
<div id="carousel_{w_id}" class="carousel-wrapper">
    <button class="carousel-nav-btn prev-btn" title="Anterior">‹</button>
    
    <div class="carousel-viewport">
        <div class="carousel-track">
            <!-- Tarjetas generadas dinámicamente -->
        </div>
    </div>

    <button class="carousel-nav-btn next-btn" title="Siguiente">›</button>
    
    <div class="carousel-indicators"></div>
</div>

<style>
#carousel_{w_id} {{
    width: 100%;
    height: 100%;
    background: {p["background"]};
    border-radius: 12px;
    display: flex;
    align-items: center;
    position: relative;
    overflow: hidden;
    box-sizing: border-box;
    padding: 10px 48px 28px 48px;
    user-select: none;
}}

#carousel_{w_id} .carousel-nav-btn {{
    position: absolute;
    top: 44%;
    transform: translateY(-50%);
    background: rgba(15, 23, 42, 0.85);
    color: {p["accent_color"]};
    border: 1px solid {p["accent_color"]};
    width: 36px;
    height: 36px;
    border-radius: 50%;
    font-size: 22px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 10;
    transition: all 0.2s ease;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4);
}}

#carousel_{w_id} .carousel-nav-btn:hover {{
    background: {p["accent_color"]};
    color: #0f172a;
    transform: translateY(-50%) scale(1.08);
}}

#carousel_{w_id} .prev-btn {{ left: 8px; }}
#carousel_{w_id} .next-btn {{ right: 8px; }}

#carousel_{w_id} .carousel-viewport {{
    width: 100%;
    height: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    display: flex;
    align-items: center;
    scroll-behavior: auto;
}}

#carousel_{w_id} .carousel-viewport::-webkit-scrollbar {{
    display: none;
}}

#carousel_{w_id} .carousel-track {{
    display: flex;
    gap: 16px;
    cursor: grab;
    align-items: center;
    width: max-content;
}}

#carousel_{w_id} .carousel-track:active {{
    cursor: grabbing;
}}

#carousel_{w_id} .carousel-card {{
    background: {p["card_bg"] if show_bg else "transparent"};
    border: { "1px solid rgba(255, 255, 255, 0.12)" if show_bg else "none" };
    border-radius: 16px;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    box-sizing: border-box;
    box-shadow: { "0 10px 22px rgba(0,0,0,0.4)" if show_bg else "none" };
    transition: background 0.2s ease, transform 0.1s ease;
    flex-shrink: 0;
    cursor: pointer;
    text-align: center;
}}

#carousel_{w_id} .carousel-card:hover {{
    background: {p["card_hover"] if show_bg else "rgba(255,255,255,0.05)"};
}}

#carousel_{w_id} .carousel-card:active {{
    transform: scale(0.98);
}}

#carousel_{w_id} .card-header {{
    width: 100%;
}}

#carousel_{w_id} .card-title {{
    color: {p["text_color"]};
    font-size: 17px;
    font-weight: bold;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

#carousel_{w_id} .card-subtitle {{
    color: #94a3b8;
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 2px;
}}

#carousel_{w_id} .card-image-container {{
    flex-grow: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 8px 0;
}}

#carousel_{w_id} .card-img {{
    max-width: 60px;
    max-height: 60px;
    width: auto;
    height: auto;
    object-fit: contain;
}}

#carousel_{w_id} .card-footer {{
    width: 100%;
}}

#carousel_{w_id} .card-value {{
    color: {p["accent_color"]};
    font-size: 24px;
    font-weight: bold;
}}

#carousel_{w_id} .carousel-indicators {{
    position: absolute;
    bottom: 6px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 8px;
    z-index: 10;
}}

#carousel_{w_id} .indicator-item {{
    cursor: pointer;
    transition: all 0.3s ease;
    background: rgba(255, 255, 255, 0.3);
}}

#carousel_{w_id} .indicator-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}
#carousel_{w_id} .indicator-dot.active {{
    background: {p["accent_color"]};
    width: 22px;
    border-radius: 4px;
}}

#carousel_{w_id} .indicator-line {{
    width: 16px;
    height: 4px;
    border-radius: 2px;
}}
#carousel_{w_id} .indicator-line.active {{
    background: {p["accent_color"]};
    width: 34px;
}}
</style>

<script>
(function() {{
    const cfg = {config_json};
    const root = document.getElementById("carousel_" + cfg.id);
    const track = root.querySelector(".carousel-track");
    const viewport = root.querySelector(".carousel-viewport");
    const prevBtn = root.querySelector(".prev-btn");
    const nextBtn = root.querySelector(".next-btn");
    const indicatorsContainer = root.querySelector(".carousel-indicators");

    let currentIndex = 0;
    let cards = [];
    let isAnimating = false;

    function applyProportionalSizes() {{
        if (cards.length === 0) return;
        const targetWidth = root.clientWidth * 0.33;
        const targetHeight = root.clientHeight * 0.90;

        cards.forEach(card => {{
            card.style.width = targetWidth + "px";
            card.style.height = targetHeight + "px";
        }});

        const viewportWidth = viewport.clientWidth;
        const padding = Math.max(0, (viewportWidth - targetWidth) / 2);
        track.style.paddingLeft = padding + "px";
        track.style.paddingRight = padding + "px";
    }}

    function renderItems() {{
        track.innerHTML = "";
        indicatorsContainer.innerHTML = "";
        if (!cfg.items || !Array.isArray(cfg.items)) return;

        cfg.items.forEach((item, index) => {{
            const card = document.createElement("div");
            card.className = "carousel-card";
            
            const imgHtml = item.image_src ? `<div class="card-image-container"><img class="card-img" src="${{item.image_src}}"></div>` : `<div class="card-image-container"></div>`;

            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title">${{item.title || "Opción " + (index + 1)}}</div>
                    <div class="card-subtitle">${{item.subtitle || ""}}</div>
                </div>
                ${{imgHtml}}
                <div class="card-footer">
                    <div class="card-value">${{item.value || ""}}</div>
                </div>
            `;

            // MODIFICACIÓN: Payload con índice y datos textuales (sin imagen ni source)
            card.addEventListener("click", (e) => {{
                e.stopPropagation();
                if (typeof emitEvent === "function") {{
                    emitEvent(
                        {{ id: cfg.id, events: {{ on_item_click: true }} }},
                        "on_item_click",
                        {{
                            index: index,
                            title: item.title || "",
                            subtitle: item.subtitle || "",
                            value: item.value || ""
                        }}
                    );
                }}
            }});

            track.appendChild(card);

            const indicator = document.createElement("div");
            const isLine = cfg.indicator_style === "Lines";
            indicator.className = `indicator-item ${{isLine ? 'indicator-line' : 'indicator-dot'}} ${{index === 0 ? 'active' : ''}}`;
            
            indicator.addEventListener("click", () => {{
                scrollToIndex(index);
            }});
            indicatorsContainer.appendChild(indicator);
        }});

        cards = Array.from(track.querySelectorAll(".carousel-card"));
        requestAnimationFrame(() => {{
            applyProportionalSizes();
            scrollToIndex(currentIndex, false);
        }});
    }}

    function updateActiveIndicator(index) {{
        currentIndex = index;
        const indicators = indicatorsContainer.children;
        for (let i = 0; i < indicators.length; i++) {{
            if (i === index) {{
                indicators[i].classList.add("active");
            }} else {{
                indicators[i].classList.remove("active");
            }}
        }}
    }}

    function smoothScrollTo(targetScrollLeft, duration = 350) {{
        const startScrollLeft = viewport.scrollLeft;
        const distance = targetScrollLeft - startScrollLeft;
        let startTime = null;

        function animation(currentTime) {{
            if (!startTime) startTime = currentTime;
            const timeElapsed = currentTime - startTime;
            const progress = Math.min(timeElapsed / duration, 1);
            
            const ease = 1 - Math.pow(1 - progress, 3);
            viewport.scrollLeft = startScrollLeft + (distance * ease);

            if (progress < 1) {{
                requestAnimationFrame(animation);
            }} else {{
                isAnimating = false;
            }}
        }}

        isAnimating = true;
        requestAnimationFrame(animation);
    }}

    function scrollToIndex(index, animate = true) {{
        if (cards.length === 0) return;
        index = Math.max(0, Math.min(index, cards.length - 1));
        const targetCard = cards[index];
        const scrollLeftPos = targetCard.offsetLeft - (viewport.clientWidth - targetCard.clientWidth) / 2;
        
        if (animate) {{
            smoothScrollTo(scrollLeftPos, 400);
        }} else {{
            viewport.scrollLeft = scrollLeftPos;
        }}
        updateActiveIndicator(index);
    }}

    renderItems();

    window.addEventListener("resize", () => {{
        applyProportionalSizes();
        scrollToIndex(currentIndex, false);
    }});

    prevBtn.addEventListener("click", () => {{
        scrollToIndex(currentIndex - 1);
    }});

    nextBtn.addEventListener("click", () => {{
        scrollToIndex(currentIndex + 1);
    }});

    let scrollTimeout;
    viewport.addEventListener("scroll", () => {{
        if (isAnimating) return;
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {{
            if (cards.length === 0) return;
            const viewportCenter = viewport.scrollLeft + viewport.clientWidth / 2;
            let closestIndex = 0;
            let minDistance = Infinity;

            cards.forEach((card, idx) => {{
                const cardCenter = card.offsetLeft + card.clientWidth / 2;
                const distance = Math.abs(viewportCenter - cardCenter);
                if (distance < minDistance) {{
                    minDistance = distance;
                    closestIndex = idx;
                }}
            }});

            if (closestIndex !== currentIndex) {{
                updateActiveIndicator(closestIndex);
            }}
        }}, 60);
    }});

    let isDown = false;
    let startX;
    let scrollLeft;

    track.addEventListener("mousedown", (e) => {{
        isDown = true;
        track.classList.add("active");
        startX = e.pageX - track.offsetLeft;
        scrollLeft = viewport.scrollLeft;
    }});

    track.addEventListener("mouseleave", () => {{
        if (!isDown) return;
        isDown = false;
        track.classList.remove("active");
        snapToNearestCard();
    }});

    track.addEventListener("mouseup", () => {{
        isDown = false;
        track.classList.remove("active");
        snapToNearestCard();
    }});

    track.addEventListener("mousemove", (e) => {{
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX);
        viewport.scrollLeft = scrollLeft - walk;
    }});

    function snapToNearestCard() {{
        if (cards.length === 0) return;
        const viewportCenter = viewport.scrollLeft + viewport.clientWidth / 2;
        let closestIndex = 0;
        let minDistance = Infinity;

        cards.forEach((card, idx) => {{
            const cardCenter = card.offsetLeft + card.clientWidth / 2;
            const distance = Math.abs(viewportCenter - cardCenter);
            if (distance < minDistance) {{
                minDistance = distance;
                closestIndex = idx;
            }}
        }});
        scrollToIndex(closestIndex);
    }}

    window.__widgets = window.__widgets || {{}};
    window.__widgets[cfg.id] = {{
        update: function(v) {{
            if (!v || typeof v !== "object") return;
            if (v.items && Array.isArray(v.items)) {{
                cfg.items = v.items;
                renderItems();
            }}
            if (v.indicator_style) {{
                cfg.indicator_style = v.indicator_style;
                renderItems();
            }}
        }}
    }};

}})();
</script>
"""