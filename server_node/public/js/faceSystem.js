// 人脸系统管理
class FaceSystem {
    constructor() {
        this.currentMode = 'idle'; // idle, collect, recognize
        this.collectProgress = { name: '', count: 0, total: 20 };
        this.facesList = [];
        this.imageUpdateInterval = null;
        this.isRecognizing = false;
        this.imageUpdateRate = 1000; // 默认1秒，将从服务器配置加载
        this.recognitionResults = []; // 存储识别结果
        this.recognitionUpdateInterval = null; // 识别结果更新定时器
        this.recognitionTimeout = 5000; // 默认识别时间5秒，将从服务器配置加载
        this.recognitionTimeoutTimer = null; // 识别超时定时器
        this.currentImageData = null; // 当前显示的图像数据
        this.lastRecognitionTime = 0; // 最后一次识别的时间戳
        this.trackingLoaded = false; // tracking.js是否已加载
        this.detectedFaces = []; // 当前检测到的人脸
    }

    /**
     * 发送命令到OpenMV
     */
    async sendCommand(command, timeout = 10000) {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/openmv/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ command, timeout })
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || '命令执行失败');
            }

            return result.response;
        } catch (error) {
            console.error('发送命令失败:', error);
            throw error;
        }
    }

    /**
     * 获取MQTT连接状态
     */
    async getStatus() {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/openmv/status', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            const result = await response.json();
            return result;
        } catch (error) {
            console.error('获取状态失败:', error);
            return { connected: false };
        }
    }

    /**
     * 开始收集人脸
     */
    async startCollect(name) {
        if (!name || !/^[a-zA-Z]+$/.test(name)) {
            throw new Error('请输入有效的英文名字（仅字母）');
        }

        try {
            this.updateStatus('正在启动人脸收集...', 'info');
            const response = await this.sendCommand(`COLLECT:${name}`, 15000);
            
            // 解析响应（可能是多行）
            const responseText = response.type === 'text' ? response.data : '';
            const lines = responseText.split('\n').map(l => l.trim()).filter(l => l);
            
            if (lines.some(line => line.includes('Starting face collection'))) {
                this.currentMode = 'collect';
                this.collectProgress.name = name;
                this.collectProgress.count = 0;
                this.updateStatus(`开始收集人脸: ${name}`, 'success');
                this.startProgressMonitoring();
                return true;
            } else if (lines.some(line => line.includes('Error'))) {
                const errorLine = lines.find(line => line.includes('Error'));
                throw new Error(errorLine || '启动收集失败');
            } else {
                throw new Error(responseText || '启动收集失败');
            }
        } catch (error) {
            this.updateStatus(`收集失败: ${error.message}`, 'error');
            throw error;
        }
    }

    /**
     * 开始识别人脸
     */
    async startRecognize() {
        try {
            this.updateStatus('正在启动人脸识别...', 'info');
            this.isRecognizing = true;
            const response = await this.sendCommand('RECOGNIZE', 15000);
            
            const responseText = response.type === 'text' ? response.data : '';
            const lines = responseText.split('\n').map(l => l.trim()).filter(l => l);
            
            // 检查是否有明确的错误或警告
            const hasError = lines.some(line => 
                line.includes('Warning: No face data loaded') || 
                (line.includes('Error') && !line.includes('Loaded'))
            );
            
            if (hasError) {
                this.isRecognizing = false;
                // 清除识别超时定时器
                if (this.recognitionTimeoutTimer) {
                    clearTimeout(this.recognitionTimeoutTimer);
                    this.recognitionTimeoutTimer = null;
                }
                this.updateStatus('警告: 没有人脸数据，请先收集人脸', 'warning');
                return false;
            }
            
            // 检查成功标志：包含以下任一情况都视为成功
            const hasSuccess = lines.some(line => 
                line.includes('Starting face recognition') ||
                line.includes('Loaded') && line.includes('samples for') ||
                line.includes('Total loaded')
            );
            
            if (hasSuccess) {
                this.currentMode = 'recognize';
                this.updateStatus('人脸识别模式已启动', 'success');
                // 启动识别结果监控
                this.startRecognitionMonitoring();
                // 启动识别超时定时器
                this.startRecognitionTimeout();
                // 图像流已经在init中启动，无需重复启动
                // this.startImageStream();
                return true;
            } else {
                // 如果没有明确的成功或失败标志，但响应不为空，也视为成功（可能是其他格式的成功消息）
                if (responseText && responseText.trim().length > 0) {
                    console.warn('未识别的响应格式，但响应不为空，视为成功:', responseText);
                    this.currentMode = 'recognize';
                    this.updateStatus('人脸识别模式已启动', 'success');
                    return true;
                } else {
                    throw new Error('未收到有效响应');
                }
            }
        } catch (error) {
            this.isRecognizing = false;
            // 清除识别超时定时器
            if (this.recognitionTimeoutTimer) {
                clearTimeout(this.recognitionTimeoutTimer);
                this.recognitionTimeoutTimer = null;
            }
            this.updateStatus(`识别失败: ${error.message}`, 'error');
            throw error;
        }
    }

    /**
     * 停止当前操作
     */
    async stop() {
        try {
            this.updateStatus('正在停止操作...', 'info');
            // STOP命令没有返回值，不用判断响应
            await this.sendCommand('STOP', 5000);
            
            this.currentMode = 'idle';
            this.isRecognizing = false;
            // 清除识别超时定时器
            if (this.recognitionTimeoutTimer) {
                clearTimeout(this.recognitionTimeoutTimer);
                this.recognitionTimeoutTimer = null;
            }
            // 不停止图像流，保持实时画面显示
            // this.stopImageStream();
            this.stopProgressMonitoring();
            // 不停止识别结果监控，继续显示历史记录
            // this.stopRecognitionMonitoring();
            this.updateStatus('操作已停止', 'success');
            return true;
        } catch (error) {
            // STOP命令即使失败也更新状态
            this.currentMode = 'idle';
            this.isRecognizing = false;
            if (this.recognitionTimeoutTimer) {
                clearTimeout(this.recognitionTimeoutTimer);
                this.recognitionTimeoutTimer = null;
            }
            this.updateStatus('操作已停止', 'success');
            return true;
        }
    }

    /**
     * 获取当前状态
     */
    async getCurrentStatus() {
        try {
            const response = await this.sendCommand('STATUS');
            const responseText = response.type === 'text' ? response.data : '';
            
            // 解析状态信息
            const lines = responseText.split('\n').map(l => l.trim()).filter(l => l);
            for (const line of lines) {
                if (line.includes('Current mode:')) {
                    const mode = line.split('Current mode:')[1]?.trim();
                    this.currentMode = mode || 'idle';
                } else if (line.includes('Collecting for:')) {
                    const match = line.match(/Collecting for: (.+), Progress: (\d+)\/(\d+)/);
                    if (match) {
                        this.collectProgress.name = match[1];
                        this.collectProgress.count = parseInt(match[2]);
                        this.collectProgress.total = parseInt(match[3]);
                    }
                }
            }
            
            this.updateStatusDisplay();
            return responseText;
        } catch (error) {
            console.error('获取状态失败:', error);
            return null;
        }
    }

    /**
     * 获取图像
     */
    async getImage() {
        // 在识别模式下，增加超时时间，因为可能需要等待识别结果消息处理完毕
        const timeout = this.currentMode === 'recognize' ? 20000 : 15000;
        
        try {
            const response = await this.sendCommand('GET_IMAGE', timeout);
            
            console.log('收到响应:', {
                type: response.type,
                dataLength: response.data ? response.data.length : 0,
                dataPreview: response.data ? response.data.substring(0, 50) : 'null'
            });
            
            // 检查是否是识别结果消息（不应该作为图像响应）
            // 注意：这种情况理论上不应该发生，因为MQTT管理器已经过滤了识别结果消息
            if (response.type === 'text' && 
                (response.data.includes('Recognized:') || response.data.includes('Unknown face detected'))) {
                console.warn('收到识别结果消息而不是图像，这不应该发生');
                throw new Error('收到识别结果消息而不是图像数据');
            }
            
            if (response.type === 'image') {
                return response.data; // Base64编码的图片数据
            } else {
                // 如果类型不是image，但数据看起来像Base64，也尝试使用
                if (response.data && response.data.length > 1000) {
                    console.warn('响应类型为text，但数据长度较大，尝试作为图像处理');
                    return response.data;
                }
                throw new Error(`未收到图像数据，响应类型: ${response.type}, 数据长度: ${response.data ? response.data.length : 0}`);
            }
        } catch (error) {
            console.error('获取图像失败:', error);
            throw error;
        }
    }

    /**
     * 列出所有人脸
     */
    async listFaces() {
        try {
            const response = await this.sendCommand('LIST_FACES', 10000);
            const responseText = response.type === 'text' ? response.data : '';
            
            // 解析人脸列表
            this.facesList = [];
            const lines = responseText.split('\n').map(l => l.trim()).filter(l => l);
            let inList = false;
            
            for (const line of lines) {
                if (line.includes('=== Face Database ===')) {
                    inList = true;
                    continue;
                }
                if (line.includes('===') && line !== '=== Face Database ===') {
                    inList = false;
                    continue;
                }
                if (inList && line.includes('Name:')) {
                    const match = line.match(/Name: (.+), Photos: (\d+)/);
                    if (match) {
                        this.facesList.push({
                            name: match[1],
                            photos: parseInt(match[2])
                        });
                    }
                }
            }
            
            this.updateFacesList();
            return this.facesList;
        } catch (error) {
            console.error('列出人脸失败:', error);
            throw error;
        }
    }

    /**
     * 删除人脸
     */
    async deleteFace(name) {
        if (!name) {
            throw new Error('请指定要删除的人脸名称');
        }

        try {
            this.updateStatus(`正在删除人脸: ${name}...`, 'info');
            const response = await this.sendCommand(`DELETE_FACE:${name}`, 10000);
            
            const responseText = response.type === 'text' ? response.data : '';
            const lines = responseText.split('\n').map(l => l.trim()).filter(l => l);
            
            if (lines.some(line => line.includes('Deleted face'))) {
                this.updateStatus(`人脸 "${name}" 已删除`, 'success');
                // 刷新列表
                await this.listFaces();
                return true;
            } else if (lines.some(line => line.includes('not found') || line.includes('Error'))) {
                const errorLine = lines.find(line => line.includes('not found') || line.includes('Error'));
                throw new Error(errorLine || `人脸 "${name}" 不存在`);
            } else {
                throw new Error(responseText || '删除失败');
            }
        } catch (error) {
            this.updateStatus(`删除失败: ${error.message}`, 'error');
            throw error;
        }
    }

    /**
     * 开始图像流（所有模式）
     */
    startImageStream() {
        if (this.imageUpdateInterval) {
            return;
        }

        this.imageUpdateInterval = setInterval(async () => {
            // 在所有模式下都更新图像，提供实时画面
            try {
                const imageData = await this.getImage();
                this.displayImage(imageData);
            } catch (error) {
                // 静默失败，避免频繁错误日志
                // 如果超时，不显示错误，继续尝试
                if (error.message.includes('超时')) {
                    console.debug('获取图像超时，将在下次循环重试');
                    // 即使获取图像失败，也尝试更新识别框（如果有之前的图像）
                    if (this.currentImageData) {
                        const imageContainer = document.getElementById('faceImageContainer');
                        if (imageContainer) {
                            const img = imageContainer.querySelector('img');
                            const canvas = imageContainer.querySelector('canvas');
                            if (img && canvas && img.complete) {
                                // 重新检测人脸并绘制
                                this.detectFaces(img).then(detections => {
                                    this.drawRecognitionBoxes(img, canvas, detections);
                                });
                            }
                        }
                    }
                } else {
                    console.debug('获取图像失败:', error.message);
                }
            }
        }, this.imageUpdateRate); // 使用配置的图像更新频率
    }

    /**
     * 更新图像流频率（重新启动图像流以应用新频率）
     */
    updateImageStreamRate(newRate) {
        const wasRunning = !!this.imageUpdateInterval;
        if (wasRunning) {
            this.stopImageStream();
        }
        this.imageUpdateRate = newRate;
        if (wasRunning) {
            this.startImageStream();
        }
    }

    /**
     * 加载设置（从服务器获取图像更新频率和识别时间）
     */
    async loadSettings() {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/settings', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            const settings = await response.json();
            if (settings.image_update_rate) {
                this.imageUpdateRate = parseInt(settings.image_update_rate);
                // 如果图像流正在运行，需要重新启动以应用新频率
                if (this.imageUpdateInterval) {
                    this.updateImageStreamRate(this.imageUpdateRate);
                }
            }
            if (settings.recognition_timeout) {
                this.recognitionTimeout = parseInt(settings.recognition_timeout);
            }
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    }

    /**
     * 启动识别超时定时器
     */
    startRecognitionTimeout() {
        // 清除之前的定时器
        if (this.recognitionTimeoutTimer) {
            clearTimeout(this.recognitionTimeoutTimer);
        }

        // 设置新的定时器
        this.recognitionTimeoutTimer = setTimeout(async () => {
            if (this.currentMode === 'recognize' && this.isRecognizing) {
                console.log(`识别时间已到（${this.recognitionTimeout}ms），自动停止识别`);
                this.updateStatus('识别时间已到，正在停止...', 'info');
                
                // 发送三次STOP命令
                for (let i = 0; i < 3; i++) {
                    try {
                        await this.sendCommand('STOP', 2000);
                        console.log(`已发送第 ${i + 1} 次STOP命令`);
                    } catch (error) {
                        console.warn(`第 ${i + 1} 次STOP命令失败:`, error.message);
                    }
                    // 每次发送之间间隔100ms
                    if (i < 2) {
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                }
                
                // 更新状态
                this.currentMode = 'idle';
                this.isRecognizing = false;
                this.updateStatus('识别已自动停止', 'success');
            }
            this.recognitionTimeoutTimer = null;
        }, this.recognitionTimeout);
    }

    /**
     * 停止图像流
     */
    stopImageStream() {
        if (this.imageUpdateInterval) {
            clearInterval(this.imageUpdateInterval);
            this.imageUpdateInterval = null;
        }
        // 清空图像显示
        const imageContainer = document.getElementById('faceImageContainer');
        if (imageContainer) {
            imageContainer.innerHTML = '<p class="no-image">暂无图像</p>';
        }
    }

    /**
     * 加载tracking.js库
     */
    async loadTrackingModels() {
        if (this.trackingLoaded) {
            return true;
        }

        if (typeof tracking === 'undefined') {
            console.warn('tracking.js未加载，将使用基础检测框');
            return false;
        }

        try {
            this.updateStatus('正在加载人脸检测模型...', 'info');
            
            // 等待face分类器加载完成
            let attempts = 0;
            const maxAttempts = 50; // 最多等待5秒
            
            while (attempts < maxAttempts) {
                // 检查face分类器是否已加载
                if (tracking.Cascade && tracking.Cascade.face) {
                    this.trackingLoaded = true;
                    console.log('tracking.js加载成功');
                    this.updateStatus('人脸检测模型已加载', 'success');
                    return true;
                }
                
                // 等待100ms后重试
                await new Promise(resolve => setTimeout(resolve, 100));
                attempts++;
            }
            
            // 如果超时仍未加载，尝试直接使用（可能face数据已加载但结构不同）
            this.trackingLoaded = true;
            console.warn('tracking.js face分类器可能未完全加载，但将继续尝试使用');
            this.updateStatus('人脸检测模型已加载', 'success');
            return true;
        } catch (error) {
            console.error('加载tracking.js失败:', error);
            this.updateStatus('人脸检测模型加载失败，将使用基础检测框', 'warning');
            return false;
        }
    }

    /**
     * 使用tracking.js检测人脸
     */
    async detectFaces(img) {
        if (!this.trackingLoaded || typeof tracking === 'undefined') {
            return [];
        }

        try {
            return new Promise((resolve) => {
                // 创建临时canvas用于tracking.js检测
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                ctx.drawImage(img, 0, 0);

                // 使用tracking.js检测人脸（使用字符串'face'）
                // 如果face分类器未加载，tracker会失败，但不会抛出错误
                let tracker;
                try {
                    tracker = new tracking.ObjectTracker('face');
                } catch (error) {
                    console.warn('创建tracker失败，face分类器可能未加载:', error);
                    resolve([]);
                    return;
                }
                tracker.setInitialScale(4);
                tracker.setStepSize(2);
                tracker.setEdgesDensity(0.1);

                const detections = [];
                let resolved = false;
                let task = null;
                
                // 只监听一次track事件
                const trackHandler = (event) => {
                    if (resolved) return;
                    
                    event.data.forEach((rect) => {
                        detections.push({
                            box: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            score: 0.8 // tracking.js不提供置信度，使用默认值
                        });
                    });
                    
                    resolved = true;
                    // 移除事件监听器
                    tracker.removeListener('track', trackHandler);
                    
                    // 尝试停止跟踪任务
                    try {
                        if (task) {
                            if (typeof task.stop === 'function') {
                                task.stop();
                            } else if (typeof task.cancel === 'function') {
                                task.cancel();
                            }
                        }
                    } catch (e) {
                        // 忽略停止错误
                    }
                    
                    resolve(detections);
                };
                
                tracker.on('track', trackHandler);

                // 开始跟踪，tracking.track返回任务对象
                try {
                    task = tracking.track(canvas, tracker);
                } catch (error) {
                    console.error('开始跟踪失败:', error);
                    resolve([]);
                    return;
                }
                
                // 设置超时，避免无限等待
                setTimeout(() => {
                    if (!resolved) {
                        resolved = true;
                        tracker.removeListener('track', trackHandler);
                        
                        // 尝试停止跟踪任务
                        try {
                            if (task) {
                                if (typeof task.stop === 'function') {
                                    task.stop();
                                } else if (typeof task.cancel === 'function') {
                                    task.cancel();
                                }
                            }
                        } catch (e) {
                            // 忽略停止错误
                        }
                        
                        resolve(detections);
                    }
                }, 2000);
            });
        } catch (error) {
            console.error('人脸检测失败:', error);
            return [];
        }
    }

    /**
     * 显示图像（带识别框）
     */
    async displayImage(base64Data) {
        const imageContainer = document.getElementById('faceImageContainer');
        if (!imageContainer) return;

        // 保存当前图像数据
        this.currentImageData = base64Data;

        // 创建容器
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.display = 'inline-block';
        wrapper.style.maxWidth = '100%';

        // 创建图像元素
        const img = document.createElement('img');
        img.src = `data:image/jpeg;base64,${base64Data}`;
        img.style.maxWidth = '100%';
        img.style.height = 'auto';
        img.style.borderRadius = '8px';
        img.style.display = 'block';
        
        // 创建Canvas用于绘制识别框
        const canvas = document.createElement('canvas');
        canvas.style.position = 'absolute';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.pointerEvents = 'none';
        canvas.style.borderRadius = '8px';

        wrapper.appendChild(img);
        wrapper.appendChild(canvas);

        // 等待图像加载后检测人脸并绘制识别框
        img.onload = async () => {
            // 确保库已加载
            if (!this.trackingLoaded) {
                await this.loadTrackingModels();
            }

            // 检测人脸
            const detections = await this.detectFaces(img);
            this.detectedFaces = detections;

            // 绘制识别框
            this.drawRecognitionBoxes(img, canvas, detections);
        };

        imageContainer.innerHTML = '';
        imageContainer.appendChild(wrapper);
    }

    /**
     * 在Canvas上绘制识别框（使用真实的人脸检测结果）
     */
    drawRecognitionBoxes(img, canvas, detections = []) {
        // 设置Canvas尺寸与图像一致
        canvas.width = img.offsetWidth;
        canvas.height = img.offsetHeight;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // 清除之前的绘制
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 计算图像缩放比例
        const scaleX = canvas.width / img.naturalWidth;
        const scaleY = canvas.height / img.naturalHeight;

        // 获取最近的识别结果（最近5秒内的）
        const now = Date.now();
        const recentResults = this.recognitionResults
            .filter(result => {
                const resultTime = new Date(result.timestamp).getTime();
                return (now - resultTime) < 5000; // 5秒内的识别结果
            });

        // 如果有检测到的人脸，使用真实位置绘制
        if (detections && detections.length > 0) {
            detections.forEach((detection, index) => {
                // 获取对应的识别结果（如果有）
                // 在识别模式下，优先使用最近的识别结果
                let recognitionResult = null;
                if (this.currentMode === 'recognize' && recentResults.length > 0) {
                    // 优先使用索引匹配，如果没有则使用最近的识别结果
                    recognitionResult = recentResults[index] || recentResults[0];
                } else {
                    recognitionResult = recentResults[index] || null;
                }
                
                // 绘制真实的人脸框
                this.drawRealFaceBox(ctx, detection, recognitionResult, 
                                    canvas.width, canvas.height, scaleX, scaleY);
            });
        } else {
            // 如果没有检测到人脸，但处于识别模式，显示提示
            if (this.currentMode === 'recognize') {
                ctx.font = 'bold 16px Arial';
                ctx.fillStyle = 'rgba(255, 170, 0, 0.8)';
                ctx.textAlign = 'center';
                ctx.fillText('未检测到人脸', canvas.width / 2, 30);
            }
        }
    }

    /**
     * 绘制真实的人脸检测框
     */
    drawRealFaceBox(ctx, detection, recognitionResult, canvasWidth, canvasHeight, scaleX, scaleY) {
        // 获取人脸边界框（相对于原始图像）
        // MediaPipe返回的格式: {box: {x, y, width, height}, score}
        const box = detection.box;
        
        if (!box) {
            return;
        }
        
        // 转换为canvas坐标
        const x = box.x * scaleX;
        const y = box.y * scaleY;
        const width = box.width * scaleX;
        const height = box.height * scaleY;

        // 判断是否有识别结果
        const isRecognized = recognitionResult && recognitionResult.type === 'recognized';
        const isUnknown = recognitionResult && recognitionResult.type === 'unknown';
        
        // 设置样式
        ctx.strokeStyle = isRecognized ? '#00ff00' : (isUnknown ? '#ffaa00' : '#0099ff');
        ctx.lineWidth = 3;
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        // 绘制人脸框
        ctx.strokeRect(x, y, width, height);

        // 标签高度（在所有模式下都使用）
        const labelHeight = 24;

        // 在识别模式下，显示名称和置信度
        if (this.currentMode === 'recognize') {
            if (recognitionResult) {
                // 绘制名称标签
                const nameText = isRecognized ? recognitionResult.name : 'Unknown';
                const nameWidth = ctx.measureText(nameText).width + 20;
                
                ctx.fillStyle = isRecognized ? 'rgba(0, 255, 0, 0.8)' : 'rgba(255, 170, 0, 0.8)';
                ctx.fillRect(x, y - labelHeight, nameWidth, labelHeight);
                
                ctx.fillStyle = '#000000';
                ctx.fillText(nameText, x + 10, y - labelHeight + 4);

                // 如果识别成功，显示距离值
                if (isRecognized && recognitionResult.distance !== undefined) {
                    // 直接显示距离值，不转换为百分比
                    const distanceText = `距离: ${recognitionResult.distance}`;
                    const distanceWidth = ctx.measureText(distanceText).width + 20;
                    
                    ctx.fillStyle = 'rgba(0, 255, 0, 0.8)';
                    ctx.fillRect(x, y + height, distanceWidth, labelHeight);
                    
                    ctx.fillStyle = '#000000';
                    ctx.fillText(distanceText, x + 10, y + height + 4);
                } else if (isUnknown) {
                    // 未知人脸
                    const unknownText = '未知人脸';
                    const unknownWidth = ctx.measureText(unknownText).width + 20;
                    
                    ctx.fillStyle = 'rgba(255, 170, 0, 0.8)';
                    ctx.fillRect(x, y + height, unknownWidth, labelHeight);
                    
                    ctx.fillStyle = '#000000';
                    ctx.fillText(unknownText, x + 10, y + height + 4);
                }
            } else {
                // 识别模式下但没有识别结果，显示"识别中..."
                const detectingText = '识别中...';
                const detectingWidth = ctx.measureText(detectingText).width + 20;
                
                ctx.fillStyle = 'rgba(255, 170, 0, 0.8)';
                ctx.fillRect(x, y - labelHeight, detectingWidth, labelHeight);
                
                ctx.fillStyle = '#000000';
                ctx.fillText(detectingText, x + 10, y - labelHeight + 4);
            }
        } else {
            // 非识别模式，只显示检测框，不显示任何文字
        }
    }


    /**
     * 开始进度监控（收集模式）
     */
    startProgressMonitoring() {
        if (this.progressInterval) {
            return;
        }

        this.progressInterval = setInterval(async () => {
            if (this.currentMode === 'collect') {
                try {
                    await this.getCurrentStatus();
                } catch (error) {
                    console.debug('获取进度失败:', error.message);
                }
            } else {
                this.stopProgressMonitoring();
            }
        }, 2000); // 每2秒更新一次进度
    }

    /**
     * 停止进度监控
     */
    stopProgressMonitoring() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    /**
     * 更新状态显示
     */
    updateStatusDisplay() {
        const statusEl = document.getElementById('faceSystemStatus');
        const progressEl = document.getElementById('collectProgress');
        
        if (statusEl) {
            let statusText = `当前模式: ${this.currentMode}`;
            if (this.currentMode === 'collect') {
                statusText += ` | 收集对象: ${this.collectProgress.name}`;
            }
            statusEl.textContent = statusText;
        }

        if (progressEl && this.currentMode === 'collect') {
            const percentage = Math.round((this.collectProgress.count / this.collectProgress.total) * 100);
            progressEl.innerHTML = `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
                <p>进度: ${this.collectProgress.count}/${this.collectProgress.total} (${percentage}%)</p>
            `;
        } else if (progressEl) {
            progressEl.innerHTML = '';
        }
    }

    /**
     * 更新状态消息
     */
    updateStatus(message, type = 'info') {
        const statusEl = document.getElementById('faceSystemMessage');
        if (!statusEl) return;

        statusEl.textContent = message;
        statusEl.className = `face-status-message ${type}`;
        
        // 3秒后清除消息
        setTimeout(() => {
            if (statusEl.textContent === message) {
                statusEl.textContent = '';
                statusEl.className = 'face-status-message';
            }
        }, 3000);
    }

    /**
     * 更新人脸列表显示
     */
    updateFacesList() {
        const listEl = document.getElementById('facesList');
        if (!listEl) return;

        if (this.facesList.length === 0) {
            listEl.innerHTML = '<p class="no-faces">暂无已保存的人脸</p>';
            return;
        }

        const html = this.facesList.map(face => `
            <div class="face-item">
                <div class="face-info">
                    <span class="face-name">${face.name}</span>
                    <span class="face-photos">${face.photos} 张照片</span>
                </div>
                <button class="btn btn-danger btn-small" onclick="faceSystem.deleteFaceHandler('${face.name}')">
                    删除
                </button>
            </div>
        `).join('');

        listEl.innerHTML = html;
    }

    /**
     * 删除人脸处理函数
     */
    async deleteFaceHandler(name) {
        if (!confirm(`确定要删除人脸 "${name}" 吗？此操作不可恢复！`)) {
            return;
        }

        try {
            await this.deleteFace(name);
        } catch (error) {
            alert(`删除失败: ${error.message}`);
        }
    }

    /**
     * 获取识别结果
     */
    async getRecognitionResults() {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/openmv/recognition-results?limit=20', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            const result = await response.json();
            if (result.success) {
                const oldResultsCount = this.recognitionResults.length;
                this.recognitionResults = result.results || [];
                this.updateRecognitionResultsDisplay();
                
                // 如果有新的识别结果，更新图像上的识别框
                if (this.recognitionResults.length > oldResultsCount && this.currentImageData) {
                    const imageContainer = document.getElementById('faceImageContainer');
                    if (imageContainer) {
                        const img = imageContainer.querySelector('img');
                        const canvas = imageContainer.querySelector('canvas');
                        if (img && canvas && img.complete) {
                            // 重新检测人脸并绘制
                            this.detectFaces(img).then(detections => {
                                this.drawRecognitionBoxes(img, canvas, detections);
                            });
                        }
                    }
                }
            }
        } catch (error) {
            console.error('获取识别结果失败:', error);
        }
    }

    /**
     * 清除识别结果
     */
    async clearRecognitionResults() {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('/api/openmv/recognition-results', {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            const result = await response.json();
            if (result.success) {
                this.recognitionResults = [];
                this.updateRecognitionResultsDisplay();
                this.updateStatus('识别记录已清除', 'success');
            }
        } catch (error) {
            console.error('清除识别结果失败:', error);
            this.updateStatus('清除失败: ' + error.message, 'error');
        }
    }

    /**
     * 更新识别结果显示
     */
    updateRecognitionResultsDisplay() {
        const resultsEl = document.getElementById('recognitionResults');
        if (!resultsEl) return;

        if (this.recognitionResults.length === 0) {
            resultsEl.innerHTML = '<p class="no-faces">暂无识别结果</p>';
            return;
        }

        const html = this.recognitionResults.map(result => {
            const date = new Date(result.timestamp);
            const timeStr = date.toLocaleTimeString('zh-CN');
            
            if (result.type === 'recognized' && result.name) {
                return `
                    <div class="recognition-result-item recognized">
                        <div class="recognition-result-header">
                            <span class="recognition-name">✅ ${result.name}</span>
                            <span class="recognition-time">${timeStr}</span>
                        </div>
                        <div class="recognition-result-details">
                            <span class="recognition-distance">相似度: ${result.distance || 'N/A'}</span>
                        </div>
                    </div>
                `;
            } else {
                return `
                    <div class="recognition-result-item unknown">
                        <div class="recognition-result-header">
                            <span class="recognition-name">❓ 未知人脸</span>
                            <span class="recognition-time">${timeStr}</span>
                        </div>
                    </div>
                `;
            }
        }).join('');

        resultsEl.innerHTML = html;
    }

    /**
     * 开始识别结果监控
     */
    startRecognitionMonitoring() {
        if (this.recognitionUpdateInterval) {
            return;
        }

        // 立即获取一次
        this.getRecognitionResults();

        // 每2秒更新一次识别结果（任何时候都更新，不只在识别模式下）
        this.recognitionUpdateInterval = setInterval(async () => {
            await this.getRecognitionResults();
        }, 2000);
    }

    /**
     * 停止识别结果监控
     */
    stopRecognitionMonitoring() {
        if (this.recognitionUpdateInterval) {
            clearInterval(this.recognitionUpdateInterval);
            this.recognitionUpdateInterval = null;
        }
    }

    /**
     * 初始化
     */
    async init() {
        // 检查MQTT连接状态
        const status = await this.getStatus();
        if (!status.connected) {
            this.updateStatus('MQTT未连接，请检查服务器配置', 'error');
        } else {
            this.updateStatus('系统就绪', 'success');
        }

        // 加载tracking.js库
        await this.loadTrackingModels();

        // 加载设置（包括图像更新频率）
        await this.loadSettings();

        // 加载人脸列表
        try {
            await this.listFaces();
        } catch (error) {
            console.error('加载人脸列表失败:', error);
        }

        // 自动启动图像流，提供实时画面
        this.startImageStream();

        // 启动识别结果监控
        this.startRecognitionMonitoring();

        // 定期更新状态
        setInterval(async () => {
            if (this.currentMode !== 'idle') {
                await this.getCurrentStatus();
            }
        }, 5000);

        // 监听窗口大小改变，重新绘制识别框（任何时候都更新）
        let resizeTimer = null;
        window.addEventListener('resize', async () => {
            if (resizeTimer) {
                clearTimeout(resizeTimer);
            }
            resizeTimer = setTimeout(async () => {
                if (this.currentImageData) {
                    const imageContainer = document.getElementById('faceImageContainer');
                    if (imageContainer) {
                        const img = imageContainer.querySelector('img');
                        const canvas = imageContainer.querySelector('canvas');
                        if (img && canvas && img.complete) {
                            // 重新检测人脸并绘制
                            const detections = await this.detectFaces(img);
                            this.drawRecognitionBoxes(img, canvas, detections);
                        }
                    }
                }
            }, 300); // 防抖，300ms后执行
        });
    }
}

// 创建全局实例
const faceSystem = new FaceSystem();
