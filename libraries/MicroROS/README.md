# MicroROSEducativo (prototipo)

Wrapper  para `micro_ros_arduino` versión Jazzy.

## API del alumno

```cpp
MicroROS ros;
Node nodo(ros, "esp32_node");

void callback(const MessageValue& msg) {
  // Leer msg.boolean, msg.int32 o msg.float32 según el tipo configurado.
}

void setup() {
  ros.setWiFiTransport("SSID", "PASSWORD", "192.168.1.11", 8888);
  nodo.addPublisher("contador", MessageType::INT32);
  nodo.addSubscriber("led", MessageType::BOOL, callback);
  if (!ros.begin()) { /* consultar ros.lastError() */ }
}
void loop() {
  nodo.publish("contador", (int32_t)123);
  ros.spinOnce(10);
}
```

## Tipos actualmente incluidos

- `MessageType::BOOL` -> `std_msgs/msg/Bool`
- `MessageType::INT32` -> `std_msgs/msg/Int32`
- `MessageType::FLOAT32` -> `std_msgs/msg/Float32`

La selección por `enum` se traduce con `switch` al `ROSIDL_GET_MSG_TYPE_SUPPORT(...)` correspondiente y a la estructura C de mensaje original.

## Instalación

Instalar desde Arduino con Install Library from zip file.

## Límites de este primer prototipo

- Un nodo por objeto `MicroROS`.
- Máximo de publishers/subscribers definido por `MICRO_ROS_MAX_PUBLISHERS` y `MICRO_ROS_MAX_SUBSCRIBERS`.
- Callback de suscripción uniforme: `void callback(const MessageValue&)`; usa el campo correspondiente al enum registrado.
- Incluye publishers, subscribers y el spin general. Servicios y acciones necesitan tipos de servicio/acción (no solo un tipo de mensaje) y se deben agregar como una extensión separada.
