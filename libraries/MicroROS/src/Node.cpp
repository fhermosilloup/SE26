#include "Node.h"

Node::Node(const char* name, const char* namespace_) {
  strncpy(node_name_, name, sizeof(node_name_) - 1);
  strncpy(node_ns_, namespace_, sizeof(node_ns_) - 1);
}

bool Node::add(Entity* entity) {
  if (entity) {
    entities_.push_back(entity);
    return true;
  }
  return false;
}