#include "sensor.h"
#include "config.h"

SensorManager::SensorManager() : lastMqReadTime(0)
{
}

void SensorManager::begin()
{
  // 初始化MQ传感器引脚
  pinMode(MQ_SENSOR_PIN, INPUT);
}

void SensorManager::update()
{
  // 读取MQ传感器数据
  if (millis() - lastMqReadTime >= 100)  // 每100ms读取一次MQ传感器
  {
    readMqSensor();
    lastMqReadTime = millis();
  }
}

void SensorManager::readMqSensor()
{
  sensorData.mq_sensor = analogRead(MQ_SENSOR_PIN);
}

void SensorManager::parseSensorData(const String &data)
{
  float val;
  
  val = parseValue(data, "T:");
  if (!isnan(val))
    sensorData.temperature = val;

  val = parseValue(data, "H:");
  if (!isnan(val))
    sensorData.humidity = val;

  val = parseValue(data, "P:");
  if (!isnan(val))
    sensorData.pressure = val;

  int pos = data.indexOf("VOC:");
  if (pos >= 0)
  {
    int commaPos = data.indexOf(',', pos);
    if (commaPos > pos)
      sensorData.voc = data.substring(pos + 4, commaPos).toInt();
  }
}

float SensorManager::parseValue(const String &data, const char *prefix)
{
  int pos = data.indexOf(prefix);
  if (pos >= 0)
  {
    int commaPos = data.indexOf(',', pos);
    if (commaPos > pos)
      return data.substring(pos + 2, commaPos).toFloat();
  }
  return NAN;
}

void SensorManager::printSensorData() const
{
  Serial.println("\n=== 传感器数据 ===");

  if (!isnan(sensorData.temperature))
    Serial.printf("温度: %.1f °C\n", sensorData.temperature);
  else
    Serial.println("温度: N/A");

  if (!isnan(sensorData.humidity))
    Serial.printf("湿度: %.1f %%\n", sensorData.humidity);
  else
    Serial.println("湿度: N/A");

  if (!isnan(sensorData.pressure))
    Serial.printf("气压: %.1f hPa\n", sensorData.pressure);
  else
    Serial.println("气压: N/A");

  if (sensorData.voc >= 0)
    Serial.printf("VOC: %d\n", sensorData.voc);
  else
    Serial.println("VOC: N/A");

  if (sensorData.mq_sensor >= 0)
    Serial.printf("MQ传感器: %d\n", sensorData.mq_sensor);
  else
    Serial.println("MQ传感器: N/A");

  Serial.println("==================\n");
}

