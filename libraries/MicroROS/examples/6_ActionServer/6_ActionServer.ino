#include <MicroROS.h>

#define LED_PIN 13

MicroROS micro_ros;
Node node("nodo_servidor_acciones");

void onMicroRosError(rcl_ret_t error_code, const char* context) {
  while(true) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(100); }
}

// Callback cuando llega una nueva meta (Goal)
bool goalCallback(const custom_msgs::action::Navegar::Goal& goal) {
  Serial.printf("Nueva meta recibida. Destino X: %f\n", goal.x);
  return true; // Aceptamos la meta
}

// Callback si el cliente pide cancelar la acción
bool cancelCallback() {
  Serial.println("El cliente ha solicitado cancelar la navegación.");
  return true; // Aceptamos la cancelación
}

// Objeto ActionServer (Falta implementarlo en Entity.h)
// Pasamos los callbacks principales en la inicialización
ActionServer<custom_msgs::action::Navegar> action_navegar("navegar_a_punto", goalCallback, cancelCallback);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  micro_ros.setWiFiTransport("192.168.1.11", 8888, "MI_RED", "MI_PASS");
  micro_ros.setErrorCallback(onMicroRosError);
  
  if (micro_ros.begin()) {
    node.add(action_navegar);
    micro_ros.add(node);
  }
}

void loop() {
  delay(10);
  micro_ros.spin(100);
  
  // Lógica ficticia para publicar el "Feedback" de la acción mientras está activa
  if (action_navegar.isActive()) {
    custom_msgs::action::Navegar::Feedback feedback;
    feedback.distancia_restante = 5.0; // valor calculado de tus sensores
    action_navegar.publishFeedback(feedback);
    
    // Si llegamos a la meta, enviamos el resultado (Result)
    if (feedback.distancia_restante <= 0.1) {
      custom_msgs::action::Navegar::Result resultado;
      resultado.exito = true;
      action_navegar.succeed(resultado);
    }
  }
}