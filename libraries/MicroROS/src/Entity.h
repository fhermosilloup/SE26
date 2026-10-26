#ifndef MICROROS_ENTITY_H
#define MICROROS_ENTITY_H

// #define USE_MICROROS_ACTIONS

#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#ifdef USE_MICROROS_ACTIONS
#include <rclc/action.h>
#endif
#include <rclc_parameter/rclc_parameter.h>
#include "Messages.h"
#include "Services.h"

enum class EntityType {
  PUBLISHER,
  SUBSCRIBER,
  SERVICE_SERVER,
  SERVICE_CLIENT,
  TIMER,
  #ifdef USE_MICROROS_ACTIONS
  ACTION_SERVER,
  ACTION_CLIENT,
  #endif
  PARAMETER_SERVER
};

class Entity {
public:
  virtual EntityType getType() = 0;
  virtual bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) = 0;
};

 
// TIMER WRAPPER
typedef void (*TimerCallback)(rcl_timer_t *, int64_t );

class Timer : public Entity {
public:
  Timer(uint32_t period_ms, TimerCallback cb) : period_ns_((uint64_t)period_ms * 1000000), callback_(cb) {}
  
  EntityType getType() override { return EntityType::TIMER; }

  static bool stop(rcl_timer_t* timer) {
      if (timer == nullptr && timer->impl == nullptr) return false;

      return rcl_timer_cancel(timer) == RCL_RET_OK;
  }

  static bool start(rcl_timer_t* timer) {
      if (timer == nullptr && timer->impl == nullptr) return false;

      return rcl_timer_reset(timer) == RCL_RET_OK;
  }

  static bool setPeriod(rcl_timer_t* timer, uint32_t period_ms) {
      if (timer == nullptr && timer->impl == nullptr) return false;

      uint64_t period_ns = static_cast<uint64_t>(period_ms) * 1000000ULL;

      return rcl_timer_exchange_period(timer, period_ns, nullptr) == RCL_RET_OK;
  }
  
  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    rcl_ret_t rc = rclc_timer_init_default(&timer_, support, period_ns_, this->callback_);
    if (rc != RCL_RET_OK) return false;
    
    is_initialized_ = true;
    return (rclc_executor_add_timer(executor, &timer_) == RCL_RET_OK);
  }

private:
  rcl_timer_t timer_;
  uint64_t period_ns_;
  TimerCallback callback_;
  bool is_initialized_;
};

 
// PUBLISHER WRAPPER
template <typename TMsg>
class Publisher : public Entity {
public:
  Publisher(const char* topic) : topic_name_(topic) {}
  EntityType getType() override { return EntityType::PUBLISHER; }
  
  bool publish(TMsg& msg) {
    return (rcl_publish(&pub_, msg.get(), NULL) == RCL_RET_OK);
  }
  
  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    TMsg dummy_msg;
    return (rclc_publisher_init_default(&pub_, node, dummy_msg.getTypeSupport(), topic_name_) == RCL_RET_OK);
  }

private:
  const char* topic_name_;
  rcl_publisher_t pub_;
};

 
// SUBSCRIBER WRAPPER
 
template <typename TMsg>
class Subscriber : public Entity {
public:
  typedef void (*SubCallback)(TMsg& msg);

  Subscriber(const char* topic, SubCallback cb) : topic_name_(topic), callback_(cb) {}
  EntityType getType() override { return EntityType::SUBSCRIBER; }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    static_callback = callback_;
    static_msg_obj = &msg_obj_;

    rcl_ret_t rc = rclc_subscription_init_default(&sub_, node, msg_obj_.getTypeSupport(), topic_name_);
    if (rc != RCL_RET_OK) return false;

    return (rclc_executor_add_subscription(executor, &sub_, msg_obj_.getRaw(), internalCallback, ON_NEW_DATA) == RCL_RET_OK);
  }

private:
  const char* topic_name_;
  rcl_subscription_t sub_;
  TMsg msg_obj_;
  SubCallback callback_;
  
  static SubCallback static_callback;
  static TMsg* static_msg_obj;

  static void internalCallback(const void * msgin) {
    if (static_callback && static_msg_obj) static_callback(*static_msg_obj);
  }
};

template <typename TMsg> typename Subscriber<TMsg>::SubCallback Subscriber<TMsg>::static_callback = NULL;
template <typename TMsg> TMsg* Subscriber<TMsg>::static_msg_obj = NULL;

 
// SERVICE SERVER WRAPPER
 
template <typename TSrv>
class ServiceServer : public Entity {
public:
  typedef typename TSrv::Request TReq;
  typedef typename TSrv::Response TRes;
  typedef void (*SrvCallback)(const TReq& req, TRes& res);

  ServiceServer(const char* service_name, SrvCallback cb) : service_name_(service_name), callback_(cb) {}
  EntityType getType() override { return EntityType::SERVICE_SERVER; }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    static_callback = callback_;
    static_req = &req_obj_;
    static_res = &res_obj_;

    rcl_ret_t rc = rclc_service_init_default(&srv_, node, TSrv::getTypeSupport(), service_name_);
    if (rc != RCL_RET_OK) return false;

    return (rclc_executor_add_service(executor, &srv_, req_obj_.getRaw(), res_obj_.getRaw(), internalCallback) == RCL_RET_OK);
  }

private:
  const char* service_name_;
  rcl_service_t srv_;
  TReq req_obj_;
  TRes res_obj_;
  SrvCallback callback_;

  static SrvCallback static_callback;
  static TReq* static_req;
  static TRes* static_res;

  static void internalCallback(const void * req, void * res) {
    if (static_callback) static_callback(*static_req, *static_res);
  }
};

template <typename TSrv> typename ServiceServer<TSrv>::SrvCallback ServiceServer<TSrv>::static_callback = NULL;
template <typename TSrv> typename ServiceServer<TSrv>::TReq* ServiceServer<TSrv>::static_req = NULL;
template <typename TSrv> typename ServiceServer<TSrv>::TRes* ServiceServer<TSrv>::static_res = NULL;

 
// SERVICE CLIENT WRAPPER
 
template <typename TSrv>
class ServiceClient : public Entity {
public:
  typedef typename TSrv::Request TReq;
  typedef typename TSrv::Response TRes;

  ServiceClient(const char* service_name) : service_name_(service_name) {}
  EntityType getType() override { return EntityType::SERVICE_CLIENT; }

  bool sendRequest(TReq& req) {
    int64_t seq;
    return (rcl_send_request(&client_, req.getRaw(), &seq) == RCL_RET_OK);
  }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    return (rclc_client_init_default(&client_, node, TSrv::getTypeSupport(), service_name_) == RCL_RET_OK);
  }

private:
  const char* service_name_;
  rcl_client_t client_;
};



#ifdef USE_MICROROS_ACTIONS
 
// ACTION SERVER WRAPPER
 
template <typename TAction>
class ActionServer : public Entity {
public:
  typedef typename TAction::Goal TGoal;
  typedef typename TAction::Feedback TFeedback;
  typedef typename TAction::Result TResult;

  typedef bool (*GoalCallback)(const TGoal& goal);
  typedef bool (*CancelCallback)();

  ActionServer(const char* action_name, GoalCallback goal_cb, CancelCallback cancel_cb) 
    : action_name_(action_name), goal_callback_(goal_cb), cancel_callback_(cancel_cb) {}
    
  EntityType getType() override { return EntityType::ACTION_SERVER; }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    static_goal_callback = goal_callback_;
    static_cancel_callback = cancel_callback_;
    static_server = this;

    rcl_ret_t rc = rclc_action_server_init_default(
      &action_server_, 
      node, 
      support, 
      TAction::getTypeSupport(), 
      action_name_
    );
    if (rc != RCL_RET_OK) return false;

    // Asignar memoria para los requests internos de la acción
    return (rclc_executor_add_action_server(
      executor,
      &action_server_,
      1, // número máximo de metas simultáneas
      &goal_request_,
      sizeof(TGoal),
      internalGoalCallback,
      internalCancelCallback,
      (void*)&result_request_
    ) == RCL_RET_OK);
  }

  bool isActive() {
    // Retorna true si hay un handle de meta actualmente en ejecución
    return current_goal_handle_ != NULL;
  }

  void publishFeedback(TFeedback& feedback) {
    if (current_goal_handle_ != NULL) {
      rclc_action_publish_feedback(current_goal_handle_, feedback.getRaw());
    }
  }

  void succeed(TResult& result) {
    if (current_goal_handle_ != NULL) {
      rclc_action_send_result(current_goal_handle_, HOST_ACTION_RESULT_ACCEPTED, result.getRaw());
      current_goal_handle_ = NULL;
    }
  }

private:
  const char* action_name_;
  rclc_action_server_t action_server_;
  GoalCallback goal_callback_;
  CancelCallback cancel_callback_;
  
  TGoal goal_request_;
  TResult result_request_;
  rclc_action_goal_handle_t* current_goal_handle_ = NULL;

  static GoalCallback static_goal_callback;
  static CancelCallback static_cancel_callback;
  static ActionServer<TAction>* static_server;

  static rcl_ret_t internalGoalCallback(rclc_action_goal_handle_t * goal_handle, void * ros_goal_request) {
    TGoal* goal = static_cast<TGoal*>(ros_goal_request);
    if (static_goal_callback && static_goal_callback(*goal)) {
      static_server->current_goal_handle_ = goal_handle;
      rclc_action_accept_new_goal(static_server->current_goal_handle_);
      return RCL_RET_OK;
    }
    rclc_action_reject_new_goal(goal_handle);
    return RCL_RET_ACTION_GOAL_REJECTED;
  }

  static bool internalCancelCallback(rclc_action_goal_handle_t * goal_handle) {
    (void)goal_handle;
    if (static_cancel_callback) {
      return static_cancel_callback();
    }
    return false;
  }
};

template <typename TAction> typename ActionServer<TAction>::GoalCallback ActionServer<TAction>::static_goal_callback = NULL;
template <typename TAction> typename ActionServer<TAction>::CancelCallback ActionServer<TAction>::static_cancel_callback = NULL;
template <typename TAction> ActionServer<TAction>* ActionServer<TAction>::static_server = NULL;

 
// ACTION CLIENT WRAPPER
template <typename TAction>
class ActionClient : public Entity {
public:
  typedef typename TAction::Goal TGoal;
  typedef typename TAction::Feedback TFeedback;
  typedef typename TAction::Result TResult;

  typedef void (*FeedbackCallback)(const TFeedback& feedback);
  typedef void (*ResultCallback)(const TResult& result);

  ActionClient(const char* action_name, FeedbackCallback fb_cb, ResultCallback res_cb) 
    : action_name_(action_name), feedback_callback_(fb_cb), result_callback_(res_cb) {}
    
  EntityType getType() override { return EntityType::ACTION_CLIENT; }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    static_feedback_callback = feedback_callback_;
    static_result_callback = result_callback_;

    rcl_ret_t rc = rclc_action_client_init_default(
      &action_client_, 
      node, 
      TAction::getTypeSupport(), 
      action_name_
    );
    if (rc != RCL_RET_OK) return false;

    return (rclc_executor_add_action_client(
      executor, 
      &action_client_, 
      1, 
      &result_response_, 
      &feedback_message_,
      internalGoalResponseCallback, 
      internalFeedbackCallback, 
      internalResultCallback, 
      internalCancelResponseCallback
    ) == RCL_RET_OK);
  }

  bool sendGoal(TGoal& goal) {
    return (rclc_action_send_goal_request(&action_client_, goal.getRaw(), NULL) == RCL_RET_OK);
  }

private:
  const char* action_name_;
  rclc_action_client_t action_client_;
  
  TFeedback feedback_message_;
  TResult result_response_;
  
  FeedbackCallback feedback_callback_;
  ResultCallback result_callback_;

  static FeedbackCallback static_feedback_callback;
  static ResultCallback static_result_callback;

  static void internalFeedbackCallback(void * msgin) {
    if (static_feedback_callback) {
      TFeedback* feedback = static_cast<TFeedback*>(msgin);
      static_feedback_callback(*feedback);
    }
  }

  static void internalResultCallback(void * msgin) {
    if (static_result_callback) {
      TResult* result = static_cast<TResult*>(msgin);
      static_result_callback(*result);
    }
  }

  static void internalGoalResponseCallback(void * msgin) {
    // Implementación interna mínima: aquí se sabe si el servidor aceptó el Goal.
    (void)msgin;
  }

  static void internalCancelResponseCallback(void * msgin) {
    // Implementación interna mínima: aquí se procesa si el servidor aceptó cancelar.
    (void)msgin;
  }
};

template <typename TAction> typename ActionClient<TAction>::FeedbackCallback ActionClient<TAction>::static_feedback_callback = NULL;
template <typename TAction> typename ActionClient<TAction>::ResultCallback ActionClient<TAction>::static_result_callback = NULL;

#endif



// PARAMETER SERVER WRAPPER 
class ParamServer : public Entity {
public:
  typedef bool (*ParamCallback)(const Parameter * old_param, const Parameter * new_param, void * context);

  ParamServer(ParamCallback cb) : callback_(cb) {}
    
  EntityType getType() override { return EntityType::PARAMETER_SERVER; }

  bool init(rcl_node_t* node, rclc_support_t* support, rclc_executor_t* executor) override {
    // Usamos init_default ya que las opciones avanzadas no están en tu versión
    rcl_ret_t rc = rclc_parameter_server_init_default(&param_server_, node);
    if (rc != RCL_RET_OK) return false;

    return (rclc_executor_add_parameter_server(executor, &param_server_, callback_) == RCL_RET_OK);
  }

  void addInt(const char* name, int64_t default_value) {
    rclc_add_parameter(&param_server_, name, RCLC_PARAMETER_INT);
    rclc_parameter_set_int(&param_server_, name, default_value);
  }
  
  void addBool(const char* name, bool default_value) {
    rclc_add_parameter(&param_server_, name, RCLC_PARAMETER_BOOL);
    rclc_parameter_set_bool(&param_server_, name, default_value);
  }

  void addDouble(const char* name, double default_value) {
    rclc_add_parameter(&param_server_, name, RCLC_PARAMETER_DOUBLE);
    rclc_parameter_set_double(&param_server_, name, default_value);
  }

private:
  rclc_parameter_server_t param_server_;
  ParamCallback callback_;
};

#endif