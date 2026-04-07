"""和风天气API客户端"""
import os
import time
import jwt
import requests
import logging
from typing import Optional, Dict, Any, List
from cryptography.hazmat.primitives import serialization


class WeatherClient:
    """和风天气API客户端"""
    
    def __init__(
        self,
        api_host: str,
        project_id: str,
        key_id: str,
        private_key_path: Optional[str] = None,
        private_key: Optional[str] = None
    ):
        """
        初始化天气客户端
        
        Args:
            api_host: API主机地址
            project_id: 项目ID
            key_id: 凭据ID (kid)
            private_key_path: 私钥文件路径
            private_key: 私钥内容（PEM格式字符串）
        """
        self.api_host = api_host.rstrip('/')
        self.project_id = project_id
        self.key_id = key_id
        self.logger = logging.getLogger(__name__)
        
        # 加载私钥
        if private_key_path:
            try:
                with open(private_key_path, 'r', encoding='utf-8') as f:
                    self.private_key_pem = f.read()
            except Exception as e:
                self.logger.error(f"读取私钥文件失败: {e}")
                raise
        elif private_key:
            self.private_key_pem = private_key
        else:
            raise ValueError("必须提供 private_key_path 或 private_key")
        
        # 解析私钥对象
        try:
            self.private_key = serialization.load_pem_private_key(
                self.private_key_pem.encode('utf-8'),
                password=None
            )
        except Exception as e:
            self.logger.error(f"加载私钥失败: {e}", exc_info=True)
            raise
    
    def _generate_jwt(self) -> str:
        """
        生成JWT token
        
        Returns:
            JWT token字符串
        """
        # Header
        header = {
            "alg": "EdDSA",
            "kid": self.key_id
        }
        
        # Payload
        iat = int(time.time()) - 30  # 当前时间前30秒
        exp = iat + 900  # 15分钟有效期
        payload = {
            "sub": self.project_id,
            "iat": iat,
            "exp": exp
        }
        
        # 生成JWT
        try:
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm='EdDSA',
                headers=header
            )
            return token
        except Exception as e:
            self.logger.error(f"生成JWT失败: {e}", exc_info=True)
            raise
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            
        Returns:
            API响应数据
        """
        url = f"{self.api_host}{endpoint}"
        token = self._generate_jwt()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept-Encoding': 'gzip'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API请求失败: {e}", exc_info=True)
            raise
    
    def city_lookup(
        self,
        location: str,
        adm: Optional[str] = None,
        range: Optional[str] = None,
        number: int = 10
    ) -> List[Dict[str, Any]]:
        """
        城市搜索
        
        Args:
            location: 城市名称、经纬度或LocationID
            adm: 上级行政区划（可选）
            range: 搜索范围，ISO 3166国家代码（可选）
            number: 返回结果数量，1-20，默认10
        
        Returns:
            城市列表
        """
        params = {
            'location': location,
            'number': min(max(number, 1), 20)
        }
        if adm:
            params['adm'] = adm
        if range:
            params['range'] = range
        
        try:
            result = self._make_request('/geo/v2/city/lookup', params)
            
            if result.get('code') == '200':
                return result.get('location', [])
            else:
                self.logger.error(f"城市搜索失败: {result.get('code')}")
                return []
        except Exception as e:
            self.logger.error(f"城市搜索异常: {e}", exc_info=True)
            return []
    
    def get_weather_now(self, location: str) -> Dict[str, Any]:
        """
        获取实时天气
        
        Args:
            location: LocationID或经纬度坐标
        
        Returns:
            实时天气数据
        """
        params = {'location': location}
        result = self._make_request('/v7/weather/now', params)
        
        if result.get('code') == '200':
            return result
        else:
            error_code = result.get('code', 'unknown')
            self.logger.error(f"获取实时天气失败: {error_code}")
            raise Exception(f"获取天气失败: {error_code}")
    
    def get_weather_daily(self, location: str, days: str = '3d') -> Dict[str, Any]:
        """
        获取每日天气预报
        
        Args:
            location: LocationID或经纬度坐标
            days: 预报天数，可选值: 3d, 7d, 10d, 15d, 30d
        
        Returns:
            每日天气预报数据
        """
        if days not in ['3d', '7d', '10d', '15d', '30d']:
            days = '3d'
        
        params = {'location': location}
        result = self._make_request(f'/v7/weather/{days}', params)
        
        if result.get('code') == '200':
            return result
        else:
            error_code = result.get('code', 'unknown')
            self.logger.error(f"获取每日天气预报失败: {error_code}")
            raise Exception(f"获取天气预报失败: {error_code}")
    
    def get_weather_hourly(self, location: str, hours: str = '24h') -> Dict[str, Any]:
        """
        获取逐小时天气预报
        
        Args:
            location: LocationID或经纬度坐标
            hours: 预报小时数，可选值: 24h, 72h, 168h
        
        Returns:
            逐小时天气预报数据
        """
        if hours not in ['24h', '72h', '168h']:
            hours = '24h'
        
        params = {'location': location}
        result = self._make_request(f'/v7/weather/{hours}', params)
        
        if result.get('code') == '200':
            return result
        else:
            error_code = result.get('code', 'unknown')
            self.logger.error(f"获取逐小时天气预报失败: {error_code}")
            raise Exception(f"获取天气预报失败: {error_code}")

