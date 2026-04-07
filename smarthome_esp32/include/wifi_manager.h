#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include "sensor.h"

class WiFiManager
{
public:
  WiFiManager();
  void begin();  // 非阻塞，启动异步连接
  void update();  // 需要在loop中调用，用于异步连接和重连
  void uploadData(const SensorData& data);
  bool isConnected() const { return wifiConnected; }
  bool isConnecting() const { return connecting; }

private:
  void connectWiFi();  // 非阻塞连接尝试
  bool wifiConnected;
  bool connecting;
  unsigned long connectStartTime;
  unsigned long lastConnectAttempt;
};

#endif // WIFI_MANAGER_H

