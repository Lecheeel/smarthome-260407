"""音频输入/输出处理模块"""
import logging
import queue
import threading
import time
from typing import Optional, Callable
import sounddevice as sd
import numpy as np
from .config import Config


class AudioIO:
    """音频输入输出处理"""
    
    def __init__(
        self,
        sample_rate: int,
        output_sample_rate: int,
        chunk_size: int,
        channels: int,
        queue_size: Optional[int] = None
    ):
        """
        初始化音频IO
        
        Args:
            sample_rate: 输入采样率
            output_sample_rate: 输出采样率
            chunk_size: 音频块大小
            channels: 声道数
            queue_size: 输出队列最大大小（可选，默认从Config读取）
        """
        self.sample_rate = sample_rate
        self.output_sample_rate = output_sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.dtype = np.int16
        
        # 缓存音频格式信息，避免重复计算
        self.bytes_per_frame = self.channels * np.dtype(self.dtype).itemsize
        self.bytes_per_sample = np.dtype(self.dtype).itemsize
        
        self.input_stream: Optional[sd.InputStream] = None
        self.output_stream: Optional[sd.OutputStream] = None
        # 使用有界队列，防止内存溢出
        queue_maxsize = queue_size or Config.AUDIO_OUTPUT_QUEUE_SIZE
        self.output_queue = queue.Queue(maxsize=queue_maxsize)
        
        self.is_recording = False
        self.is_playing = False
        self.recording_callback: Optional[Callable[[bytes], None]] = None
        self.playback_thread_lock = threading.Lock()
        self.last_playback_activity = time.time()
        self._current_audio_chunk: Optional[bytes] = None
        self._current_audio_offset = 0
        
        # 用于事件驱动的播放完成检测
        self.playback_complete_event = threading.Event()
        self.playback_complete_lock = threading.Lock()
        self.queued_chunks_count = 0  # 队列中的块数量
        self.dropped_chunks = 0  # 统计丢弃的音频块数量
        self.total_chunks = 0  # 统计总音频块数量
        
        # 播放流健康检查相关
        self.last_stream_check_time = 0
        self.stream_check_interval = 2.0  # 每2秒检查一次流状态
        
        self.logger = logging.getLogger(__name__)
        
    def start_recording(self, callback: Optional[Callable[[bytes], None]] = None):
        """
        开始录音
        
        Args:
            callback: 音频数据回调函数
        """
        if self.is_recording:
            self.logger.warning("录音已在进行中")
            return
        
        try:
            self.recording_callback = callback
            
            def input_callback(indata: np.ndarray, frames: int, time_info, status):
                """sounddevice 输入回调函数"""
                if status:
                    self.logger.warning(f"录音状态: {status}")
                if self.is_recording and self.recording_callback:
                    try:
                        # 将 NumPy 数组转换为 bytes
                        audio_bytes = indata.tobytes()
                        self.recording_callback(audio_bytes)
                    except Exception as e:
                        self.logger.error(f"录音回调错误: {e}", exc_info=True)
            
            self.input_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.chunk_size,
                callback=input_callback
            )
            self.input_stream.start()
            self.is_recording = True
            self.logger.info("录音已启动")
        except Exception as e:
            self.logger.error(f"启动录音失败: {e}", exc_info=True)
            self.is_recording = False
            if self.input_stream:
                try:
                    self.input_stream.stop()
                    self.input_stream.close()
                except:
                    pass
                self.input_stream = None
            raise
        
    def stop_recording(self):
        """停止录音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self.recording_callback = None
        
        if self.input_stream:
            try:
                self.input_stream.stop()
                self.input_stream.close()
            except Exception as e:
                self.logger.error(f"关闭输入流失败: {e}")
            finally:
                self.input_stream = None
        
        self.logger.info("录音已停止")
        
    def _check_and_restart_playback(self):
        """检查播放流状态，如果停止则重启（减少检查频率）"""
        current_time = time.time()
        # 减少检查频率，避免频繁检查
        if current_time - self.last_stream_check_time < self.stream_check_interval:
            return
        
        self.last_stream_check_time = current_time
        
        with self.playback_thread_lock:
            if self.is_playing:
                # 检查输出流是否还在运行
                if self.output_stream and self.output_stream.active:
                    return  # 流正常运行，无需重启
                
                # 流已停止，需要重启
                self.logger.warning("播放流已停止，正在重启...")
                self.is_playing = False
                # 清理旧的输出流
                if self.output_stream:
                    try:
                        self.output_stream.stop()
                        self.output_stream.close()
                    except Exception as e:
                        self.logger.error(f"关闭旧输出流失败: {e}")
                    finally:
                        self.output_stream = None
                # 清空队列中的旧数据
                with self.playback_complete_lock:
                    while not self.output_queue.empty():
                        try:
                            self.output_queue.get_nowait()
                            self.queued_chunks_count = max(0, self.queued_chunks_count - 1)
                        except queue.Empty:
                            break
                # 重置当前音频块
                self._current_audio_chunk = None
                self._current_audio_offset = 0
                # 重新启动播放
                try:
                    self._start_playback_internal()
                except Exception as e:
                    self.logger.error(f"重启播放失败: {e}", exc_info=True)
                    self.is_playing = False
    
    def _convert_bytes_to_array(self, audio_bytes: bytes, offset: int = 0) -> np.ndarray:
        """
        将字节数据转换为numpy数组（优化版本，使用memoryview）
        
        Args:
            audio_bytes: 音频字节数据
            offset: 起始偏移量
            
        Returns:
            形状正确的numpy数组
        """
        if offset >= len(audio_bytes):
            return np.array([], dtype=self.dtype).reshape(-1, self.channels)
        
        # 使用memoryview减少内存复制
        remaining_bytes = audio_bytes[offset:]
        audio_array = np.frombuffer(remaining_bytes, dtype=self.dtype)
        
        # 确保形状正确
        if self.channels > 1:
            total_samples = len(audio_array) // self.channels
            audio_array = audio_array[:total_samples * self.channels].reshape(-1, self.channels)
        else:
            audio_array = audio_array.reshape(-1, 1)
        
        return audio_array
    
    def _fill_output_buffer(self, outdata: np.ndarray, frames: int) -> int:
        """
        填充输出缓冲区（从队列获取音频数据）
        
        Args:
            outdata: 输出缓冲区
            frames: 需要的帧数
            
        Returns:
            实际写入的帧数
        """
        frames_written = 0
        
        while frames_written < frames and self.is_playing:
            # 如果当前音频块已用完或不存在，从队列获取新数据
            if self._current_audio_chunk is None or self._current_audio_offset >= len(self._current_audio_chunk):
                try:
                    self._current_audio_chunk = self.output_queue.get_nowait()
                    self._current_audio_offset = 0
                    with self.playback_complete_lock:
                        self.queued_chunks_count = max(0, self.queued_chunks_count - 1)
                        # 如果队列为空且当前块是最后一个，设置完成事件
                        if self.output_queue.empty() and self._current_audio_chunk:
                            # 延迟设置事件，等待当前块播放完成
                            pass
                except queue.Empty:
                    # 队列为空，检查是否可以设置完成事件
                    with self.playback_complete_lock:
                        if self.queued_chunks_count == 0:
                            self.playback_complete_event.set()
                    break
            
            if self._current_audio_chunk:
                # 转换音频数据
                audio_array = self._convert_bytes_to_array(self._current_audio_chunk, self._current_audio_offset)
                
                if len(audio_array) == 0:
                    self._current_audio_chunk = None
                    self._current_audio_offset = 0
                    continue
                
                # 计算需要复制的帧数
                frames_needed = frames - frames_written
                frames_available = len(audio_array)
                frames_to_copy = min(frames_needed, frames_available)
                
                # 复制数据到输出缓冲区
                if self.channels > 1:
                    outdata[frames_written:frames_written + frames_to_copy] = audio_array[:frames_to_copy]
                else:
                    outdata[frames_written:frames_written + frames_to_copy, 0] = audio_array[:frames_to_copy].flatten()
                
                # 更新偏移量
                self._current_audio_offset += frames_to_copy * self.bytes_per_frame
                frames_written += frames_to_copy
                
                # 如果当前块已用完，重置
                if self._current_audio_offset >= len(self._current_audio_chunk):
                    self._current_audio_chunk = None
                    self._current_audio_offset = 0
                    # 检查队列是否为空，如果为空则设置完成事件
                    with self.playback_complete_lock:
                        if self.output_queue.empty() and self.queued_chunks_count == 0:
                            self.playback_complete_event.set()
        
        return frames_written
    
    def _start_playback_internal(self):
        """内部启动播放方法"""
        # 用于存储当前正在播放的音频块（可能跨多个回调调用）
        self._current_audio_chunk: Optional[bytes] = None
        self._current_audio_offset = 0
        
        def output_callback(outdata: np.ndarray, frames: int, time_info, status):
            """sounddevice 输出回调函数（重构后的简化版本）"""
            if status:
                self.logger.warning(f"播放状态: {status}")
            
            try:
                outdata.fill(0)  # 初始化为静音
                frames_written = self._fill_output_buffer(outdata, frames)
                
                if frames_written > 0:
                    self.last_playback_activity = time.time()
            except Exception as e:
                self.logger.error(f"播放回调错误: {e}", exc_info=True)
                outdata.fill(0)
        
        try:
            self.output_stream = sd.OutputStream(
                samplerate=self.output_sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.chunk_size,
                callback=output_callback
            )
            self.output_stream.start()
            self.is_playing = True
            self.last_playback_activity = time.time()
            self._current_audio_chunk = None
            self._current_audio_offset = 0
            self.logger.info("播放已启动")
        except Exception as e:
            self.logger.error(f"启动播放失败: {e}", exc_info=True)
            self.is_playing = False
            if self.output_stream:
                try:
                    self.output_stream.stop()
                    self.output_stream.close()
                except:
                    pass
                self.output_stream = None
            raise
    
    def start_playback(self):
        """开始播放"""
        with self.playback_thread_lock:
            if self.is_playing:
                # 检查流是否真的在运行
                if self.output_stream and self.output_stream.active:
                    self.logger.warning("播放已在进行中")
                    return
                else:
                    # 标记为播放但流已停止，需要重启
                    self.logger.warning("播放状态异常，正在重启...")
                    self.is_playing = False
            
            try:
                self._start_playback_internal()
            except Exception as e:
                self.logger.error(f"启动播放失败: {e}", exc_info=True)
                self.is_playing = False
                raise
    
    def play_audio_chunk(self, audio_data: bytes):
        """
        播放音频数据块
        
        Args:
            audio_data: 音频数据
        """
        # 检查并重启播放线程（如果需要）
        self._check_and_restart_playback()
        
        if self.is_playing:
            try:
                self.total_chunks += 1
                # 清除完成事件，因为新数据已加入
                with self.playback_complete_lock:
                    self.playback_complete_event.clear()
                
                # 尝试添加音频数据到队列，如果队列满则丢弃最旧的数据
                try:
                    self.output_queue.put_nowait(audio_data)
                    with self.playback_complete_lock:
                        self.queued_chunks_count += 1
                except queue.Full:
                    # 队列满时，尝试丢弃最旧的数据并添加新数据
                    try:
                        self.output_queue.get_nowait()  # 丢弃最旧的数据
                        self.output_queue.put_nowait(audio_data)
                        self.dropped_chunks += 1
                        if self.dropped_chunks % 10 == 0:  # 每10个丢弃块记录一次警告
                            self.logger.warning(
                                f"音频输出队列溢出，已丢弃 {self.dropped_chunks} 个音频块 "
                                f"(队列大小: {self.output_queue.qsize()}/{self.output_queue.maxsize})"
                            )
                    except queue.Empty:
                        # 队列已空，直接添加
                        try:
                            self.output_queue.put_nowait(audio_data)
                            with self.playback_complete_lock:
                                self.queued_chunks_count += 1
                        except queue.Full:
                            # 仍然满，丢弃当前数据
                            self.dropped_chunks += 1
                            self.logger.warning("音频输出队列持续溢出，丢弃音频数据")
            except Exception as e:
                self.logger.error(f"添加音频数据到队列失败: {e}", exc_info=True)
                # 如果添加失败，尝试重启播放
                self._check_and_restart_playback()
    
    def wait_for_playback_complete(self, timeout: Optional[float] = None) -> bool:
        """
        等待播放队列清空（使用事件驱动机制）
        
        Args:
            timeout: 超时时间（秒），None表示无限等待
            
        Returns:
            是否在超时前完成
        """
        # 检查播放流健康状态
        self._check_and_restart_playback()
        
        if not self.is_playing:
            return True
        
        # 检查是否已经完成
        with self.playback_complete_lock:
            queue_empty = self.output_queue.empty()
            current_chunk_done = (self._current_audio_chunk is None or 
                                 self._current_audio_offset >= len(self._current_audio_chunk))
            if queue_empty and current_chunk_done and self.queued_chunks_count == 0:
                return True
        
        # 计算缓冲区持续时间（用于最后的额外等待）
        buffer_duration = (self.chunk_size * 2) / self.output_sample_rate
        
        # 使用事件等待，而不是轮询
        start_time = time.time()
        check_interval = 0.5  # 每0.5秒检查一次流状态
        
        while True:
            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    self.logger.warning(f"等待播放完成超时（{timeout}秒）")
                    return False
                remaining_timeout = timeout - elapsed
            else:
                remaining_timeout = None
            
            # 定期检查播放流状态
            elapsed = time.time() - start_time
            if elapsed > check_interval:
                self._check_and_restart_playback()
                if not self.is_playing:
                    self.logger.warning("播放流在等待过程中停止")
                    return False
                start_time = time.time()  # 重置检查时间
            
            # 等待完成事件（最多等待check_interval秒）
            wait_timeout = min(check_interval, remaining_timeout) if remaining_timeout else check_interval
            if self.playback_complete_event.wait(timeout=wait_timeout):
                # 事件已设置，再次确认队列确实为空
                with self.playback_complete_lock:
                    queue_empty = self.output_queue.empty()
                    current_chunk_done = (self._current_audio_chunk is None or 
                                         self._current_audio_offset >= len(self._current_audio_chunk))
                    if queue_empty and current_chunk_done and self.queued_chunks_count == 0:
                        # 额外等待一小段时间确保播放完成
                        time.sleep(buffer_duration)
                        return True
                    else:
                        # 状态不一致，清除事件继续等待
                        self.playback_complete_event.clear()
        
        return True
    
    def get_queue_stats(self) -> dict:
        """
        获取队列统计信息
        
        Returns:
            包含统计信息的字典
        """
        with self.playback_complete_lock:
            return {
                'queue_size': self.output_queue.qsize(),
                'queue_maxsize': self.output_queue.maxsize,
                'queued_chunks_count': self.queued_chunks_count,
                'total_chunks': self.total_chunks,
                'dropped_chunks': self.dropped_chunks,
                'is_playing': self.is_playing,
                'has_current_chunk': self._current_audio_chunk is not None
            }
    
    def close(self):
        """关闭音频IO"""
        self.stop_recording()
        
        self.is_playing = False
        
        if self.output_stream:
            try:
                self.output_stream.stop()
                self.output_stream.close()
            except Exception as e:
                self.logger.error(f"关闭输出流失败: {e}")
            finally:
                self.output_stream = None
        
        # 清理状态
        self._current_audio_chunk = None
        self._current_audio_offset = 0
        
        # 清空队列
        with self.playback_complete_lock:
            while not self.output_queue.empty():
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    break
            self.queued_chunks_count = 0
            self.playback_complete_event.set()
        
        self.logger.info("音频IO已关闭")

