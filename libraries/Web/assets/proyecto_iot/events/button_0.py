# Controlador para el widget: button_0
#ui.set_value("timer_1", {"action": "start"})
#ui.set_value("timer_1", {"action": "stop"})
#ui.set_value("timer_1", {"period_ms": 250})
#ui.set_value("plotlive_19", {"values": [1,2,5,8,...]})
#ui.set_value("plotlive_19", {"values": [1,2,5,8,...], "labels:", [5, 6, 7,8,...]})
#ui.set_value("plotlive_19", {"series": {"Temperature": [2,1,5,3], "Humedad": [1,2,3,4,5,6]}})
#ui.set_value("plotlive_19", {"series_id": "Temperature", "value": 26.5})
#ui.set_value("plotlive_19", {"series": {"Temperature": [2,1,5,3], "Humedad": [1,2,3,4,5,6]}})
import random
import base64
import cv2
import numpy as np
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la cámara")

def file_to_base64(file_path):
    """Lee un archivo de imagen (JPG, PNG) y lo convierte a Base64."""
    with open(file_path, "rb") as f:
        bytes_data = f.read()
        return base64.b64encode(bytes_data).decode("utf-8")
def image_to_base64(image, format=".jpg"):
    """Convierte una imagen OpenCV (numpy.ndarray) a Base64."""
    success, buffer = cv2.imencode(format, image)
    if not success:
        raise ValueError("No se pudo codificar la imagen")
    return base64.b64encode(buffer).decode("utf-8")
# Variable de estado global para alternar (Inicia apagado: False)
_led_state = False
_first_time = True
lat = 20.6597
lon = -103.3496
rumbo = 0
def on_click(context):
    global _led_state
    global lat
    global lon
    global rumbo
    global _first_time
    widget_id = context.get('widget_id')
    ui = context.get('ui')
    
    # Invertimos el estado actual del LED
    _led_state = not _led_state
    valor = random.uniform(0, 10)
    rumbo = (rumbo + 90) % 360
    ret, frame = cap.read()
    if not ret:
        frame = cv2.zeros((100,100), dtype=np.uint8)
    # Actualizamos el valor del LED con ID = 'led_4' en la interfaz
    if ui:
        # Supongamos que tu widget tiene ID 'video_1'
        #b64_img = file_to_base64("static/seg.png")
        b64_img = image_to_base64(frame)
        ui.set_value("videostreamer_20", b64_img)


        ui.set_value('led_4', _led_state)
        #ui.set_value("plotlive_19", round(valor,1))
        ui.set_value('compass_14', rumbo)   # Rumbo dinámico con decimales (ej. desde un magnetómetro/IMU)
        ui.set_value("maplive_19", {"lat": lat, "lon": lon})
        if _first_time:
            _first_time=False
            ui.set_value("plotlive_19", {
                "series": [
                    {
                        "id": "temperatura",
                        "label": "Temperatura",
                        "color": "#ef4444",
                        "values": [20, 22, 24, 23]
                    },
                    {
                        "id": "humedad",
                        "label": "Humedad",
                        "color": "#3b82f6",
                        "values": [60, 58, 55, 57]
                    }
                ]
            })
        else:
            ui.set_value("plotlive_19", {
                "series_id": "temperatura",
                "value": 26
            })

        lat += 0.0001
        lon -= 0.0001
		
        
    print(f'Botón {widget_id} presionado. LED 4 cambiado a: {_led_state}')
