// 图表实例
let temperatureChart, humidityChart, pressureChart, vocChart, mqSensorChart;
let updateInterval;
let updateRate = 5; // 默认5秒更新一次

// 图表设置
let chartSettings = {
    smoothness: 0.1,
    pointSize: 2,
    showGrid: true,
    showPoints: true,
    fillArea: true
};

// 更新自动更新间隔
function updateAutoRefresh() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    updateInterval = setInterval(loadData, updateRate * 1000);
}

// 更新图表设置
function updateChartSettings() {
    const charts = [temperatureChart, humidityChart, pressureChart, vocChart, mqSensorChart];

    charts.forEach(chart => {
        if (chart) {
            // 更新线条平滑度
            chart.options.elements.line.tension = chartSettings.smoothness;

            // 更新数据点设置
            chart.data.datasets[0].pointRadius = chartSettings.showPoints ? chartSettings.pointSize : 0;
            chart.data.datasets[0].pointHoverRadius = chartSettings.showPoints ? chartSettings.pointSize + 2 : 0;

            // 更新填充
            chart.data.datasets[0].fill = chartSettings.fillArea;

            // 更新网格线
            chart.options.scales.x.grid.display = chartSettings.showGrid;
            chart.options.scales.y.grid.display = chartSettings.showGrid;

            // 重新渲染图表
            chart.update('none');
        }
    });
}

// 初始化图表
function initCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            x: {
                type: 'time',
                time: {
                    displayFormats: {
                        minute: 'HH:mm',
                        hour: 'MM/dd HH:mm'
                    }
                },
                title: {
                    display: true,
                    text: '时间'
                },
                grid: {
                    display: chartSettings.showGrid
                }
            },
            y: {
                beginAtZero: false,
                grid: {
                    display: chartSettings.showGrid
                }
            }
        },
        elements: {
            point: {
                radius: chartSettings.pointSize
            },
            line: {
                tension: chartSettings.smoothness
            }
        }
    };

    // 温度图表
    temperatureChart = new Chart(
        document.getElementById('temperatureChart'),
        {
            type: 'line',
            data: {
                datasets: [{
                    label: '温度 (°C)',
                    data: [],
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    fill: chartSettings.fillArea,
                    pointRadius: chartSettings.showPoints ? chartSettings.pointSize : 0,
                    pointHoverRadius: chartSettings.showPoints ? chartSettings.pointSize + 2 : 0
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: {
                        ...commonOptions.scales.y,
                        title: {
                            display: true,
                            text: '温度 (°C)'
                        }
                    }
                }
            }
        }
    );

    // 湿度图表
    humidityChart = new Chart(
        document.getElementById('humidityChart'),
        {
            type: 'line',
            data: {
                datasets: [{
                    label: '湿度 (%)',
                    data: [],
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78, 205, 196, 0.1)',
                    fill: chartSettings.fillArea,
                    pointRadius: chartSettings.showPoints ? chartSettings.pointSize : 0,
                    pointHoverRadius: chartSettings.showPoints ? chartSettings.pointSize + 2 : 0
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: {
                        ...commonOptions.scales.y,
                        title: {
                            display: true,
                            text: '湿度 (%)'
                        }
                    }
                }
            }
        }
    );

    // 气压图表
    pressureChart = new Chart(
        document.getElementById('pressureChart'),
        {
            type: 'line',
            data: {
                datasets: [{
                    label: '气压 (hPa)',
                    data: [],
                    borderColor: '#45b7d1',
                    backgroundColor: 'rgba(69, 183, 209, 0.1)',
                    fill: chartSettings.fillArea,
                    pointRadius: chartSettings.showPoints ? chartSettings.pointSize : 0,
                    pointHoverRadius: chartSettings.showPoints ? chartSettings.pointSize + 2 : 0
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: {
                        ...commonOptions.scales.y,
                        min: 1020,
                        max: 1030,
                        title: {
                            display: true,
                            text: '气压 (hPa)'
                        }
                    }
                }
            }
        }
    );

    // VOC图表
    vocChart = new Chart(
        document.getElementById('vocChart'),
        {
            type: 'line',
            data: {
                datasets: [{
                    label: 'VOC',
                    data: [],
                    borderColor: '#96ceb4',
                    backgroundColor: 'rgba(150, 206, 180, 0.1)',
                    fill: chartSettings.fillArea,
                    pointRadius: chartSettings.showPoints ? chartSettings.pointSize : 0,
                    pointHoverRadius: chartSettings.showPoints ? chartSettings.pointSize + 2 : 0
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: {
                        ...commonOptions.scales.y,
                        title: {
                            display: true,
                            text: 'VOC 指数'
                        }
                    }
                }
            }
        }
    );

    // MQ传感器图表
    mqSensorChart = new Chart(
        document.getElementById('mqSensorChart'),
        {
            type: 'line',
            data: {
                datasets: [{
                    label: 'MQ传感器',
                    data: [],
                    borderColor: '#ff7b7b',
                    backgroundColor: 'rgba(255, 123, 123, 0.1)',
                    fill: chartSettings.fillArea,
                    pointRadius: chartSettings.showPoints ? chartSettings.pointSize : 0,
                    pointHoverRadius: chartSettings.showPoints ? chartSettings.pointSize + 2 : 0
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: {
                        ...commonOptions.scales.y,
                        title: {
                            display: true,
                            text: 'MQ传感器 (ADC值)'
                        }
                    }
                }
            }
        }
    );
}

// 更新图表数据
function updateCharts(data) {
    if (!data || !Array.isArray(data)) return;

    const temperatureData = [];
    const humidityData = [];
    const pressureData = [];
    const vocData = [];
    const mqSensorData = [];

    data.forEach(item => {
        const timestamp = item.server_timestamp ? new Date(item.server_timestamp) : new Date();

        if (item.temperature !== null && item.temperature !== undefined) {
            temperatureData.push({
                x: timestamp,
                y: item.temperature
            });
        }

        if (item.humidity !== null && item.humidity !== undefined) {
            humidityData.push({
                x: timestamp,
                y: item.humidity
            });
        }

        if (item.pressure !== null && item.pressure !== undefined) {
            pressureData.push({
                x: timestamp,
                y: item.pressure
            });
        }

        if (item.voc !== null && item.voc !== undefined) {
            vocData.push({
                x: timestamp,
                y: item.voc
            });
        }

        if (item.mq_sensor !== null && item.mq_sensor !== undefined) {
            mqSensorData.push({
                x: timestamp,
                y: item.mq_sensor
            });
        }
    });

    // 更新图表数据
    temperatureChart.data.datasets[0].data = temperatureData;
    humidityChart.data.datasets[0].data = humidityData;
    pressureChart.data.datasets[0].data = pressureData;
    vocChart.data.datasets[0].data = vocData;
    mqSensorChart.data.datasets[0].data = mqSensorData;

    // 如果没有数据，显示提示信息
    if (temperatureData.length === 0) {
        temperatureChart.options.plugins.legend.display = false;
        temperatureChart.options.plugins.title = {
            display: true,
            text: '暂无温度数据',
            font: { size: 14 }
        };
    } else {
        temperatureChart.options.plugins.title = { display: false };
    }

    if (humidityData.length === 0) {
        humidityChart.options.plugins.title = {
            display: true,
            text: '暂无湿度数据',
            font: { size: 14 }
        };
    } else {
        humidityChart.options.plugins.title = { display: false };
    }

    if (pressureData.length === 0) {
        pressureChart.options.plugins.title = {
            display: true,
            text: '暂无气压数据',
            font: { size: 14 }
        };
    } else {
        pressureChart.options.plugins.title = { display: false };
    }

    if (vocData.length === 0) {
        vocChart.options.plugins.title = {
            display: true,
            text: '暂无VOC数据',
            font: { size: 14 }
        };
    } else {
        vocChart.options.plugins.title = { display: false };
    }

    if (mqSensorData.length === 0) {
        mqSensorChart.options.plugins.title = {
            display: true,
            text: '暂无MQ传感器数据',
            font: { size: 14 }
        };
    } else {
        mqSensorChart.options.plugins.title = { display: false };
    }

    temperatureChart.update('none'); // 不重新渲染动画，提高性能
    humidityChart.update('none');
    pressureChart.update('none');
    vocChart.update('none');
    mqSensorChart.update('none');
}

// 更新统计信息
function updateStats(stats) {
    const container = document.getElementById('statsContainer');
    container.innerHTML = '';

    const sensors = [
        { key: 'temperature', name: '温度', unit: '°C', color: '#ff6b6b' },
        { key: 'humidity', name: '湿度', unit: '%', color: '#4ecdc4' },
        { key: 'pressure', name: '气压', unit: 'hPa', color: '#45b7d1' },
        { key: 'voc', name: 'VOC', unit: '', color: '#96ceb4' },
        { key: 'mq_sensor', name: 'MQ传感器', unit: 'ADC', color: '#ff7b7b' }
    ];

    sensors.forEach(sensor => {
        const stat = stats[sensor.key];
        const card = document.createElement('div');
        card.className = 'stat-card';
        card.style.background = `linear-gradient(135deg, ${sensor.color} 0%, ${sensor.color}88 100%)`;

        let value = 'N/A';
        if (stat && stat.avg !== null && stat.avg !== undefined) {
            value = stat.avg.toFixed(1);
        }

        card.innerHTML = `
            <h3>${sensor.name}</h3>
            <div class="value">${value}<span class="unit">${sensor.unit}</span></div>
            ${stat && stat.min !== null && stat.max !== null ?
                `<div style="font-size: 12px; margin-top: 5px; opacity: 0.8;">
                    ${stat.min.toFixed(1)} - ${stat.max.toFixed(1)}${sensor.unit}
                </div>` : ''}
        `;

        container.appendChild(card);
    });
}
