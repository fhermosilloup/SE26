
import json
import os
import json
import base64
import mimetypes


class ImageButton:
    default_props = {
        "label": "Boton Imagen",
        "img_release": "",
        "img_pressed": "",
        "img_hover": "",
        "image_fit": "contain",
    }

    custom_properties = [
        {"name": "label", "label": "Etiqueta:", "type": "text"},
        {
            "name": "img_release",
            "label": "Imagen en reposo:",
            "type": "file",
            "file_types": [
                ("Imágenes", "*.png *.jpg *.jpeg *.gif *.webp *.svg"),
                ("Todos los archivos", "*.*"),
            ],
        },
        {
            "name": "img_pressed",
            "label": "Imagen presionada:",
            "type": "file",
            "file_types": [
                ("Imágenes", "*.png *.jpg *.jpeg *.gif *.webp *.svg"),
                ("Todos los archivos", "*.*"),
            ],
        },
        {
            "name": "img_hover",
            "label": "Imagen al pasar cursor (hover):",
            "type": "file",
            "file_types": [
                ("Imágenes", "*.png *.jpg *.jpeg *.gif *.webp *.svg"),
                ("Todos los archivos", "*.*"),
            ],
        },
        {
            "name": "image_fit",
            "label": "Ajuste de imagen:",
            "type": "select",
            "options": ["contain", "cover", "fill"],
        },
    ]

    supported_events = ["on_click"]

    def __init__(self, width=100, height=60):
        self.width = width
        self.height = height
        self.props = self.default_props.copy()

    def _get_image_src(self, path):
        """
        Convierte una imagen local en Base64.
        También acepta URLs y data URIs.
        """
        if not path:
            return ""

        path = str(path)

        # Ya es una URL o data URI
        if path.startswith(("http://", "https://", "data:", "/")):
            return path

        # Ruta local
        if not os.path.isfile(path):
            print(f"ImageButton: imagen no encontrada: {path}")
            return ""

        mime_type, _ = mimetypes.guess_type(path)

        if not mime_type:
            mime_type = "image/png"

        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{encoded}"
    
    def to_dict(self):
        return {
            "id": getattr(self, 'id', "w_0"),
            "type": getattr(self, 'type', self.__class__.__name__),
            "x": getattr(self, 'x', 50),
            "y": getattr(self, 'y', 50),
            "width": getattr(self, 'width', getattr(self, 'default_props', {}).get('width', 300)),
            "height": getattr(self, 'height', getattr(self, 'default_props', {}).get('height', 150)),
            # IMPORTANTE: Aseguramos que se guarde el diccionario de propiedades actual de la instancia
            "props": getattr(self, 'props', {}),
            "events": getattr(self, 'events', {})
        }
        
    def render_canvas(self, canvas, x, y):
        return [
            canvas.create_rectangle(
                x, y,
                x + self.width,
                y + self.height,
                fill="#234764",
                outline="#203b5c",
                width=2
            ),
            canvas.create_text(
                x + self.width / 2,
                y + self.height / 2,
                text="BUTTON",
                fill="white",
                font=("Arial", 10, "bold")
            )
        ]

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}

        # Obtener las imágenes configuradas en el inspector
        print("img_release: ",p["img_release"])
        print("img_pressed: ",p["img_pressed"])
        print("img_hover: ",p["img_hover"])
        img_release = self._get_image_src(p["img_release"])
        img_pressed = self._get_image_src(p["img_pressed"])
        img_hover = self._get_image_src(p["img_hover"])

        cfg = json.dumps({
            "id": w_id,
            "img_release": img_release,
            "img_pressed": img_pressed,
            "img_hover": img_hover
        })

        return f"""
<div id="imgbtn_{w_id}" class="imgbtn-widget">
    <img class="imgbtn-image" draggable="false">
</div>

<style>
#imgbtn_{w_id} {{
    width:100%;
    height:100%;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow:hidden;
    cursor:pointer;
    user-select:none;
    touch-action:manipulation;
}}

#imgbtn_{w_id} .imgbtn-image {{
    width:100%;
    height:100%;
    object-fit:{p["image_fit"]};
    pointer-events:none;
}}
</style>

<script>
(function() {{
    const cfg = {cfg};

    const root = document.getElementById("imgbtn_" + cfg.id);
    const img = root.querySelector(".imgbtn-image");

    let pressed = false;
    let hovered = false;

    function updateImage() {{
        if (pressed) {{
            img.src = cfg.img_pressed || cfg.img_release;
        }}
        else if (hovered && cfg.img_hover) {{
            img.src = cfg.img_hover;
        }}
        else {{
            img.src = cfg.img_release;
        }}
    }}

    // Imagen inicial
    updateImage();

    root.addEventListener("pointerenter", () => {{
        hovered = true;
        updateImage();
    }});

    root.addEventListener("pointerleave", () => {{
        hovered = false;
        pressed = false;
        updateImage();
    }});

    root.addEventListener("pointerdown", () => {{
        pressed = true;
        updateImage();
    }});

    root.addEventListener("pointerup", () => {{
        pressed = false;
        updateImage();
    }});

    root.addEventListener("pointercancel", () => {{
        pressed = false;
        updateImage();
    }});

    root.addEventListener("click", () => {{
        emitEvent(
            {{id: cfg.id}},
            "on_click",
            true
        );
    }});

}})();
</script>
"""
