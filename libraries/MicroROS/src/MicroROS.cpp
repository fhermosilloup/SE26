#include "MicroROS.h"

MicroROS::MicroROS() {}

void MicroROS::setUSBTransport(unsigned long baud) {
  Serial.begin(baud);
  set_microros_transports(); 
}

void MicroROS::setWiFiTransport(const char* agent_ip, uint32_t agent_port, const char* ssid, const char* wpa_key) {
  WiFi.begin(ssid, wpa_key);
  while (WiFi.status() != WL_CONNECTED) { delay(250); }
  set_microros_wifi_transports((char*)ssid, (char*)wpa_key, (char*)agent_ip, agent_port);
}

void MicroROS::onError(ErrorCallback callback) {
  error_callback_ = callback;
}

// Lógica para evaluar si hubo error y llamar al callback si existe
bool MicroROS::checkError(rcl_ret_t rc, const char* context) {
  if (rc != RCL_RET_OK) {
    if (error_callback_ != nullptr) {
      error_callback_(rc, context);
    }
    return false;
  }
  return true;
}

bool MicroROS::isConnected() {
    // Validar conexión WiFi
    if (WiFi.status() != WL_CONNECTED) {
      return false;
    }

    // Hacer ping al agente micro-ROS (timeout 100ms, 1 intento)
    if (rmw_uros_ping_agent(100, 1) != RMW_RET_OK) {
      return false;
    }

    return true;
  }

  void MicroROS::spinWithWatchdog() {
    static unsigned long last_check = 0;
    
    // Revisar la conexión cada 3 segundos
    if (millis() - last_check > 3000) { 
      last_check = millis();
      
      if (!isConnected()) {
        Serial.println("Enlace perdido. Reiniciando nodo...");
        delay(1000);
        ESP.restart(); // Reinicio limpio del microcontrolador
      }
    }
    
    // Continuar ejecutando callbacks si hay conexión
    rclc_executor_spin_some(&executor_, RCL_MS_TO_NS(10));
  }

bool MicroROS::begin() {
  allocator_ = rcl_get_default_allocator();
  
  rcl_ret_t rc = rclc_support_init(&support_, 0, NULL, &allocator_);
  if (!checkError(rc, "rclc_support_init")) return false;

  executor_ = rclc_executor_get_zero_initialized_executor();
  rc = rclc_executor_init(&executor_, &support_.context, 20, &allocator_);
  if (!checkError(rc, "rclc_executor_init")) return false;
  
  initialized_ = true;
  return true;
}

bool MicroROS::add(Node& node) {
  if (!initialized_) return false;
  
  rcl_ret_t rc = rclc_node_init_default(node.getRclNode(), node.getName(), node.getNamespace(), &support_);
  if (!checkError(rc, "rclc_node_init_default")) return false;

  for (Entity* entity : node.getEntities()) {
    if (!entity->init(node.getRclNode(), &support_, &executor_)) {
      // Como el init de la entidad devuelve un bool, generamos un error genérico
      checkError(RCL_RET_ERROR, "Entity init failed");
      return false;
    }
  }
  return true;
}

void MicroROS::spin(unsigned long timeout_ms) {
  if (initialized_) {
    rclc_executor_spin_some(&executor_, RCL_MS_TO_NS(timeout_ms));
  }
}