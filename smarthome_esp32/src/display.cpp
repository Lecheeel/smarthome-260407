#include "display.h"

DisplayManager::DisplayManager() : tft(TFT_CS, TFT_DC, TFT_RST), lastDisplayUpdate(0), bootAnimationComplete(false), lastTemp(NAN), lastWifiConnected(false), firstUpdate(true), lastTimeUpdate(0)
{
  // 初始化上一次数据
  lastData.temperature = NAN;
  lastData.humidity = NAN;
  lastData.pressure = NAN;
  lastData.voc = -1;
  lastData.mq_sensor = -1;
}

void DisplayManager::begin()
{
  initDisplay();
}

void DisplayManager::initDisplay()
{
  Serial.println("初始化TFT显示屏...");
  
  // 初始化SPI（使用硬件SPI）
  tft.initR(INITR_BLACKTAB);  // 初始化ST7735芯片，使用黑色标签初始化
  tft.setRotation(1);  // 设置屏幕方向：1=顺时针旋转90度（128x160纵向显示）
  tft.fillScreen(ST7735_BLACK);  // 清屏为黑色
  
  Serial.println("TFT显示屏初始化完成");
}

// 绘制旋转加载动画
void DisplayManager::drawSpinner(int centerX, int centerY, int radius, int angle, uint16_t color)
{
  // 清除上一帧
  tft.fillCircle(centerX, centerY, radius + 2, ST7735_BLACK);

  // 计算指针位置
  float rad = angle * PI / 180.0;
  int x = centerX + cos(rad) * radius;
  int y = centerY + sin(rad) * radius;

  // 绘制旋转指针
  tft.drawLine(centerX, centerY, x, y, color);
  tft.fillCircle(x, y, 2, color);

  // 绘制外圈
  tft.drawCircle(centerX, centerY, radius, color);
}

// 绘制渐变背景
void DisplayManager::drawGradientBackground(uint16_t color1, uint16_t color2)
{
  for (int y = 0; y < 160; y++)
  {
    // 简单的线性渐变
    float ratio = (float)y / 160.0;
    uint16_t r1 = (color1 >> 11) & 0x1F;
    uint16_t g1 = (color1 >> 5) & 0x3F;
    uint16_t b1 = color1 & 0x1F;
    uint16_t r2 = (color2 >> 11) & 0x1F;
    uint16_t g2 = (color2 >> 5) & 0x3F;
    uint16_t b2 = color2 & 0x1F;

    uint16_t r = r1 + (r2 - r1) * ratio;
    uint16_t g = g1 + (g2 - g1) * ratio;
    uint16_t b = b1 + (b2 - b1) * ratio;

    uint16_t color = (r << 11) | (g << 5) | b;
    tft.drawFastHLine(0, y, 160, color);
  }
}

// 绘制Logo
void DisplayManager::drawLogo(int x, int y, uint16_t color, float scale)
{
  int centerX = x;
  int centerY = y;

  // 绘制房屋轮廓
  tft.drawLine(centerX - 8*scale, centerY + 6*scale, centerX, centerY - 6*scale, color);
  tft.drawLine(centerX, centerY - 6*scale, centerX + 8*scale, centerY + 6*scale, color);
  tft.drawLine(centerX - 8*scale, centerY + 6*scale, centerX - 8*scale, centerY + 12*scale, color);
  tft.drawLine(centerX + 8*scale, centerY + 6*scale, centerX + 8*scale, centerY + 12*scale, color);
  tft.drawLine(centerX - 8*scale, centerY + 12*scale, centerX + 8*scale, centerY + 12*scale, color);

  // 绘制门
  tft.drawRect(centerX - 2*scale, centerY + 8*scale, 4*scale, 4*scale, color);

  // 绘制窗户
  tft.drawRect(centerX - 6*scale, centerY + 2*scale, 3*scale, 3*scale, color);
  tft.drawRect(centerX + 3*scale, centerY + 2*scale, 3*scale, 3*scale, color);
}

void DisplayManager::showBootAnimation()
{
  Serial.println("显示开机动画...");

  // // 阶段1: 渐变背景动画
  // for (int i = 0; i < 160; i += 4)
  // {
  //   tft.fillRect(0, 0, i, 128, 0x001F); // 深蓝色渐变
  //   delay(15);
  // }
  // // 确保完全填充屏幕
  // tft.fillRect(0, 0, 160, 128, 0x001F);

  // delay(300);

  // // 阶段2: 旋转加载动画
  // int spinnerX = 80;
  // int spinnerY = 64;
  // int spinnerRadius = 20;

  // for (int angle = 0; angle < 360; angle += 10)
  // {
  //   drawSpinner(spinnerX, spinnerY, spinnerRadius, angle, ST7735_CYAN);
  //   delay(20);
  // }

  delay(200);

  // 阶段3: Logo动画
  tft.fillScreen(ST7735_BLACK);

  // Logo缩放动画
  for (float scale = 0.1; scale <= 1.0; scale += 0.1)
  {
    tft.fillScreen(ST7735_BLACK);
    drawLogo(80, 50, ST7735_CYAN, scale);
    delay(50);
  }

  delay(300);

  // 显示标题 - 打字机效果
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(2);
  tft.setCursor(30, 70);

  String title = "Smart Home";
  for (size_t i = 0; i < title.length(); i++)
  {
    tft.print(title[i]);
    delay(100);
  }

  delay(400);

  // 显示副标题
  tft.setTextColor(ST7735_CYAN);
  tft.setTextSize(1);
  tft.setCursor(50, 90);
  tft.print("System v2.0");

  delay(500);

  // 阶段4: 现代化进度条 (充分利用宽度)
  int progressX = 20;
  int progressY = 110;
  int progressW = 120;
  int progressH = 8;

  // 绘制进度条背景
  tft.drawRoundRect(progressX, progressY, progressW, progressH, 3, ST7735_WHITE);

  // 进度条填充动画
  for (int i = 0; i <= progressW - 4; i += 3)
  {
    tft.fillRoundRect(progressX + 2, progressY + 2, i, progressH - 4, 2, ST7735_GREEN);
    delay(25);
  }

  delay(300);

  // 显示状态信息
  tft.setTextColor(ST7735_YELLOW);
  tft.setTextSize(1);
  tft.setCursor(60, 125);
  tft.print("Starting up...");

  delay(600);

  // 清除状态信息并显示完成
  tft.fillRect(55, 123, 48, 10, ST7735_BLACK);
  tft.setTextColor(ST7735_GREEN);
  tft.setCursor(70, 125);
  tft.print("Ready!");

  delay(800);

  // 阶段5: 优雅淡出
  for (int alpha = 0; alpha < 255; alpha += 25)
  {
    // 创建淡出效果（简化版）
    tft.fillScreen(ST7735_BLACK);
    delay(30);
  }

  bootAnimationComplete = true;
  Serial.println("开机动画完成");
}

// 绘制圆角矩形（简化版，用小的圆角效果）
void DisplayManager::drawRoundedRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color)
{
  // 绘制圆角（用小的矩形模拟）
  tft.drawRect(x, y, w, h, color);
  tft.drawRect(x + 1, y + 1, w - 2, h - 2, color);
}

// 绘制传感器卡片
void DisplayManager::drawSensorCard(int x, int y, int w, int h, const char* label, const char* value, const char* unit, uint16_t valueColor)
{
  // 绘制卡片背景（深色）
  tft.fillRect(x, y, w, h, ST7735_NAVY);
  // 绘制边框
  tft.drawRect(x, y, w, h, ST7735_CYAN);
  
  // 显示标签
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(1);
  tft.setCursor(x + 2, y + 2);
  tft.print(label);
  
  // 显示数值
  tft.setTextColor(valueColor);
  tft.setTextSize(1);
  int valueX = x + 2;
  int valueY = y + 12;
  tft.setCursor(valueX, valueY);
  tft.print(value);
  
  // 显示单位
  if (unit != NULL)
  {
    tft.setTextColor(ST7735_WHITE);
    tft.print(unit);
  }
}

// 绘制现代化的传感器卡片
void DisplayManager::drawModernSensorCard(int x, int y, int w, int h, const char* label, const char* value, const char* unit, uint16_t valueColor, char icon)
{
  // 卡片背景 - 深色渐变效果
  tft.fillRoundRect(x, y, w, h, 4, ST7735_DARK_GRAY);

  // 边框
  tft.drawRoundRect(x, y, w, h, 4, ST7735_LIGHT_GRAY);

  // 图标区域背景 - 缩小图标区域以留出更多空间
  tft.fillRoundRect(x + 2, y + 2, 14, 14, 2, ST7735_NAVY);

  // 绘制图标
  tft.setTextColor(ST7735_CYAN);
  tft.setTextSize(1);
  tft.setCursor(x + 5, y + 4);
  tft.print(icon);

  // 标签 - 调整位置避免与图标重叠
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(1);
  tft.setCursor(x + 19, y + 3);
  // 限制标签长度避免溢出
  char labelBuf[6];
  strncpy(labelBuf, label, 5);
  labelBuf[5] = '\0';
  tft.print(labelBuf);

  // 数值 - 分行显示，增加间距
  tft.setTextColor(valueColor);
  tft.setTextSize(1);
  tft.setCursor(x + 19, y + 15);
  // 限制数值长度
  char valueBuf[8];
  strncpy(valueBuf, value, 7);
  valueBuf[7] = '\0';
  tft.print(valueBuf);

  // 单位 - 在数值下一行显示
  if (unit != NULL && strlen(unit) > 0)
  {
    tft.setTextColor(ST7735_LIGHT_GRAY);
    tft.setCursor(x + 19, y + 25);
    tft.print(unit);
  }
}

// 绘制WiFi状态指示器
void DisplayManager::drawWiFiStatus(int x, int y, bool connected)
{
  if (connected)
  {
    // 绘制WiFi信号强度图标
    tft.drawLine(x, y + 8, x, y + 10, ST7735_GREEN);
    tft.drawLine(x - 2, y + 6, x + 2, y + 6, ST7735_GREEN);
    tft.drawLine(x - 4, y + 4, x + 4, y + 4, ST7735_GREEN);
    tft.drawLine(x - 6, y + 2, x + 6, y + 2, ST7735_GREEN);
  }
}

// 绘制电池状态指示器
void DisplayManager::drawBatteryStatus(int x, int y)
{
  // 电池外壳
  tft.drawRect(x, y + 2, 12, 6, ST7735_WHITE);
  tft.drawRect(x + 12, y + 4, 2, 2, ST7735_WHITE);

  // 电池电量（模拟）
  tft.fillRect(x + 1, y + 3, 8, 4, ST7735_GREEN);
  tft.fillRect(x + 9, y + 3, 2, 4, ST7735_GREEN);
}

// 绘制迷你进度条
void DisplayManager::drawMiniProgressBar(int x, int y, int w, int h, float value, float minVal, float maxVal, uint16_t color)
{
  // 进度条背景
  tft.fillRoundRect(x, y, w, h, 2, ST7735_DARK_GRAY);

  // 计算进度
  float progress = (value - minVal) / (maxVal - minVal);
  if (progress < 0) progress = 0;
  if (progress > 1) progress = 1;

  int fillWidth = (int)(progress * (w - 2));

  // 绘制进度条
  if (fillWidth > 0)
  {
    tft.fillRoundRect(x + 1, y + 1, fillWidth, h - 2, 1, color);
  }
}

// 绘制温度趋势指示器
void DisplayManager::drawTempTrend(int x, int y, const SensorData& data)
{
  static int trend = 0; // -1:下降, 0:稳定, 1:上升

  if (!isnan(data.temperature) && !isnan(lastTemp))
  {
    if (data.temperature > lastTemp + 0.5) trend = 1;
    else if (data.temperature < lastTemp - 0.5) trend = -1;
    else trend = 0;
  }

  lastTemp = data.temperature;

  // 绘制趋势箭头
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(1);
  tft.setCursor(x, y);

  if (trend == 1) tft.print("↑");
  else if (trend == -1) tft.print("↓");
  else tft.print("→");
}

// 只更新传感器卡片数值部分（不清除整个卡片）
void DisplayManager::updateSensorCardValue(int x, int y, int w, int h, const char* value, const char* unit, uint16_t valueColor)
{
  // 清除数值和单位区域（y+15到y+h-8，x+19到x+w-2），留出进度条空间
  tft.fillRect(x + 19, y + 15, w - 21, h - 23, ST7735_DARK_GRAY);

  // 绘制新数值
  tft.setTextColor(valueColor);
  tft.setTextSize(1);
  tft.setCursor(x + 19, y + 15);

  // 限制数值长度
  char valueBuf[8];
  strncpy(valueBuf, value, 7);
  valueBuf[7] = '\0';
  tft.print(valueBuf);

  // 显示单位（分行显示）
  if (unit != NULL && strlen(unit) > 0)
  {
    tft.setTextColor(ST7735_LIGHT_GRAY);
    tft.setCursor(x + 19, y + 25);
    tft.print(unit);
  }
}

// 绘制完整屏幕（首次或需要全屏刷新时）
void DisplayManager::drawFullScreen(const SensorData& data, bool wifiConnected)
{
  // 清屏
  tft.fillScreen(ST7735_BLACK);

  // 绘制顶部标题栏 - 现代渐变设计 (充分利用160px宽度)
  for (int i = 0; i < 22; i++)
  {
    uint16_t color = tft.color565(0, i * 4, i * 6); // 蓝色到青色的渐变
    tft.drawFastHLine(0, i, 160, color);
  }

  // 标题文字 - 优化位置避免重叠
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(1);
  tft.setCursor(48, 4);
  tft.print("Smart Home");
  tft.setCursor(58, 13);
  tft.setTextSize(1);
  tft.print("v2.0");

  // 状态指示器 (调整位置适应更大屏幕)
  drawWiFiStatus(140, 3, wifiConnected);
  drawBatteryStatus(120, 3);

  // 主内容区域 - 优化布局避免重叠
  int startY = 25;  // 增加与标题栏的间距
  int cardWidth = 49;  // 稍微调小以适应3列布局
  int cardHeight = 36; // 增加高度以容纳数值和单位分行显示
  int cardSpacingX = 3;
  int cardSpacingY = 6;  // 增加行间距

  // 第一行：温度、湿度和气压 (3列布局)
  int yPos = startY;

  // 温度卡片
  char tempStr[10];
  uint16_t tempColor = ST7735_RED;
  if (!isnan(data.temperature))
  {
    snprintf(tempStr, sizeof(tempStr), "%.1f", data.temperature);
    if (data.temperature < 10) tempColor = ST7735_BLUE;
    else if (data.temperature < 25) tempColor = ST7735_GREEN;
    else if (data.temperature < 30) tempColor = ST7735_ORANGE;
    else tempColor = ST7735_RED;
  }
  else
  {
    strcpy(tempStr, "N/A");
    tempColor = ST7735_RED;
  }
  drawModernSensorCard(2, yPos, cardWidth, cardHeight, "Temp   ", tempStr, "C", tempColor, 'T');

  // 湿度卡片
  char humStr[10];
  uint16_t humColor = ST7735_CYAN;
  if (!isnan(data.humidity))
  {
    snprintf(humStr, sizeof(humStr), "%.0f", data.humidity);
    humColor = ST7735_CYAN;
  }
  else
  {
    strcpy(humStr, "N/A");
    humColor = ST7735_RED;
  }
  drawModernSensorCard(54, yPos, cardWidth, cardHeight, "Humid", humStr, "%", humColor, 'H');

  // 气压卡片
  char pressStr[10];
  uint16_t pressColor = ST7735_GREEN;
  if (!isnan(data.pressure))
  {
    snprintf(pressStr, sizeof(pressStr), "%.0f", data.pressure);
    pressColor = ST7735_GREEN;
  }
  else
  {
    strcpy(pressStr, "N/A");
    pressColor = ST7735_RED;
  }
  drawModernSensorCard(106, yPos, cardWidth, cardHeight, "Press", pressStr, "hPa", pressColor, 'P');

  // 第一行进度条和趋势指示器 - 调整位置避免重叠
  if (!isnan(data.temperature))
  {
    // 趋势指示器放在卡片右上角，避免与数值重叠
    drawTempTrend(2 + cardWidth - 10, yPos + 3, data);
    drawMiniProgressBar(2, yPos + cardHeight - 5, cardWidth, 3, data.temperature, 0, 40, tempColor);
  }
  if (!isnan(data.humidity))
  {
    drawMiniProgressBar(54, yPos + cardHeight - 5, cardWidth, 3, data.humidity, 0, 100, humColor);
  }
  if (!isnan(data.pressure))
  {
    drawMiniProgressBar(106, yPos + cardHeight - 5, cardWidth, 3, data.pressure, 950, 1050, pressColor);
  }

  yPos += cardHeight + cardSpacingY;

  // 第二行：VOC和MQ传感器 (2列布局，居中)
  int secondRowWidth = cardWidth * 2 + cardSpacingX;
  int secondRowStartX = (160 - secondRowWidth) / 2;
  int secondRowY = yPos;

  // VOC卡片
  char vocStr[10];
  uint16_t vocColor = ST7735_YELLOW;
  if (data.voc >= 0)
  {
    snprintf(vocStr, sizeof(vocStr), "%d", data.voc);
    if (data.voc < 100) vocColor = ST7735_GREEN;
    else if (data.voc < 200) vocColor = ST7735_YELLOW;
    else vocColor = ST7735_RED;
  }
  else
  {
    strcpy(vocStr, "N/A");
    vocColor = ST7735_RED;
  }
  drawModernSensorCard(secondRowStartX, yPos, cardWidth, cardHeight, "VOC", vocStr, "", vocColor, 'V');

  // MQ传感器卡片
  char mqStr[10];
  uint16_t mqColor = ST7735_PURPLE;
  if (data.mq_sensor >= 0)
  {
    snprintf(mqStr, sizeof(mqStr), "%d", data.mq_sensor);
    int mqPercent = (data.mq_sensor * 100) / 4095;
    if (mqPercent < 30) mqColor = ST7735_GREEN;
    else if (mqPercent < 60) mqColor = ST7735_YELLOW;
    else mqColor = ST7735_RED;
  }
  else
  {
    strcpy(mqStr, "N/A");
    mqColor = ST7735_RED;
  }
  drawModernSensorCard(secondRowStartX + cardWidth + cardSpacingX, yPos, cardWidth, cardHeight, "Air Q", mqStr, "", mqColor, 'A');

  // 第二行进度条
  if (data.voc >= 0)
  {
    drawMiniProgressBar(secondRowStartX, yPos + cardHeight - 5, cardWidth, 3, data.voc, 0, 500, vocColor);
  }
  if (data.mq_sensor >= 0)
  {
    drawMiniProgressBar(secondRowStartX + cardWidth + cardSpacingX, yPos + cardHeight - 5, cardWidth, 3, data.mq_sensor, 0, 4095, mqColor);
  }

  // 底部状态栏 - 优化位置和布局，分两行显示避免重叠
  int bottomY = 110;  // 调整位置避免与第二行重叠
  tft.fillRect(0, bottomY, 160, 20, ST7735_NAVY);

  // 装饰线
  tft.drawFastHLine(0, bottomY, 160, ST7735_CYAN);

  // 第一行：运行时间和连接状态
  tft.setTextColor(ST7735_WHITE);
  tft.setTextSize(1);
  tft.setCursor(2, bottomY + 3);

  unsigned long runtime = millis() / 1000;
  int hours = runtime / 3600;
  int minutes = (runtime % 3600) / 60;
  int seconds = runtime % 60;
  char timeStr[10];
  snprintf(timeStr, sizeof(timeStr), "%02d:%02d:%02d", hours, minutes, seconds);
  tft.print(timeStr);

  // 连接状态 - 调整位置
  tft.setCursor(70, bottomY + 3);
  if (wifiConnected)
  {
    tft.setTextColor(ST7735_GREEN);
    tft.print("WiFi");
  }
  else
  {
    tft.setTextColor(ST7735_RED);
    tft.print("Off");
  }

  // 第二行：传感器状态指示器
  int sensorCount = 0;
  if (!isnan(data.temperature)) sensorCount++;
  if (!isnan(data.humidity)) sensorCount++;
  if (!isnan(data.pressure)) sensorCount++;
  if (data.voc >= 0) sensorCount++;
  if (data.mq_sensor >= 0) sensorCount++;

  tft.setTextColor(ST7735_CYAN);
  tft.setCursor(2, bottomY + 12);
  tft.printf("Sensors: %d/5", sensorCount);
  
  // 右侧显示状态
  tft.setTextColor(ST7735_GREEN);
  tft.setCursor(110, bottomY + 12);
  tft.print("OK");
}

// 局部更新函数（只更新变化的部分）
void DisplayManager::update(const SensorData& data, bool wifiConnected)
{
  // 首次更新或需要全屏刷新时，绘制完整屏幕
  if (firstUpdate)
  {
    drawFullScreen(data, wifiConnected);
    lastData = data;
    lastWifiConnected = wifiConnected;
    firstUpdate = false;
    lastTimeUpdate = millis();
    return;
  }

  // 定义卡片位置常量
  const int startY = 25;
  const int cardWidth = 49;
  const int cardHeight = 36;
  const int cardSpacingX = 3;
  const int cardSpacingY = 6;
  const int yPos = startY;
  const int secondRowWidth = cardWidth * 2 + cardSpacingX;
  const int secondRowStartX = (160 - secondRowWidth) / 2;
  const int secondRowY = startY + cardHeight + cardSpacingY;
  const int bottomY = 110;

  // 检查并更新温度卡片
  bool tempChanged = (isnan(data.temperature) != isnan(lastData.temperature)) ||
                     (!isnan(data.temperature) && !isnan(lastData.temperature) && 
                      abs(data.temperature - lastData.temperature) >= 0.1);
  if (tempChanged)
  {
    char tempStr[10];
    uint16_t tempColor = ST7735_RED;
    if (!isnan(data.temperature))
    {
      snprintf(tempStr, sizeof(tempStr), "%.1f", data.temperature);
      if (data.temperature < 10) tempColor = ST7735_BLUE;
      else if (data.temperature < 25) tempColor = ST7735_GREEN;
      else if (data.temperature < 30) tempColor = ST7735_ORANGE;
      else tempColor = ST7735_RED;
    }
    else
    {
      strcpy(tempStr, "");
      tempColor = ST7735_RED;
    }
    updateSensorCardValue(2, yPos, cardWidth, cardHeight, tempStr, "C", tempColor);
    
    // 更新进度条
    if (!isnan(data.temperature))
    {
      drawMiniProgressBar(2, yPos + cardHeight - 5, cardWidth, 3, data.temperature, 0, 40, tempColor);
      drawTempTrend(2 + cardWidth - 10, yPos + 3, data);
    }
  }

  // 检查并更新湿度卡片
  bool humChanged = (isnan(data.humidity) != isnan(lastData.humidity)) ||
                    (!isnan(data.humidity) && !isnan(lastData.humidity) && 
                     abs(data.humidity - lastData.humidity) >= 1.0);
  if (humChanged)
  {
    char humStr[10];
    uint16_t humColor = ST7735_CYAN;
    if (!isnan(data.humidity))
    {
      snprintf(humStr, sizeof(humStr), "%.0f", data.humidity);
      humColor = ST7735_CYAN;
    }
    else
    {
      strcpy(humStr, "N/A");
      humColor = ST7735_RED;
    }
    updateSensorCardValue(54, yPos, cardWidth, cardHeight, humStr, "%", humColor);
    
    // 更新进度条
    if (!isnan(data.humidity))
    {
      drawMiniProgressBar(54, yPos + cardHeight - 5, cardWidth, 3, data.humidity, 0, 100, humColor);
    }
  }

  // 检查并更新气压卡片
  bool pressChanged = (isnan(data.pressure) != isnan(lastData.pressure)) ||
                      (!isnan(data.pressure) && !isnan(lastData.pressure) && 
                       abs(data.pressure - lastData.pressure) >= 1.0);
  if (pressChanged)
  {
    char pressStr[10];
    uint16_t pressColor = ST7735_GREEN;
    if (!isnan(data.pressure))
    {
      snprintf(pressStr, sizeof(pressStr), "%.0f", data.pressure);
      pressColor = ST7735_GREEN;
    }
    else
    {
      strcpy(pressStr, "N/A");
      pressColor = ST7735_RED;
    }
    updateSensorCardValue(106, yPos, cardWidth, cardHeight, pressStr, "hPa", pressColor);
    
    // 更新进度条
    if (!isnan(data.pressure))
    {
      drawMiniProgressBar(106, yPos + cardHeight - 5, cardWidth, 3, data.pressure, 950, 1050, pressColor);
    }
  }

  // 检查并更新VOC卡片
  bool vocChanged = (data.voc != lastData.voc);
  if (vocChanged)
  {
    char vocStr[10];
    uint16_t vocColor = ST7735_YELLOW;
    if (data.voc >= 0)
    {
      snprintf(vocStr, sizeof(vocStr), "%d", data.voc);
      if (data.voc < 100) vocColor = ST7735_GREEN;
      else if (data.voc < 200) vocColor = ST7735_YELLOW;
      else vocColor = ST7735_RED;
    }
    else
    {
      strcpy(vocStr, "N/A");
      vocColor = ST7735_RED;
    }
    updateSensorCardValue(secondRowStartX, secondRowY, cardWidth, cardHeight, vocStr, "", vocColor);
    
    // 更新进度条
    if (data.voc >= 0)
    {
      drawMiniProgressBar(secondRowStartX, secondRowY + cardHeight - 5, cardWidth, 3, data.voc, 0, 500, vocColor);
    }
  }

  // 检查并更新MQ传感器卡片
  bool mqChanged = (data.mq_sensor != lastData.mq_sensor);
  if (mqChanged)
  {
    char mqStr[10];
    uint16_t mqColor = ST7735_PURPLE;
    if (data.mq_sensor >= 0)
    {
      snprintf(mqStr, sizeof(mqStr), "%d", data.mq_sensor);
      int mqPercent = (data.mq_sensor * 100) / 4095;
      if (mqPercent < 30) mqColor = ST7735_GREEN;
      else if (mqPercent < 60) mqColor = ST7735_YELLOW;
      else mqColor = ST7735_RED;
    }
    else
    {
      strcpy(mqStr, "N/A");
      mqColor = ST7735_RED;
    }
    updateSensorCardValue(secondRowStartX + cardWidth + cardSpacingX, secondRowY, cardWidth, cardHeight, mqStr, "", mqColor);
    
    // 更新进度条
    if (data.mq_sensor >= 0)
    {
      drawMiniProgressBar(secondRowStartX + cardWidth + cardSpacingX, secondRowY + cardHeight - 5, cardWidth, 3, data.mq_sensor, 0, 4095, mqColor);
    }
  }

  // 更新WiFi状态（如果变化）
  if (wifiConnected != lastWifiConnected)
  {
    // 清除WiFi状态区域
    tft.fillRect(140, 3, 20, 10, ST7735_BLACK);
    // 重新绘制渐变背景（如果需要）
    for (int i = 3; i < 13; i++)
    {
      uint16_t color = tft.color565(0, i * 4, i * 6);
      tft.drawFastHLine(140, i, 20, color);
    }
    drawWiFiStatus(140, 3, wifiConnected);
    
    // 更新底部WiFi状态文字
    tft.fillRect(70, bottomY + 3, 30, 8, ST7735_NAVY);
    tft.setCursor(70, bottomY + 3);
    if (wifiConnected)
    {
      tft.setTextColor(ST7735_GREEN);
      tft.print("WiFi");
    }
    else
    {
      tft.setTextColor(ST7735_RED);
      tft.print("Off");
    }
  }

  // 每秒更新一次运行时间
  if (millis() - lastTimeUpdate >= 1000)
  {
    tft.fillRect(2, bottomY + 3, 60, 8, ST7735_NAVY);
    tft.setTextColor(ST7735_WHITE);
    tft.setTextSize(1);
    tft.setCursor(2, bottomY + 3);
    
    unsigned long runtime = millis() / 1000;
    int hours = runtime / 3600;
    int minutes = (runtime % 3600) / 60;
    int seconds = runtime % 60;
    char timeStr[10];
    snprintf(timeStr, sizeof(timeStr), "%02d:%02d:%02d", hours, minutes, seconds);
    tft.print(timeStr);
    
    lastTimeUpdate = millis();
  }

  // 更新传感器计数（如果变化）
  int sensorCount = 0;
  if (!isnan(data.temperature)) sensorCount++;
  if (!isnan(data.humidity)) sensorCount++;
  if (!isnan(data.pressure)) sensorCount++;
  if (data.voc >= 0) sensorCount++;
  if (data.mq_sensor >= 0) sensorCount++;
  
  int lastSensorCount = 0;
  if (!isnan(lastData.temperature)) lastSensorCount++;
  if (!isnan(lastData.humidity)) lastSensorCount++;
  if (!isnan(lastData.pressure)) lastSensorCount++;
  if (lastData.voc >= 0) lastSensorCount++;
  if (lastData.mq_sensor >= 0) lastSensorCount++;
  
  if (sensorCount != lastSensorCount)
  {
    tft.fillRect(2, bottomY + 12, 50, 8, ST7735_NAVY);
    tft.setTextColor(ST7735_CYAN);
    tft.setCursor(2, bottomY + 12);
    tft.printf("Sensors: %d/5", sensorCount);
  }

  // 保存当前数据
  lastData = data;
  lastWifiConnected = wifiConnected;
}

