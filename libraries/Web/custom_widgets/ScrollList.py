import tkinter as tk
import json
import re


class ScrollList:
    default_props = {
        "label": "ScrollList",
        "scroll_rows": "12, 13, 14, 15, 16 | February, March, April, May, June | 2018, 2019, 2020, 2021, 2022",
        "scroll_cols": "Día, Mes, Año",
        "accent_color": "#38a1ff"
    }

    custom_properties = [
        {"name": "scroll_rows", "label": "Filas (separa columnas con '|'):", "type": "text"},
        {"name": "scroll_cols", "label": "Encabezados (separados por coma):", "type": "text"},
        {"name": "accent_color", "label": "Color de Selección:", "type": "color"}
    ]

    supported_events = ["on_value_change", "on_click"]

    def __init__(self, width=280, height=180):
        self.width = width
        self.height = height

    def render_canvas(self, canvas, x, y):
        # Marco exterior
        box = canvas.create_rectangle(x, y, x + self.width, y + self.height, fill='#111827', outline='#1f2937', width=2)
        # Tres tambores separados
        gap = 4
        col_w = (self.width - 12 - gap * 2) / 3
        for i in range(3):
            cx = x + 6 + i * (col_w + gap)
            canvas.create_rectangle(cx, y + 6, cx + col_w, y + self.height - 6, fill='#e5e5e5', outline='#111111', width=2)
        # Franja de selección
        pill = canvas.create_rectangle(x + 6, y + self.height / 2 - 18, x + self.width - 6, y + self.height / 2 + 18, fill='', outline='#ffffff', width=2)
        # Texto de vista previa
        txt_d = canvas.create_text(x + self.width / 6, y + self.height / 2, text='14', fill='#38a1ff', font=('Segoe UI', 11, 'bold'))
        txt_m = canvas.create_text(x + self.width / 2, y + self.height / 2, text='April', fill='#38a1ff', font=('Segoe UI', 11, 'bold'))
        txt_a = canvas.create_text(x + (self.width / 6) * 5, y + self.height / 2, text='2020', fill='#38a1ff', font=('Segoe UI', 11, 'bold'))
        return [box, pill, txt_d, txt_m, txt_a]

    def render_html(self, w_id, props):
        label = props.get('label') or 'ScrollList'
        rows_raw = props.get('scroll_rows') or self.default_props["scroll_rows"]
        cols_raw = props.get('scroll_cols') or self.default_props["scroll_cols"]
        accent = props.get('accent_color') or self.default_props["accent_color"]

        orig_id = str(w_id)
        w_id = re.sub(r'\W', '_', orig_id)
        orig_id_js = json.dumps(orig_id)

        cols = [c.strip() for c in str(cols_raw).split(',') if c.strip()]
        if not cols:
            cols = ["Col 1", "Col 2", "Col 3"]

        raw_parts = [p.strip() for p in str(rows_raw).split('|')]
        items_per_col = []
        for i in range(len(cols)):
            if i < len(raw_parts) and raw_parts[i]:
                col_items = [r.strip() for r in raw_parts[i].split(',') if r.strip()]
            elif raw_parts and raw_parts[0]:
                col_items = [r.strip() for r in raw_parts[0].split(',') if r.strip()]
            else:
                col_items = ["Item 1", "Item 2", "Item 3"]
            items_per_col.append(col_items)

        cols_json = json.dumps(cols)
        items_per_col_json = json.dumps(items_per_col)

        # Eventos activados para este widget (por defecto TODOS desactivados)
        events_cfg = props.get('events') or {}
        if not isinstance(events_cfg, dict):
            events_cfg = {}

        def _is_on(name):
            v = events_cfg.get(name, props.get(name, False))
            if isinstance(v, str):
                return v.strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')
            return bool(v)

        events_json = json.dumps({ev: _is_on(ev) for ev in self.supported_events})

        return f"""
        <div id="el_{w_id}" class="w-full h-full flex flex-col select-none relative overflow-hidden"
             style="background: #111827; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.35);">

            <div id="drum_area_{w_id}" class="w-full flex-1 relative overflow-hidden" style="background:#050505; border-radius: 6px;">

                <!-- Columnas (tambores independientes separados por una línea oscura) -->
                <div id="columns_wrapper_{w_id}" class="absolute inset-0 flex flex-row" style="gap: 4px;"></div>

                <!-- Franja de selección translúcida sobre todas las columnas -->
                <div id="band_{w_id}" class="absolute pointer-events-none"
                     style="left:0; right:0; top:50%; height:40px; transform: translateY(-50%); z-index: 30;
                            background: rgba(255,255,255,0.28);
                            border-top: 2px solid rgba(255,255,255,0.75);
                            border-bottom: 2px solid rgba(255,255,255,0.75);
                            box-shadow: 0 0 10px rgba(255,255,255,0.25);"></div>
            </div>

            <span class="text-[10px] mt-2 text-white font-bold uppercase tracking-widest text-center">{label}</span>
        </div>

        <script>
            (function() {{
                const widgetId_{w_id} = {orig_id_js};
                const cols_{w_id} = {cols_json};
                const itemsPerCol_{w_id} = {items_per_col_json};
                const accentColor_{w_id} = "{accent}";
                const events_{w_id} = {events_json};
                let silent_{w_id} = false;
                const wrapper_{w_id} = document.getElementById('columns_wrapper_{w_id}');
                const band_{w_id} = document.getElementById('band_{w_id}');

                let currentIndexes_{w_id} = itemsPerCol_{w_id}.map(items => Math.floor(items.length / 2));
                let itemH_{w_id} = 40;

                function render_{w_id}() {{
                    if (!wrapper_{w_id}) return;

                    wrapper_{w_id}.innerHTML = cols_{w_id}.map((colName, cIdx) => {{
                        const items = itemsPerCol_{w_id}[cIdx] || [];
                        const trackHtml = items.map(it =>
                            `<div class="sl_item_{w_id} w-full flex items-center justify-center text-center" style="height:40px; line-height:40px; font-weight:800; color:#3a3a3a; white-space:nowrap;">${{it}}</div>`
                        ).join('');

                        return `
                        <div id="viewport_{w_id}_${{cIdx}}" class="flex-1 h-full overflow-hidden relative cursor-grab active:cursor-grabbing"
                             style="background: linear-gradient(to bottom, #8f8f8f 0%, #e6e6e6 22%, #ffffff 50%, #e6e6e6 78%, #8f8f8f 100%);">
                            <div id="track_{w_id}_${{cIdx}}" class="w-full flex flex-col items-center" style="transform: translateY(0px); transition: transform 0.3s ease-out; position:relative; z-index:10;">
                                ${{trackHtml}}
                            </div>
                            <!-- Sombreado cilíndrico (arriba/abajo y bordes laterales) -->
                            <div class="absolute inset-0 pointer-events-none" style="z-index:20;
                                background:
                                  linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 70%, rgba(0,0,0,0.6) 100%),
                                  linear-gradient(to right, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0) 14%, rgba(0,0,0,0) 86%, rgba(0,0,0,0.4) 100%);"></div>
                        </div>`;
                    }}).join('');

                    cols_{w_id}.forEach((_, cIdx) => {{
                        const vp = document.getElementById(`viewport_{w_id}_${{cIdx}}`);
                        if (!vp) return;

                        // A. Rueda del mouse
                        vp.addEventListener('wheel', (e) => {{
                            e.preventDefault();
                            e.stopPropagation();
                            if (e.deltaY > 0) {{
                                setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] + 1);
                            }} else if (e.deltaY < 0) {{
                                setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] - 1);
                            }}
                        }}, {{ passive: false }});

                        // B. Arrastre con Mouse / Touch
                        let startY = 0;
                        let isDown = false;
                        let hasDragged = false;

                        function handleStart(pageY) {{
                            isDown = true;
                            startY = pageY;
                            hasDragged = false;
                        }}

                        function handleMove(pageY) {{
                            if (!isDown) return;
                            const distY = pageY - startY;
                            if (Math.abs(distY) > 15) {{
                                hasDragged = true;
                                if (distY < 0) {{
                                    setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] + 1);
                                }} else {{
                                    setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] - 1);
                                }}
                                startY = pageY;
                            }}
                        }}

                        function handleEnd() {{
                            isDown = false;
                        }}

                        vp.addEventListener('mousedown', (e) => handleStart(e.pageY));
                        vp.addEventListener('mousemove', (e) => {{
                            if (isDown) {{
                                e.preventDefault();
                                handleMove(e.pageY);
                            }}
                        }});
                        vp.addEventListener('mouseup', handleEnd);
                        vp.addEventListener('mouseleave', handleEnd);

                        vp.addEventListener('touchstart', (e) => {{
                            if (e.touches.length === 1) handleStart(e.touches[0].pageY);
                        }}, {{ passive: true }});
                        vp.addEventListener('touchmove', (e) => {{
                            if (isDown && e.touches.length === 1) handleMove(e.touches[0].pageY);
                        }}, {{ passive: true }});
                        vp.addEventListener('touchend', handleEnd);

                        // C. Clic en el tercio superior o inferior
                        vp.addEventListener('click', (e) => {{
                            if (hasDragged) return;
                            const rect = vp.getBoundingClientRect();
                            const clickY = e.clientY - rect.top;
                            if (clickY < rect.height / 3) {{
                                setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] - 1);
                            }} else if (clickY > (rect.height * 2) / 3) {{
                                setColIndex_{w_id}(cIdx, currentIndexes_{w_id}[cIdx] + 1);
                            }}
                        }});
                    }});

                    layout_{w_id}();

                    if (typeof ResizeObserver !== 'undefined') {{
                        new ResizeObserver(() => layout_{w_id}()).observe(wrapper_{w_id});
                    }}
                }}

                // Ajusta el alto de cada fila para mostrar 5 filas visibles (como en la referencia)
                function layout_{w_id}() {{
                    const firstVp = document.getElementById('viewport_{w_id}_0');
                    if (!firstVp) return;
                    const h = firstVp.clientHeight;
                    if (!h) return;

                    itemH_{w_id} = h / 5;
                    const fontPx = Math.max(11, Math.round(itemH_{w_id} * 0.36));

                    document.querySelectorAll('#columns_wrapper_{w_id} .sl_item_{w_id}').forEach(el => {{
                        el.style.height = itemH_{w_id} + 'px';
                        el.style.lineHeight = itemH_{w_id} + 'px';
                        el.style.fontSize = fontPx + 'px';
                    }});

                    if (band_{w_id}) band_{w_id}.style.height = itemH_{w_id} + 'px';
                    updateAllPositions_{w_id}();
                }}

                function updateColPosition_{w_id}(cIdx) {{
                    const vp = document.getElementById(`viewport_{w_id}_${{cIdx}}`);
                    const track = document.getElementById(`track_{w_id}_${{cIdx}}`);
                    if (!vp || !track) return;

                    const idx = currentIndexes_{w_id}[cIdx];
                    const vHeight = vp.clientHeight || (itemH_{w_id} * 5);
                    const centerOffset = (vHeight / 2) - (itemH_{w_id} / 2);
                    const targetY = -(idx * itemH_{w_id}) + centerOffset;

                    track.style.transform = `translateY(${{targetY}}px)`;

                    Array.from(track.children).forEach((child, i) => {{
                        child.style.color = (i === idx) ? accentColor_{w_id} : "#3a3a3a";
                    }});
                }}

                function updateAllPositions_{w_id}() {{
                    cols_{w_id}.forEach((_, cIdx) => updateColPosition_{w_id}(cIdx));
                }}

                function setColIndex_{w_id}(cIdx, newIdx) {{
                    const items = itemsPerCol_{w_id}[cIdx] || [];
                    const clamped = Math.max(0, Math.min(items.length - 1, newIdx));
                    if (clamped !== currentIndexes_{w_id}[cIdx]) {{
                        currentIndexes_{w_id}[cIdx] = clamped;
                        updateColPosition_{w_id}(cIdx);

                        const selectedValues = cols_{w_id}.map((_, i) => {{
                            const colItems = itemsPerCol_{w_id}[i] || [];
                            return colItems[currentIndexes_{w_id}[i]] || '';
                        }});

                        if (!silent_{w_id} && events_{w_id}.on_value_change && typeof emitEvent === 'function') {{
                            emitEvent({{id: widgetId_{w_id}, events: events_{w_id}}}, 'on_value_change', {{
                                changed_column: cIdx,
                                column_name: cols_{w_id}[cIdx],
                                value: items[clamped],
                                selected: selectedValues
                            }});
                        }}
                    }}
                }}

                if (typeof socket !== 'undefined') {{
                    socket.on('update', function(data) {{
                        if (data.id === widgetId_{w_id}) {{
                            silent_{w_id} = true;
                            try {{
                            const val = data.value;
                            if (Array.isArray(val)) {{
                                val.forEach((v, cIdx) => {{
                                    if (cIdx < cols_{w_id}.length) {{
                                        if (typeof v === 'number') setColIndex_{w_id}(cIdx, v);
                                        else {{
                                            const fIdx = (itemsPerCol_{w_id}[cIdx] || []).indexOf(String(v));
                                            if (fIdx !== -1) setColIndex_{w_id}(cIdx, fIdx);
                                        }}
                                    }}
                                }});
                            }} else if (typeof val === 'object' && val !== null && 'col' in val && 'val' in val) {{
                                const cIdx = val.col;
                                const v = val.val;
                                if (typeof v === 'number') setColIndex_{w_id}(cIdx, v);
                                else {{
                                    const fIdx = (itemsPerCol_{w_id}[cIdx] || []).indexOf(String(v));
                                    if (fIdx !== -1) setColIndex_{w_id}(cIdx, fIdx);
                                }}
                            }} else if (typeof val === 'number') {{
                                setColIndex_{w_id}(0, val);
                            }} else {{
                                const fIdx = (itemsPerCol_{w_id}[0] || []).indexOf(String(val));
                                if (fIdx !== -1) setColIndex_{w_id}(0, fIdx);
                            }}
                            }} finally {{
                                silent_{w_id} = false;
                            }}
                        }}
                    }});
                }}

                setTimeout(render_{w_id}, 50);
            }})();
        </script>
        """