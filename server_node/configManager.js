const fs = require('fs-extra');
const path = require('path');

class ConfigManager {
    constructor() {
        this.configFile = path.join(process.cwd(), 'server_config.json');
        this.defaultConfig = {
            server: {
                host: "0.0.0.0",
                port: 13501,
                debug: true
            },
            data: {
                max_data_points: 1000,
                auto_cleanup: true
            },
            api: {
                version: "v1",
                cors_enabled: true
            }
        };
        this.config = { ...this.defaultConfig };
    }

    async loadConfig() {
        try {
            if (await fs.pathExists(this.configFile)) {
                const userConfig = await fs.readJson(this.configFile);
                this.config = this.mergeConfigs(this.defaultConfig, userConfig);
            } else {
                // 创建默认配置文件
                await this.saveConfig();
            }
        } catch (error) {
            console.error('加载配置文件失败，使用默认配置:', error);
            this.config = { ...this.defaultConfig };
        }
    }

    async saveConfig() {
        try {
            await fs.writeJson(this.configFile, this.config, { spaces: 2 });
        } catch (error) {
            console.error('保存配置文件失败:', error);
            throw error;
        }
    }

    getConfig() {
        return { ...this.config };
    }

    mergeConfigs(defaultConfig, userConfig) {
        const result = { ...defaultConfig };

        for (const key in userConfig) {
            if (key in result && typeof result[key] === 'object' && result[key] !== null && typeof userConfig[key] === 'object' && userConfig[key] !== null) {
                result[key] = this.mergeConfigs(result[key], userConfig[key]);
            } else {
                result[key] = userConfig[key];
            }
        }

        return result;
    }
}

module.exports = { ConfigManager };
