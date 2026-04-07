#include <Arduino.h>
#include "config.h"
#include "sensor.h"
#include "wifi_manager.h"
#include "display.h"
#include "uart_manager.h"
#include "openmv_manager.h"
#include "mqtt_manager.h"

// 全局对象
SensorManager sensorManager;
WiFiManager wifiManager;
DisplayManager displayManager;
UARTManager uartManager;
OpenMVManager openMVManager;
MQTTManager mqttManager;

void setup()
{
  Serial.begin(115200);
  Serial.println("ESP32 Smart Home - Starting...");
  
  // 初始化UART
  uartManager.begin();
  
  // 初始化OpenMV UART
  openMVManager.begin();
  
  // 初始化传感器管理器
  sensorManager.begin();
  
  // 初始化TFT显示屏
  displayManager.begin();
  
  // 显示开机动画
  displayManager.showBootAnimation();
  
  // 连接WiFi
  wifiManager.begin();
  
  // 初始化MQTT（将在WiFi连接成功后自动连接）
  mqttManager.begin();

  Serial.println("ESP32 Smart Home - Ready");
}


void loop()
{
  // ========== WiFi连接状态更新（异步，非阻塞）==========
  wifiManager.update();  // 检查连接状态，处理异步连接和重连

  // ========== UART通信处理（异步，无定时限制）==========
  uartManager.update();
  
  // 处理接收到的UART数据（更新传感器数据结构体）
  if (uartManager.hasData())
  {
    String data = uartManager.getData();
    sensorManager.parseSensorData(data);
    // sensorManager.printSensorData();
  }

  // ========== OpenMV通信处理（异步，无定时限制，自动打印到日志）==========
  openMVManager.update();

  // ========== MQTT通信处理（异步，无定时限制）==========
  if (wifiManager.isConnected())
  {
    mqttManager.update();  // 内部会检查OpenMV响应并发布
  }

  // ========== 传感器数据更新任务（独立定时：100ms）==========
  static unsigned long lastSensorUpdate = 0;
  if (millis() - lastSensorUpdate >= SENSOR_UPDATE_INTERVAL)
  {
    sensorManager.update();  // 更新MQ传感器等数据到结构体
    lastSensorUpdate = millis();
  }

  // ========== 屏幕更新任务（独立定时：500ms，只读取结构体）==========
  if (displayManager.isBootAnimationComplete())
  {
    static unsigned long lastDisplayUpdate = 0;
    if (millis() - lastDisplayUpdate >= DISPLAY_UPDATE_INTERVAL)
    {
      // 只读取结构体数据，不调用传感器更新
      displayManager.update(sensorManager.getData(), wifiManager.isConnected());
      lastDisplayUpdate = millis();
    }
  }

  // ========== WiFi数据上传任务（独立定时：1000ms，只读取结构体）==========
  if (wifiManager.isConnected())
  {
    static unsigned long lastUploadTime = 0;
    if (millis() - lastUploadTime >= UPLOAD_INTERVAL)
    {
      // 只读取结构体数据，不调用传感器更新
      wifiManager.uploadData(sensorManager.getData());
      lastUploadTime = millis();
    }
  }

  // ========== USB串口命令处理（异步，无定时限制）==========
  if (Serial.available())
  {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "status")
      sensorManager.printSensorData();
  }
}
