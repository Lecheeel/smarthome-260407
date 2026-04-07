"""环境监控模块"""
import logging
import threading
import time
import requests
from typing import Optional, Callable
from .config import Config


class EnvironmentMonitor:
    """环境监控类 - 监控传感器数据并发出警告"""

    def __init__(self, alert_callback: Optional[Callable[[str], None]] = None):
        """
        初始化环境监控器

        Args:
            alert_callback: 警告回调函数，参数为警告消息
        """
        self.logger = logging.getLogger(__name__)
        self.alert_callback = alert_callback
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_alert_time = 0
        self.alert_cooldown = 10  # 警告冷却时间（秒），避免频繁报警

    def start(self):
        """启动环境监控"""
        if not Config.ENV_MONITOR_ENABLED:
            self.logger.info("环境监控已禁用")
            return

        if self.is_running:
            self.logger.warning("环境监控已在运行中")
            return

        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self.monitor_thread.start()
        self.logger.info("环境监控已启动")

    def stop(self):
        """停止环境监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
        
        self.logger.info("环境监控已停止")

    def _monitor_worker(self):
        """监控工作线程"""
        while self.is_running:
            try:
                self._check_sensors()
                time.sleep(Config.ENV_MONITOR_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"环境监控错误: {e}", exc_info=True)
                time.sleep(5)  # 出错后等待5秒再试

    def _check_sensors(self):
        """检查传感器数据"""
        try:
            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/sensor-data/latest",
                timeout=10
            )
            response.raise_for_status()
            api_response = response.json()

            # 检查API响应是否成功
            if not api_response.get('success'):
                self.logger.warning("API响应表示失败")
                return

            # 从API响应中提取传感器数据
            sensors_data = api_response.get('data', {})

            # 检查MQ传感器
            mq_value = self._extract_mq_value(sensors_data)
            if mq_value is not None:
                self.logger.debug(f"MQ传感器值: {mq_value}")
                self._check_gas_leakage(mq_value)

        except requests.RequestException as e:
            self.logger.warning(f"获取传感器数据失败: {e}")
        except Exception as e:
            self.logger.error(f"解析传感器数据失败: {e}", exc_info=True)

    def _extract_mq_value(self, sensors_data: dict) -> Optional[int]:
        """
        从传感器数据中提取MQ传感器值
        
        Args:
            sensors_data: 传感器数据字典
            
        Returns:
            MQ传感器值或None
        """
        try:
            # 支持多种MQ传感器类型
            mq_sensor_keys = ['mq_sensor', 'mq135', 'mq2', 'mq5', 'mq9', 'mq']

            if isinstance(sensors_data, dict):
                # 遍历所有可能的MQ传感器键名
                for key in mq_sensor_keys:
                    if key in sensors_data and sensors_data[key] is not None:
                        return int(sensors_data[key])

                # 检查是否有以'mq'开头的传感器（兼容性）
                for key, value in sensors_data.items():
                    if key.lower().startswith('mq') and value is not None:
                        return int(value)

            return None
        except (ValueError, TypeError) as e:
            self.logger.debug(f"提取MQ传感器值失败: {e}")
            return None

    def _check_gas_leakage(self, mq_value: int):
        """
        检查气体泄漏
        
        Args:
            mq_value: MQ传感器值
        """
        if mq_value > Config.MQ_SENSOR_THRESHOLD:
            current_time = time.time()

            # 检查是否在冷却期内
            if current_time - self.last_alert_time > self.alert_cooldown:
                alert_message = (
                    f"检测到可燃气体泄漏！MQ传感器值：{mq_value}，"
                    f"超过阈值{Config.MQ_SENSOR_THRESHOLD}。"
                    f"请立即检查并采取安全措施！"
                )
                self.logger.warning(alert_message)

                if self.alert_callback:
                    self.alert_callback(alert_message)

                self.last_alert_time = current_time
            else:
                self.logger.debug(f"MQ传感器值过高但在冷却期内: {mq_value}")

    def set_alert_callback(self, callback: Callable[[str], None]):
        """
        设置警告回调函数
        
        Args:
            callback: 警告回调函数
        """
        self.alert_callback = callback

