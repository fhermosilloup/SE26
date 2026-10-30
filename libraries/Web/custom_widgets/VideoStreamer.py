
import tkinter as tk
import html


class VideoStreamer:
    """Widget para visualizar imágenes recibidas por streaming."""

    default_props = {
        "label": "Video Stream",
        "background": "#020617",
        "fit": "contain",
        "show_status": True
    }

    supported_events = ["on_click"]

    def __init__(self, width=320, height=240):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        """Vista previa del widget en el diseñador Tkinter."""
        box = canvas.create_rectangle(
            x, y, x + self.width, y + self.height,
            fill="#020617", outline="#334155", width=2
        )

        # Representación de una imagen de video
        screen = canvas.create_rectangle(
            x + 8, y + 8,
            x + self.width - 8, y + self.height - 35,
            fill="#0f172a", outline="#1e293b"
        )

        txt = canvas.create_text(
            x + self.width / 2,
            y + self.height / 2 - 8,
            text="VIDEO STREAM",
            fill="#38bdf8",
            font=("Segoe UI", 11, "bold")
        )

        status = canvas.create_text(
            x + self.width / 2,
            y + self.height - 17,
            text="Esperando imagen...",
            fill="#94a3b8",
            font=("Segoe UI", 8)
        )

        return [box, screen, txt, status]

    def render_html(self, w_id, props):
        """Renderizado del streaming en el dashboard web."""
        label = html.escape(
            str(props.get("label", "Video Stream"))
        )
        background = html.escape(
            str(props.get("background", "#020617")),
            quote=True
        )

        fit = props.get("fit", "contain")
        if fit not in ("contain", "cover", "fill"):
            fit = "contain"

        show_status = (
            "true" if props.get("show_status", True) else "false"
        )

        return f"""
        <div id="video_container_{w_id}"
             class="w-full h-full flex flex-col overflow-hidden rounded-xl"
             style="background:{background};">

            <div class="flex items-center justify-between px-3 py-2
                        border-b border-slate-700">
                <span class="text-xs font-semibold text-slate-200">
                    {label}
                </span>
                <span id="video_dot_{w_id}"
                      class="w-2 h-2 rounded-full bg-slate-500">
                </span>
            </div>

            <div class="relative flex-1 min-h-0 flex items-center
                        justify-center overflow-hidden">
                <img id="video_image_{w_id}"
                     alt="Video Stream"
                     class="w-full h-full"
                     style="object-fit:{fit};display:none;"
                     draggable="false">

                <span id="video_placeholder_{w_id}"
                      class="text-xs text-slate-500">
                    Esperando imagen...
                </span>
            </div>

            <div id="video_status_{w_id}"
                 class="px-3 py-1 text-xs text-slate-400"
                 style="display:{'block' if show_status == 'true' else 'none'};">
                Sin señal
            </div>
        </div>

        <script>
        (function() {{
            const id = '{w_id}';
            const img = document.getElementById('video_image_' + id);
            const placeholder = document.getElementById(
                'video_placeholder_' + id
            );
            const status = document.getElementById('video_status_' + id);
            const dot = document.getElementById('video_dot_' + id);

            if (!img || !placeholder) return;

            // Convierte distintos formatos de payload en una URL de imagen.
            function getImageSource(value) {{
                if (typeof value === 'string') {{
                    if (value.startsWith('data:image/')) return value;

                    // Base64 JPEG por defecto.
                    return 'data:image/jpeg;base64,' + value;
                }}

                if (value && typeof value === 'object') {{
                    if (value.image_url) return value.image_url;
                    if (value.src) return value.src;

                    if (value.data) {{
                        if (value.data.startsWith &&
                            value.data.startsWith('data:image/')) {{
                            return value.data;
                        }}

                        const mime = value.mime_type || 'image/jpeg';
                        return 'data:' + mime + ';base64,' + value.data;
                    }}
                }}

                return null;
            }}

            function showFrame(value) {{
                const source = getImageSource(value);
                if (!source) return;

                img.onload = function() {{
                    img.style.display = 'block';
                    placeholder.style.display = 'none';
                    dot.className =
                        'w-2 h-2 rounded-full bg-emerald-500';

                    if (status) status.textContent = 'Recibiendo imagen';
                }};

                img.onerror = function() {{
                    dot.className = 'w-2 h-2 rounded-full bg-red-500';
                    if (status) status.textContent = 'Error de imagen';
                }};

                img.src = source;
            }}

            // Recibe imágenes desde Flask-SocketIO.
            if (typeof socket !== 'undefined') {{
                socket.on('update', function(data) {{
                    if (!data || data.id !== id) return;
                    showFrame(data.value);
                }});
            }}

            // Evento de usuario: clic sobre el video.
            img.addEventListener('click', function() {{
                if (typeof emitEvent === 'function') {{
                    emitEvent(
                        {{id: id, events: {{on_click: true}}}},
                        'on_click',
                        true
                    );
                }}
            }});
        }})();
        </script>
        """
