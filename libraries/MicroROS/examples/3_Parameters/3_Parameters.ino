#include <MicroROS.h>

#define LED_PIN 13

MicroROS micro_ros;
Node node("nodo_parametros_dinamicos");

// Variables globales controladas por parámetros
int blink_delay = 500;
bool led_enabled = true;

// Manejo de errores
void onMicroRosError(rcl_ret_t error_code, const char* context) {
  Serial.printf("Error en micro-ROS [%d]: %s\n", error_code, context);
  while(true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(100); }
}

// Callback del Servidor de Parámetros
bool onParamChange(const Parameter * old_param, const Parameter * new_param, void * context) {
  (void) context;
  (void) old_param;

  if (new_param == NULL) return false;

  // Extraemos el nombre del parámetro solicitado
  String param_name = String(new_param->name.data);

  if (param_name == "blink_delay") {
    // Validamos que sea mayor a 50ms por seguridad
    if (new_param->value.integer_value < 50) return false; 
    
    blink_delay = new_param->value.integer_value;
    Serial.print("Parámetro actualizado - blink_delay: ");
    Serial.println(blink_delay);
    return true; // Retornar true aprueba el cambio
  }

  if (param_name == "led_enabled") {
    led_enabled = new_param->value.bool_value;
    Serial.print("Parámetro actualizado - led_enabled: ");
    Serial.println(led_enabled ? "ENCENDIDO" : "APAGADO");
    
    if (!led_enabled) digitalWrite(LED_PIN, LOW); // Apagar inmediatamente
    return true; 
  }

  // Si intentan cambiar un parámetro desconocido, lo rechazamos
  return false; 
}

// Instanciamos el servidor de parámetros
ParamServer servidor_params(onParamChange);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  micro_ros.setWiFiTransport("192.168.1.11", 8888, "MI_RED", "MI_PASS");
  micro_ros.setErrorCallback(onMicroRosError);
  
  if (micro_ros.begin()) {
    node.add(servidor_params);
    micro_ros.add(node);
    
    // IMPORTANTE: Se declaran e inicializan una vez que el nodo ya arrancó
    servidor_params.addInt("blink_delay", blink_delay);
    servidor_params.addBool("led_enabled", led_enabled);
    
    Serial.println("Servidor de parámetros listo.");
    Serial.println("Prueba en terminal: ros2 param set /nodo_parametros_dinamicos blink_delay 100");
  }
}

void loop() {
  micro_ros.spin(10); // Ejecutor atiende ROS 2
  
  // Lógica no bloqueante del LED (reemplaza al uso de delay)
  static unsigned long last_time = 0;
  if (led_enabled && (millis() - last_time >= blink_delay)) {
    last_time = millis();
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
  }
}