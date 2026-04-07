"""ASR模块 - 实时语音识别"""
import base64
import logging
import queue
from typing import Optional, Callable
import dashscope
from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
from dashscope.audio.qwen_omni.omni_realtime import TranscriptionParams, MultiModality


class ASRCallback(OmniRealtimeCallback):
    """ASR回调处理器"""
    
    def __init__(self, text_queue: queue.Queue, final_text_callback: Optional[Callable] = None):
        """
        初始化ASR回调
        
        Args:
            text_queue: 文本队列
            final_text_callback: 最终文本回调函数
        """
        self.text_queue = text_queue
        self.final_text_callback = final_text_callback
        self.conversation = None
        self.logger = logging.getLogger(__name__)
        
    def on_open(self):
        """连接打开回调"""
        self.logger.info("ASR连接已打开")
        
    def on_close(self, code, msg):
        """连接关闭回调"""
        self.logger.info(f"ASR连接已关闭: code={code}, msg={msg}")
        
    def on_event(self, response):
        """事件处理回调"""
        try:
            event_type = response.get('type', '')
            if event_type == 'conversation.item.input_audio_transcription.completed':
                final_text = response.get('transcript', '')
                if final_text:
                    self.text_queue.put(('final', final_text))
                    if self.final_text_callback:
                        self.final_text_callback(final_text)
            elif event_type == 'conversation.item.input_audio_transcription.text':
                stash_text = response.get('stash', '')
                if stash_text:
                    self.text_queue.put(('stash', stash_text))
        except Exception as e:
            self.logger.error(f"ASR回调错误: {e}", exc_info=True)


class ASRModule:
    """ASR模块 - 实时语音识别"""
    
    def __init__(self, api_key: str, sample_rate: int, url: str, model: str):
        """
        初始化ASR模块
        
        Args:
            api_key: API密钥
            sample_rate: 采样率
            url: WebSocket URL
            model: 模型名称
        """
        dashscope.api_key = api_key
        self.sample_rate = sample_rate
        self.url = url
        self.model = model
        self.text_queue = queue.Queue()
        self.conversation: Optional[OmniRealtimeConversation] = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
    def initialize(self, final_text_callback: Optional[Callable] = None):
        """
        初始化ASR连接
        
        Args:
            final_text_callback: 最终文本回调函数
        """
        try:
            callback = ASRCallback(self.text_queue, final_text_callback)
            self.conversation = OmniRealtimeConversation(
                model=self.model,
                url=self.url,
                callback=callback
            )
            callback.conversation = self.conversation
            self.conversation.connect()
            
            params = TranscriptionParams(
                language='zh',
                sample_rate=self.sample_rate,
                input_audio_format='pcm'
            )
            self.conversation.update_session(
                output_modalities=[MultiModality.TEXT],
                enable_input_audio_transcription=True,
                transcription_params=params
            )
            self.is_running = True
            self.logger.info("ASR模块初始化成功")
        except Exception as e:
            self.logger.error(f"ASR模块初始化失败: {e}", exc_info=True)
            raise
    
    def send_audio_chunk(self, audio_data: bytes):
        """
        发送音频数据块
        
        Args:
            audio_data: 音频数据（PCM格式）
        """
        if not self.is_running or not self.conversation:
            return
        
        try:
            audio_b64 = base64.b64encode(audio_data).decode('ascii')
            self.conversation.append_audio(audio_b64)
        except Exception as e:
            self.logger.error(f"发送音频块失败: {e}", exc_info=True)
    
    def get_text(self, timeout: Optional[float] = None):
        """
        获取识别文本
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            识别结果元组 (type, text) 或 None
        """
        try:
            return self.text_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def close(self):
        """关闭ASR连接"""
        self.is_running = False
        if self.conversation:
            try:
                self.conversation.close()
                self.logger.info("ASR模块已关闭")
            except Exception as e:
                self.logger.error(f"关闭ASR模块失败: {e}", exc_info=True)
            finally:
                self.conversation = None

