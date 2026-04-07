#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "sensor.h"
#include "config.h"

class DisplayManager
{
public:
  DisplayManager();
  void begin();
  void update(const SensorData& data, bool wifiConnected);
  void showBootAnimation();
  bool isBootAnimationComplete() const { return bootAnimationComplete; }

private:
  void initDisplay();
  void drawRoundedRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
  void drawSensorCard(int x, int y, int w, int h, const char* label, const char* value, const char* unit, uint16_t valueColor);
  void drawModernSensorCard(int x, int y, int w, int h, const char* label, const char* value, const char* unit, uint16_t valueColor, char icon);
  void drawWiFiStatus(int x, int y, bool connected);
  void drawBatteryStatus(int x, int y);
  void drawMiniProgressBar(int x, int y, int w, int h, float value, float minVal, float maxVal, uint16_t color);
  void drawTempTrend(int x, int y, const SensorData& data);
  void drawSpinner(int centerX, int centerY, int radius, int angle, uint16_t color);
  void drawGradientBackground(uint16_t color1, uint16_t color2);
  void drawLogo(int x, int y, uint16_t color, float scale);
  void updateSensorCardValue(int x, int y, int w, int h, const char* value, const char* unit, uint16_t valueColor);  // 只更新卡片数值部分
  void drawFullScreen(const SensorData& data, bool wifiConnected);  // 绘制完整屏幕（首次或需要全屏刷新时）

  Adafruit_ST7735 tft;
  unsigned long lastDisplayUpdate;
  bool bootAnimationComplete;
  float lastTemp;  // 用于温度趋势
  
  // 用于局部更新的上一次数据
  SensorData lastData;
  bool lastWifiConnected;
  bool firstUpdate;  // 标记是否是首次更新
  unsigned long lastTimeUpdate;  // 上次更新时间显示
};

#endif // DISPLAY_H

