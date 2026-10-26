#include <MicroROS.h>

#define LED_PIN 13

MicroROS micro_ros;
Node node("nodo_cliente_acciones");

void onMicroRosError(rcl_ret_t error_code, const char* context) {
  Serial.printf("Error en micro-ROS [%d]: %s\n", error_code, context);
  while(true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(100); }
}

// Callback para recibir la retroalimentación en tiempo real (Feedback)
void feedbackCallback(const custom_msgs::action::Navegar::Feedback& feedback) {
  Serial.printf("Progreso: Faltan %.2f metros para llegar.\n", feedback.distancia_restante);
}

// Callback para recibir el resultado final de la acción (Result)
void resultCallback(const custom_msgs::action::Navegar::Result& resultado) {
  if (resultado.exito) {
    Serial.println("¡Meta alcanzada con éxito!");
  } else {
    Serial.println("La navegación falló o fue cancelada.");
  }
}

// Objeto ActionClient (Falta implementarlo en Entity.h)
ActionClient<custom_msgs::action::Navegar> cliente_navegacion("navegar_a_punto", feedbackCallback, resultCallback);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  micro_ros.setWiFiTransport("192.168.1.11", 8888, "MI_RED", "MI_PASS");
  micro_ros.setErrorCallback(onMicroRosError);
  
  if (micro_ros.begin()) {
    node.add(cliente_navegacion);
    micro_ros.add(node);
    Serial.println("Cliente de acciones listo.");
    
    // Damos un poco de tiempo para que ROS 2 descubra la red antes de enviar la meta
    delay(2000); 
    
    // Preparamos y enviamos la meta (Goal)
    custom_msgs::action::Navegar::Goal meta;
    meta.x = 10.5;
    meta.y = 5.2;
    
    Serial.println("Enviando meta de navegación al servidor...");
    cliente_navegacion.sendGoal(meta);
  }
}

void loop() {
  delay(10);
  // Mantener el spin ejecutándose es lo que permite que se reciban 
  // los callbacks de Feedback y Result asíncronamente
  micro_ros.spin(100);
}