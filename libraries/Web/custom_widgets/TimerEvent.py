
import tkinter as tk
import json
import re


class TimerEvent:
    default_props = {
        "period_ms": "1000",
        "autostart": "True"
    }

    custom_properties = [
        {
            "name": "period_ms",
            "label": "Periodo del temporizador (ms):",
            "type": "text"
        },
        {
            "name": "autostart",
            "label": "Iniciar automáticamente (True/False):",
            "type": "text"
        }
    ]

    supported_events = ["on_timer"]

    def __init__(self, width=1, height=1):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        # Widget invisible en el diseñador.
        return []

    def render_html(self, w_id, props):
        orig_id = str(w_id)
        safe_id = re.sub(r"\W", "_", orig_id)

        try:
            period_ms = max(
                1, int(props.get("period_ms", 1000))
            )
        except (ValueError, TypeError):
            period_ms = 1000

        autostart = str(
            props.get("autostart", "True")
        ).strip().lower() not in (
            "false", "0", "no", "off"
        )

        cfg = json.dumps({
            "id": orig_id,
            "period_ms": period_ms,
            "autostart": autostart
        })

        return f"""
        <div id="timer_{safe_id}" style="display:none;"></div>

        <script>
        (function() {{
            const cfg = {cfg};

            let period = cfg.period_ms;
            let timerId = null;
            let running = false;

            function emitTick() {{
                if (typeof emitEvent === "function") {{
                    emitEvent(
                        {{
                            id: cfg.id,
                            events: {{on_timer: true}}
                        }},
                        "on_timer",
                        {{
                            period_ms: period,
                            timestamp: Date.now()
                        }}
                    );
                }}
            }}

            function start() {{
                if (running) return;

                running = true;
                timerId = setInterval(emitTick, period);
            }}

            function stop() {{
                if (timerId !== null) {{
                    clearInterval(timerId);
                    timerId = null;
                }}

                running = false;
            }}

            function setPeriod(ms) {{
                const value = Number(ms);

                if (!Number.isFinite(value) || value < 1) {{
                    throw new Error(
                        "El periodo debe ser un número positivo en ms."
                    );
                }}

                period = Math.floor(value);

                // Si está activo, reinicia el intervalo con el nuevo periodo.
                if (running) {{
                    stop();
                    start();
                }}
            }}

            function update(value) {{
                if (typeof value === "string") {{
                    try {{
                        value = JSON.parse(value);
                    }} catch (e) {{
                        return;
                    }}
                }}

                if (!value || typeof value !== "object") return;

                if (value.period_ms !== undefined) {{
                    setPeriod(value.period_ms);
                }}

                if (value.action === "start") start();
                else if (value.action === "stop") stop();
            }}

            // API para el sistema de widgets del dashboard.
            window.__widgets = window.__widgets || {{}};

            window.__widgets[cfg.id] = {{
                update: update,
                update_prop: function(prop, value) {{
                    if (prop === "period_ms") {{
                        setPeriod(value);
                    }}
                }},
                start: start,
                stop: stop,
                set_period: setPeriod
            }};

            // Permite controlar el temporizador mediante mensajes update.
            if (typeof socket !== "undefined") {{
                socket.on("update", function(data) {{
                    if (data && data.id === cfg.id) {{
                        update(data.value);
                    }}
                }});
            }}

            if (cfg.autostart) start();

        }})();
        </script>
        """
