"""工具模块 - 定义LLM可调用的工具"""
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from .weather_client import WeatherClient
from .config import Config
from .memory_module import MemoryModule


class ToolsModule:
    """工具模块 - 管理LLM可调用的工具"""
    
    def __init__(self, memory_file: Optional[str] = None):
        """
        初始化工具模块
        
        Args:
            memory_file: 记忆文件路径（可选）
        """
        self.logger = logging.getLogger(__name__)
        
        # 初始化记忆模块
        memory_path = memory_file or Config.MEMORY_FILE
        self.memory_module = MemoryModule(memory_file=memory_path)
        
        # LLM模块引用（用于刷新系统提示词）
        self.llm_module: Optional[Any] = None
        
        # 初始化天气客户端（如果配置存在）
        self.weather_client: Optional[WeatherClient] = None
        self._init_weather_client()
        
        # 定义工具列表
        self.tools = self._define_tools()
        
        # 工具函数映射
        self.tool_functions = {
            "get_current_time": self._get_current_time,
            "get_current_weather": self._get_current_weather,
            "get_weather_daily_forecast": self._get_weather_daily_forecast,
            "get_weather_hourly_forecast": self._get_weather_hourly_forecast,
            "save_memory": self._save_memory,
            "get_latest_sensor_data": self._get_latest_sensor_data,
            "get_sensor_data_summary": self._get_sensor_data_summary,
            "get_sensor_data_list": self._get_sensor_data_list,
            "get_sensor_data_range": self._get_sensor_data_range,
            "export_sensor_data": self._export_sensor_data
        }
    
    def _init_weather_client(self):
        """初始化天气客户端"""
        try:
            if (Config.QWEATHER_API_HOST and Config.QWEATHER_PROJECT_ID and 
                Config.QWEATHER_KEY_ID and 
                (Config.QWEATHER_PRIVATE_KEY_PATH or Config.QWEATHER_PRIVATE_KEY)):
                self.weather_client = WeatherClient(
                    api_host=Config.QWEATHER_API_HOST,
                    project_id=Config.QWEATHER_PROJECT_ID,
                    key_id=Config.QWEATHER_KEY_ID,
                    private_key_path=Config.QWEATHER_PRIVATE_KEY_PATH,
                    private_key=Config.QWEATHER_PRIVATE_KEY
                )
                self.logger.info("天气API客户端初始化成功")
            else:
                self.logger.warning("和风天气API配置不完整，天气功能将使用模拟数据")
        except Exception as e:
            self.logger.error(f"初始化天气客户端失败: {e}，将使用模拟数据", exc_info=True)
    
    def _define_tools(self) -> List[Dict[str, Any]]:
        """定义工具列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "当你想知道现在的时间时非常有用。",
                    "parameters": {}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "当你想查询指定城市的实时天气时非常有用。返回当前温度、体感温度、天气状况、风力风向、湿度等信息。如果用户没有指定城市，可以使用记忆中保存的用户位置。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "城市或县区名称，比如北京市、杭州市、余杭区等。如果不提供，将使用记忆中保存的用户位置。"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather_daily_forecast",
                    "description": "当你想查询指定城市的每日天气预报时非常有用。可以获取未来3-30天的天气预报，包括最高最低温度、天气状况、风力风向、降水量等信息。如果用户没有指定城市，可以使用记忆中保存的用户位置。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "城市或县区名称，比如北京市、杭州市、余杭区等。如果不提供，将使用记忆中保存的用户位置。"
                            },
                            "days": {
                                "type": "string",
                                "description": "预报天数，可选值：3d（3天）、7d（7天）、10d（10天）、15d（15天）、30d（30天），默认为3d。",
                                "enum": ["3d", "7d", "10d", "15d", "30d"]
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather_hourly_forecast",
                    "description": "当你想查询指定城市的逐小时天气预报时非常有用。可以获取未来24-168小时的逐小时天气预报，包括每小时温度、天气状况、风力风向、降水概率等信息。如果用户没有指定城市，可以使用记忆中保存的用户位置。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "城市或县区名称，比如北京市、杭州市、余杭区等。如果不提供，将使用记忆中保存的用户位置。"
                            },
                            "hours": {
                                "type": "string",
                                "description": "预报小时数，可选值：24h（24小时）、72h（72小时）、168h（168小时），默认为24h。",
                                "enum": ["24h", "72h", "168h"]
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": "当用户告诉你重要信息时，使用此工具保存到记忆中。例如：用户的位置、姓名、偏好设置、重要事件等。这些信息会在以后的对话中自动使用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "记忆的键名，例如：'location'（位置）、'name'（姓名）、'preference'（偏好）等。使用有意义的英文键名。"
                            },
                            "value": {
                                "type": "string",
                                "description": "要保存的值，例如：'北京市'、'张三'等。"
                            },
                            "description": {
                                "type": "string",
                                "description": "可选的描述信息，说明这条记忆的用途或上下文。"
                            }
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_latest_sensor_data",
                    "description": "当用户想要了解智能家居中最新传感器数据时非常有用。返回当前的温度、湿度、气压和VOC等环境数据。",
                    "parameters": {}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sensor_data_summary",
                    "description": "当用户想要了解智能家居传感器数据统计摘要时非常有用。可以查看指定时间范围内的温度、湿度等数据的最大值、最小值和平均值。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hours": {
                                "type": "integer",
                                "description": "要统计的小时数，默认为1小时。可选值：1、2、3、6、12、24等。",
                                "default": 1
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sensor_data_list",
                    "description": "当用户想要查看智能家居传感器数据列表时非常有用。可以分页查看历史传感器数据。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "返回的记录数量，默认为5条。最大值50。",
                                "default": 5,
                                "maximum": 50
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sensor_data_range",
                    "description": "当用户想要查看指定时间范围内的智能家居传感器数据时非常有用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {
                                "type": "string",
                                "description": "开始时间，格式为ISO 8601字符串，如'2024-01-01T00:00:00'。"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "结束时间，格式为ISO 8601字符串，如'2024-01-01T23:59:59'。"
                            },
                            "sensor": {
                                "type": "string",
                                "description": "传感器类型，可选值：'temperature'（温度）、'humidity'（湿度）、'pressure'（气压）、'voc'（VOC）。如果不指定则返回所有传感器数据。",
                                "enum": ["temperature", "humidity", "pressure", "voc"]
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "export_sensor_data",
                    "description": "当用户想要导出智能家居传感器数据时非常有用。可以导出指定时间范围和传感器类型的数据。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hours": {
                                "type": "integer",
                                "description": "要导出的小时数，默认为1小时。",
                                "default": 1
                            },
                            "sensor": {
                                "type": "string",
                                "description": "要导出的传感器类型，可选值：'temperature'（温度）、'humidity'（湿度）、'pressure'（气压）、'voc'（VOC）。如果不指定则导出所有传感器数据。",
                                "enum": ["temperature", "humidity", "pressure", "voc"]
                            }
                        },
                        "required": []
                    }
                }
            }
        ]
    
    def _get_current_time(self, **kwargs) -> str:
        """获取当前时间"""
        time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        return f"当前时间是：{time_str}"
    
    def _get_location_id(self, location: str) -> Optional[str]:
        """
        通过城市名称获取LocationID
        
        Args:
            location: 城市名称
            
        Returns:
            LocationID或None
        """
        if not self.weather_client:
            return None
        
        try:
            cities = self.weather_client.city_lookup(location, number=1)
            if cities:
                return cities[0].get('id')
        except Exception as e:
            self.logger.error(f"城市搜索失败: {e}", exc_info=True)
        return None
    
    def _get_current_weather(self, location: Optional[str] = None, **kwargs) -> str:
        """
        获取指定城市的实时天气
        
        Args:
            location: 城市名称（可选）
            
        Returns:
            天气信息字符串
        """
        # 如果未提供位置，尝试从记忆中获取
        if not location:
            location = self.memory_module.get_memory('location')
            if location:
                self.logger.info(f"从记忆中获取用户位置: {location}")
            else:
                return "抱歉，请提供城市名称，或者告诉我您所在的位置，我会记住它。"
        
        if self.weather_client:
            try:
                location_id = self._get_location_id(location)
                if not location_id:
                    return f"抱歉，找不到城市：{location}"
                
                result = self.weather_client.get_weather_now(location_id)
                now = result.get('now', {})
                
                temp = now.get('temp', 'N/A')
                feels_like = now.get('feelsLike', 'N/A')
                text = now.get('text', 'N/A')
                wind_dir = now.get('windDir', 'N/A')
                wind_scale = now.get('windScale', 'N/A')
                humidity = now.get('humidity', 'N/A')
                pressure = now.get('pressure', 'N/A')
                vis = now.get('vis', 'N/A')
                obs_time = now.get('obsTime', '')
                
                response = f"{location}的实时天气：{text}，温度{temp}°C，体感温度{feels_like}°C。"
                response += f"风向{wind_dir}，风力{wind_scale}级。"
                response += f"相对湿度{humidity}%，大气压强{pressure}百帕，能见度{vis}公里。"
                
                if obs_time:
                    response += f"观测时间：{obs_time}。"
                
                return response
            except Exception as e:
                self.logger.error(f"获取实时天气失败: {e}", exc_info=True)
                return f"抱歉，获取{location}的天气信息时出错：{str(e)}"
        else:
            # 模拟数据
            return self._get_mock_weather(location)
    
    def _get_mock_weather(self, location: str) -> str:
        """获取模拟天气数据"""
        weather_data = {
            "北京": "晴天，温度15-25°C",
            "上海": "多云，温度18-26°C",
            "杭州": "小雨，温度12-20°C",
            "深圳": "晴天，温度22-30°C",
            "广州": "多云，温度20-28°C"
        }
        for city, weather in weather_data.items():
            if city in location or location in city:
                return f"{location}的天气是：{weather}"
        return f"{location}的天气：晴天，温度20-28°C（模拟数据）"
    
    def _get_weather_daily_forecast(
        self,
        location: Optional[str] = None,
        days: str = "3d",
        **kwargs
    ) -> str:
        """
        获取指定城市的每日天气预报
        
        Args:
            location: 城市名称（可选）
            days: 预报天数
            
        Returns:
            天气预报字符串
        """
        if not location:
            location = self.memory_module.get_memory('location')
            if location:
                self.logger.info(f"从记忆中获取用户位置: {location}")
            else:
                return "抱歉，请提供城市名称，或者告诉我您所在的位置，我会记住它。"
        
        if self.weather_client:
            try:
                location_id = self._get_location_id(location)
                if not location_id:
                    return f"抱歉，找不到城市：{location}"
                
                result = self.weather_client.get_weather_daily(location_id, days)
                daily_list = result.get('daily', [])
                
                if not daily_list:
                    return f"抱歉，无法获取{location}的天气预报"
                
                response = f"{location}未来{len(daily_list)}天的天气预报：\n"
                
                for day in daily_list:
                    fx_date = day.get('fxDate', '')
                    temp_max = day.get('tempMax', 'N/A')
                    temp_min = day.get('tempMin', 'N/A')
                    text_day = day.get('textDay', 'N/A')
                    text_night = day.get('textNight', 'N/A')
                    wind_dir_day = day.get('windDirDay', 'N/A')
                    wind_scale_day = day.get('windScaleDay', 'N/A')
                    precip = day.get('precip', '0.0')
                    
                    date_str = fx_date if fx_date else "某天"
                    response += f"{date_str}：白天{text_day}，夜间{text_night}，"
                    response += f"最高温度{temp_max}°C，最低温度{temp_min}°C，"
                    response += f"白天{wind_dir_day}{wind_scale_day}级，"
                    
                    if float(precip) > 0:
                        response += f"降水量{precip}毫米。"
                    else:
                        response += "无降水。"
                    response += "\n"
                
                return response.strip()
            except Exception as e:
                self.logger.error(f"获取每日天气预报失败: {e}", exc_info=True)
                return f"抱歉，获取{location}的天气预报时出错：{str(e)}"
        else:
            return f"抱歉，天气API未配置，无法获取{location}的天气预报"
    
    def _get_weather_hourly_forecast(
        self,
        location: Optional[str] = None,
        hours: str = "24h",
        **kwargs
    ) -> str:
        """
        获取指定城市的逐小时天气预报
        
        Args:
            location: 城市名称（可选）
            hours: 预报小时数
            
        Returns:
            逐小时天气预报字符串
        """
        if not location:
            location = self.memory_module.get_memory('location')
            if location:
                self.logger.info(f"从记忆中获取用户位置: {location}")
            else:
                return "抱歉，请提供城市名称，或者告诉我您所在的位置，我会记住它。"
        
        if self.weather_client:
            try:
                location_id = self._get_location_id(location)
                if not location_id:
                    return f"抱歉，找不到城市：{location}"
                
                result = self.weather_client.get_weather_hourly(location_id, hours)
                hourly_list = result.get('hourly', [])
                
                if not hourly_list:
                    return f"抱歉，无法获取{location}的逐小时天气预报"
                
                # 只返回前12小时的数据，避免信息过多
                display_hours = min(12, len(hourly_list))
                hourly_list = hourly_list[:display_hours]
                
                response = f"{location}未来{display_hours}小时的天气预报：\n"
                
                for hour in hourly_list:
                    fx_time = hour.get('fxTime', '')
                    temp = hour.get('temp', 'N/A')
                    text = hour.get('text', 'N/A')
                    wind_dir = hour.get('windDir', 'N/A')
                    wind_scale = hour.get('windScale', 'N/A')
                    pop = hour.get('pop', '0')
                    precip = hour.get('precip', '0.0')
                    
                    # 提取时间部分
                    time_str = fx_time.split('T')[1][:5] if 'T' in fx_time else fx_time
                    response += f"{time_str}：{text}，温度{temp}°C，"
                    response += f"{wind_dir}{wind_scale}级，"
                    
                    if float(pop) > 0:
                        response += f"降水概率{pop}%，"
                    if float(precip) > 0:
                        response += f"降水量{precip}毫米。"
                    else:
                        response += "无降水。"
                    response += "\n"
                
                return response.strip()
            except Exception as e:
                self.logger.error(f"获取逐小时天气预报失败: {e}", exc_info=True)
                return f"抱歉，获取{location}的逐小时天气预报时出错：{str(e)}"
        else:
            return f"抱歉，天气API未配置，无法获取{location}的逐小时天气预报"
    
    def _save_memory(
        self,
        key: str,
        value: str,
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        保存记忆
        
        Args:
            key: 记忆键
            value: 记忆值
            description: 描述（可选）
            
        Returns:
            保存结果字符串
        """
        try:
            success = self.memory_module.save_memory(key, value, description)
            if success:
                # 保存成功后，刷新LLM模块的系统提示词
                if self.llm_module and hasattr(self.llm_module, 'refresh_memory_in_prompt'):
                    self.llm_module.refresh_memory_in_prompt()
                return f"已成功保存记忆：{key} = {value}"
            else:
                return f"保存记忆失败：{key} = {value}"
        except Exception as e:
            self.logger.error(f"保存记忆失败: {e}", exc_info=True)
            return f"保存记忆时出错: {str(e)}"
    
    def _get_latest_sensor_data(self, **kwargs) -> str:
        """获取最新的传感器数据"""
        try:
            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/sensor-data/latest",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('data'):
                latest = data['data']
                return self._format_sensor_data(latest, "智能家居最新环境数据：")
            else:
                return "抱歉，无法获取最新的传感器数据"
        except requests.RequestException as e:
            self.logger.error(f"获取最新传感器数据失败: {e}", exc_info=True)
            return f"获取传感器数据时出错: {str(e)}"
        except Exception as e:
            self.logger.error(f"处理传感器数据失败: {e}", exc_info=True)
            return f"处理传感器数据时出错: {str(e)}"
    
    def _format_sensor_data(self, sensor_data: Dict[str, Any], prefix: str = "") -> str:
        """
        格式化传感器数据
        
        Args:
            sensor_data: 传感器数据字典
            prefix: 前缀字符串
            
        Returns:
            格式化后的字符串
        """
        # 定义传感器单位映射
        sensor_units = {
            'temperature': '°C',
            'humidity': '%',
            'pressure': 'hPa',
            'voc': 'ppm',
            'mq_sensor': 'ppm',
            'mq135': 'ppm',
            'mq2': 'ppm',
            'mq5': 'ppm',
            'mq9': 'ppm',
        }
        
        # 定义传感器显示名称映射
        sensor_names = {
            'temperature': '温度',
            'humidity': '湿度',
            'pressure': '气压',
            'voc': 'VOC浓度'
        }
        
        result = prefix if prefix else ""
        sensor_parts = []
        
        for sensor_name, value in sensor_data.items():
            if value is not None and sensor_name != 'timestamp':
                unit = sensor_units.get(sensor_name.lower(), '')
                
                if sensor_name.lower().startswith('mq'):
                    sensor_parts.append(f"气体浓度{value}{unit}")
                else:
                    display_name = sensor_names.get(sensor_name.lower(), sensor_name)
                    sensor_parts.append(f"{display_name}{value}{unit}")
        
        if sensor_parts:
            result += "，".join(sensor_parts)
        else:
            result += "暂无数据"
        
        return result
    
    def _get_sensor_data_summary(self, hours: int = 1, **kwargs) -> str:
        """获取传感器数据摘要"""
        try:
            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/sensor-data/summary?hours={hours}",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('summary'):
                summary = data.get('summary', {})
                total_records = summary.get('total_records', 0)
                sensors = summary.get('sensors', {})

                result = f"智能家居传感器数据摘要（最近{hours}小时）：\n"
                result += f"总记录数：{total_records}\n"

                if 'temperature' in sensors:
                    temp = sensors['temperature']
                    result += f"温度：最小{temp['min']:.1f}°C，最大{temp['max']:.1f}°C，平均{temp['avg']:.1f}°C\n"

                if 'humidity' in sensors:
                    hum = sensors['humidity']
                    result += f"湿度：最小{hum['min']:.1f}%，最大{hum['max']:.1f}%，平均{hum['avg']:.1f}%"

                return result.strip()
            else:
                return "抱歉，无法获取传感器数据摘要"
        except requests.RequestException as e:
            self.logger.error(f"获取传感器数据摘要失败: {e}", exc_info=True)
            return f"获取传感器数据摘要时出错: {str(e)}"
        except Exception as e:
            self.logger.error(f"处理传感器数据摘要失败: {e}", exc_info=True)
            return f"处理传感器数据摘要时出错: {str(e)}"
    
    def _get_sensor_data_list(self, limit: int = 5, **kwargs) -> str:
        """获取传感器数据列表"""
        try:
            limit = min(max(limit, 1), 50)  # 限制在1-50之间

            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/sensor-data?limit={limit}",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('data'):
                records = data.get('data', [])
                total_count = data.get('total_count', 0)

                result = f"智能家居传感器数据列表（显示最新{len(records)}条，共{total_count}条）：\n"

                for i, record in enumerate(records, 1):
                    timestamp = record.get('timestamp', 'N/A')
                    sensor_str = self._format_sensor_data(record, "")
                    result += f"{i}. {timestamp} - {sensor_str}\n"

                return result.strip()
            else:
                return "抱歉，无法获取传感器数据列表"
        except requests.RequestException as e:
            self.logger.error(f"获取传感器数据列表失败: {e}", exc_info=True)
            return f"获取传感器数据列表时出错: {str(e)}"
        except Exception as e:
            self.logger.error(f"处理传感器数据列表失败: {e}", exc_info=True)
            return f"处理传感器数据列表时出错: {str(e)}"
    
    def _get_sensor_data_range(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sensor: Optional[str] = None,
        **kwargs
    ) -> str:
        """获取时间范围内的传感器数据"""
        try:
            params = {}
            if start_time:
                params['start_time'] = start_time
            if end_time:
                params['end_time'] = end_time
            if sensor:
                params['sensor'] = sensor

            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/sensor-data/range",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('data'):
                records = data.get('data', [])
                count = len(records)

                result = f"智能家居传感器数据（时间范围查询，返回{count}条记录）：\n"

                for i, record in enumerate(records[:10], 1):  # 最多显示10条
                    timestamp = record.get('timestamp', 'N/A')
                    sensor_str = self._format_sensor_data(record, "")
                    result += f"{i}. {timestamp} - {sensor_str}\n"

                if count > 10:
                    result += f"\n...还有{count-10}条记录未显示"

                return result.strip()
            else:
                return "抱歉，在指定时间范围内没有找到传感器数据"
        except requests.RequestException as e:
            self.logger.error(f"获取时间范围传感器数据失败: {e}", exc_info=True)
            return f"获取时间范围传感器数据时出错: {str(e)}"
        except Exception as e:
            self.logger.error(f"处理时间范围传感器数据失败: {e}", exc_info=True)
            return f"处理时间范围传感器数据时出错: {str(e)}"
    
    def _export_sensor_data(
        self,
        hours: int = 1,
        sensor: Optional[str] = None,
        **kwargs
    ) -> str:
        """导出传感器数据"""
        try:
            params = {'hours': hours}
            if sensor:
                params['sensor'] = sensor

            response = requests.get(
                f"{Config.SMARTHOME_API_BASE_URL}/api/v1/export",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('export_info'):
                export_info = data.get('export_info', {})
                total_records = export_info.get('total_records', 0)
                sensor_type = export_info.get('sensor', '所有传感器')

                result = f"智能家居传感器数据导出成功：\n"
                result += f"导出的传感器类型：{sensor_type}\n"
                result += f"时间范围：最近{hours}小时\n"
                result += f"总记录数：{total_records}"

                return result
            else:
                return "抱歉，导出传感器数据失败"
        except requests.RequestException as e:
            self.logger.error(f"导出传感器数据失败: {e}", exc_info=True)
            return f"导出传感器数据时出错: {str(e)}"
        except Exception as e:
            self.logger.error(f"处理导出传感器数据失败: {e}", exc_info=True)
            return f"处理导出传感器数据时出错: {str(e)}"
    
    def set_llm_module(self, llm_module: Any):
        """
        设置LLM模块引用，用于刷新系统提示词
        
        Args:
            llm_module: LLM模块实例
        """
        self.llm_module = llm_module
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        执行指定的工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tool_functions:
            self.logger.warning(f"[工具执行] 未知工具: {tool_name}")
            return f"未知工具: {tool_name}"
        
        try:
            self.logger.info(f"[工具执行] 开始执行工具: {tool_name}")
            result = self.tool_functions[tool_name](**arguments)
            self.logger.info(f"[工具执行] 工具 {tool_name} 执行完成")
            return result
        except Exception as e:
            self.logger.error(
                f"[工具执行] 执行工具 {tool_name} 失败: {e}",
                exc_info=True
            )
            return f"执行工具时出错: {str(e)}"
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表
        
        Returns:
            工具定义列表
        """
        return self.tools

