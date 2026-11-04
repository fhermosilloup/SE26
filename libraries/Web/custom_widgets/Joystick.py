import json


class Joystick:
    default_props = {
        "label": "Joystick",
        "width": 180,
        "height": 180,
        "background": "#6054a9",
        "ring_color": "#35d4d0",
        "knob_color": "#83a9df",
        "dead_zone": "0.05",
        "show_arrows": "True",
        "return_to_center": "True",
    }

    custom_properties = [
        {"name": "label", "label": "Título del Widget:", "type": "text"},
        {"name": "background", "label": "Color de fondo:", "type": "color"},
        {"name": "ring_color", "label": "Color del anillo:", "type": "color"},
        {"name": "knob_color", "label": "Color de la palanca:", "type": "color"},
        {"name": "dead_zone", "label": "Zona muerta (0.0 - 0.5):", "type": "text"},
        {"name": "show_arrows", "label": "Mostrar flechas:", "type": "boolean"},
        {
            "name": "return_to_center",
            "label": "Regresar al centro:",
            "type": "boolean",
        },
    ]

    supported_events = ["on_click", "on_change_value"]

    def __init__(self, width=180, height=180):
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
        s = min(self.width, self.height)
        cx = x + self.width / 2
        cy = y + self.height / 2

        items = []
        items.append(canvas.create_rectangle(
            x, y, x + self.width, y + self.height,
            fill="#234764", outline="#334155", width=2,
        ))
        items.append(canvas.create_text(
            cx, cy, text="Joystick", fill="#FFFFFF", font=("Segoe UI", 10, "bold"),
        ))
        return items

    def render_html(self, w_id, props):
        p = {**self.default_props, **(props or {})}
        
        def _parse_bool(val, default=True):
            if isinstance(val, str):
                return val.strip().lower() not in ("false", "0", "no", "off")
            return bool(val)

        return_to_center = _parse_bool(p.get("return_to_center", "True"), True)
        show_arrows = _parse_bool(p.get("show_arrows", "True"), True)

        cfg = json.dumps({
            "id": str(w_id),
            "dead_zone": float(p.get("dead_zone", 0)),
            "return_to_center": return_to_center,
            "show_arrows": show_arrows
        })

        return f"""
<div id="joy_{w_id}" class="joy-widget">
  <div class="joy-container">
    <div class="joy-arrows">
      <span class="up">⌃</span>
      <span class="down">⌄</span>
      <span class="left">‹</span>
      <span class="right">›</span>
    </div>
    <div class="joy-ring">
      <div class="joy-base">
        <div class="joy-knob">
          <div class="joy-center"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
#joy_{w_id} {{
  width: 100%;
  height: 100%;
  min-width: 100px;
  min-height: 100px;
  background: {p["background"]};
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  user-select: none;
  touch-action: none;
  container-type: size;
}}

#joy_{w_id} .joy-container {{
  position: relative;
  width: calc(80 * min(1cqw, 1cqh));
  height: calc(80 * min(1cqw, 1cqh));
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}}

#joy_{w_id} .joy-ring {{
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(145deg,#101e32,#263d5b);
  border: 5px solid {p["ring_color"]};
  box-shadow: 0 0 15px {p["ring_color"]},
              inset 0 0 12px #071426;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  position: relative;
}}

#joy_{w_id} .joy-base {{
  width: 75%;
  height: 75%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%,
    #91b4e9,#456b9f 65%,#263d5c);
  box-shadow: inset 0 0 15px #203958,
              0 3px 8px #071426;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}}

#joy_{w_id} .joy-knob {{
  width: 42%;
  height: 42%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%,
    #9fc1ee,#4772a9 75%,#29466b);
  border: 2px solid #75a4d9;
  box-shadow: 0 2px 8px #142a47;
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  will-change: left, top;
}}

#joy_{w_id} .joy-center {{
  width: 42%;
  height: 42%;
  border-radius: 50%;
  border: 2px solid {p["ring_color"]};
  box-shadow: 0 0 8px {p["ring_color"]};
}}

#joy_{w_id} .joy-arrows {{
  position: absolute;
  inset: -12px;
  color: {p["ring_color"]};
  font-size: 22px;
  font-weight: bold;
  pointer-events: none;
  z-index: 2;
}}

#joy_{w_id} .joy-arrows span {{
  position: absolute;
  text-shadow: 0 0 5px {p["ring_color"]};
}}

#joy_{w_id} .up {{top: 0%; left: 50%; transform: translateX(-50%)}}
#joy_{w_id} .down {{bottom: 0%; left: 50%; transform: translateX(-50%)}}
#joy_{w_id} .left {{left: 0%; top: 50%; transform: translateY(-50%)}}
#joy_{w_id} .right {{right: 0%; top: 50%; transform: translateY(-50%)}}
</style>

<script>
(function() {{
  const cfg = {cfg};
  const root = document.getElementById("joy_" + cfg.id);
  const knob = root.querySelector(".joy-knob");
  const base = root.querySelector(".joy-base");
  const arrowsEl = root.querySelector(".joy-arrows");

  let active = false;
  let lastX = 0, lastY = 0;

  function applyConfig(data) {{
    if (data.show_arrows !== undefined) {{
      arrowsEl.style.display = data.show_arrows ? "block" : "none";
    }}
  }}

  applyConfig(cfg);

  function emit(event, value) {{
    if (typeof emitEvent === "function") {{
      emitEvent({{id: cfg.id}}, event, value);
    }}
  }}

  function updatePosition(e) {{
    const rect = base.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const maxRadius = rect.width / 2;

    let deltaX = e.clientX - cx;
    let deltaY = e.clientY - cy;

    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    let dx = 0;
    let dy = 0;

    if (distance > 0) {{
      dx = deltaX / distance;
      dy = deltaY / distance;
    }}

    const normalizedMag = Math.min(1.0, distance / maxRadius);
    let finalDx = dx * normalizedMag;
    let finalDy = dy * normalizedMag;

    const dead = cfg.dead_zone || 0;
    if (normalizedMag < dead) {{
      finalDx = 0;
      finalDy = 0;
    }}

    const percentOffset = 50; 
    let moveX = finalDx * percentOffset;
    let moveY = finalDy * percentOffset;

    knob.style.left = (50 + moveX) + "%";
    knob.style.top = (50 + moveY) + "%";

    if (Math.abs(finalDx - lastX) > 0.005 || Math.abs(finalDy - lastY) > 0.005) {{
      lastX = finalDx;
      lastY = finalDy;

      emit("on_change_value", {{
        x: Number(finalDx.toFixed(3)),
        y: Number((-finalDy).toFixed(3)),
        magnitude: Number(Math.min(1, Math.sqrt(finalDx*finalDx + finalDy*finalDy)).toFixed(3)),
        angle: Number((Math.atan2(-finalDy, finalDx) * 180 / Math.PI).toFixed(1))
      }});
    }}
  }}

  root.addEventListener("pointerdown", e => {{
    active = true;
    root.setPointerCapture(e.pointerId);
    updatePosition(e);
  }});

  root.addEventListener("pointermove", e => {{
    if (active) updatePosition(e);
  }});

  function release() {{
    if (!active) return;
    active = false;

    emit("on_click", {{
      x: lastX,
      y: -lastY
    }});

    if (cfg.return_to_center) {{
      knob.style.left = "50%";
      knob.style.top = "50%";
      lastX = 0;
      lastY = 0;

      emit("on_change_value", {{
        x: 0, y: 0, magnitude: 0, angle: 0
      }});
    }}
  }}

  root.addEventListener("pointerup", release);
  root.addEventListener("pointercancel", release);

  window.__widgets = window.__widgets || {{}};
  window.__widgets[cfg.id] = {{
    update: function(v) {{
      if (!v || typeof v !== "object") return;
      if (Object.prototype.hasOwnProperty.call(v, "show_arrows")) {{
        cfg.show_arrows = v.show_arrows;
        applyConfig(cfg);
      }}
      if (Object.prototype.hasOwnProperty.call(v, "dead_zone")) {{
        cfg.dead_zone = Number(v.dead_zone);
      }}
      if (Object.prototype.hasOwnProperty.call(v, "return_to_center")) {{
        cfg.return_to_center = Boolean(v.return_to_center);
      }}
    }}
  }};

}})();
</script>
"""