#ifndef CONFIG_H
#define CONFIG_H

// UART配置
#define UART_RX_PIN 18
#define UART_TX_PIN 17
#define UART_BAUD 115200
#define RECEIVE_TIMEOUT 100

// OpenMV UART配置
#define OPENMV_RX_PIN 15
#define OPENMV_TX_PIN 16
#define OPENMV_BAUD 115200
#define OPENMV_RECEIVE_TIMEOUT 100
#define OPENMV_MULTILINE_TIMEOUT 10  // 多行文本数据接收超时
#define OPENMV_BINARY_TIMEOUT 500  // 二进制数据接收超时（500ms，用于图片数据）
#define OPENMV_MAX_BINARY_SIZE 50000  // 最大二进制数据大小（50KB）

// MQ传感器配置
#define MQ_SENSOR_PIN 13  // MQ传感器模拟输入引脚

// TFT显示屏引脚定义
#define TFT_CS    10  // CS引脚
#define TFT_RST   6   // RES引脚
#define TFT_DC    7   // DC引脚
#define TFT_SCLK  12  // SCK引脚
#define TFT_MOSI  11  // SDA引脚

// 自定义颜色定义（RGB565格式）
#define ST7735_NAVY    0x000F  // 深蓝色
#define ST7735_DARKGREEN 0x03E0  // 深绿色
#define ST7735_ORANGE  0xFD20  // 橙色
#define ST7735_PURPLE  0x8818  // 紫色
#define ST7735_PINK    0xF8B2  // 粉色
#define ST7735_DARK_GRAY 0x4A69  // 深灰色
#define ST7735_LIGHT_GRAY 0xBDF7  // 浅灰色

// WiFi配置
#define WIFI_SSID "liqiu"
#define WIFI_PASSWORD "asdfghjk"
#define SERVER_IP  // ⚠️ 请根据实际服务器IP修改！运行服务器后查看控制台输出的IP地址
#define SERVER_PORT 13501  // 默认端口，可在server_config.json中修改
#define UPLOAD_INTERVAL 1000  // 1秒上传一次
#define WIFI_CONNECT_CHECK_INTERVAL 100  // WiFi连接检查间隔（ms）
#define WIFI_CONNECT_TIMEOUT 30000  // WiFi连接超时时间（30秒）
#define HTTP_TIMEOUT 5000  // HTTP请求超时时间（5秒）

// MQTT配置
#define MQTT_SERVER 
#define MQTT_PORT 1883
#define MQTT_USERNAME "mqttuser"
#define MQTT_PASSWORD "qawsed"
#define MQTT_CLIENT_ID "esp32_smarthome"
#define MQTT_TOPIC_COMMAND "smarthome/command"  // 接收命令的主题
#define MQTT_TOPIC_RESPONSE "smarthome/response"  // 发送响应的主题
#define MQTT_RECONNECT_INTERVAL 5000  // MQTT重连间隔（5秒）
#define MQTT_RESPONSE_TIMEOUT 2000  // MQTT响应超时时间（2秒）
#define MQTT_BUFFER_SIZE 8192  // MQTT消息缓冲区大小（8KB，用于Base64编码的图片数据）

// 传感器数据更新配置
#define SENSOR_UPDATE_INTERVAL 200 

// 显示屏更新配置
#define DISPLAY_UPDATE_INTERVAL 500 
#endif // CONFIG_H

