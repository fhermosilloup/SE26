#ifndef MICROROS_MESSAGES_H
#define MICROROS_MESSAGES_H

#include <micro_ros_arduino.h>
#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/bool.h>

#include <geometry_msgs/msg/twist.h>
#include <geometry_msgs/msg/vector3.h>
#include <geometry_msgs/msg/pose.h>

#include <sensor_msgs/msg/imu.h>
#include <sensor_msgs/msg/battery_state.h>
#include <sensor_msgs/msg/joint_state.h>
#include <sensor_msgs/msg/camera_info.h>
#include <sensor_msgs/msg/image.h>
#include <sensor_msgs/msg/compressed_image.h>
#include <sensor_msgs/msg/laser_scan.h>

class MessageWrapper {
public:
  virtual ~MessageWrapper() = default;

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
      std_msgs__msg__Int32 msg_{};
    };

    class Float32 : public MessageWrapper {
    public:
      Float32(float val = 0.0f) { msg_.data = val; }
      void set(float val) { msg_.data = val; }
      float get() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32); }
      void* getRaw() override { return &msg_; }
    private:
      std_msgs__msg__Float32 msg_{};
    };

    class Bool : public MessageWrapper {
    public:
      Bool(bool val = false) { msg_.data = val; }
      void set(bool val) { msg_.data = val; }
      bool get() const { return msg_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool); }
      void* getRaw() override { return &msg_; }
    private:
      std_msgs__msg__Bool msg_{};
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

      geometry_msgs__msg__Vector3* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Vector3);
      }

      void* getRaw() override { return &msg_; }

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
      void* getRaw() override { return &msg_; }
    private:
      geometry_msgs__msg__Twist msg_{};
    };


    class Pose : public MessageWrapper {
      public:
        Pose() = default;

        geometry_msgs__msg__Pose* get() { return &msg_; }

        const rosidl_message_type_support_t* getTypeSupport() override {
          return ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Pose);
        }

        void* getRaw() override { return &msg_; }

      private:
        geometry_msgs__msg__Pose msg_{};
    };
  }
}

namespace sensor_msgs {
  namespace msg {
    class Imu : public MessageWrapper {
    public:
      Imu() = default;

      sensor_msgs__msg__Imu* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__Imu msg_{};
    };


    class BatteryState : public MessageWrapper {
    public:
      BatteryState() {
        initialized_ = sensor_msgs__msg__BatteryState__init(&msg_);
      }

      ~BatteryState() override {
        if (initialized_) {
          sensor_msgs__msg__BatteryState__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__BatteryState* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__BatteryState msg_{};
      bool initialized_ = false;
    };


    class JointState : public MessageWrapper {
    public:
      JointState() {
        initialized_ = sensor_msgs__msg__JointState__init(&msg_);
      }

      ~JointState() override {
        if (initialized_) {
          sensor_msgs__msg__JointState__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__JointState* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, JointState);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__JointState msg_{};
      bool initialized_ = false;
    };


    class CameraInfo : public MessageWrapper {
    public:
      CameraInfo() {
        initialized_ = sensor_msgs__msg__CameraInfo__init(&msg_);
      }

      ~CameraInfo() override {
        if (initialized_) {
          sensor_msgs__msg__CameraInfo__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__CameraInfo* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, CameraInfo);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__CameraInfo msg_{};
      bool initialized_ = false;
    };


    class Image : public MessageWrapper {
    public:
      Image() {
        initialized_ = sensor_msgs__msg__Image__init(&msg_);
      }

      ~Image() override {
        if (initialized_) {
          sensor_msgs__msg__Image__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__Image* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Image);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__Image msg_{};
      bool initialized_ = false;
    };


    class CompressedImage : public MessageWrapper {
    public:
      CompressedImage() {
        initialized_ =
          sensor_msgs__msg__CompressedImage__init(&msg_);
      }

      ~CompressedImage() override {
        if (initialized_) {
          sensor_msgs__msg__CompressedImage__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__CompressedImage* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, CompressedImage);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__CompressedImage msg_{};
      bool initialized_ = false;
    };


    class LaserScan : public MessageWrapper {
    public:
      LaserScan() {
        initialized_ = sensor_msgs__msg__LaserScan__init(&msg_);
      }

      ~LaserScan() override {
        if (initialized_) {
          sensor_msgs__msg__LaserScan__fini(&msg_);
        }
      }

      bool isInitialized() const { return initialized_; }

      sensor_msgs__msg__LaserScan* get() { return &msg_; }

      const rosidl_message_type_support_t* getTypeSupport() override {
        return ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, LaserScan);
      }

      void* getRaw() override { return &msg_; }

    private:
      sensor_msgs__msg__LaserScan msg_{};
      bool initialized_ = false;
    };
  } // namespace msg
} // namespace sensor_msgs
#endif
