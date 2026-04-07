#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"

class MQTTManager
{
public:
  MQTTManager();
  void begin();
  void update();
  bool isConnected();
  void checkAndPublishResponse();  // 检查OpenMV响应并发布

private:
  WiFiClient wifiClient;
  PubSubClient mqttClient;
  unsigned long lastReconnectAttempt;
  bool waitingForResponse;  // 是否正在等待OpenMV响应
  unsigned long responseStartTime;  // 开始等待响应的时间
  String pendingResponse;   // 待发送的响应内容
  String lastCommand;      // 最后发送的命令，用于判断是否需要延长超时
  
  void connect();
  void onMessage(char* topic, byte* payload, unsigned int length);
  static void onMessageCallback(char* topic, byte* payload, unsigned int length);
  void publishResponse(const String& response);  // 发布响应到MQTT
  static MQTTManager* instance;  // 静态实例指针，用于回调函数
};

#endif // MQTT_MANAGER_H
