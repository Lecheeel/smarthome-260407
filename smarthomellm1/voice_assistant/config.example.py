"""配置模块 - 支持环境变量和配置文件"""
import os
import logging
from typing import Optional


class Config:
    """配置类 - 支持环境变量覆盖"""
    
    # API配置
    # API_KEY: str = 
    REGION: str = os.getenv('DASHSCOPE_REGION', 'beijing')
    
    # ASR配置
    ASR_MODEL: str = os.getenv('ASR_MODEL', 'qwen3-asr-flash-realtime')
    ASR_LANGUAGE: str = os.getenv('ASR_LANGUAGE', 'zh')
    ASR_SAMPLE_RATE: int = int(os.getenv('ASR_SAMPLE_RATE', '16000'))
    
    # LLM配置
    LLM_MODEL: str = os.getenv('LLM_MODEL', 'qwen-flash')
    LLM_USE_STREAM: bool = os.getenv('LLM_USE_STREAM', 'true').lower() == 'true'
    LLM_SYSTEM_PROMPT: str = os.getenv(
        'LLM_SYSTEM_PROMPT',
        '你是一个AI智能家居助手，你的自然语言模型是DeepSeek，你需要用**简洁自然**的语言回答问题，不要输出颜文字，表情符号emoji，要连贯回答，像说出一段话一样回答。'
    )
    
    # TTS配置
    TTS_MODEL: str = os.getenv('TTS_MODEL', 'qwen3-tts-flash-realtime-2025-11-27')
    TTS_VOICE: str = os.getenv('TTS_VOICE', 'Maia')
    TTS_SAMPLE_RATE: int = int(os.getenv('TTS_SAMPLE_RATE', '24000'))
    TTS_SPEED: float = float(os.getenv('TTS_SPEED', '2.0'))
    TTS_INITIAL_BUFFER_SIZE: int = int(os.getenv('TTS_INITIAL_BUFFER_SIZE', '7'))  # 初始缓冲字符数
    TTS_SEGMENT_PUNCTUATION: str = os.getenv('TTS_SEGMENT_PUNCTUATION', '。！？；：')  # 分段标点符号
    TTS_AUDIO_QUEUE_SIZE: int = int(os.getenv('TTS_AUDIO_QUEUE_SIZE', '20000'))  # TTS音频队列最大大小
    
    # 音频IO配置
    AUDIO_CHUNK_SIZE: int = int(os.getenv('AUDIO_CHUNK_SIZE', '3200'))
    AUDIO_CHANNELS: int = int(os.getenv('AUDIO_CHANNELS', '1'))
    AUDIO_OUTPUT_QUEUE_SIZE: int = int(os.getenv('AUDIO_OUTPUT_QUEUE_SIZE', '20000'))  # 音频输出队列最大大小
    
    # 和风天气API配置
    # QWEATHER_API_HOST: str = 
    # QWEATHER_PROJECT_ID: str = 
    # QWEATHER_KEY_ID: str = 
    # QWEATHER_PRIVATE_KEY_PATH: Optional[str] = os.getenv('QWEATHER_PRIVATE_KEY_PATH', None)
    # QWEATHER_PRIVATE_KEY: str = 

    # 智能家居传感器API配置
    SMARTHOME_API_BASE_URL: str = 

    # 环境监控配置
    ENV_MONITOR_ENABLED: bool = os.getenv('ENV_MONITOR_ENABLED', 'true').lower() == 'true'
    ENV_MONITOR_CHECK_INTERVAL: int = int(os.getenv('ENV_MONITOR_CHECK_INTERVAL', '3'))
    MQ_SENSOR_THRESHOLD: int = int(os.getenv('MQ_SENSOR_THRESHOLD', '600'))
    
    # 记忆文件路径
    MEMORY_FILE: str = os.getenv('MEMORY_FILE', 'user_memory.json')
    
    @staticmethod
    def get_ws_url(region: Optional[str] = None) -> str:
        """获取WebSocket URL"""
        region = region or Config.REGION
        if region == 'singapore':
            return 'wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime'
        return 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime'
    
    @staticmethod
    def validate() -> bool:
        """验证配置是否有效"""
        logger = logging.getLogger(__name__)
        
        if not Config.API_KEY:
            logger.error("API_KEY未配置，请设置DASHSCOPE_API_KEY环境变量")
            return False
        
        if Config.ASR_SAMPLE_RATE <= 0:
            logger.error(f"无效的ASR_SAMPLE_RATE: {Config.ASR_SAMPLE_RATE}")
            return False
        
        if Config.TTS_SAMPLE_RATE <= 0:
            logger.error(f"无效的TTS_SAMPLE_RATE: {Config.TTS_SAMPLE_RATE}")
            return False
        
        if Config.AUDIO_CHUNK_SIZE <= 0:
            logger.error(f"无效的AUDIO_CHUNK_SIZE: {Config.AUDIO_CHUNK_SIZE}")
            return False
        
        return True