#ifndef UART_MANAGER_H
#define UART_MANAGER_H

#include <Arduino.h>
#include "config.h"

class UARTManager
{
public:
  UARTManager();
  void begin();
  void update();
  bool hasData() const { return dataAvailable; }
  String getData() { dataAvailable = false; return receivedData; }

private:
  HardwareSerial SerialUART;
  String receiveBuffer;
  String receivedData;
  unsigned long lastReceiveTime;
  bool dataAvailable;
};

#endif // UART_MANAGER_H

