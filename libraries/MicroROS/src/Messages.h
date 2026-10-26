#ifndef MICROROS_MESSAGES_H
#define MICROROS_MESSAGES_H

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <micro_ros_arduino.h>
#include <rosidl_runtime_c/string_functions.h>
#include <rosidl_runtime_c/primitives_sequence_functions.h>
// Standar messages
#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/bool.h>
#include <std_msgs/msg/string.h>
// Geometry messages
#include <geometry_msgs/msg/twist.h>
#include <geometry_msgs/msg/vector3.h>
#include <geometry_msgs/msg/pose.h>
// Sensor messages
#include <sensor_msgs/msg/imu.h>
#include <sensor_msgs/msg/battery_state.h>
#include <sensor_msgs/msg/joint_state.h>
#include <sensor_msgs/msg/camera_info.h>
#include <sensor_msgs/msg/image.h>
#include <sensor_msgs/msg/compressed_image.h>
#include <sensor_msgs/msg/laser_scan.h>
// Navigation messages
#include <nav_msgs/msg/grid_cells.h>
#include <nav_msgs/msg/occupancy_grid.h>
#include <nav_msgs/msg/odometry.h>
#include <nav_msgs/msg/path.h>









class MessageWrapper {
public:
  virtual const rosidl_message_type_support_t* getTypeSupport() = 0;
  virtual void* get() = 0;
  virtual ~MessageWrapper() = default;
};

namespace std_msgs {
  namespace msg {
    
    class Int32 : public MessageWrapper {
    public:
      Int32(int32_t val = 0) { msg_.data = val; }
      void setValue(int32_t val) { msg_.data = val; }
      int32_t getValue() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32); }
      void* get() override { return &msg_; }
    private:
      std_msgs__msg__Int32 msg_{};
    };

    class Float32 : public MessageWrapper {
    public:
      Float32(float val = 0.0f) { msg_.data = val; }
      void setValue(float val) { msg_.data = val; }
      float getValue() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32); }
      void* get() override { return &msg_; }
    private:
      std_msgs__msg__Float32 msg_{};
    };

    class Bool : public MessageWrapper {
    public:
      Bool(bool val = false) { msg_.data = val; }
      void setValue(bool val) { msg_.data = val; }
      bool getValue() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool); }
      void* get() override { return &msg_; }
    private:
      std_msgs__msg__Bool msg_{};
    };

    class String : public MessageWrapper {
    public:
      String() {
        initialized_ = std_msgs__msg__String__init(&msg_);
      }

      explicit String(const char* value) {
        initialized_ = std_msgs__msg__String__init(&msg_);
        if (initialized_ && value != nullptr) {
          rosidl_runtime_c__String__assign(&msg_.data, value);
        }
      }

      ~String() override {
        if (initialized_) {
          std_msgs__msg__String__fini(&msg_);
        }
      }

      bool isInitialized() const {
        return initialized_;
      }

      bool setString(const char* value) {
        if (!initialized_) return false;
        return rosidl_runtime_c__String__assign(
            &msg_.data, value != nullptr ? value : "");
      }

      const char* getString() const {
        return initialized_ ? msg_.data.data : "";
      }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String);
      }

      void* get() override {
        return &msg_;
      }

    private:
      std_msgs__msg__String msg_{};
      bool initialized_ = false;
    };

  }
}



namespace geometry_msgs {
  namespace msg {
    class Vector3 : public MessageWrapper {
    public:
      Vector3(double x = 0.0, double y = 0.0, double z = 0.0) {
        msg_.x = x;
        msg_.y = y;
        msg_.z = z;
      }

      void set(double x, double y, double z) {
        msg_.x = x;
        msg_.y = y;
        msg_.z = z;
      }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Vector3);
      }

      void* get() override { return &msg_; }

    private:
      geometry_msgs__msg__Vector3 msg_;
    };

    class Twist : public MessageWrapper {
    public:
      Twist() {
        msg_.linear.x = 0; msg_.linear.y = 0; msg_.linear.z = 0;
        msg_.angular.x = 0; msg_.angular.y = 0; msg_.angular.z = 0;
      }
      void setLinear(float x, float y = 0, float z = 0) { msg_.linear.x = x; msg_.linear.y = y; msg_.linear.z = z; }
      void setAngular(float x, float y = 0, float z = 0) { msg_.angular.x = x; msg_.angular.y = y; msg_.angular.z = z; }
      float getLinearX() const { return msg_.linear.x; }
      float getLinearY() const { return msg_.linear.y; }
      float getLinearZ() const { return msg_.linear.z; }
      float getAngularX() const { return msg_.angular.x; }
      float getAngularY() const { return msg_.angular.y; }
      float getAngularZ() const { return msg_.angular.z; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist); }
      void* get() override { return &msg_; }
    private:
      geometry_msgs__msg__Twist msg_{};
    };


    class Pose : public MessageWrapper {
    public:
      Pose() = default;

      void setPosition(double x, double y, double z) {
        msg_.position.x = x;
        msg_.position.y = y;
        msg_.position.z = z;
      }

      void setOrientation(double x, double y, double z, double w) {
        msg_.orientation.x = x;
        msg_.orientation.y = y;
        msg_.orientation.z = z;
        msg_.orientation.w = w;
      }

      double getPositionX() const { return msg_.position.x; }
      double getPositionY() const { return msg_.position.y; }
      double getPositionZ() const { return msg_.position.z; }

      double getOrientationX() const { return msg_.orientation.x; }
      double getOrientationY() const { return msg_.orientation.y; }
      double getOrientationZ() const { return msg_.orientation.z; }
      double getOrientationW() const { return msg_.orientation.w; }


      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Pose);
      }

      void* get() override { return &msg_; }

    private:
      geometry_msgs__msg__Pose msg_{};
    };
  }
}






namespace sensor_msgs {
namespace msg {
// IMU
class Imu : public MessageWrapper {
public:
  Imu() {
    initialized_ = sensor_msgs__msg__Imu__init(&msg_);
  }

  ~Imu() override {
    if (initialized_) sensor_msgs__msg__Imu__fini(&msg_);
  }

  bool isInitialized() const { return initialized_; }

  void setOrientation(double x, double y, double z, double w) {
    msg_.orientation.x = x;
    msg_.orientation.y = y;
    msg_.orientation.z = z;
    msg_.orientation.w = w;
  }

  void setAngularVelocity(double x, double y, double z) {
    msg_.angular_velocity.x = x;
    msg_.angular_velocity.y = y;
    msg_.angular_velocity.z = z;
  }

  void setLinearAcceleration(double x, double y, double z) {
    msg_.linear_acceleration.x = x;
    msg_.linear_acceleration.y = y;
    msg_.linear_acceleration.z = z;
  }

  double getOrientationX() const { return msg_.orientation.x; }
  double getOrientationY() const { return msg_.orientation.y; }
  double getOrientationZ() const { return msg_.orientation.z; }
  double getOrientationW() const { return msg_.orientation.w; }

  double getAngularVelocityX() const { return msg_.angular_velocity.x; }
  double getAngularVelocityY() const { return msg_.angular_velocity.y; }
  double getAngularVelocityZ() const { return msg_.angular_velocity.z; }

  double getLinearAccelerationX() const { return msg_.linear_acceleration.x; }
  double getLinearAccelerationY() const { return msg_.linear_acceleration.y; }
  double getLinearAccelerationZ() const { return msg_.linear_acceleration.z; }

  void setOrientationCovariance(size_t i, double v) {
    if (i < 9) msg_.orientation_covariance[i] = v;
  }

  void setAngularVelocityCovariance(size_t i, double v) {
    if (i < 9) msg_.angular_velocity_covariance[i] = v;
  }

  void setLinearAccelerationCovariance(size_t i, double v) {
    if (i < 9) msg_.linear_acceleration_covariance[i] = v;
  }

  double getOrientationCovariance(size_t i) const {
    return i < 9 ? msg_.orientation_covariance[i] : 0.0;
  }

  double getAngularVelocityCovariance(size_t i) const {
    return i < 9 ? msg_.angular_velocity_covariance[i] : 0.0;
  }

  double getLinearAccelerationCovariance(size_t i) const {
    return i < 9 ? msg_.linear_acceleration_covariance[i] : 0.0;
  }

  const rosidl_message_type_support_t* getTypeSupport() override {
    return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu);
  }

  void* get() override { return &msg_; }

private:
  sensor_msgs__msg__Imu msg_{};
  bool initialized_ = false;
};


} // namespace msg
} // namespace sensor_msgs

namespace nav_msgs {
namespace msg {

} // namespace msg
} // namespace nav_msgs
#endif