const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs-extra');
const cookieParser = require('cookie-parser');
const { DataManager } = require('./dataManager');
const { ConfigManager } = require('./configManager');
const { UserManager } = require('./userManager');
const { MQTTManager } = require('./mqttManager');

const app = express();

// 中间件
app.use(cors());
app.use(express.json());
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

// 初始化管理器
const dataManager = new DataManager();
const configManager = new ConfigManager();
const userManager = new UserManager();
let mqttManager = null;

// 加载配置和数据
async function initializeApp() {
    await configManager.loadConfig();
    await dataManager.loadData();
    await dataManager.loadSettings();
    await dataManager.loadChartSettings();
    await userManager.loadUsers();
    
    // 初始化MQTT管理器
    const config = configManager.getConfig();
    if (config.mqtt) {
        mqttManager = new MQTTManager(config.mqtt);
        mqttManager.connect();
        console.log('[MQTT] MQTT管理器已初始化');
    } else {
        console.warn('[MQTT] 未找到MQTT配置，MQTT功能将不可用');
    }
}

// 会话验证中间件
function authenticateToken(req, res, next) {
    const token = req.headers['authorization']?.split(' ')[1] || req.cookies?.token || req.query?.token;
    
    if (!token) {
        return res.status(401).json({ error: '未授权，请先登录' });
    }

    const session = userManager.verifySession(token);
    if (!session) {
        return res.status(401).json({ error: '会话已过期，请重新登录' });
    }

    req.user = session;
    next();
}

// 路由
// 登录页面
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'login.html'));
});

// 注册页面
app.get('/register', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'register.html'));
});

// 认证中间件
function requireAuth(req, res, next) {
    const token = req.headers['authorization']?.split(' ')[1] || req.cookies?.token || req.query?.token;
    
    if (!token) {
        return res.redirect('/login');
    }

    const session = userManager.verifySession(token);
    if (!session) {
        return res.redirect('/login');
    }

    req.user = session;
    next();
}

// 主页面（重定向到仪表板）
app.get('/', requireAuth, (req, res) => {
    res.redirect('/dashboard');
});

// 设置API（需要登录）- 使用/api前缀避免与页面路由冲突
app.get('/api/settings', authenticateToken, (req, res) => {
    res.json(dataManager.getSettings());
});

app.post('/api/settings', authenticateToken, async (req, res) => {
    try {
        const newSettings = req.body;

        if ('max_data_points' in newSettings) {
            let maxPoints = parseInt(newSettings.max_data_points);
            if (maxPoints < 10) maxPoints = 10;
            if (maxPoints > 10000) maxPoints = 10000;
            dataManager.updateMaxDataPoints(maxPoints);
        }

        if ('update_rate' in newSettings) {
            let updateRate = parseInt(newSettings.update_rate);
            if (updateRate < 1) updateRate = 1;
            if (updateRate > 300) updateRate = 300;
            dataManager.updateUpdateRate(updateRate);
        }

        if ('image_update_rate' in newSettings) {
            let imageUpdateRate = parseInt(newSettings.image_update_rate);
            if (imageUpdateRate < 100) imageUpdateRate = 100;  // 最小100毫秒
            if (imageUpdateRate > 10000) imageUpdateRate = 10000;  // 最大10秒
            dataManager.updateImageUpdateRate(imageUpdateRate);
        }

        if ('recognition_timeout' in newSettings) {
            let recognitionTimeout = parseInt(newSettings.recognition_timeout);
            if (recognitionTimeout < 1000) recognitionTimeout = 1000;  // 最小1秒
            if (recognitionTimeout > 60000) recognitionTimeout = 60000;  // 最大60秒
            dataManager.updateRecognitionTimeout(recognitionTimeout);
        }

        await dataManager.saveSettings();
        res.json({ status: 'success', settings: dataManager.getSettings() });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 图表设置API（需要登录）
app.get('/api/chart-settings', authenticateToken, (req, res) => {
    res.json(dataManager.getChartSettings());
});

app.post('/api/chart-settings', authenticateToken, async (req, res) => {
    try {
        const newSettings = req.body;

        if ('smoothness' in newSettings) {
            dataManager.updateChartSettings('smoothness', parseFloat(newSettings.smoothness));
        }
        if ('point_size' in newSettings) {
            dataManager.updateChartSettings('pointSize', parseInt(newSettings.point_size));
        }
        if ('show_grid' in newSettings) {
            dataManager.updateChartSettings('showGrid', Boolean(newSettings.show_grid));
        }
        if ('show_points' in newSettings) {
            dataManager.updateChartSettings('showPoints', Boolean(newSettings.show_points));
        }
        if ('fill_area' in newSettings) {
            dataManager.updateChartSettings('fillArea', Boolean(newSettings.fill_area));
        }

        await dataManager.saveChartSettings();
        res.json({ status: 'success', settings: dataManager.getChartSettings() });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 仪表板页面（需要登录）
app.get('/dashboard', requireAuth, (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

// 人脸系统页面（需要登录）
app.get('/face', requireAuth, (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'face.html'));
});

// 设置页面（需要登录）- 必须在API路由之后
// 注意：API路由在前面，所以JSON请求会被API路由处理
app.get('/settings', requireAuth, (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'settings.html'));
});

// 用户注册API
app.post('/api/register', async (req, res) => {
    try {
        const { username, password, email } = req.body;

        if (!username || !password) {
            return res.status(400).json({ error: '用户名和密码不能为空' });
        }

        const user = await userManager.register(username, password, email || '');
        res.json({ 
            status: 'success', 
            message: '注册成功',
            user: user
        });
    } catch (error) {
        console.error('注册失败:', error);
        res.status(400).json({ error: error.message });
    }
});

// 用户登录API
app.post('/api/login', async (req, res) => {
    try {
        const { username, password } = req.body;

        if (!username || !password) {
            return res.status(400).json({ error: '用户名和密码不能为空' });
        }

        const result = await userManager.login(username, password);
        
        // 设置cookie（可选）
        res.cookie('token', result.token, { 
            httpOnly: true, 
            maxAge: 7 * 24 * 60 * 60 * 1000 // 7天
        });

        res.json({ 
            status: 'success', 
            message: '登录成功',
            token: result.token,
            user: result.user
        });
    } catch (error) {
        console.error('登录失败:', error);
        res.status(401).json({ error: error.message });
    }
});

// 用户登出API（无需认证）
app.post('/api/logout', (req, res) => {
    const token = req.headers['authorization']?.split(' ')[1] || req.cookies?.token || req.query?.token;
    if (token) {
        userManager.logout(token);
    }
    res.clearCookie('token');
    res.json({ status: 'success', message: '登出成功' });
});

// 获取当前用户信息API（无需认证）
app.get('/api/user', (req, res) => {
    const token = req.headers['authorization']?.split(' ')[1] || req.cookies?.token || req.query?.token;
    if (!token) {
        return res.status(401).json({ error: '未提供token' });
    }
    const session = userManager.verifySession(token);
    if (!session) {
        return res.status(401).json({ error: '无效的token' });
    }
    const user = userManager.getUserById(session.userId);
    if (!user) {
        return res.status(404).json({ error: '用户不存在' });
    }
    res.json({ status: 'success', user: user });
});

// 数据接收API（传感器设备无需认证）
app.post('/data', async (req, res) => {
    try {
        const data = req.body;
        if (!data) {
            return res.status(400).json({ error: '无效的JSON数据' });
        }

        // 添加服务器时间戳
        data.server_timestamp = new Date().toISOString();

        // 添加到数据列表
        dataManager.addData(data);

        // 保存数据
        await dataManager.saveData();

        console.log(`收到数据:`, data);
        res.json({ status: 'success', message: '数据已接收' });
    } catch (error) {
        console.error('处理数据时出错:', error);
        res.status(500).json({ error: error.message });
    }
});

app.get('/data', authenticateToken, (req, res) => {
    try {
        const limit = parseInt(req.query.limit) || 100;
        const data = dataManager.getData(limit);
        res.json({
            data: data,
            count: data.length,
            total_count: dataManager.getTotalCount()
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// 清空数据（需要登录）
app.post('/clear', authenticateToken, async (req, res) => {
    try {
        dataManager.clearData();
        await dataManager.saveData();
        console.log('所有数据已清空');
        res.json({ status: 'success', message: '所有数据已清空' });
    } catch (error) {
        console.error('清空数据失败:', error);
        res.status(500).json({ error: error.message });
    }
});

// 图表设置API（需要登录）
app.get('/api/chart-settings', authenticateToken, (req, res) => {
    res.json(dataManager.getChartSettings());
});

app.post('/api/chart-settings', authenticateToken, async (req, res) => {
    try {
        const newSettings = req.body;

        if ('smoothness' in newSettings) {
            dataManager.updateChartSettings('smoothness', parseFloat(newSettings.smoothness));
        }
        if ('point_size' in newSettings) {
            dataManager.updateChartSettings('pointSize', parseInt(newSettings.point_size));
        }
        if ('show_grid' in newSettings) {
            dataManager.updateChartSettings('showGrid', !!newSettings.show_grid);
        }
        if ('show_points' in newSettings) {
            dataManager.updateChartSettings('showPoints', !!newSettings.show_points);
        }
        if ('fill_area' in newSettings) {
            dataManager.updateChartSettings('fillArea', !!newSettings.fill_area);
        }

        await dataManager.saveChartSettings();
        console.log(`图表设置已更新:`, dataManager.getChartSettings());
        res.json({ status: 'success', settings: dataManager.getChartSettings() });
    } catch (error) {
        console.error('更新图表设置失败:', error);
        res.status(500).json({ error: error.message });
    }
});

// V1 API（无需认证）
app.get('/api/v1/sensor-data', (req, res) => {
    try {
        const limit = parseInt(req.query.limit) || 100;
        const offset = parseInt(req.query.offset) || 0;
        const sensor = req.query.sensor;

        let data = dataManager.getData(limit, offset);

        // 过滤特定传感器数据
        if (sensor) {
            const filteredData = [];
            data.forEach(item => {
                const filteredItem = { server_timestamp: item.server_timestamp };
                let added = false;

                if (sensor === 'temperature' && item.temperature !== undefined) {
                    filteredItem.value = item.temperature;
                    filteredItem.unit = '°C';
                    filteredData.push(filteredItem);
                    added = true;
                } else if (sensor === 'humidity' && item.humidity !== undefined) {
                    filteredItem.value = item.humidity;
                    filteredItem.unit = '%';
                    filteredData.push(filteredItem);
                    added = true;
                } else if (sensor === 'pressure' && item.pressure !== undefined) {
                    filteredItem.value = item.pressure;
                    filteredItem.unit = 'hPa';
                    filteredData.push(filteredItem);
                    added = true;
                } else if (sensor === 'voc' && item.voc !== undefined) {
                    filteredItem.value = item.voc;
                    filteredItem.unit = 'index';
                    filteredData.push(filteredItem);
                    added = true;
                } else if (sensor === 'mq_sensor' && item.mq_sensor !== undefined) {
                    filteredItem.value = item.mq_sensor;
                    filteredItem.unit = 'adc';
                    filteredData.push(filteredItem);
                    added = true;
                }
            });
            data = filteredData;
        }

        res.json({
            success: true,
            data: data,
            count: data.length,
            total_count: dataManager.getTotalCount(),
            limit: limit,
            offset: offset,
            sensor: sensor,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/v1/sensor-data/latest', (req, res) => {
    try {
        const latest = dataManager.getLatestData();
        if (!latest) {
            return res.json({
                success: true,
                data: null,
                message: '暂无数据'
            });
        }

        res.json({
            success: true,
            data: latest,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/v1/sensor-data/range', (req, res) => {
    try {
        const startTime = req.query.start;
        const endTime = req.query.end;
        const sensor = req.query.sensor;

        if (!startTime || !endTime) {
            return res.status(400).json({
                success: false,
                error: '需要提供start和end时间参数'
            });
        }

        const startDt = new Date(startTime.replace('Z', '+00:00'));
        const endDt = new Date(endTime.replace('Z', '+00:00'));

        if (isNaN(startDt.getTime()) || isNaN(endDt.getTime())) {
            return res.status(400).json({
                success: false,
                error: '时间格式无效，请使用ISO格式'
            });
        }

        const filteredData = dataManager.getDataByTimeRange(startDt, endDt, sensor);

        res.json({
            success: true,
            data: filteredData,
            count: filteredData.length,
            start_time: startTime,
            end_time: endTime,
            sensor: sensor,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/v1/sensor-data/summary', (req, res) => {
    try {
        const hours = parseInt(req.query.hours) || 24;
        const summary = dataManager.getDataSummary(hours);

        res.json({
            success: true,
            summary: summary,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/v1/export', (req, res) => {
    try {
        const format = req.query.format || 'json';
        const sensor = req.query.sensor;
        const hours = req.query.hours ? parseInt(req.query.hours) : null;

        let exportData = dataManager.getAllData();

        // 按时间过滤
        if (hours) {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - hours * 60 * 60 * 1000);
            exportData = exportData.filter(item => {
                if (item.server_timestamp) {
                    const itemTime = new Date(item.server_timestamp);
                    return itemTime >= startTime;
                }
                return false;
            });
        }

        // 按传感器过滤
        if (sensor) {
            const filtered = [];
            exportData.forEach(item => {
                if (item[sensor] !== undefined) {
                    const unitMap = {
                        temperature: '°C',
                        humidity: '%',
                        pressure: 'hPa',
                        voc: 'index',
                        mq_sensor: 'adc'
                    };

                    filtered.push({
                        timestamp: item.server_timestamp,
                        sensor: sensor,
                        value: item[sensor],
                        unit: unitMap[sensor]
                    });
                }
            });
            exportData = filtered;
        }

        if (format === 'json') {
            res.json({
                success: true,
                export_info: {
                    total_records: exportData.length,
                    sensor: sensor,
                    hours: hours,
                    exported_at: new Date().toISOString()
                },
                data: exportData
            });
        } else {
            res.status(400).json({ success: false, error: `不支持的格式: ${format}` });
        }
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// 统计信息（需要登录）
app.get('/stats', authenticateToken, (req, res) => {
    try {
        const stats = dataManager.getStats();
        res.json(stats);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// OpenMV MQTT API（需要登录）
// 发送命令到OpenMV
app.post('/api/openmv/command', authenticateToken, async (req, res) => {
    try {
        if (!mqttManager) {
            return res.status(503).json({ 
                success: false, 
                error: 'MQTT服务未初始化' 
            });
        }

        const { command, timeout } = req.body;

        if (!command || typeof command !== 'string') {
            return res.status(400).json({ 
                success: false, 
                error: '请提供有效的命令字符串' 
            });
        }

        // 验证命令格式（可选，根据OpenMV支持的命令）
        const validCommands = [
            'COLLECT:',
            'RECOGNIZE',
            'STOP',
            'STATUS',
            'GET_IMAGE',
            'LIST_FACES',
            'DELETE_FACE:'
        ];

        const isValidCommand = validCommands.some(cmd => {
            if (cmd.endsWith(':')) {
                return command.startsWith(cmd);
            }
            return command === cmd;
        });

        if (!isValidCommand) {
            return res.status(400).json({ 
                success: false, 
                error: `无效的命令。支持的命令: ${validCommands.join(', ')}` 
            });
        }

        // 发送命令并等待响应
        const timeoutMs = timeout || 10000; // 默认10秒超时
        const response = await mqttManager.sendCommand(command, timeoutMs);

        res.json({
            success: true,
            command: command,
            response: response,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('[OpenMV API] 发送命令失败:', error);
        res.status(500).json({ 
            success: false, 
            error: error.message || '发送命令失败' 
        });
    }
});

// 获取MQTT连接状态
app.get('/api/openmv/status', authenticateToken, (req, res) => {
    try {
        if (!mqttManager) {
            return res.json({
                success: false,
                connected: false,
                message: 'MQTT服务未初始化'
            });
        }

        const status = mqttManager.getConnectionStatus();
        res.json({
            success: true,
            ...status,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ 
            success: false, 
            error: error.message 
        });
    }
});

// 获取最近的识别结果
app.get('/api/openmv/recognition-results', authenticateToken, (req, res) => {
    try {
        if (!mqttManager) {
            return res.status(503).json({ 
                success: false, 
                error: 'MQTT服务未初始化' 
            });
        }

        const limit = parseInt(req.query.limit) || 10;
        const results = mqttManager.getRecognitionResults(limit);
        
        res.json({
            success: true,
            results: results,
            count: results.length,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ 
            success: false, 
            error: error.message 
        });
    }
});

// 清除识别结果
app.delete('/api/openmv/recognition-results', authenticateToken, (req, res) => {
    try {
        if (!mqttManager) {
            return res.status(503).json({ 
                success: false, 
                error: 'MQTT服务未初始化' 
            });
        }

        mqttManager.clearRecognitionResults();
        
        res.json({
            success: true,
            message: '识别结果已清除',
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ 
            success: false, 
            error: error.message 
        });
    }
});

// 启动定期清理任务
function startPeriodicCleanup() {
    if (configManager.getConfig()['data']['auto_cleanup']) {
        setInterval(() => {
            dataManager.cleanupOldData();
        }, 5 * 60 * 1000); // 每5分钟清理一次
    }
}

// 启动服务器
async function startServer() {
    try {
        await initializeApp();

        const config = configManager.getConfig();
        const host = config.server.host;
        const port = config.server.port;

        // 更新全局设置中的最大数据点数
        dataManager.updateMaxDataPoints(config.data.max_data_points);

        // 启动定期清理
        startPeriodicCleanup();

        app.listen(port, host, () => {
            console.log('🏠 智能家居传感器数据服务器启动...');
            console.log(`📁 数据文件: ${dataManager.dataFile}`);
            console.log(`⚙️ 设置文件: ${dataManager.settingsFile}`);
            console.log(`📊 图表设置文件: ${dataManager.chartSettingsFile}`);
            console.log(`🔧 配置文件: ${configManager.configFile}`);
            console.log(`🌐 服务器地址: http://${host}:${port}`);
            console.log(`📈 最大数据点数: ${dataManager.getSettings().max_data_points}`);
            console.log(`🔄 自动清理: ${config.data.auto_cleanup ? '启用' : '禁用'}`);
            if (mqttManager) {
                console.log(`📡 MQTT功能: 已启用`);
            } else {
                console.log(`📡 MQTT功能: 未启用`);
            }
            console.log(`🎯 访问地址: http://localhost:${port}`);
        });

        // 优雅关闭：断开MQTT连接
        process.on('SIGINT', () => {
            console.log('\n正在关闭服务器...');
            if (mqttManager) {
                mqttManager.disconnect();
            }
            process.exit(0);
        });

        process.on('SIGTERM', () => {
            console.log('\n正在关闭服务器...');
            if (mqttManager) {
                mqttManager.disconnect();
            }
            process.exit(0);
        });
    } catch (error) {
        console.error('启动服务器失败:', error);
        process.exit(1);
    }
}

// 处理命令行参数
function getServerPort() {
    const args = process.argv.slice(2);
    if (args.length > 0) {
        const port = parseInt(args[0]);
        if (port >= 1000 && port <= 65535) {
            return port;
        }
    }

    // 检查环境变量
    const envPort = process.env.SMARTHOME_PORT;
    if (envPort) {
        const port = parseInt(envPort);
        if (port >= 1000 && port <= 65535) {
            return port;
        }
    }

    // 使用配置文件中的端口
    return configManager.getConfig().server.port;
}

startServer();
