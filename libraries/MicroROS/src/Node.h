#ifndef MICROROS_NODE_H
#define MICROROS_NODE_H

#include <vector>
#include "Entity.h"

class Node {
public:
  Node(const char* name, const char* namespace_ = "");
  
  bool add(Entity* entity);
  bool add(Entity& entity) { return add(&entity); }

  const char* getName() const { return node_name_; }
  const char* getNamespace() const { return node_ns_; }
  rcl_node_t* getRclNode() { return &node_; }
  std::vector<Entity*>& getEntities() { return entities_; }

private:
  char node_name_[64];
  char node_ns_[64];
  rcl_node_t node_;
  std::vector<Entity*> entities_;
};

#endif