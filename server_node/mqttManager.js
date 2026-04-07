const mqtt = require('mqtt');

class MQTTManager {
    constructor(config) {
        this.config = config;
        this.client = null;
        this.isConnected = false;
        this.pendingCommands = new Map(); // 存储待处理的命令和回调
        this.reconnectTimer = null;
        this.recognitionResults = []; // 存储最近的识别结果
        this.maxRecognitionResults = 50; // 最多保存50条识别结果
    }

    /**
     * 连接到MQTT服务器
     */
    connect() {
        const { server, port, username, password, client_id } = this.config;
        
        const brokerUrl = `mqtt://${server}:${port}`;
        const options = {
            clientId: client_id,
            username: username,
            password: password,
            clean: true,
            reconnectPeriod: this.config.reconnect_interval || 5000,
            connectTimeout: 10000
        };

        console.log(`[MQTT] 正在连接到 ${brokerUrl}...`);

        this.client = mqtt.connect(brokerUrl, options);

        // 连接成功事件
        this.client.on('connect', () => {
            this.isConnected = true;
            console.log('[MQTT] 连接成功');
            
            // 订阅响应主题
            this.client.subscribe(this.config.topic_response, (err) => {
                if (err) {
                    console.error('[MQTT] 订阅响应主题失败:', err);
                } else {
                    console.log(`[MQTT] 已订阅主题: ${this.config.topic_response}`);
                }
            });
        });

        // 连接错误事件
        this.client.on('error', (error) => {
            console.error('[MQTT] 连接错误:', error);
            this.isConnected = false;
        });

        // 断开连接事件
        this.client.on('close', () => {
            console.log('[MQTT] 连接已断开');
            this.isConnected = false;
        });

        // 重连事件
        this.client.on('reconnect', () => {
            console.log('[MQTT] 正在重连...');
        });

        // 接收消息事件
        this.client.on('message', (topic, message) => {
            this.handleMessage(topic, message);
        });

        // 离线事件
        this.client.on('offline', () => {
            console.log('[MQTT] 客户端已离线');
            this.isConnected = false;
        });
    }

    /**
     * 检查字符串是否为有效的Base64编码
     */
    isBase64(str) {
        if (!str || str.length === 0) return false;
        
        // Base64字符集: A-Z, a-z, 0-9, +, /, = (用于填充)
        // 允许换行符和空格（某些Base64编码可能包含）
        const cleanedStr = str.replace(/[\s\n\r]/g, '');
        if (cleanedStr.length === 0) return false;
        
        const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
        // Base64字符串长度必须是4的倍数（填充后）
        return base64Regex.test(cleanedStr) && cleanedStr.length % 4 === 0 && cleanedStr.length > 100;
    }

    /**
     * 处理接收到的MQTT消息
     */
    handleMessage(topic, message) {
        if (topic === this.config.topic_response) {
            // 处理Buffer或字符串消息
            let messageStr;
            if (Buffer.isBuffer(message)) {
                // 对于图像数据，可能是二进制，先尝试作为Base64字符串处理
                // 检查是否可以直接转换为字符串（已经是Base64编码的字符串）
                try {
                    messageStr = message.toString('utf8');
                } catch (e) {
                    // 如果是纯二进制，转换为Base64
                    messageStr = message.toString('base64');
                }
            } else {
                messageStr = message.toString();
            }
            
            const messageLength = messageStr.length;
            
            // 查找对应的命令
            let commandInfo = null;
            let commandId = null;
            if (this.pendingCommands.size > 0) {
                const firstEntry = this.pendingCommands.entries().next().value;
                [commandId, commandInfo] = firstEntry;
            }

            // 检查是否为Base64编码的图片数据
            // 方法1: 检查是否有IMAGE_BASE64:前缀
            let isImage = messageStr.startsWith('IMAGE_BASE64:');
            let imageData = messageStr;
            
            if (isImage) {
                // 移除前缀
                imageData = messageStr.substring(13);
            } else {
                // 方法2: 如果没有前缀，检查是否是纯Base64数据
                // 图像数据通常较大（>1000字符），且是有效的Base64字符串
                // 如果当前命令是GET_IMAGE，且数据看起来像Base64，则认为是图像
                if (commandInfo && commandInfo.command === 'GET_IMAGE') {
                    // Base64编码的JPEG图像通常至少几千字符
                    if (messageLength > 1000) {
                        if (this.isBase64(messageStr)) {
                            isImage = true;
                            imageData = messageStr;
                            console.log(`[MQTT] 检测到纯Base64图像数据，长度: ${messageLength}`);
                        } else {
                            console.log(`[MQTT] GET_IMAGE响应数据长度${messageLength}，但不是有效Base64，前100字符: ${messageStr.substring(0, 100)}`);
                        }
                    } else {
                        console.log(`[MQTT] GET_IMAGE响应数据长度${messageLength}，可能不是图像数据`);
                    }
                }
            }

            // 检查是否为识别结果消息（异步消息，不是命令响应）
            const isRecognitionResult = messageStr.startsWith('Recognized:') || 
                                       messageStr.includes('Unknown face detected');
            
            // 无论是否有命令在等待，都要先存储识别结果
            if (isRecognitionResult) {
                const recognitionResult = {
                    message: messageStr.trim(),
                    timestamp: new Date().toISOString(),
                    type: messageStr.startsWith('Recognized:') ? 'recognized' : 'unknown'
                };
                
                // 解析识别结果
                if (recognitionResult.type === 'recognized') {
                    const match = messageStr.match(/Recognized:\s*(.+?)\s*\((\d+)\)/);
                    if (match) {
                        recognitionResult.name = match[1];
                        recognitionResult.distance = parseInt(match[2]);
                    }
                }
                
                // 添加到识别结果列表
                this.recognitionResults.unshift(recognitionResult);
                if (this.recognitionResults.length > this.maxRecognitionResults) {
                    this.recognitionResults.pop();
                }
                
                console.log(`[MQTT] 识别结果: ${messageStr.trim()}`);
                
                // 如果当前有命令在等待，且是GET_IMAGE命令，且收到的是识别结果（不是图像），则忽略它作为命令响应
                // 这样GET_IMAGE命令可以继续等待真正的图像响应
                if (commandInfo && commandInfo.command === 'GET_IMAGE' && !isImage) {
                    console.log(`[MQTT] GET_IMAGE命令收到识别结果消息，已存储识别结果，但忽略作为命令响应，继续等待图像`);
                    return; // 不处理为命令响应，等待真正的图像响应
                }
                
                // 如果没有命令在等待，则只存储识别结果，不处理为命令响应
                if (!commandInfo) {
                    return; // 不处理为命令响应
                }
                
                // 如果有其他命令在等待（不是GET_IMAGE），识别结果不应该作为命令响应
                // 但这种情况理论上不应该发生，因为识别结果消息是异步的
                return; // 不处理为命令响应
            }

            let responseData = {
                type: isImage ? 'image' : 'text',
                data: imageData,
                timestamp: new Date().toISOString()
            };

            if (commandInfo) {
                console.log(`[MQTT] 收到响应 (${isImage ? '图像' : '文本'}): ${messageLength} 字符`);
                
                // 清除超时定时器
                if (commandInfo.timeout) {
                    clearTimeout(commandInfo.timeout);
                }
                
                // 执行回调
                commandInfo.resolve(responseData);
                
                // 移除已处理的命令
                this.pendingCommands.delete(commandId);
            } else {
                // 如果没有待处理的命令，但也不是识别结果，记录警告
                if (!isRecognitionResult) {
                    console.warn('[MQTT] 收到响应但没有待处理的命令');
                }
            }
        }
    }

    /**
     * 发送命令到OpenMV
     * @param {string} command - 要发送的命令
     * @param {number} timeout - 超时时间（毫秒）
     * @returns {Promise<Object>} 返回响应数据
     */
    async sendCommand(command, timeout = null) {
        return new Promise((resolve, reject) => {
            if (!this.isConnected || !this.client) {
                reject(new Error('MQTT未连接'));
                return;
            }

            const commandId = Date.now().toString();
            const timeoutMs = timeout || this.config.response_timeout || 5000;

            // 设置超时定时器
            const timeoutTimer = setTimeout(() => {
                this.pendingCommands.delete(commandId);
                reject(new Error(`命令超时: ${command}`));
            }, timeoutMs);

            // 存储命令和回调
            this.pendingCommands.set(commandId, {
                command: command,
                resolve: resolve,
                timeout: timeoutTimer,
                timestamp: Date.now()
            });

            // 发布命令
            this.client.publish(this.config.topic_command, command, (err) => {
                if (err) {
                    this.pendingCommands.delete(commandId);
                    clearTimeout(timeoutTimer);
                    reject(new Error(`发布命令失败: ${err.message}`));
                } else {
                    console.log(`[MQTT] 已发送命令: ${command}`);
                }
            });
        });
    }

    /**
     * 断开MQTT连接
     */
    disconnect() {
        if (this.client) {
            // 清理所有待处理的命令
            for (const [commandId, { timeout }] of this.pendingCommands.entries()) {
                if (timeout) {
                    clearTimeout(timeout);
                }
            }
            this.pendingCommands.clear();

            this.client.end();
            this.isConnected = false;
            console.log('[MQTT] 已断开连接');
        }
    }

    /**
     * 获取连接状态
     */
    getConnectionStatus() {
        return {
            connected: this.isConnected,
            pendingCommands: this.pendingCommands.size
        };
    }

    /**
     * 获取最近的识别结果
     * @param {number} limit - 返回的结果数量限制
     * @returns {Array} 识别结果数组
     */
    getRecognitionResults(limit = 10) {
        return this.recognitionResults.slice(0, limit);
    }

    /**
     * 清除识别结果
     */
    clearRecognitionResults() {
        this.recognitionResults = [];
    }
}

module.exports = { MQTTManager };
