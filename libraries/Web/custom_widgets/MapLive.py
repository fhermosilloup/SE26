import json
import re
import tkinter as tk


class MapLive:
    default_props = {
        "label": "Mapa en vivo",
        "latitude": "20.6597",
        "longitude": "-103.3496",
        "zoom": "15",
        "plot_color": "#3b82f6",
        "show_marker": "True",
        "max_points": "1000",
    }

    custom_properties = [
        {"name": "label", "label": "Título:", "type": "text"},
        {"name": "latitude", "label": "Latitud inicial:", "type": "text"},
        {"name": "longitude", "label": "Longitud inicial:", "type": "text"},
        {"name": "zoom", "label": "Zoom:", "type": "text"},
        {
            "name": "plot_color",
            "label": "Color de trayectoria:",
            "type": "color",
        },
        {
            "name": "show_marker",
            "label": "Mostrar marcador (True/False):",
            "type": "text",
        },
        {"name": "max_points", "label": "Máximo de puntos:", "type": "text"},
    ]

    supported_events = []

    def __init__(self, width=360, height=260):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        box = canvas.create_rectangle(
            x,
            y,
            x + self.width,
            y + self.height,
            fill="#0f172a",
            outline="#334155",
            width=2,
        )

        title = canvas.create_text(
            x + self.width / 2,
            y + 14,
            text="MapLive",
            fill="#e2e8f0",
            font=("Segoe UI", 10, "bold"),
        )

        return [box, title]

    def render_html(self, w_id, props):
        orig_id = str(w_id)
        safe_id = re.sub(r"\W", "_", orig_id)

        label = str(props.get("label", "Mapa en vivo"))
        color = str(props.get("plot_color", "#3b82f6"))

        try:
            lat = float(props.get("latitude", 20.6597))
            lon = float(props.get("longitude", -103.3496))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except (ValueError, TypeError):
            lat, lon = 20.6597, -103.3496

        try:
            zoom = max(1, min(19, int(props.get("zoom", 15))))
        except (ValueError, TypeError):
            zoom = 15

        try:
            max_points = max(2, int(props.get("max_points", 1000)))
        except (ValueError, TypeError):
            max_points = 1000

        show_marker = str(props.get("show_marker", "True")).lower() not in (
            "false",
            "0",
            "no",
            "off",
        )

        cfg = json.dumps(
            {
                "id": orig_id,
                "label": label,
                "lat": lat,
                "lon": lon,
                "zoom": zoom,
                "color": color,
                "max_points": max_points,
                "show_marker": show_marker,
            }
        )

        return f"""
        <div id="map_container_{safe_id}"
             class="w-full h-full flex flex-col overflow-hidden rounded-xl"
             style="background:#0f172a;border:1px solid #1e293b;">

            <div class="px-3 py-2 text-xs font-semibold text-slate-200">
                {label}
            </div>

            <div id="map_{safe_id}"
                 style="flex:1;min-height:0;width:100%;z-index:1;">
            </div>
        </div>

        <script>
        (function() {{
            const cfg = {cfg};
            let map = null;
            let route = null;
            let marker = null;
            let initialized = false;
            let pending = [];

            function init() {{
                const el = document.getElementById("map_{safe_id}");
                if (!el) return;

                if (typeof L === "undefined") {{
                    init.tries = (init.tries || 0) + 1;
                    if (init.tries < 40) setTimeout(init, 250);
                    return;
                }}

                map = L.map(el).setView(
                    [cfg.lat, cfg.lon], cfg.zoom
                );

                L.tileLayer(
                    "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
                    {{
                        maxZoom: 19,
                        attribution: "&copy; OpenStreetMap contributors"
                    }}
                ).addTo(map);

                route = L.polyline([], {{
                    color: cfg.color,
                    weight: 3,
                    opacity: 0.9,
                    dashArray: "6 7"
                }}).addTo(map);

                if (cfg.show_marker) {{
                    marker = L.marker([cfg.lat, cfg.lon]).addTo(map);
                }}

                initialized = true;

                // Coordenada inicial
                addPoint({{lat: cfg.lat, lon: cfg.lon}});

                pending.splice(0).forEach(update);

                setTimeout(() => map.invalidateSize(), 100);
            }}

            function addPoint(point) {{
                const lat = Number(point.lat ?? point.latitude);
                const lon = Number(point.lon ?? point.lng ?? point.longitude);

                if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
                if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return;

                const coords = route.getLatLngs();
                const last = coords.length ? coords[coords.length - 1] : null;

                // No duplicar puntos consecutivos idénticos
                if (last && last.lat === lat && last.lng === lon) return;

                coords.push(L.latLng(lat, lon));

                while (coords.length > cfg.max_points) {{
                    coords.shift();
                }}

                route.setLatLngs(coords);

                if (marker) marker.setLatLng([lat, lon]);

                // CENTRADO AUTOMÁTICO DEL MAPA EN LA POSICIÓN ACTUAL
                if (map) {{
                    map.panTo([lat, lon], {{ animate: true }});
                }}
            }}

            function update(value) {{
                if (!initialized) {{
                    pending.push(value);
                    return;
                }}

                if (typeof value === "string") {{
                    try {{
                        value = JSON.parse(value);
                    }} catch (e) {{
                        return;
                    }}
                }}

                if (!value || typeof value !== "object") return;

                if (Array.isArray(value.points)) {{
                    value.points.forEach(addPoint);
                }} else if (Array.isArray(value)) {{
                    value.forEach(addPoint);
                }} else {{
                    addPoint(value);
                }}
            }}

            window.__widgets = window.__widgets || {{}};
            window.__widgets[cfg.id] = {{
                update: update,
                update_prop: function(prop, value) {{
                    if (prop === "plot_color") {{
                        cfg.color = String(value);
                        if (route) route.setStyle({{color: cfg.color}});
                    }}

                    if (prop === "zoom" && map) {{
                        map.setZoom(Number(value));
                    }}
                }}
            }};

            init();
        }})();
        </script>
        """