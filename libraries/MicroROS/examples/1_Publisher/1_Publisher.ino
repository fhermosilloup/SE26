#include <MicroROS.h>

#define LED_PIN 13


void onErrorCallback(rcl_ret_t error_code, const char* context) {
  Serial.printf("Error en micro-ROS [%d]: %s\n", error_code, context);
  while(true) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(100);
  }
}

MicroROS ros2;
Node node("nodo_contador");
Publisher<std_msgs::msg::Int32> pub_contador("contador");
std_msgs::msg::Int32 msg_contador;

void onTimer(rcl_timer_t* timer, int64_t last_call_time) {
  //Timer::stop(timer);
  //Timer::start(timer);
  //Timer::setPeriod(timer, 10);
  msg_contador.setValue(msg_contador.getValue() + 1);
  pub_contador.publish(msg_contador);
}
Timer timer_1sec(1000, onTimer);

void setup() {
  Serial.begin(115200);

  // Configurate microros
  ros2.onError(onErrorCallback);
  ros2.setWiFiTransport("192.168.1.11", 8888, "Megacable_2.4G_B46C", "9fdvCAE3");

  // Start service
  ros2.begin();

  // Add publisher and timer to a node
  node.add(pub_contador);
  node.add(timer_1sec);

  // Add node to microros
  ros2.add(node);
}

void loop() {
  ros2.spin(10);
}