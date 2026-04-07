#include "wifi_manager.h"
#include "config.h"
#include <HTTPClient.h>

WiFiManager::WiFiManager() : wifiConnected(false), connecting(false), connectStartTime(0), lastConnectAttempt(0)
{
}

void WiFiManager::begin()
{
  // 启动异步连接，不阻塞
  connecting = true;
  connectStartTime = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("开始连接WiFi: %s (异步模式)\n", WIFI_SSID);
}

void WiFiManager::update()
{
  // 检查WiFi连接状态（非阻塞）
  if (connecting)
  {
    if (WiFi.status() == WL_CONNECTED)
    {
      wifiConnected = true;
      connecting = false;
      Serial.println("\nWiFi连接成功!");
      Serial.printf("IP地址: %s\n", WiFi.localIP().toString().c_str());
    }
    else if (millis() - connectStartTime > WIFI_CONNECT_TIMEOUT)
    {
      // 连接超时
      connecting = false;
      wifiConnected = false;
      Serial.println("\nWiFi连接超时!");
    }
  }
  else if (!wifiConnected && WiFi.status() != WL_CONNECTED)
  {
    // WiFi断开，启动异步重连
    if (millis() - lastConnectAttempt > 5000)  // 每5秒尝试一次重连
    {
      Serial.println("WiFi断开，尝试重新连接...");
      connecting = true;
      connectStartTime = millis();
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      lastConnectAttempt = millis();
    }
  }
  else if (wifiConnected && WiFi.status() != WL_CONNECTED)
  {
    // 连接状态丢失
    wifiConnected = false;
    Serial.println("WiFi连接丢失");
  }
}

void WiFiManager::uploadData(const SensorData& data)
{
  if (!wifiConnected || WiFi.status() != WL_CONNECTED)
    return;

  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/data";

  // 构建JSON数据
  String jsonData = "{";
  jsonData += "\"temperature\":" + (isnan(data.temperature) ? "null" : String(data.temperature, 1));
  jsonData += ",\"humidity\":" + (isnan(data.humidity) ? "null" : String(data.humidity, 1));
  jsonData += ",\"pressure\":" + (isnan(data.pressure) ? "null" : String(data.pressure, 1));
  jsonData += ",\"voc\":" + (data.voc < 0 ? "null" : String(data.voc));
  jsonData += ",\"mq_sensor\":" + (data.mq_sensor < 0 ? "null" : String(data.mq_sensor));
  jsonData += ",\"timestamp\":" + String(millis());
  jsonData += "}";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT);  // 设置超时时间，避免长时间阻塞

  // Serial.printf("上传数据到服务器: %s\n", url.c_str());
  int httpResponseCode = http.POST(jsonData);

  if (httpResponseCode > 0)
  {
    // Serial.printf("HTTP响应码: %d\n", httpResponseCode);
    // 不读取响应内容，减少阻塞时间（如果需要响应，可以异步处理）
    // String response = http.getString();
    // Serial.println("响应: " + response);
  }
  else
  {
    Serial.printf("HTTP请求失败，错误码: %d\n", httpResponseCode);
  }

  http.end();
}

void WiFiManager::connectWiFi()
{
  // 此函数已废弃，连接逻辑移至update()中异步处理
  // 保留函数以避免编译错误，但实际不使用
}

