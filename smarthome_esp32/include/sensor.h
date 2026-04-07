#ifndef SENSOR_H
#define SENSOR_H

#include <Arduino.h>

// 传感器数据结构
struct SensorData
{
  float temperature = NAN;
  float humidity = NAN;
  float pressure = NAN;
  int32_t voc = -1;
  int32_t mq_sensor = -1;  // MQ传感器模拟值 (0-4095)
};

class SensorManager
{
public:
  SensorManager();
  void begin();
  void update();
  void parseSensorData(const String &data);
  void readMqSensor();
  void printSensorData() const;
  SensorData getData() const { return sensorData; }

private:
  SensorData sensorData;
  float parseValue(const String &data, const char *prefix);
  unsigned long lastMqReadTime;
};

#endif // SENSOR_H

