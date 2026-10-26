#ifndef MICROROS_SERVICES_H
#define MICROROS_SERVICES_H

#include <micro_ros_arduino.h>
#include "Messages.h"
#include <std_srvs/srv/set_bool.h>
#include <std_srvs/srv/trigger.h>

namespace std_srvs {
  namespace srv {
    
    // --- SetBool Service ---
    class SetBool_Request : public MessageWrapper {
    public:
      SetBool_Request(bool data = false) { req_.data = data; }
      bool getData() const { return req_.data; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_srvs, srv, SetBool_Request); }
      void* get() override { return &req_; }
    private:
      std_srvs__srv__SetBool_Request req_;
    };

    class SetBool_Response : public MessageWrapper {
    public:
      SetBool_Response() { res_.success = false; }
      void setSuccess(bool val) { res_.success = val; }
      const rosidl_message_type_support_t* getTypeSupport() override { return ROSIDL_GET_MSG_TYPE_SUPPORT(std_srvs, srv, SetBool_Response); }
      void* get() override { return &res_; }
    private:
      std_srvs__srv__SetBool_Response res_;
    };

    class SetBool {
    public:
      typedef SetBool_Request Request;
      typedef SetBool_Response Response;
      static const rosidl_service_type_support_t* getTypeSupport() {
        return ROSIDL_GET_SRV_TYPE_SUPPORT(std_srvs, srv, SetBool);
      }
    };

  }
}

#endif