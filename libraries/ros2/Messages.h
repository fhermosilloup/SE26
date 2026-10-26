#ifndef MICROROS_MESSAGES_H
#define MICROROS_MESSAGES_H

#include <micro_ros_arduino.h>
#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/bool.h>
#include <geometry_msgs/msg/twist.h>
#include <geometry_msgs/msg/inertia.h>

class MessageWrapper {
public:
  virtual const rosidl_message_type_support_t* getTypeSupport() = 0;
  virtual void* getRaw() = 0;
};

namespace std_msgs {
  namespace msg {
    
    class Int32 : public MessageWrapper {
    public:
      Int32(int32_t val = 0) { msg_.data = val; }
      void set(int32_t val) { msg_.data = val; }
      int32_t get() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32); }
      void* getRaw() override { return &msg_; }
    private:
      std_msgs__msg__Int32 msg_;
    };

    class Float32 : public MessageWrapper {
    public:
      Float32(float val = 0.0f) { msg_.data = val; }
      void set(float val) { msg_.data = val; }
      float get() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32); }
      void* getRaw() override { return &msg_; }
    private:
      std_msgs__msg__Float32 msg_;
    };

    class Bool : public MessageWrapper {
    public:
      Bool(bool val = false) { msg_.data = val; }
      void set(bool val) { msg_.data = val; }
      bool get() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool); }
      void* getRaw() override { return &msg_; }
    private:
      std_msgs__msg__Bool msg_;
    };

  }
}

namespace geometry_msgs {
  namespace msg {
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
      void* getRaw() override { return &msg_; }
    private:
      geometry_msgs__msg__Twist msg_;
    };
  }
}

#endif
