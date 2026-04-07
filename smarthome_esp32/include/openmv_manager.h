#ifndef OPENMV_MANAGER_H
#define OPENMV_MANAGER_H

#include <Arduino.h>
#include "config.h"
#include <HardwareSerial.h>

class OpenMVManager
{
public:
  OpenMVManager();
  void begin();
  void update();
  void sendCommand(const String& command);  // 发送命令到OpenMV
  bool hasResponse();  // 检查是否有新的响应
  String getResponse();  // 获取响应并清空缓冲区（文本或Base64编码的二进制）
  bool isBinaryResponse();  // 检查响应是否为二进制数据
  void clearResponse();  // 清空响应缓冲区

private:
  HardwareSerial SerialOpenMV;
  String receiveBuffer;
  String multiLineBuffer;  // 多行数据累积缓冲区
  String responseBuffer;  // 存储完整的响应（文本或Base64编码）
  uint8_t* binaryBuffer;  // 二进制数据缓冲区
  size_t binaryBufferSize;  // 二进制数据大小
  bool isBinary;  // 是否为二进制数据
  unsigned long lastReceiveTime;
  unsigned long multiLineStartTime;  // 多行数据开始接收时间
  unsigned long binaryStartTime;  // 二进制数据开始接收时间
  
  bool isBinaryData(const String& data);  // 检测是否为二进制数据
  bool isJPEGHeader(const uint8_t* data, size_t len);  // 检测是否为JPEG文件头
  String base64Encode(const uint8_t* data, size_t length);  // Base64编码
  bool isProgressMessage(const String& data);  // 检测是否为进度消息（需要立即发送）
};

#endif // OPENMV_MANAGER_H
