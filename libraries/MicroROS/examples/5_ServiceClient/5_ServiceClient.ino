#include <MicroROS.h>

#define LED_PIN 13

MicroROS micro_ros;
Node node("nodo_cliente_servicios");

// Instancia del cliente de servicio
ServiceClient<std_srvs::srv::SetBool> cliente_luces("control_luces");
std_srvs::srv::SetBool::Request peticion;

void onMicroRosError(rcl_ret_t error_code, const char* context) {
  Serial.printf("Error en micro-ROS [%d]: %s\n", error_code, context);
  while(true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(100); }
}

// Timer para enviar peticiones periódicamente
void timerCallback(rcl_timer_t* timer, int64_t last_call_time) {
  static bool alternar = false;
  alternar = !alternar;
  
  peticion.set(alternar); // Preparamos el Request
  
  Serial.print("Enviando peticion de luz: ");
  Serial.println(alternar ? "ENCENDIDA" : "APAGADA");
  
  // Enviamos la petición de manera asíncrona
  if (!cliente_luces.sendRequest(peticion)) {
    Serial.println("Fallo al poner la peticion en la cola.");
  }
}

Timer timer_peticiones(5000, timerCallback);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  micro_ros.setWiFiTransport("192.168.1.11", 8888, "MI_RED", "MI_PASS");
  micro_ros.setErrorCallback(onMicroRosError);
  
  if (micro_ros.begin()) {
    node.add(cliente_luces);
    node.add(timer_peticiones);
    micro_ros.add(node);
    
    Serial.println("Cliente de servicios inicializado.");
  }
}

void loop() {
  delay(10);
  micro_ros.spin(100);
  
  // Opcional: si la clase ServiceClient implementa un método checkResponse(),
  // se llamaría aquí para leer la respuesta de forma no bloqueante.
}