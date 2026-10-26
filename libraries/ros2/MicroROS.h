#ifndef MICROROS_H
#define MICROROS_H

#include <Arduino.h>
#include <WiFi.h>
#include <micro_ros_arduino.h>
#include "Node.h"

#ifndef UNUSED
#define UNUSED(x) ((void)x)
#endif

// Definimos el tipo de función para el callback de error
typedef void (*ErrorCallback)(rcl_ret_t error_code, const char* context);

class MicroROS {
public:
  MicroROS();
  
  void setUSBTransport(unsigned long baud = 115200);
  void setWiFiTransport(const char* agent_ip, uint32_t agent_port, const char* ssid, const char* wpa_key);
  
  // Nueva función para registrar el callback
  void onError(ErrorCallback callback);
  
  bool begin();
  bool add(Node& node);
  void spin(unsigned long timeout_ms = 10);

  bool isConnected();
  void spinWithWatchdog();

private:
  rcl_allocator_t allocator_;
  rclc_support_t support_;
  rclc_executor_t executor_;
  bool initialized_ = false;
  
  // Puntero interno para guardar el callback
  ErrorCallback error_callback_ = nullptr;

  // Función interna para chequear errores
  bool checkError(rcl_ret_t rc, const char* context);
};

#endif