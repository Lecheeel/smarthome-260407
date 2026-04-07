"""TTS模块 - 实时语音合成"""
import base64
import logging
import queue
import threading
import time
from typing import Optional
import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat
from .config import Config


class TTSCallback(QwenTtsRealtimeCallback):
    """TTS回调处理器"""
    
    def __init__(self, audio_queue: queue.Queue):
        """
        初始化TTS回调
        
        Args:
            audio_queue: 音频数据队列
        """
        self.audio_queue = audio_queue
        self.complete_event = threading.Event()
        self.event_lock = threading.Lock()
        self.is_session_active = False
        self.dropped_chunks = 0  # 统计丢弃的音频块数量
        self.total_chunks = 0  # 统计总音频块数量
        self.logger = logging.getLogger(__name__)
        
    def on_open(self):
        """连接打开回调"""
        self.logger.info("TTS连接已打开")
        with self.event_lock:
            self.is_session_active = False
            # 确保事件处于正确状态
            if self.complete_event.is_set():
                self.complete_event.clear()
        
    def on_close(self, code, msg):
        """连接关闭回调"""
        self.logger.info(f"TTS连接已关闭: code={code}, msg={msg}")
        with self.event_lock:
            self.is_session_active = False
            self.complete_event.set()
        
    def on_event(self, response: dict):
        """事件处理回调"""
        try:
            event_type = response.get('type', '')
            if event_type == 'response.audio.delta':
                audio_b64 = response.get('delta', '')
                if audio_b64:
                    try:
                        audio_data = base64.b64decode(audio_b64)
                        self.total_chunks += 1
                        # 尝试添加音频数据到队列，如果队列满则丢弃最旧的数据
                        try:
                            self.audio_queue.put_nowait(audio_data)
                        except queue.Full:
                            # 队列满时，尝试丢弃最旧的数据并添加新数据
                            try:
                                self.audio_queue.get_nowait()  # 丢弃最旧的数据
                                self.audio_queue.put_nowait(audio_data)
                                self.dropped_chunks += 1
                                if self.dropped_chunks % 10 == 0:  # 每10个丢弃块记录一次警告
                                    self.logger.warning(
                                        f"TTS音频队列溢出，已丢弃 {self.dropped_chunks} 个音频块 "
                                        f"(队列大小: {self.audio_queue.qsize()})"
                                    )
                            except queue.Empty:
                                # 队列已空，直接添加
                                try:
                                    self.audio_queue.put_nowait(audio_data)
                                except queue.Full:
                                    # 仍然满，丢弃当前数据
                                    self.dropped_chunks += 1
                                    self.logger.warning("TTS音频队列持续溢出，丢弃音频数据")
                    except Exception as e:
                        self.logger.error(f"解码音频数据失败: {e}", exc_info=True)
            elif event_type == 'session.finished':
                with self.event_lock:
                    self.is_session_active = False
                    self.complete_event.set()
            elif event_type == 'session.started':
                with self.event_lock:
                    self.is_session_active = True
                    # 新会话开始时清除完成事件
                    if self.complete_event.is_set():
                        self.complete_event.clear()
        except Exception as e:
            self.logger.error(f"TTS回调错误: {e}", exc_info=True)
    
    def wait_for_finished(self, timeout: Optional[float] = None) -> bool:
        """
        等待会话完成
        
        Args:
            timeout: 超时时间（秒），None表示无限等待
            
        Returns:
            是否在超时前完成
        """
        # 先检查状态，避免不必要的等待
        with self.event_lock:
            if self.complete_event.is_set():
                return True
            if not self.is_session_active:
                return True
        
        # 等待事件（timeout=None表示无限等待）
        result = self.complete_event.wait(timeout=timeout)
        
        # 如果超时，强制设置事件避免阻塞
        if not result and timeout is not None:
            self.logger.warning(f"等待TTS完成超时（{timeout}秒）")
            with self.event_lock:
                if not self.complete_event.is_set():
                    self.complete_event.set()
                    self.is_session_active = False
        
        return result
    
    def get_stats(self) -> dict:
        """
        获取队列统计信息
        
        Returns:
            包含统计信息的字典
        """
        return {
            'queue_size': self.audio_queue.qsize(),
            'queue_maxsize': getattr(self.audio_queue, 'maxsize', 'unlimited'),
            'total_chunks': self.total_chunks,
            'dropped_chunks': self.dropped_chunks,
            'is_session_active': self.is_session_active
        }


class TTSModule:
    """TTS模块 - 实时语音合成"""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        voice: str,
        url: str,
        speed: Optional[float] = None,
        queue_size: Optional[int] = None
    ):
        """
        初始化TTS模块
        
        Args:
            api_key: API密钥
            model: 模型名称
            voice: 语音名称
            url: WebSocket URL
            speed: 语速（可选）
            queue_size: 音频队列最大大小（可选，默认从Config读取）
        """
        dashscope.api_key = api_key
        self.model = model
        self.voice = voice
        self.url = url
        self.speed = speed
        # 使用有界队列，防止内存溢出
        queue_maxsize = queue_size or Config.TTS_AUDIO_QUEUE_SIZE
        self.audio_queue = queue.Queue(maxsize=queue_maxsize)
        self.tts_realtime: Optional[QwenTtsRealtime] = None
        self.callback: Optional[TTSCallback] = None
        self.is_running = False
        self.synthesis_lock = threading.Lock()
        self.connection_retry_count = 0
        self.max_retry_count = 3
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """初始化TTS连接，支持重试机制"""
        last_error = None
        for attempt in range(self.max_retry_count):
            try:
                self.callback = TTSCallback(self.audio_queue)
                self.tts_realtime = QwenTtsRealtime(
                    model=self.model,
                    callback=self.callback,
                    url=self.url
                )
                self.tts_realtime.connect()
                
                session_params = {
                    'voice': self.voice,
                    'response_format': AudioFormat.PCM_24000HZ_MONO_16BIT,
                    'mode': 'server_commit'
                }
                
                if self.speed is not None:
                    session_params['speed'] = self.speed
                
                self.tts_realtime.update_session(**session_params)
                self.is_running = True
                self.connection_retry_count = 0
                self.logger.info(f"TTS模块初始化成功 (队列大小: {self.audio_queue.maxsize})")
                return
            except Exception as e:
                last_error = e
                self.connection_retry_count = attempt + 1
                if attempt < self.max_retry_count - 1:
                    wait_time = min(2 ** attempt, 5)  # 指数退避，最多5秒
                    self.logger.warning(
                        f"TTS模块初始化失败 (尝试 {attempt + 1}/{self.max_retry_count}): {e}，"
                        f"{wait_time}秒后重试..."
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"TTS模块初始化失败，已重试 {self.max_retry_count} 次: {e}", exc_info=True)
        
        # 所有重试都失败
        raise RuntimeError(f"TTS模块初始化失败: {last_error}") from last_error
    
    def synthesize_text_stream(self, text_chunk: str):
        """
        流式合成文本块
        
        Args:
            text_chunk: 文本块
        """
        if not self.is_running or not self.tts_realtime:
            self.logger.warning("TTS未运行或未初始化，无法合成文本")
            return
        
        text = text_chunk.strip()
        if not text:
            return
        
        with self.synthesis_lock:
            # 确保回调存在
            if not self.callback:
                self.logger.error("TTS回调未初始化")
                return
            
            # 检查队列状态，如果队列接近满，记录警告
            queue_size = self.audio_queue.qsize()
            queue_maxsize = self.audio_queue.maxsize
            if queue_maxsize > 0 and queue_size > queue_maxsize * 0.8:
                self.logger.warning(
                    f"TTS音频队列使用率较高: {queue_size}/{queue_maxsize} "
                    f"({queue_size / queue_maxsize * 100:.1f}%)"
                )
            
            # 如果是第一次文本块或上次会话已完成，重置完成事件（开始新的合成会话）
            with self.callback.event_lock:
                if self.callback.complete_event.is_set() or not self.callback.is_session_active:
                    self.callback.complete_event.clear()
                    self.callback.is_session_active = True
            
            try:
                self.tts_realtime.append_text(text)
            except Exception as e:
                self.logger.error(f"合成文本块失败: {e}", exc_info=True)
                # 如果append失败，尝试重新初始化连接
                try:
                    self.close()
                    time.sleep(0.5)
                    self.initialize()
                    self.logger.info("TTS连接已重新初始化")
                except Exception as e2:
                    self.logger.error(f"重新初始化TTS连接失败: {e2}", exc_info=True)
                # 标记会话为非活动状态
                with self.callback.event_lock:
                    self.callback.is_session_active = False
                    if not self.callback.complete_event.is_set():
                        self.callback.complete_event.set()
    
    def finish_synthesis(self):
        """完成合成"""
        if not self.tts_realtime:
            self.logger.warning("TTS实时对象不存在，无法完成合成")
            return
        
        with self.synthesis_lock:
            try:
                # 确保回调存在且会话处于活动状态
                if self.callback:
                    with self.callback.event_lock:
                        # 只有在会话活动时才需要finish
                        if self.callback.is_session_active:
                            self.tts_realtime.finish()
                        else:
                            self.logger.debug("会话已非活动状态，跳过finish")
                else:
                    self.logger.warning("TTS回调不存在，无法完成合成")
            except Exception as e:
                self.logger.error(f"完成合成失败: {e}", exc_info=True)
                # 确保事件被设置，避免后续等待被阻塞
                if self.callback:
                    with self.callback.event_lock:
                        self.callback.is_session_active = False
                        if not self.callback.complete_event.is_set():
                            self.callback.complete_event.set()
    
    def get_audio(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        获取音频数据
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            音频数据或None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待当前合成完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否在超时前完成
        """
        if not self.callback:
            self.logger.warning("TTS回调不存在，无法等待完成")
            return False
        
        # 使用回调的wait_for_finished方法，它已经处理了超时和状态检查
        return self.callback.wait_for_finished(timeout)
    
    def get_queue_stats(self) -> dict:
        """
        获取队列统计信息
        
        Returns:
            包含统计信息的字典
        """
        if self.callback:
            return self.callback.get_stats()
        return {
            'queue_size': self.audio_queue.qsize(),
            'queue_maxsize': self.audio_queue.maxsize,
            'is_running': self.is_running
        }
    
    def close(self):
        """关闭TTS连接"""
        self.is_running = False
        if self.tts_realtime:
            try:
                self.tts_realtime.close()
                self.logger.info("TTS模块已关闭")
            except Exception as e:
                self.logger.error(f"关闭TTS模块失败: {e}", exc_info=True)
            finally:
                self.tts_realtime = None
                self.callback = None

