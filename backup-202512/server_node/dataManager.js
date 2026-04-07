const fs = require('fs-extra');
const path = require('path');

class DataManager {
    constructor() {
        this.dataFile = path.join(process.cwd(), 'sensor_data.json');
        this.settingsFile = path.join(process.cwd(), 'settings.json');
        this.chartSettingsFile = path.join(process.cwd(), 'chart_settings.json');

        this.sensorData = [];
        this.settings = {
            max_data_points: 1000,
            update_rate: 5,
            image_update_rate: 1000,  // 图像更新频率（毫秒），默认1秒
            recognition_timeout: 5000  // 识别超时时间（毫秒），默认5秒
        };
        this.chartSettings = {
            smoothness: 0.1,
            pointSize: 2,
            showGrid: true,
            showPoints: true,
            fillArea: true
        };
    }

    // 数据管理
    async loadData() {
        try {
            if (await fs.pathExists(this.dataFile)) {
                const data = await fs.readJson(this.dataFile);
                this.sensorData = Array.isArray(data) ? data : [];
            } else {
                this.sensorData = [];
            }
        } catch (error) {
            console.error('加载数据失败:', error);
            this.sensorData = [];
        }
    }

    async saveData() {
        try {
            await fs.writeJson(this.dataFile, this.sensorData, { spaces: 2 });
        } catch (error) {
            console.error('保存数据失败:', error);
            throw error;
        }
    }

    addData(data) {
        this.sensorData.push(data);
        this.cleanupOldData();
    }

    getData(limit = 100, offset = 0) {
        const start = Math.max(0, this.sensorData.length - offset - limit);
        const end = this.sensorData.length - offset;
        return this.sensorData.slice(start, end);
    }

    getAllData() {
        return [...this.sensorData];
    }

    getTotalCount() {
        return this.sensorData.length;
    }

    getLatestData() {
        return this.sensorData.length > 0 ? this.sensorData[this.sensorData.length - 1] : null;
    }

    clearData() {
        this.sensorData = [];
    }

    cleanupOldData() {
        const maxPoints = this.settings.max_data_points;
        if (this.sensorData.length > maxPoints) {
            this.sensorData = this.sensorData.slice(-maxPoints);
        }
    }

    // 设置管理
    async loadSettings() {
        try {
            if (await fs.pathExists(this.settingsFile)) {
                const settings = await fs.readJson(this.settingsFile);
                this.settings = { ...this.settings, ...settings };
            }
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    }

    async saveSettings() {
        try {
            await fs.writeJson(this.settingsFile, this.settings, { spaces: 2 });
        } catch (error) {
            console.error('保存设置失败:', error);
            throw error;
        }
    }

    getSettings() {
        return { ...this.settings };
    }

    updateMaxDataPoints(points) {
        this.settings.max_data_points = points;
    }

    updateUpdateRate(rate) {
        this.settings.update_rate = rate;
    }

    updateImageUpdateRate(rate) {
        this.settings.image_update_rate = rate;
    }

    updateRecognitionTimeout(timeout) {
        this.settings.recognition_timeout = timeout;
    }

    // 图表设置管理
    async loadChartSettings() {
        try {
            if (await fs.pathExists(this.chartSettingsFile)) {
                const settings = await fs.readJson(this.chartSettingsFile);
                this.chartSettings = { ...this.chartSettings, ...settings };
            }
        } catch (error) {
            console.error('加载图表设置失败:', error);
        }
    }

    async saveChartSettings() {
        try {
            await fs.writeJson(this.chartSettingsFile, this.chartSettings, { spaces: 2 });
        } catch (error) {
            console.error('保存图表设置失败:', error);
            throw error;
        }
    }

    getChartSettings() {
        return { ...this.chartSettings };
    }

    updateChartSettings(key, value) {
        this.chartSettings[key] = value;
    }

    // 数据分析
    getStats() {
        if (this.sensorData.length === 0) {
            return {
                count: 0,
                temperature: { min: null, max: null, avg: null },
                humidity: { min: null, max: null, avg: null },
                pressure: { min: null, max: null, avg: null },
                voc: { min: null, max: null, avg: null },
                mq_sensor: { min: null, max: null, avg: null }
            };
        }

        const stats = {
            count: this.sensorData.length,
            temperature: { values: [], min: null, max: null, avg: null },
            humidity: { values: [], min: null, max: null, avg: null },
            pressure: { values: [], min: null, max: null, avg: null },
            voc: { values: [], min: null, max: null, avg: null },
            mq_sensor: { values: [], min: null, max: null, avg: null }
        };

        // 收集数据
        this.sensorData.forEach(item => {
            if (item.temperature !== undefined) stats.temperature.values.push(item.temperature);
            if (item.humidity !== undefined) stats.humidity.values.push(item.humidity);
            if (item.pressure !== undefined) stats.pressure.values.push(item.pressure);
            if (item.voc !== undefined) stats.voc.values.push(item.voc);
            if (item.mq_sensor !== undefined) stats.mq_sensor.values.push(item.mq_sensor);
        });

        // 计算统计值
        ['temperature', 'humidity', 'pressure', 'voc', 'mq_sensor'].forEach(sensor => {
            const values = stats[sensor].values;
            if (values.length > 0) {
                stats[sensor].min = Math.min(...values);
                stats[sensor].max = Math.max(...values);
                stats[sensor].avg = values.reduce((a, b) => a + b, 0) / values.length;
            }
            delete stats[sensor].values; // 移除原始值列表
        });

        return stats;
    }

    getDataByTimeRange(startTime, endTime, sensor) {
        const filteredData = [];

        this.sensorData.forEach(item => {
            if (item.server_timestamp) {
                const itemTime = new Date(item.server_timestamp);
                if (itemTime >= startTime && itemTime <= endTime) {
                    if (sensor) {
                        // 只返回指定传感器的数据
                        if (sensor === 'temperature' && item.temperature !== undefined) {
                            filteredData.push({
                                timestamp: item.server_timestamp,
                                value: item.temperature,
                                unit: '°C',
                                sensor: 'temperature'
                            });
                        } else if (sensor === 'humidity' && item.humidity !== undefined) {
                            filteredData.push({
                                timestamp: item.server_timestamp,
                                value: item.humidity,
                                unit: '%',
                                sensor: 'humidity'
                            });
                        } else if (sensor === 'pressure' && item.pressure !== undefined) {
                            filteredData.push({
                                timestamp: item.server_timestamp,
                                value: item.pressure,
                                unit: 'hPa',
                                sensor: 'pressure'
                            });
                        } else if (sensor === 'voc' && item.voc !== undefined) {
                            filteredData.push({
                                timestamp: item.server_timestamp,
                                value: item.voc,
                                unit: 'index',
                                sensor: 'voc'
                            });
                        } else if (sensor === 'mq_sensor' && item.mq_sensor !== undefined) {
                            filteredData.push({
                                timestamp: item.server_timestamp,
                                value: item.mq_sensor,
                                unit: 'adc',
                                sensor: 'mq_sensor'
                            });
                        }
                    } else {
                        // 返回所有传感器数据
                        filteredData.push(item);
                    }
                }
            }
        });

        return filteredData;
    }

    getDataSummary(hours = 24) {
        const endTime = new Date();
        const startTime = new Date(endTime.getTime() - hours * 60 * 60 * 1000);

        // 过滤数据
        const filteredData = this.sensorData.filter(item => {
            if (item.server_timestamp) {
                const itemTime = new Date(item.server_timestamp);
                return itemTime >= startTime;
            }
            return false;
        });

        // 计算统计信息
        const summary = {
            total_records: filteredData.length,
            time_range: {
                start: startTime.toISOString(),
                end: endTime.toISOString(),
                hours: hours
            },
            sensors: {}
        };

        // 为每个传感器计算统计
        const sensors = ['temperature', 'humidity', 'pressure', 'voc', 'mq_sensor'];
        sensors.forEach(sensor => {
            const values = [];
            filteredData.forEach(item => {
                if (item[sensor] !== undefined) {
                    values.push(item[sensor]);
                }
            });

            const unitMap = {
                temperature: '°C',
                humidity: '%',
                pressure: 'hPa',
                voc: 'index',
                mq_sensor: 'adc'
            };

            if (values.length > 0) {
                summary.sensors[sensor] = {
                    count: values.length,
                    min: Math.min(...values),
                    max: Math.max(...values),
                    avg: values.reduce((a, b) => a + b, 0) / values.length,
                    latest: values[values.length - 1],
                    unit: unitMap[sensor]
                };
            }
        });

        return summary;
    }
}

module.exports = { DataManager };
