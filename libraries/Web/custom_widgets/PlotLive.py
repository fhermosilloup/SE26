import json
import re
import tkinter as tk


class PlotLive:
    default_props = {
        "label": "Sensor",
        "plot_color": "#3b82f6",
        "max_points": "50",
        "show_legend": "True",
        "fill_area": "True",
        "y_min": "",
        "y_max": "",
    }

    custom_properties = [
        {"name": "label", "label": "Etiqueta de la serie:", "type": "text"},
        {"name": "plot_color", "label": "Color de la línea:", "type": "color"},
        {
            "name": "max_points",
            "label": "Máx. de puntos visibles:",
            "type": "text",
        },
        {
            "name": "show_legend",
            "label": "Mostrar leyenda (True/False):",
            "type": "text",
        },
        {
            "name": "fill_area",
            "label": "Rellenar área (True/False):",
            "type": "text",
        },
        {
            "name": "y_min",
            "label": "Eje Y mínimo (vacío = auto):",
            "type": "text",
        },
        {
            "name": "y_max",
            "label": "Eje Y máximo (vacío = auto):",
            "type": "text",
        },
    ]

    supported_events = []

    def __init__(self, width=360, height=220):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        box = canvas.create_rectangle(
            x,
            y,
            x + self.width,
            y + self.height,
            fill="#0f172a",
            outline="#1e293b",
            width=2,
        )

        pts = [0.7, 0.45, 0.6, 0.25, 0.4, 0.15, 0.3]
        step = (self.width - 36) / (len(pts) - 1)
        coords = []
        for i, p in enumerate(pts):
            coords += [
                x + 18 + i * step,
                y + 14 + p * (self.height - 28),
            ]

        line = canvas.create_line(
            *coords, fill="#3b82f6", width=3, smooth=True
        )
        txt = canvas.create_text(
            x + self.width / 2,
            y + 12,
            text="Plot",
            fill="#94a3b8",
            font=("Segoe UI", 9, "bold"),
        )
        return [box, line, txt]

    def render_html(self, w_id, props):
        label = props.get("label") or self.default_props["label"]
        color = props.get("plot_color") or self.default_props["plot_color"]
        max_points = (
            props.get("max_points") or self.default_props["max_points"]
        )
        show_legend = props.get(
            "show_legend", self.default_props["show_legend"]
        )
        fill_area = props.get("fill_area", self.default_props["fill_area"])
        y_min = props.get("y_min", "")
        y_max = props.get("y_max", "")

        orig_id = str(w_id)
        safe_id = re.sub(r"\W", "_", orig_id)

        cfg_json = json.dumps(
            {
                "id": orig_id,
                "label": str(label),
                "color": str(color),
                "max_points": str(max_points),
                "show_legend": str(show_legend),
                "fill_area": str(fill_area),
                "y_min": str(y_min),
                "y_max": str(y_max),
            }
        )

        return f"""
        <div id="el_{safe_id}" class="w-full h-full flex flex-col select-none"
             style="background:#0f172a; border:1px solid #1e293b;
                    border-radius:12px; padding:8px;
                    box-shadow:0 4px 16px rgba(0,0,0,0.35);">
            <div style="position:relative; flex:1; min-height:0; width:100%;">
                <canvas id="chart_{safe_id}"></canvas>
            </div>
        </div>

        <script>
        (function() {{
            const cfg = {cfg_json};
            const state = {{
                chart: null,
                pending: [],
                nextX: 1
            }};

            const truthy = (v) =>
                !["false", "0", "no", "off", ""].includes(
                    String(v).trim().toLowerCase()
                );

            const numberOrNull = (v) => {{
                if (v === null || v === undefined || v === "") return null;
                const n = Number(v);
                return Number.isFinite(n) ? n : null;
            }};

            const maxPts = () =>
                Math.max(1, parseInt(cfg.max_points, 10) || 15);

            function withAlpha(hex, alpha) {{
                if (/^#[0-9a-fA-F]{{6}}$/.test(hex)) return hex + alpha;
                return hex;
            }}

            function makeDataset(id, label, color, fill) {{
                const finalColor = color || cfg.color;
                return {{
                    id: String(id),
                    label: String(label),
                    data: [],
                    borderColor: finalColor,
                    backgroundColor: withAlpha(finalColor, "33"),
                    fill: fill === undefined ? truthy(cfg.fill_area) : truthy(fill),
                    tension: 0.35,
                    pointRadius: 2,
                    spanGaps: false
                }};
            }}

            function getDataset(id) {{
                if (!state.chart) return null;
                return state.chart.data.datasets.find(
                    ds => String(ds.id) === String(id)
                ) || null;
            }}

            function ensureDataset(id, label, color, fill) {{
                let ds = getDataset(id);
                if (!ds) {{
                    ds = makeDataset(
                        id,
                        label === undefined ? String(id) : label,
                        color,
                        fill
                    );
                    state.chart.data.datasets.push(ds);
                }} else {{
                    if (label !== undefined && label !== null) ds.label = String(label);
                    // Solo actualiza el color si se envió un color explícito
                    if (color) {{
                        ds.borderColor = color;
                        ds.backgroundColor = withAlpha(color, "33");
                    }}
                    if (fill !== undefined) ds.fill = truthy(fill);
                }}
                return ds;
            }}

            function trimToLimit() {{
                if (!state.chart) return;
                const labels = state.chart.data.labels;
                while (labels.length > maxPts()) {{
                    labels.shift();
                    state.chart.data.datasets.forEach(ds => ds.data.shift());
                }}
            }}

            function updateChart() {{
                if (state.chart) {{
                    trimToLimit();
                    state.chart.update();
                }}
            }}

            function setSeries(id, values, labels, meta={{}}) {{
                if (!state.chart) {{
                    state.pending.push({{
                        action: "set_series", series_id: id,
                        values: values, labels: labels, meta: meta
                    }});
                    return;
                }}

                const ds = ensureDataset(
                    id,
                    meta.label === undefined ? String(id) : meta.label,
                    meta.color,
                    meta.fill
                );
                const ys = values.map(numberOrNull);
                const xs = Array.isArray(labels)
                    ? labels.slice(0, ys.length).map(String)
                    : ys.map((_, i) => String(i + 1));
                const count = Math.min(xs.length, ys.length);

                ds.data = ys.slice(0, count);
                state.chart.data.labels = xs.slice(0, count);

                state.chart.data.datasets.forEach(other => {{
                    if (other === ds) return;
                    other.data = other.data.slice(0, count);
                    while (other.data.length < count) other.data.push(null);
                }});

                state.nextX = count + 1;
                updateChart();
            }}

            function appendPoint(id, value, xLabel, meta={{}}) {{
                if (!state.chart) {{
                    state.pending.push({{
                        action: "append", series_id: id,
                        value: value, x: xLabel, meta: meta
                    }});
                    return;
                }}

                const ds = ensureDataset(
                    id,
                    meta.label === undefined ? String(id) : meta.label,
                    meta.color,
                    meta.fill
                );

                const labels = state.chart.data.labels;
                const x = xLabel === undefined || xLabel === null
                    ? String(state.nextX)
                    : String(xLabel);

                let index = labels.indexOf(x);
                if (index < 0) {{
                    labels.push(x);
                    index = labels.length - 1;
                    state.chart.data.datasets.forEach(other => {{
                        while (other.data.length < labels.length) other.data.push(null);
                    }});
                    state.nextX++;
                }}

                while (ds.data.length < labels.length) ds.data.push(null);
                ds.data[index] = numberOrNull(value);
                updateChart();
            }}

            function appendMany(id, values, labels, meta={{}}) {{
                if (!Array.isArray(values)) return;
                values.forEach((value, i) => {{
                    const x = Array.isArray(labels) ? labels[i] : undefined;
                    appendPoint(id, value, x, meta);
                }});
            }}

            function clearSeries(id) {{
                if (!state.chart) {{
                    state.pending.push({{
                        action: "clear_series", series_id: id
                    }});
                    return;
                }}

                if (id === undefined || id === null || id === "") {{
                    state.chart.data.datasets = [];
                    state.chart.data.labels = [];
                    state.nextX = 1;
                }} else {{
                    const idx = state.chart.data.datasets.findIndex(
                        ds => String(ds.id) === String(id)
                    );
                    if (idx >= 0) state.chart.data.datasets.splice(idx, 1);
                    if (state.chart.data.datasets.length === 0) {{
                        state.chart.data.labels = [];
                        state.nextX = 1;
                    }}
                }}
                updateChart();
            }}

            function applyValue(val) {{
                if (val === null || val === undefined) return;

                if (typeof val === "string") {{
                    try {{
                        val = JSON.parse(val);
                    }} catch (e) {{
                        val = Number(val);
                    }}
                }}

                if (typeof val === "number" && Number.isFinite(val)) {{
                    appendPoint("default", val, undefined, {{
                        label: cfg.label, color: cfg.color
                    }});
                    return;
                }}

                if (Array.isArray(val)) {{
                    if (val.length > 0 && Array.isArray(val[0])) {{
                        setSeries(
                            "default",
                            val.map(p => p[1]),
                            val.map(p => p[0]),
                            {{label: cfg.label, color: cfg.color}}
                        );
                    }} else if (val.length === 2 && !Array.isArray(val[0])) {{
                        appendPoint("default", val[1], val[0], {{
                            label: cfg.label, color: cfg.color
                        }});
                    }} else {{
                        setSeries("default", val, undefined, {{
                            label: cfg.label, color: cfg.color
                        }});
                    }}
                    return;
                }}

                if (typeof val !== "object") return;

                if (Array.isArray(val.series)) {{
                    val.series.forEach(s => {{
                        if (!s || s.id === undefined) return;
                        setSeries(
                            s.id,
                            Array.isArray(s.values) ? s.values : [],
                            s.labels,
                            {{
                                label: s.label === undefined ? s.id : s.label,
                                color: s.color,
                                fill: s.fill
                            }}
                        );
                    }});
                    return;
                }}

                if (val.action === "clear_all" || val.clear === true) {{
                    clearSeries();
                    return;
                }}

                const id = val.series_id === undefined
                    ? "default" : String(val.series_id);
                const meta = {{
                    label: val.label === undefined
                        ? (id === "default" ? cfg.label : id) : val.label,
                    color: val.color,
                    fill: val.fill
                }};

                if (val.action === "clear_series") {{
                    clearSeries(id);
                }} else if (val.action === "set_series" && Array.isArray(val.values)) {{
                    setSeries(id, val.values, val.labels, meta);
                }} else if (val.action === "append_many" && Array.isArray(val.values)) {{
                    appendMany(id, val.values, val.labels, meta);
                }} else if (Array.isArray(val.values)) {{
                    setSeries(id, val.values, val.labels, meta);
                }} else if ("value" in val || "y" in val) {{
                    appendPoint(
                        id,
                        "y" in val ? val.y : val.value,
                        val.x !== undefined ? val.x : val.label,
                        meta
                    );
                }}
            }}

            function updateProp(prop, val) {{
                cfg[prop] = String(val);
                if (!state.chart) return;

                const chart = state.chart;
                if (prop === "label") {{
                    const ds = getDataset("default");
                    if (ds) ds.label = String(val);
                }} else if (prop === "plot_color") {{
                    const ds = getDataset("default");
                    if (ds) {{
                        ds.borderColor = val;
                        ds.backgroundColor = withAlpha(val, "33");
                    }}
                }} else if (prop === "show_legend") {{
                    chart.options.plugins.legend.display = truthy(val);
                }} else if (prop === "fill_area") {{
                    chart.data.datasets.forEach(ds => ds.fill = truthy(val));
                }} else if (prop === "y_min") {{
                    chart.options.scales.y.min =
                        String(val).trim() === "" ? undefined : numberOrNull(val);
                }} else if (prop === "y_max") {{
                    chart.options.scales.y.max =
                        String(val).trim() === "" ? undefined : numberOrNull(val);
                }} else if (prop === "max_points") {{
                    trimToLimit();
                }}
                chart.update();
            }}

            window.__widgets = window.__widgets || {{}};
            window.__widgets[cfg.id] = {{
                update: applyValue,
                update_prop: updateProp,
                set_series: setSeries,
                append: appendPoint,
                append_many: appendMany,
                clear_series: clearSeries
            }};

            function init() {{
                const cv = document.getElementById("chart_{safe_id}");
                if (!cv) return;

                if (typeof Chart === "undefined") {{
                    init.tries = (init.tries || 0) + 1;
                    if (init.tries < 40) setTimeout(init, 250);
                    return;
                }}

                const ymin = String(cfg.y_min).trim() === ""
                    ? undefined : numberOrNull(cfg.y_min);
                const ymax = String(cfg.y_max).trim() === ""
                    ? undefined : numberOrNull(cfg.y_max);

                state.chart = new Chart(cv.getContext("2d"), {{
                    type: "line",
                    data: {{
                        labels: [],
                        datasets: [] // Se inicia totalmente vacío
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {{ duration: 250 }},
                        plugins: {{
                            legend: {{
                                display: truthy(cfg.show_legend),
                                labels: {{ color: "#94a3b8" }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                grid: {{ color: "#334155" }},
                                ticks: {{
                                    color: "#94a3b8",
                                    maxRotation: 0,
                                    autoSkip: true
                                }}
                            }},
                            y: {{
                                min: ymin,
                                max: ymax,
                                grid: {{ color: "#334155" }},
                                ticks: {{ color: "#94a3b8" }}
                            }}
                        }}
                    }}
                }});

                const queued = state.pending.splice(0);
                queued.forEach(msg => applyValue(msg));
            }}

            init();
        }})();
        </script>
        """