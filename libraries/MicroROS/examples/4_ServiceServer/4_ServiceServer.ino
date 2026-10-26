#include <MicroROS.h>

MicroROS micro_ros;
Node node("nodo_led_service");

// Callback cuando llega una nueva petición
void setLedCallback(const std_srvs::srv::SetBool::Request& req, std_srvs::srv::SetBool::Response& res) {
  bool state = req.getData();
  digitalWrite(2, state ? HIGH : LOW);
  res.setSuccess(true);
}

// Objeto micro-ros2 service
ServiceServer<std_srvs::srv::SetBool> srv_led("set_led", setLedCallback);

void setup() {
  pinMode(2, OUTPUT);
  
  micro_ros.setUSBTransport(115200);
  micro_ros.begin();

  node.add(srv_led);
  micro_ros.add(node);
}

void loop() {
  micro_ros.spin(10);
}