import os
import json
import base64
import mimetypes


class WildCard:

    default_props = {
        "label": "Tarjeta de Lectura",
        "label_color": "#FFFFFF",
        "label_font_size": 22,
        "width": 300,
        "height": 150,
        "background": "#234764",
        "border_radius": 16,
        "image": "",
        "image_width": 65,
        "image_height": 90,
        "value": "22.8",
        "value_color": "#FFFFFF",
        "value_font_size": 38,
        "units": "°C",
        "units_color": "#FFFFFF",
        "units_font_size": 24,
        "label_horizontal": "Center",
        "label_vertical": "Top",
        "image_horizontal": "Left",
        "image_vertical": "Center",
        "value_horizontal": "Center",
        "value_vertical": "Center",
        "units_horizontal": "Right",
        "units_vertical": "Bottom",
    }

    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "label_color", "label": "Color del título:", "type": "color"},
        {"name": "label_font_size", "label": "Tamaño de fuente del título:", "type": "text"},
        {"name": "background", "label": "Color de fondo:", "type": "color"},
        {
            "name": "border_radius",
            "label": "Radio de esquinas (px):",
            "type": "text",
        },
        {
            "name": "image",
            "label": "Imagen / Ícono:",
            "type": "file",
            "file_types": [
                ("Imágenes", "*.png *.jpg *.jpeg *.svg *.webp *.gif"),
                ("Todos los archivos", "*.*"),
            ],
        },
        {"name": "image_width", "label": "Ancho de imagen (px):", "type": "text"},
        {"name": "image_height", "label": "Alto de imagen (px):", "type": "text"},
        {"name": "value", "label": "Valor inicial:", "type": "text"},
        {"name": "value_color", "label": "Color del valor:", "type": "color"},
        {
            "name": "value_font_size",
            "label": "Tamaño de fuente del valor:",
            "type": "text",
        },
        {"name": "units", "label": "Unidades:", "type": "text"},
        {"name": "units_color", "label": "Color de unidades:", "type": "color"},
        {
            "name": "units_font_size",
            "label": "Tamaño de fuente de unidades:",
            "type": "text",
        },
        # Alineamiento de título
        {
            "name": "label_horizontal",
            "label": "Título - Horizontal:",
            "type": "select",
            "options": ["Left", "Center", "Right"],
        },
        {
            "name": "label_vertical",
            "label": "Título - Vertical:",
            "type": "select",
            "options": ["Top", "Center", "Bottom"],
        },
        # Alineamiento de imagen
        {
            "name": "image_horizontal",
            "label": "Imagen - Horizontal:",
            "type": "select",
            "options": ["Left", "Center", "Right"],
        },
        {
            "name": "image_vertical",
            "label": "Imagen - Vertical:",
            "type": "select",
            "options": ["Top", "Center", "Bottom"],
        },
        # Alineamiento de valor
        {
            "name": "value_horizontal",
            "label": "Valor - Horizontal:",
            "type": "select",
            "options": ["Left", "Center", "Right"],
        },
        {
            "name": "value_vertical",
            "label": "Valor - Vertical:",
            "type": "select",
            "options": ["Top", "Center", "Bottom"],
        },
        # Alineamiento de unidades
        {
            "name": "units_horizontal",
            "label": "Unidades - Horizontal:",
            "type": "select",
            "options": ["Left", "Center", "Right"],
        },
        {
            "name": "units_vertical",
            "label": "Unidades - Vertical:",
            "type": "select",
            "options": ["Top", "Center", "Bottom"],
        },
    ]

    supported_events = []

    def __init__(self, width=300, height=150):
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
            print(f"WildCard: imagen no encontrada: {path}")
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
            "width": getattr(self, 'width', getattr(self, 'default_props', {}).get('width', 300)),
            "height": getattr(self, 'height', getattr(self, 'default_props', {}).get('height', 150)),
            "props": getattr(self, 'props', {}),
            "events": getattr(self, 'events', {})
        }
        
    def render_canvas(self, canvas, x, y):
        p = getattr(self, 'props', self.default_props)
        lbl = p.get("label", "WildCard")
        return [
            canvas.create_rectangle(
                x, y,
                x + self.width,
                y + self.height,
                fill="#234764",
                outline="#18354d",
                width=2
            ),
            canvas.create_text(
                x + self.width / 2,
                y + self.height / 2,
                text=lbl,
                fill="white",
                font=("Arial", 12, "bold")
            )
        ]

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}

        cfg = {
            "id": w_id,
            "label": p["label"],
            "image": self._get_image_src(p["image"]),
            "value": p["value"],
            "units": p["units"]
        }

        config = json.dumps(cfg)

        def justify(value):
            return {
                "Left": "flex-start",
                "Center": "center",
                "Right": "flex-end"
            }.get(value, "center")

        def align(value):
            return {
                "Top": "flex-start",
                "Center": "center",
                "Bottom": "flex-end"
            }.get(value, "center")

        def layer_style(horizontal, vertical):
            return (
                f"display:flex;"
                f"justify-content:{justify(horizontal)};"
                f"align-items:{align(vertical)};"
            )

        label_style = layer_style(
            p.get("label_horizontal", "Center"), p.get("label_vertical", "Top")
        )
        image_style = layer_style(
            p["image_horizontal"], p["image_vertical"]
        )
        value_style = layer_style(
            p["value_horizontal"], p["value_vertical"]
        )
        units_style = layer_style(
            p["units_horizontal"], p["units_vertical"]
        )

        return f"""
<div id="wildcard_{w_id}" class="wildcard">

    <div class="wc-layer wc-label" style="{label_style}">
        <span class="wc-label-content"></span>
    </div>

    <div class="wc-layer wc-image" style="{image_style}">
        <img class="wc-image-content">
    </div>

    <div class="wc-layer wc-value" style="{value_style}">
        <span class="wc-value-content"></span>
    </div>

    <div class="wc-layer wc-units" style="{units_style}">
        <span class="wc-units-content"></span>
    </div>

</div>

<style>
#wildcard_{w_id} {{
    width:100%;
    height:100%;
    position:relative;
    overflow:hidden;
    box-sizing:border-box;
    background:{p["background"]};
    border-radius:{p["border_radius"]}px;
}}

#wildcard_{w_id} .wc-layer {{
    position:absolute;
    inset:0;
    padding:14px;
    box-sizing:border-box;
    pointer-events:none;
}}

/* Capa exclusiva del título anclada estrictamente arriba */
#wildcard_{w_id} .wc-label {{
    padding: 8px 14px; 
}}

#wildcard_{w_id} .wc-label-content {{
    color:{p.get("label_color", "#FFFFFF")};
    font-size:{p.get("label_font_size", 22)}px;
    font-weight:bold;
    white-space:nowrap;
}}

#wildcard_{w_id} .wc-image-content {{
    max-width:{p["image_width"]}px;
    max-height:{p["image_height"]}px;
    width:auto;
    height:auto;
    object-fit:contain;
}}

#wildcard_{w_id} .wc-value-content {{
    color:{p["value_color"]};
    font-size:{p["value_font_size"]}px;
    font-weight:bold;
    white-space:nowrap;
}}

#wildcard_{w_id} .wc-units-content {{
    color:{p["units_color"]};
    font-size:{p["units_font_size"]}px;
    font-weight:500;
    white-space:nowrap;
}}
</style>

<script>
(function() {{

    const cfg = {config};

    const root = document.getElementById("wildcard_" + cfg.id);

    const label = root.querySelector(".wc-label-content");
    const image = root.querySelector(".wc-image-content");
    const value = root.querySelector(".wc-value-content");
    const units = root.querySelector(".wc-units-content");

    function setLabel(l) {{
        label.textContent = l ?? "";
    }}

    function setImage(src) {{
        image.src = src || "";
        image.style.display = src ? "block" : "none";
    }}

    function setValue(v) {{
        value.textContent = v ?? "";
    }}

    function setUnits(u) {{
        units.textContent = u ?? "";
    }}

    setLabel(cfg.label);
    setImage(cfg.image);
    setValue(cfg.value);
    setUnits(cfg.units);

    window.__widgets = window.__widgets || {{}};

    window.__widgets[cfg.id] = {{
        update: function(v) {{

            if (!v || typeof v !== "object") return;

            if (Object.prototype.hasOwnProperty.call(v, "label")) {{
                cfg.label = v.label;
                setLabel(v.label);
            }}

            if (Object.prototype.hasOwnProperty.call(v, "image")) {{
                cfg.image = v.image;
                setImage(v.image);
            }}

            if (Object.prototype.hasOwnProperty.call(v, "value")) {{
                cfg.value = v.value;
                setValue(v.value);
            }}

            if (Object.prototype.hasOwnProperty.call(v, "units")) {{
                cfg.units = v.units;
                setUnits(v.units);
            }}
        }}
    }};

}})();
</script>
"""