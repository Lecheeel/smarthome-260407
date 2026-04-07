#include "openmv_manager.h"

// Base64编码表
static const char base64_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

OpenMVManager::OpenMVManager() : SerialOpenMV(1), lastReceiveTime(0), binaryBuffer(nullptr), binaryBufferSize(0), isBinary(false), multiLineStartTime(0), binaryStartTime(0)
{
  binaryBuffer = (uint8_t*)malloc(OPENMV_MAX_BINARY_SIZE);
  if (binaryBuffer == nullptr)
  {
    Serial.println("[OpenMV] ERROR: Failed to allocate binary buffer!");
  }
}

void OpenMVManager::begin()
{
  SerialOpenMV.begin(OPENMV_BAUD, SERIAL_8N1, OPENMV_RX_PIN, OPENMV_TX_PIN);
  Serial.println("[OpenMV] HardwareSerial (Serial1) initialized on RX=" + String(OPENMV_RX_PIN) + ", TX=" + String(OPENMV_TX_PIN) + ", Baud=" + String(OPENMV_BAUD));
}

void OpenMVManager::update()
{
  // 接收OpenMV数据
  while (SerialOpenMV.available())
  {
    uint8_t c = SerialOpenMV.read();
    
    // 检测是否为二进制数据（JPEG图片通常以0xFF 0xD8开头）
    if (!isBinary && receiveBuffer.length() == 0 && c == 0xFF)
    {
      // 可能是JPEG文件头，先保存这个字节
      receiveBuffer += (char)c;
      binaryStartTime = millis();
      continue;
    }
    
    if (!isBinary && receiveBuffer.length() == 1 && receiveBuffer[0] == 0xFF && c == 0xD8)
    {
      // 确认是JPEG文件头，切换到二进制模式
      isBinary = true;
      binaryBufferSize = 0;
      if (binaryBuffer != nullptr)
      {
        binaryBuffer[binaryBufferSize++] = 0xFF;
        binaryBuffer[binaryBufferSize++] = 0xD8;
      }
      receiveBuffer = "";
      lastReceiveTime = millis();
      Serial.println("[OpenMV] Detected JPEG image data, switching to binary mode");
      continue;
    }
    
    if (isBinary)
    {
      // 二进制模式：直接保存到二进制缓冲区
      if (binaryBuffer != nullptr && binaryBufferSize < OPENMV_MAX_BINARY_SIZE)
      {
        binaryBuffer[binaryBufferSize++] = c;
        lastReceiveTime = millis();
        
        // 检测JPEG结束标记（0xFF 0xD9）
        if (binaryBufferSize >= 2 && 
            binaryBuffer[binaryBufferSize - 2] == 0xFF && 
            binaryBuffer[binaryBufferSize - 1] == 0xD9)
        {
          // JPEG数据接收完成
          Serial.print("[OpenMV] JPEG image data complete, size: ");
          Serial.println(binaryBufferSize);
          
          String base64Data = base64Encode(binaryBuffer, binaryBufferSize);
          responseBuffer = "IMAGE_BASE64:" + base64Data;
          Serial.print("[OpenMV] Base64 encoded size: ");
          Serial.println(base64Data.length());
          
          isBinary = false;
          binaryBufferSize = 0;
        }
      }
      else if (binaryBufferSize >= OPENMV_MAX_BINARY_SIZE)
      {
        Serial.println("[OpenMV] WARNING: Binary buffer overflow!");
        // 处理已接收的数据
        String base64Data = base64Encode(binaryBuffer, binaryBufferSize);
        responseBuffer = "IMAGE_BASE64:" + base64Data;
        isBinary = false;
        binaryBufferSize = 0;
      }
    }
    else
    {
      // 文本模式：正常处理
      receiveBuffer += (char)c;
      lastReceiveTime = millis();

      // 当收到换行符时，处理完整消息
      if (c == '\n' || c == '\r')
      {
        receiveBuffer.trim();
        if (receiveBuffer.length() > 0)
        {
          // 检查是否为二进制数据（包含不可打印字符）
          if (isBinaryData(receiveBuffer))
          {
            // 切换到二进制模式
            isBinary = true;
            binaryBufferSize = 0;
            if (binaryBuffer != nullptr)
            {
              for (size_t i = 0; i < receiveBuffer.length() && binaryBufferSize < OPENMV_MAX_BINARY_SIZE; i++)
              {
                binaryBuffer[binaryBufferSize++] = (uint8_t)receiveBuffer[i];
              }
            }
            receiveBuffer = "";
            multiLineBuffer = "";  // 清空多行缓冲区
            multiLineStartTime = 0;
            binaryStartTime = millis();
            Serial.println("[OpenMV] Detected binary data, switching to binary mode");
          }
          else
          {
            // 使用 Serial.write() 直接输出原始字节，避免字符编码问题
            Serial.print("[OpenMV] ");
            Serial.write((const uint8_t*)receiveBuffer.c_str(), receiveBuffer.length());
            Serial.println();
            
            // 检测是否为进度消息（需要立即发送）
            if (isProgressMessage(receiveBuffer))
            {
              // 进度消息立即发送，不等待超时
              responseBuffer = receiveBuffer;
              Serial.println("[OpenMV] Progress message detected, moved to responseBuffer");
              receiveBuffer = "";
              lastReceiveTime = millis();
              // 不清空 multiLineBuffer，保留之前的消息
            }
            else
            {
              // 将当前行添加到多行缓冲区，等待更多行
              if (multiLineBuffer.length() > 0)
              {
                multiLineBuffer += "\n";
              }
              multiLineBuffer += receiveBuffer;
              
              // 记录多行数据开始时间（如果这是第一行）
              if (multiLineStartTime == 0)
              {
                multiLineStartTime = millis();
              }
              
              receiveBuffer = "";
              lastReceiveTime = millis();  // 更新最后接收时间
            }
          }
        }
        else
        {
          receiveBuffer = "";
        }
      }
    }
  }

  // 二进制数据超时处理（如果数据没有以JPEG结束标记结束）
  if (isBinary && binaryBufferSize > 0)
  {
    unsigned long now = millis();
    if (now - lastReceiveTime > OPENMV_BINARY_TIMEOUT)
    {
      // 超时，处理已接收的二进制数据（可能数据不完整，但仍发送）
      Serial.print("[OpenMV] Binary data timeout (may be incomplete), size: ");
      Serial.println(binaryBufferSize);
      
      if (binaryBuffer != nullptr && binaryBufferSize > 0)
      {
        String base64Data = base64Encode(binaryBuffer, binaryBufferSize);
        responseBuffer = "IMAGE_BASE64:" + base64Data;
        Serial.print("[OpenMV] Base64 encoded size: ");
        Serial.println(base64Data.length());
      }
      
      isBinary = false;
      binaryBufferSize = 0;
    }
  }

  // 检查多行缓冲区超时，如果超时则将其移到响应缓冲区
  if (!isBinary && multiLineBuffer.length() > 0)
  {
    unsigned long now = millis();
    // 如果距离最后接收时间超过多行超时时间，认为多行响应完成
    if (now - lastReceiveTime > OPENMV_MULTILINE_TIMEOUT)
    {
      // 将多行数据移到响应缓冲区
      responseBuffer = multiLineBuffer;
      multiLineBuffer = "";
      multiLineStartTime = 0;
      Serial.println("[OpenMV] Multi-line response complete");
    }
  }

  // 文本数据超时清空缓冲区（防止缓冲区溢出）
  if (!isBinary && receiveBuffer.length() > 0 && (millis() - lastReceiveTime > OPENMV_RECEIVE_TIMEOUT))
  {
    if (receiveBuffer.length() > 0)
    {
      // 检查是否为二进制数据
      if (isBinaryData(receiveBuffer))
      {
        // 切换到二进制模式
        isBinary = true;
        binaryBufferSize = 0;
        if (binaryBuffer != nullptr)
        {
          for (size_t i = 0; i < receiveBuffer.length() && binaryBufferSize < OPENMV_MAX_BINARY_SIZE; i++)
          {
            binaryBuffer[binaryBufferSize++] = (uint8_t)receiveBuffer[i];
          }
        }
        receiveBuffer = "";
        multiLineBuffer = "";  // 清空多行缓冲区
        multiLineStartTime = 0;
        binaryStartTime = millis();
      }
      else
      {
        // 使用 Serial.write() 直接输出原始字节，避免字符编码问题
        Serial.print("[OpenMV] ");
        Serial.write((const uint8_t*)receiveBuffer.c_str(), receiveBuffer.length());
        Serial.println();
        
        // 将当前行添加到多行缓冲区
        if (multiLineBuffer.length() > 0)
        {
          multiLineBuffer += "\n";
        }
        multiLineBuffer += receiveBuffer;
        
        // 如果多行缓冲区有内容，立即移到响应缓冲区（超时情况）
        if (multiLineBuffer.length() > 0)
        {
          responseBuffer = multiLineBuffer;
          multiLineBuffer = "";
          multiLineStartTime = 0;
        }
      }
    }
    receiveBuffer = "";
  }
}

bool OpenMVManager::hasResponse()
{
  return responseBuffer.length() > 0;
}

String OpenMVManager::getResponse()
{
  String response = responseBuffer;
  responseBuffer = "";
  isBinary = false;
  binaryBufferSize = 0;
  return response;
}

bool OpenMVManager::isBinaryResponse()
{
  return responseBuffer.startsWith("IMAGE_BASE64:");
}

void OpenMVManager::clearResponse()
{
  responseBuffer = "";
  receiveBuffer = "";
  multiLineBuffer = "";
  isBinary = false;
  binaryBufferSize = 0;
  lastReceiveTime = 0;
  multiLineStartTime = 0;
  binaryStartTime = 0;
}

bool OpenMVManager::isBinaryData(const String& data)
{
  // 检查是否包含大量不可打印字符（二进制数据的特征）
  int nonPrintableCount = 0;
  for (size_t i = 0; i < data.length(); i++)
  {
    uint8_t c = (uint8_t)data[i];
    // 不可打印字符（除了常见的空白字符）
    if (c < 0x20 && c != '\n' && c != '\r' && c != '\t')
    {
      nonPrintableCount++;
    }
    // 如果不可打印字符超过10%，认为是二进制数据
    if (nonPrintableCount * 10 > (int)data.length())
    {
      return true;
    }
  }
  return false;
}

bool OpenMVManager::isJPEGHeader(const uint8_t* data, size_t len)
{
  if (len < 2) return false;
  return (data[0] == 0xFF && data[1] == 0xD8);
}

bool OpenMVManager::isProgressMessage(const String& data)
{
  // 检测是否为进度消息（需要立即发送，不等待超时）
  // 例如: "Collected: 1/20", "Collected: 2/20" 等
  if (data.startsWith("Collected:"))
  {
    return true;
  }
  
  // 检测是否为识别结果消息（需要立即发送）
  // 例如: "Recognized: fghj (5671)", "Unknown face detected" 等
  if (data.startsWith("Recognized:") || data.indexOf("Unknown face detected") >= 0)
  {
    return true;
  }
  
  return false;
}

String OpenMVManager::base64Encode(const uint8_t* data, size_t length)
{
  // 简单的Base64编码实现
  // Base64编码后的大小约为原数据的4/3倍
  String encoded = "";
  encoded.reserve(4 * ((length + 2) / 3) + 1);  // 预分配空间
  
  size_t i = 0;
  uint8_t char_array_3[3];
  uint8_t char_array_4[4];
  
  while (i < length)
  {
    char_array_3[0] = data[i++];
    char_array_3[1] = (i < length) ? data[i++] : 0;
    char_array_3[2] = (i < length) ? data[i++] : 0;
    
    char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
    char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
    char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
    char_array_4[3] = char_array_3[2] & 0x3f;
    
    encoded += base64_chars[char_array_4[0]];
    encoded += base64_chars[char_array_4[1]];
    
    if (i - 2 < length)
    {
      encoded += base64_chars[char_array_4[2]];
    }
    else
    {
      encoded += '=';
    }
    
    if (i - 1 < length)
    {
      encoded += base64_chars[char_array_4[3]];
    }
    else
    {
      encoded += '=';
    }
  }
  
  return encoded;
}

void OpenMVManager::sendCommand(const String& command)
{
  if (command.length() > 0)
  {
    // 发送命令前清空所有缓冲区，避免混入之前的响应
    receiveBuffer = "";
    multiLineBuffer = "";
    responseBuffer = "";
    multiLineStartTime = 0;
    lastReceiveTime = millis();  // 重置接收时间
    
    SerialOpenMV.print(command);
    SerialOpenMV.print("\n");  // 发送换行符作为命令结束符
    Serial.println("[OpenMV] Sent command: " + command);
  }
}
