#include "mqtt_manager.h"
#include "openmv_manager.h"

// 静态成员初始化
MQTTManager* MQTTManager::instance = nullptr;

MQTTManager::MQTTManager() : mqttClient(wifiClient), lastReconnectAttempt(0), waitingForResponse(false), responseStartTime(0), lastCommand("")
{
  instance = this;  // 设置静态实例指针
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(onMessageCallback);
  mqttClient.setBufferSize(MQTT_BUFFER_SIZE);  // 设置缓冲区大小以支持Base64编码的图片数据
}

void MQTTManager::begin()
{
  // 连接将在WiFi连接成功后进行
  Serial.println("[MQTT] Manager initialized");
}

void MQTTManager::update()
{
  if (!mqttClient.connected())
  {
    unsigned long now = millis();
    if (now - lastReconnectAttempt >= MQTT_RECONNECT_INTERVAL)
    {
      lastReconnectAttempt = now;
      connect();
    }
  }
  else
  {
    mqttClient.loop();
    
    // 检查OpenMV响应
    checkAndPublishResponse();
    
    // 检查响应超时
    if (waitingForResponse)
    {
      unsigned long now = millis();
      // 如果是 COLLECT 命令，使用更长的超时时间（60秒，因为收集需要时间）
      unsigned long timeout = lastCommand.startsWith("COLLECT:") ? 60000 : MQTT_RESPONSE_TIMEOUT;
      
      if (now - responseStartTime >= timeout)
      {
        // 超时，检查是否有已收集的响应
        extern OpenMVManager openMVManager;
        if (openMVManager.hasResponse())
        {
          // 有响应但可能还没发送成功，再试一次
          String response = openMVManager.getResponse();
          Serial.println("[MQTT] Response timeout, retrying to send collected response");
          publishResponse(response);
        }
        else
        {
          // 如果是 COLLECT 命令，可能还在收集过程中，不清除 waitingForResponse
          // 继续等待进度消息
          if (lastCommand.startsWith("COLLECT:"))
          {
            Serial.println("[MQTT] COLLECT command timeout, but continuing to wait for progress messages");
            // 更新超时时间，继续等待
            responseStartTime = millis();
          }
          // 如果是 RECOGNIZE 命令，可能还在识别过程中，不清除 waitingForResponse
          // 继续等待识别结果
          else if (lastCommand == "RECOGNIZE")
          {
            Serial.println("[MQTT] RECOGNIZE command timeout, but continuing to wait for recognition results");
            // 更新超时时间，继续等待
            responseStartTime = millis();
          }
          else
          {
            // 其他命令超时，发送超时消息
            Serial.println("[MQTT] Response timeout, no response from OpenMV");
            String timeoutMsg = "TIMEOUT: No response from OpenMV";
            if (mqttClient.publish(MQTT_TOPIC_RESPONSE, timeoutMsg.c_str()))
            {
              waitingForResponse = false;
              responseStartTime = 0;
              pendingResponse = "";
              lastCommand = "";
            }
          }
        }
      }
    }
  }
}

bool MQTTManager::isConnected()
{
  return mqttClient.connected();
}

void MQTTManager::connect()
{
  // 只有在WiFi连接成功后才尝试连接MQTT
  if (WiFi.status() != WL_CONNECTED)
  {
    return;
  }

  Serial.print("[MQTT] Attempting to connect to ");
  Serial.print(MQTT_SERVER);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD))
  {
    Serial.println("[MQTT] Connected successfully!");
    
    // 订阅命令主题
    if (mqttClient.subscribe(MQTT_TOPIC_COMMAND))
    {
      Serial.println("[MQTT] Subscribed to topic: " + String(MQTT_TOPIC_COMMAND));
    }
    else
    {
      Serial.println("[MQTT] Failed to subscribe to topic: " + String(MQTT_TOPIC_COMMAND));
    }
  }
  else
  {
    Serial.print("[MQTT] Connection failed, rc=");
    Serial.print(mqttClient.state());
    Serial.println(" (will retry)");
  }
}

void MQTTManager::onMessage(char* topic, byte* payload, unsigned int length)
{
  // 将payload转换为字符串
  String message = "";
  for (unsigned int i = 0; i < length; i++)
  {
    message += (char)payload[i];
  }
  message.trim();

  Serial.println("[MQTT] Received command: " + message);
  Serial.println("[MQTT] Topic: " + String(topic));

  // STOP命令是特殊命令，可以中断当前的等待状态
  bool isStopCommand = (message == "STOP");
  
  // 如果正在等待响应，且不是STOP命令，忽略新命令
  if (waitingForResponse && !isStopCommand)
  {
    Serial.println("[MQTT] Still waiting for OpenMV response, ignoring new command");
    return;
  }

  // 如果是STOP命令且正在等待响应，先重置等待状态
  if (isStopCommand && waitingForResponse)
  {
    Serial.println("[MQTT] STOP command received, interrupting current wait state");
    waitingForResponse = false;
    responseStartTime = 0;
    pendingResponse = "";
  }

  // 发送命令到OpenMV
  extern OpenMVManager openMVManager;
  openMVManager.clearResponse();  // 清空之前的响应
  openMVManager.sendCommand(message);
  
  // 保存最后发送的命令
  lastCommand = message;
  
  // 标记正在等待响应（STOP命令通常不需要等待响应，但为了统一处理，仍然设置）
  // 如果STOP命令不需要等待响应，可以在发送后立即重置
  if (isStopCommand)
  {
    // STOP命令发送后，不等待响应，立即重置状态
    waitingForResponse = false;
    responseStartTime = 0;
    pendingResponse = "";
    Serial.println("[MQTT] STOP command sent, not waiting for response");
  }
  else
  {
    // 其他命令需要等待响应
    waitingForResponse = true;
    responseStartTime = millis();
    pendingResponse = "";
  }
}

void MQTTManager::onMessageCallback(char* topic, byte* payload, unsigned int length)
{
  // 静态回调函数，调用实例方法
  if (instance != nullptr)
  {
    instance->onMessage(topic, payload, length);
  }
}

void MQTTManager::checkAndPublishResponse()
{
  // 只有在等待响应时才检查OpenMV的响应
  if (!waitingForResponse)
  {
    return;
  }
  
  extern OpenMVManager openMVManager;
  if (openMVManager.hasResponse())
  {
    String response = openMVManager.getResponse();
    int previewLen = response.length() > 50 ? 50 : response.length();
    Serial.println("[MQTT] Found response in buffer, publishing: " + response.substring(0, previewLen));
    publishResponse(response);
  }
}

void MQTTManager::publishResponse(const String& response)
{
  if (mqttClient.connected() && waitingForResponse)
  {
    // 检查是否为Base64编码的图片数据
    bool isImage = response.startsWith("IMAGE_BASE64:");
    String payload = response;
    
    if (isImage)
    {
      // 移除前缀，只发送Base64数据
      payload = response.substring(13);  // 跳过 "IMAGE_BASE64:" 前缀
      Serial.print("[MQTT] Publishing image data (Base64), size: ");
      Serial.print(payload.length());
      Serial.println(" bytes");
      
      // 对于大数据，使用字节数组方式发送，避免String操作
      const char* payloadPtr = payload.c_str();
      size_t payloadLen = payload.length();
      
      // 计算最大可用块大小（留出一些空间用于MQTT协议开销）
      size_t maxChunkSize = MQTT_BUFFER_SIZE - 100;  // 预留100字节用于协议开销
      
      // 检查数据大小是否超过缓冲区
      if (payloadLen > maxChunkSize)
      {
        // 需要分块发送
        size_t totalChunks = (payloadLen + maxChunkSize - 1) / maxChunkSize;  // 向上取整
        Serial.print("[MQTT] Payload size (");
        Serial.print(payloadLen);
        Serial.print(") exceeds chunk size (");
        Serial.print(maxChunkSize);
        Serial.print("), splitting into ");
        Serial.print(totalChunks);
        Serial.println(" chunks");
        
        bool allChunksSent = true;
        for (size_t chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++)
        {
          size_t chunkStart = chunkIndex * maxChunkSize;
          size_t chunkSize = (chunkStart + maxChunkSize > payloadLen) ? 
                            (payloadLen - chunkStart) : maxChunkSize;
          
          // 构建块消息：CHUNK:index/total:data
          String chunkTopic = String(MQTT_TOPIC_RESPONSE) + "/chunk";
          String chunkHeader = "CHUNK:" + String(chunkIndex) + "/" + String(totalChunks) + ":";
          size_t headerLen = chunkHeader.length();
          
          // 创建完整的块消息（头部 + 数据）
          String chunkMsg = chunkHeader + payload.substring(chunkStart, chunkStart + chunkSize);
          
          Serial.print("[MQTT] Sending chunk ");
          Serial.print(chunkIndex + 1);
          Serial.print("/");
          Serial.print(totalChunks);
          Serial.print(" (size: ");
          Serial.print(chunkSize);
          Serial.println(" bytes)");
          
          bool chunkResult = mqttClient.publish(chunkTopic.c_str(), chunkMsg.c_str());
          
          if (!chunkResult)
          {
            Serial.print("[MQTT] Failed to publish chunk ");
            Serial.print(chunkIndex + 1);
            Serial.print(", state: ");
            Serial.println(mqttClient.state());
            allChunksSent = false;
            break;
          }
          
          // 在块之间添加小延迟，避免网络拥塞
          delay(10);
        }
        
        if (allChunksSent)
        {
          Serial.println("[MQTT] All image chunks published successfully");
          waitingForResponse = false;
          responseStartTime = 0;
          pendingResponse = "";
        }
        else
        {
          Serial.println("[MQTT] Failed to publish some chunks, will retry");
          // 不重置waitingForResponse，允许重试
        }
      }
      else
      {
        // 数据大小在限制内，直接发送
        bool result = mqttClient.publish(MQTT_TOPIC_RESPONSE, (const uint8_t*)payloadPtr, payloadLen, false);
        
        if (result)
        {
          Serial.println("[MQTT] Image data published successfully");
          waitingForResponse = false;
          responseStartTime = 0;
          pendingResponse = "";
        }
        else
        {
          Serial.print("[MQTT] Failed to publish response, state: ");
          Serial.println(mqttClient.state());
          // 不重置waitingForResponse，允许重试
        }
      }
    }
    else
    {
      Serial.println("[MQTT] Publishing text response: " + response);
      
      // 检测是否为进度消息（需要继续等待后续消息）
      bool isProgress = response.startsWith("Collected:");
      
      // 检测是否包含 "Starting face collection"，说明后续会有进度消息
      bool hasMoreProgress = response.indexOf("Starting face collection") >= 0;
      
      // 检测是否包含 "Collection complete"，说明收集完成
      bool isComplete = response.indexOf("Collection complete") >= 0;
      
      // 检测是否为识别结果消息（需要继续等待后续识别结果）
      bool isRecognitionResult = response.startsWith("Recognized:") || response.indexOf("Unknown face detected") >= 0;
      
      // 检测是否包含 "Starting face recognition mode" 或 "face recognition mode"，说明后续会有识别结果
      bool hasRecognitionMode = response.indexOf("face recognition mode") >= 0;
      
      // 调试信息
      if (hasRecognitionMode)
      {
        Serial.println("[MQTT] Detected 'Starting face recognition mode', will keep waitingForResponse = true");
      }
      if (isRecognitionResult)
      {
        Serial.println("[MQTT] Detected recognition result, will keep waitingForResponse = true");
      }
      
      // 文本响应通常较小，使用普通方式发送
      if (mqttClient.publish(MQTT_TOPIC_RESPONSE, payload.c_str()))
      {
        Serial.println("[MQTT] Published successfully");
        
        // 如果是进度消息，不重置 waitingForResponse，继续等待后续消息
        // 如果响应包含 "Starting face collection"，说明后续会有进度消息，也应该保持 waitingForResponse = true
        // 如果响应包含 "Starting face recognition mode"，说明后续会有识别结果，也应该保持 waitingForResponse = true
        // 如果是识别结果消息，也应该保持 waitingForResponse = true，以便持续发送识别结果
        // 只有在收到最终响应（包含 "Collection complete"）或不是上述消息时才重置
        if (isProgress || hasMoreProgress || hasRecognitionMode || isRecognitionResult)
        {
          // 进度消息、识别模式启动、识别结果消息发送后，
          // 保持 waitingForResponse = true，允许后续消息继续发送
          // 更新响应开始时间，避免超时
          responseStartTime = millis();
          Serial.println("[MQTT] Keeping waitingForResponse = true for continuous messages");
        }
        else if (isComplete)
        {
          // 收集完成，重置状态
          waitingForResponse = false;
          responseStartTime = 0;
          pendingResponse = "";
          lastCommand = "";
        }
        else
        {
          // 其他普通响应，重置状态
          waitingForResponse = false;
          responseStartTime = 0;
          pendingResponse = "";
          lastCommand = "";
        }
      }
      else
      {
        Serial.print("[MQTT] Failed to publish response, state: ");
        Serial.println(mqttClient.state());
      }
    }
  }
}
