#include <MicroROS.h>

#define LED_PIN 13

MicroROS micro_ros;
Node node("nodo_suscriptor");

// Función de manejo de errores
void onMicroRosError(rcl_ret_t error_code, const char* context) {
  Serial.printf("Error en micro-ROS [%d]: %s\n", error_code, context);
  while(true) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(100);
  }
}

// Callback del Subscriber
void ledCallback(std_msgs::msg::Bool& msg) {
  digitalWrite(LED_PIN, msg.get() ? HIGH : LOW);
  Serial.println(msg.get() ? "LED Encendido" : "LED Apagado");
}

Subscriber<std_msgs::msg::Bool> sub_led("estado_led", ledCallback);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  micro_ros.setWiFiTransport("192.168.1.11", 8888, "MI_RED", "MI_PASS");
  micro_ros.setErrorCallback(onMicroRosError);
  
  if (micro_ros.begin()) {
    node.add(sub_led);
    micro_ros.add(node);
    Serial.println("Suscriptor inicializado correctamente.");
  }
}

void loop() {
  delay(10); // Cede tiempo al RTOS para mantener el WiFi vivo
  micro_ros.spin(100);
}