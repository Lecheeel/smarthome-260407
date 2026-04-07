// 获取认证token
function getAuthToken() {
    return localStorage.getItem('token') || '';
}

// 创建带认证头的fetch请求
function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    return fetch(url, { ...options, headers });
}

// 检查登录状态
async function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/login';
        return false;
    }
    
    try {
        const response = await fetchWithAuth('/api/user');
        if (!response.ok) {
            if (response.status === 401) {
                localStorage.removeItem('token');
                localStorage.removeItem('username');
                window.location.href = '/login';
                return false;
            }
        } else {
            const result = await response.json();
            if (result.user) {
                document.getElementById('usernameDisplay').textContent = result.user.username;
            }
        }
        return true;
    } catch (error) {
        console.error('检查认证状态失败:', error);
        return false;
    }
}

// 登出功能
async function logout() {
    const token = getAuthToken();
    if (token) {
        try {
            await fetchWithAuth('/api/logout', { method: 'POST' });
        } catch (error) {
            console.error('登出失败:', error);
        }
    }
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    window.location.href = '/login';
}

// 加载数据
async function loadData() {
    const indicator = document.getElementById('updateIndicator');
    indicator.style.display = 'block'; // 显示更新指示器

    try {
        // 并行加载数据和统计信息，提高性能
        const [dataResponse, statsResponse] = await Promise.all([
            fetchWithAuth('/data?limit=200'), // 减少数据点数，提高加载速度
            fetchWithAuth('/stats')
        ]);

        const [result, stats] = await Promise.all([
            dataResponse.json(),
            statsResponse.json()
        ]);

        if (result.data) {
            updateCharts(result.data);
            document.getElementById('totalDataPoints').textContent = result.total_count || 0;

            // 更新最后更新时间
            if (result.data.length > 0) {
                const lastData = result.data[result.data.length - 1];
                if (lastData.server_timestamp) {
                    const date = new Date(lastData.server_timestamp);
                    document.getElementById('lastUpdate').textContent =
                        date.toLocaleString('zh-CN');
                }
            }
        }

        updateStats(stats);

        // 更新连接状态
        const statusEl = document.getElementById('connectionStatus');
        statusEl.className = 'status connected';
        statusEl.innerHTML = '<span>✅</span><span>连接状态: 已连接</span>';

    } catch (error) {
        console.error('加载数据失败:', error);
        const statusEl = document.getElementById('connectionStatus');
        statusEl.className = 'status disconnected';
        statusEl.innerHTML = '<span>❌</span><span>连接状态: 连接失败</span>';

        // 连接失败时不更新图表，保持现有数据
        // 这避免了连接中断时的图表空白
    } finally {
        // 延迟隐藏指示器，让用户看到更新效果
        setTimeout(() => {
            indicator.style.display = 'none';
        }, 500);
    }
}

// 加载设置
async function loadSettings() {
    try {
        // 加载数据设置
        const response = await fetchWithAuth('/api/settings');
        const settings = await response.json();
        
        // 更新数据设置（如果元素存在）
        const maxDataPointsEl = document.getElementById('maxDataPoints');
        if (maxDataPointsEl) {
            maxDataPointsEl.value = settings.max_data_points || 1000;
        }
        
        const updateRateEl = document.getElementById('updateRate');
        if (updateRateEl) {
            updateRateEl.value = settings.update_rate || 5;
        }
        updateRate = settings.update_rate || 5;
        
        // 加载图像更新频率设置
        const imageUpdateRateEl = document.getElementById('imageUpdateRate');
        if (imageUpdateRateEl) {
            imageUpdateRateEl.value = settings.image_update_rate || 1000;
        }
        
        const recognitionTimeoutEl = document.getElementById('recognitionTimeout');
        if (recognitionTimeoutEl) {
            recognitionTimeoutEl.value = settings.recognition_timeout || 5000;
        }

        // 加载图表设置
        const chartResponse = await fetchWithAuth('/api/chart-settings');
        const chartSettingsData = await chartResponse.json();

        // 更新全局设置
        chartSettings = { ...chartSettings, ...chartSettingsData };

        // 更新表单UI（如果元素存在）
        const chartSmoothnessEl = document.getElementById('chartSmoothness');
        if (chartSmoothnessEl) {
            chartSmoothnessEl.value = chartSettings.smoothness;
        }
        
        const smoothnessValueEl = document.getElementById('smoothnessValue');
        if (smoothnessValueEl) {
            smoothnessValueEl.textContent = chartSettings.smoothness;
        }
        
        const pointSizeEl = document.getElementById('pointSize');
        if (pointSizeEl) {
            pointSizeEl.value = chartSettings.pointSize;
        }
        
        const pointSizeValueEl = document.getElementById('pointSizeValue');
        if (pointSizeValueEl) {
            pointSizeValueEl.textContent = chartSettings.pointSize;
        }
        
        const showGridEl = document.getElementById('showGrid');
        if (showGridEl) {
            showGridEl.checked = chartSettings.showGrid;
        }
        
        const showPointsEl = document.getElementById('showPoints');
        if (showPointsEl) {
            showPointsEl.checked = chartSettings.showPoints;
        }
        
        const fillAreaEl = document.getElementById('fillArea');
        if (fillAreaEl) {
            fillAreaEl.checked = chartSettings.fillArea;
        }

        // 更新自动刷新间隔（仅在仪表板页面）
        if (typeof updateAutoRefresh === 'function' && getCurrentPage() === 'dashboard') {
            updateAutoRefresh();
        }

    } catch (error) {
        console.error('加载设置失败:', error);
    }
}

// 保存设置
async function saveSettings(maxDataPoints, updateRateValue, imageUpdateRateValue, recognitionTimeoutValue) {
    try {
        const response = await fetchWithAuth('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                max_data_points: parseInt(maxDataPoints),
                update_rate: parseInt(updateRateValue),
                image_update_rate: parseInt(imageUpdateRateValue),
                recognition_timeout: parseInt(recognitionTimeoutValue)
            })
        });

        const result = await response.json();
        if (result.status === 'success') {
            alert('设置已保存！');
            loadSettings();
            
            // 通知 faceSystem 更新图像流频率和识别超时时间
            if (typeof faceSystem !== 'undefined') {
                if (faceSystem.updateImageStreamRate) {
                    faceSystem.updateImageStreamRate(parseInt(imageUpdateRateValue));
                }
                if (faceSystem.recognitionTimeout !== undefined) {
                    faceSystem.recognitionTimeout = parseInt(recognitionTimeoutValue);
                }
            }
        } else {
            alert('保存设置失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        alert('保存设置失败: ' + error.message);
    }
}

// 清空数据
async function clearData() {
    if (!confirm('确定要清空所有数据吗？此操作不可恢复！')) {
        return;
    }

    try {
        const response = await fetchWithAuth('/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();
        if (result.status === 'success') {
            alert('所有数据已清空！');
            // 如果在仪表板页面，重新加载数据
            if (getCurrentPage() === 'dashboard' && typeof loadData === 'function') {
                loadData();
            }
        } else {
            alert('清空数据失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('清空数据失败:', error);
        alert('清空数据失败: ' + error.message);
    }
}

// 保存图表设置
async function saveChartSettings() {
    try {
        // 从表单获取当前值
        const newSettings = {
            smoothness: parseFloat(document.getElementById('chartSmoothness').value),
            point_size: parseInt(document.getElementById('pointSize').value),
            show_grid: document.getElementById('showGrid').checked,
            show_points: document.getElementById('showPoints').checked,
            fill_area: document.getElementById('fillArea').checked
        };

        const response = await fetchWithAuth('/api/chart-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(newSettings)
        });

        const result = await response.json();
        if (result.status === 'success') {
            // 更新全局设置
            chartSettings = { ...chartSettings, ...result.settings };
            alert('图表设置已保存！');
        } else {
            alert('保存图表设置失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存图表设置失败:', error);
        alert('保存图表设置失败: ' + error.message);
    }
}

// 获取当前页面路径
function getCurrentPage() {
    const path = window.location.pathname;
    if (path === '/' || path === '/dashboard' || path.includes('dashboard')) {
        return 'dashboard';
    } else if (path === '/face' || path.includes('face')) {
        return 'face';
    } else if (path === '/settings' || path.includes('settings')) {
        return 'settings';
    }
    return 'dashboard'; // 默认
}

// 事件监听器
document.addEventListener('DOMContentLoaded', async function() {
    // 检查登录状态
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) {
        return;
    }

    const currentPage = getCurrentPage();

    // 登出按钮（所有页面都有）
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // 根据页面初始化不同的功能
    if (currentPage === 'dashboard') {
        // 仪表板页面：初始化图表和数据加载
        initCharts();
        loadSettings();
        loadData();
        updateAutoRefresh();
    } else if (currentPage === 'face') {
        // 人脸系统页面：初始化人脸系统
        if (typeof faceSystem !== 'undefined') {
            faceSystem.init();

            // 人脸收集表单
            const collectFaceForm = document.getElementById('collectFaceForm');
            if (collectFaceForm) {
                collectFaceForm.addEventListener('submit', async function(e) {
                    e.preventDefault();
                    const nameInput = document.getElementById('collectName');
                    const name = nameInput.value.trim();
                    
                    if (!name) {
                        alert('请输入姓名');
                        return;
                    }

                    try {
                        await faceSystem.startCollect(name);
                        nameInput.value = '';
                    } catch (error) {
                        alert(`启动收集失败: ${error.message}`);
                    }
                });
            }

            // 开始识别按钮
            const startRecognizeBtn = document.getElementById('startRecognizeBtn');
            if (startRecognizeBtn) {
                startRecognizeBtn.addEventListener('click', async function() {
                    try {
                        await faceSystem.startRecognize();
                    } catch (error) {
                        alert(`启动识别失败: ${error.message}`);
                    }
                });
            }

            // 停止按钮
            const stopBtn = document.getElementById('stopBtn');
            if (stopBtn) {
                stopBtn.addEventListener('click', async function() {
                    try {
                        await faceSystem.stop();
                    } catch (error) {
                        alert(`停止失败: ${error.message}`);
                    }
                });
            }

            // 获取图像按钮
            const getImageBtn = document.getElementById('getImageBtn');
            if (getImageBtn) {
                getImageBtn.addEventListener('click', async function() {
                    try {
                        const imageData = await faceSystem.getImage();
                        faceSystem.displayImage(imageData);
                        faceSystem.updateStatus('图像已获取', 'success');
                    } catch (error) {
                        alert(`获取图像失败: ${error.message}`);
                    }
                });
            }

            // 刷新人脸列表按钮
            const refreshFacesBtn = document.getElementById('refreshFacesBtn');
            if (refreshFacesBtn) {
                refreshFacesBtn.addEventListener('click', async function() {
                    try {
                        await faceSystem.listFaces();
                        faceSystem.updateStatus('列表已刷新', 'success');
                    } catch (error) {
                        alert(`刷新列表失败: ${error.message}`);
                    }
                });
            }

            // 清除识别结果按钮
            const clearRecognitionResultsBtn = document.getElementById('clearRecognitionResultsBtn');
            if (clearRecognitionResultsBtn) {
                clearRecognitionResultsBtn.addEventListener('click', async function() {
                    if (confirm('确定要清除所有识别记录吗？')) {
                        try {
                            await faceSystem.clearRecognitionResults();
                        } catch (error) {
                            alert(`清除失败: ${error.message}`);
                        }
                    }
                });
            }
        }
    } else if (currentPage === 'settings') {
        // 设置页面：初始化设置表单
        loadSettings();

        // 设置表单提交
        const settingsForm = document.getElementById('settingsForm');
        if (settingsForm) {
            settingsForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const maxDataPoints = document.getElementById('maxDataPoints').value;
                const updateRateValue = document.getElementById('updateRate').value;
                const imageUpdateRateValue = document.getElementById('imageUpdateRate').value;
                const recognitionTimeoutValue = document.getElementById('recognitionTimeout').value;
                saveSettings(maxDataPoints, updateRateValue, imageUpdateRateValue, recognitionTimeoutValue);
            });
        }

        // 刷新按钮
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                // 跳转到仪表板页面刷新数据
                window.location.href = '/dashboard';
            });
        }

        // 清空数据按钮
        const clearDataBtn = document.getElementById('clearDataBtn');
        if (clearDataBtn) {
            clearDataBtn.addEventListener('click', clearData);
        }

        // 图表设置表单
        const chartSettingsForm = document.getElementById('chartSettingsForm');
        if (chartSettingsForm) {
            chartSettingsForm.addEventListener('submit', function(e) {
                e.preventDefault();
                saveChartSettings();
            });

            // 实时预览滑块变化（仅更新显示值，不更新图表，因为设置页面没有图表）
            const chartSmoothness = document.getElementById('chartSmoothness');
            if (chartSmoothness) {
                chartSmoothness.addEventListener('input', function(e) {
                    const value = parseFloat(e.target.value);
                    const smoothnessValue = document.getElementById('smoothnessValue');
                    if (smoothnessValue) {
                        smoothnessValue.textContent = value;
                    }
                });
            }

            const pointSize = document.getElementById('pointSize');
            if (pointSize) {
                pointSize.addEventListener('input', function(e) {
                    const value = parseInt(e.target.value);
                    const pointSizeValue = document.getElementById('pointSizeValue');
                    if (pointSizeValue) {
                        pointSizeValue.textContent = value;
                    }
                });
            }
        }
    }

    // 页面关闭时清理定时器
    window.addEventListener('beforeunload', function() {
        if (typeof updateInterval !== 'undefined' && updateInterval) {
            clearInterval(updateInterval);
        }
        if (typeof faceSystem !== 'undefined') {
            if (faceSystem.imageUpdateInterval) {
                clearInterval(faceSystem.imageUpdateInterval);
            }
            if (faceSystem.progressInterval) {
                clearInterval(faceSystem.progressInterval);
            }
            if (faceSystem.recognitionUpdateInterval) {
                clearInterval(faceSystem.recognitionUpdateInterval);
            }
        }
    });
});
