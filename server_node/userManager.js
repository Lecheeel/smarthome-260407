const fs = require('fs-extra');
const path = require('path');
const crypto = require('crypto');

class UserManager {
    constructor() {
        this.usersFile = path.join(process.cwd(), 'users.json');
        this.users = [];
        this.sessions = new Map(); // 存储活跃会话
    }

    // 加载用户数据
    async loadUsers() {
        try {
            if (await fs.pathExists(this.usersFile)) {
                const data = await fs.readJson(this.usersFile);
                this.users = data.users || [];
            } else {
                this.users = [];
                await this.saveUsers();
            }
        } catch (error) {
            console.error('加载用户数据失败:', error);
            this.users = [];
        }
    }

    // 保存用户数据
    async saveUsers() {
        try {
            await fs.writeJson(this.usersFile, { users: this.users }, { spaces: 2 });
        } catch (error) {
            console.error('保存用户数据失败:', error);
            throw error;
        }
    }

    // 生成密码哈希（使用SHA-256 + 盐值）
    hashPassword(password) {
        const salt = crypto.randomBytes(16).toString('hex');
        const hash = crypto.pbkdf2Sync(password, salt, 10000, 64, 'sha512').toString('hex');
        return {
            salt: salt,
            hash: hash
        };
    }

    // 验证密码
    verifyPassword(password, salt, hash) {
        const verifyHash = crypto.pbkdf2Sync(password, salt, 10000, 64, 'sha512').toString('hex');
        return hash === verifyHash;
    }

    // 注册新用户
    async register(username, password, email = '') {
        // 检查用户名是否已存在
        if (this.users.find(u => u.username === username)) {
            throw new Error('用户名已存在');
        }

        // 验证用户名和密码
        if (!username || username.length < 3) {
            throw new Error('用户名至少需要3个字符');
        }

        if (!password || password.length < 6) {
            throw new Error('密码至少需要6个字符');
        }

        // 加密密码
        const { salt, hash } = this.hashPassword(password);

        // 创建新用户
        const newUser = {
            id: crypto.randomBytes(16).toString('hex'),
            username: username,
            email: email,
            passwordHash: hash,
            passwordSalt: salt,
            createdAt: new Date().toISOString(),
            lastLogin: null
        };

        this.users.push(newUser);
        await this.saveUsers();

        return {
            id: newUser.id,
            username: newUser.username,
            email: newUser.email,
            createdAt: newUser.createdAt
        };
    }

    // 用户登录
    async login(username, password) {
        const user = this.users.find(u => u.username === username);
        
        if (!user) {
            throw new Error('用户名或密码错误');
        }

        // 验证密码
        if (!this.verifyPassword(password, user.passwordSalt, user.passwordHash)) {
            throw new Error('用户名或密码错误');
        }

        // 更新最后登录时间
        user.lastLogin = new Date().toISOString();
        await this.saveUsers();

        // 生成会话token
        const token = crypto.randomBytes(32).toString('hex');
        this.sessions.set(token, {
            userId: user.id,
            username: user.username,
            createdAt: new Date().toISOString()
        });

        return {
            token: token,
            user: {
                id: user.id,
                username: user.username,
                email: user.email
            }
        };
    }

    // 验证会话token
    verifySession(token) {
        const session = this.sessions.get(token);
        if (!session) {
            return null;
        }
        return session;
    }

    // 登出
    logout(token) {
        this.sessions.delete(token);
    }

    // 获取用户信息
    getUserById(userId) {
        const user = this.users.find(u => u.id === userId);
        if (!user) {
            return null;
        }
        return {
            id: user.id,
            username: user.username,
            email: user.email,
            createdAt: user.createdAt,
            lastLogin: user.lastLogin
        };
    }
}

module.exports = { UserManager };

