#include "uart_manager.h"

UARTManager::UARTManager() : SerialUART(2), lastReceiveTime(0), dataAvailable(false)
{
}

void UARTManager::begin()
{
  SerialUART.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
}

void UARTManager::update()
{
  // 接收UART数据
  while (SerialUART.available())
  {
    char c = SerialUART.read();
    receiveBuffer += c;
    lastReceiveTime = millis();

    if (c == '\n' || c == '\r')
    {
      receiveBuffer.trim();
      if (receiveBuffer.length() > 0)
      {
        receivedData = receiveBuffer;
        dataAvailable = true;
        receiveBuffer = "";
      }
    }
  }

  // 超时清空缓冲区
  if (receiveBuffer.length() > 0 && (millis() - lastReceiveTime > RECEIVE_TIMEOUT))
  {
    receiveBuffer = "";
  }
}

