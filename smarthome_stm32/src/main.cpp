#include <Arduino.h>
#include <Wire.h>
#include <AHTxx.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_SGP40.h>

// USART2：PA2(TX), PA3(RX) - 与上位机通信
// I2C：PB6(SCL), PB7(SDA)
// LED：PC13

#define I2C_SDA PB7
#define I2C_SCL PB6
#define LED_PIN PC13
#define SERIAL2_BAUD 115200
#define I2C_CLOCK 100000
#define SAMPLE_INTERVAL 100
#define BMP280_ADDR_1 0x76
#define BMP280_ADDR_2 0x77
#define DEFAULT_TEMP 25.0
#define DEFAULT_HUMIDITY 50.0

AHTxx aht20(AHTXX_ADDRESS_X38, AHT2x_SENSOR);
Adafruit_BMP280 bmp280(&Wire);
Adafruit_SGP40 sgp40;

bool aht20_ok = false;
bool bmp280_ok = false;
bool sgp40_ok = false;

struct SensorData {
  float temperature = NAN;
  float humidity = NAN;
  float pressure = NAN;
  int32_t voc = -1;
  bool valid = false;
} sensorData;

unsigned long lastSampleTime = 0;

void initSensors();
bool initAHT20();
bool initBMP280();
bool initSGP40();
void readAHT20();
void readBMP280();
void readSGP40();
void sendData();

void setup()
{
  Serial2.begin(SERIAL2_BAUD);
  pinMode(LED_PIN, OUTPUT);
  Wire.begin();
  Wire.setClock(I2C_CLOCK);
  initSensors();
  lastSampleTime = millis();
}

void loop()
{
  unsigned long currentTime = millis();
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL) {
    lastSampleTime = currentTime;
    readAHT20();
    readBMP280();
    readSGP40();
    sendData();
  }
}

void initSensors()
{
  aht20_ok = initAHT20();
  bmp280_ok = initBMP280();
  sgp40_ok = initSGP40();
}

bool initAHT20()
{
  return aht20.begin(I2C_SDA, I2C_SCL);
}

bool initBMP280()
{
  bool ok = bmp280.begin(BMP280_ADDR_1);
  if (!ok) ok = bmp280.begin(BMP280_ADDR_2);
  if (ok) {
    bmp280.setSampling(Adafruit_BMP280::MODE_NORMAL,
                       Adafruit_BMP280::SAMPLING_X2,
                       Adafruit_BMP280::SAMPLING_X16,
                       Adafruit_BMP280::FILTER_OFF,
                       Adafruit_BMP280::STANDBY_MS_500);
  }
  return ok;
}

bool initSGP40()
{
  return sgp40.begin(&Wire);
}

void readAHT20()
{
  if (!aht20_ok) return;
  float temp = aht20.readTemperature();
  float hum = aht20.readHumidity(AHTXX_USE_READ_DATA);
  if (temp != AHTXX_ERROR && hum != AHTXX_ERROR) {
    sensorData.temperature = temp;
    sensorData.humidity = hum;
    sensorData.valid = true;
  } else {
    sensorData.valid = false;
  }
}

void readBMP280()
{
  if (!bmp280_ok) return;
  float temp = bmp280.readTemperature();
  float press = bmp280.readPressure() / 100.0;
  if (!isnan(temp) && !isnan(press) && press > 0) {
    if (!aht20_ok || isnan(sensorData.temperature)) {
      sensorData.temperature = temp;
    }
    sensorData.pressure = press;
  }
}

void readSGP40()
{
  if (!sgp40_ok) return;
  float temp = sensorData.temperature;
  float hum = sensorData.humidity;
  if (isnan(temp)) {
    temp = bmp280_ok ? bmp280.readTemperature() : DEFAULT_TEMP;
  }
  if (isnan(hum)) {
    hum = DEFAULT_HUMIDITY;
  }
  temp = constrain(temp, -40.0, 85.0);
  hum = constrain(hum, 0.0, 100.0);
  sensorData.voc = sgp40.measureVocIndex(temp, hum);
}

void sendData()
{
  bool hasData = false;
  
  if (aht20_ok && sensorData.valid) {
    Serial2.print(F("T:"));
    Serial2.print(sensorData.temperature, 1);
    Serial2.print(F(",H:"));
    Serial2.print(sensorData.humidity, 1);
    Serial2.print(F(","));
    hasData = true;
  }
  
  if (bmp280_ok && !isnan(sensorData.pressure)) {
    if (!hasData || isnan(sensorData.temperature)) {
      Serial2.print(F("T:"));
      Serial2.print(sensorData.temperature, 1);
      Serial2.print(F(","));
    }
    Serial2.print(F("P:"));
    Serial2.print(sensorData.pressure, 1);
    Serial2.print(F(","));
    hasData = true;
  }
  
  if (sgp40_ok && sensorData.voc >= 0) {
    Serial2.print(F("VOC:"));
    Serial2.print(sensorData.voc);
    Serial2.print(F(","));
    hasData = true;
  }
  
  if (hasData) {
    Serial2.println();
  }
}
