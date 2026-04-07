"""语音助手主控制器"""
import logging
import threading
import queue
import time
from typing import Optional
from .asr_module import ASRModule
from .llm_module import LLMModule
from .tts_module import TTSModule
from .audio_io import AudioIO
from .config import Config
from .tools_module import ToolsModule
from .environment_monitor import EnvironmentMonitor


class VoiceAssistant:
    """语音助手主类"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        memory_file: Optional[str] = None
    ):
        """
        初始化语音助手
        
        Args:
            api_key: API密钥（可选，默认从Config读取）
            region: 区域（可选，默认从Config读取）
            memory_file: 记忆文件路径（可选）
        """
        self.api_key = api_key or Config.API_KEY
        if not self.api_key:
            raise ValueError(
                "API Key is required. Set DASHSCOPE_API_KEY environment variable."
            )
        
        self.region = region or Config.REGION
        ws_url = Config.get_ws_url(self.region)
        
        # 初始化各个模块
        self.asr = ASRModule(
            self.api_key,
            Config.ASR_SAMPLE_RATE,
            ws_url,
            Config.ASR_MODEL
        )
        
        self.tools_module = ToolsModule(memory_file=memory_file)
        
        # 从tools_module获取memory_module并传递给llm
        memory_module = (
            self.tools_module.memory_module
            if hasattr(self.tools_module, 'memory_module')
            else None
        )
        
        self.llm = LLMModule(
            self.api_key,
            Config.LLM_MODEL,
            Config.LLM_SYSTEM_PROMPT,
            Config.LLM_USE_STREAM,
            self.tools_module,
            memory_module
        )
        
        # 设置tools_module的llm_module引用，以便在保存记忆后刷新系统提示词
        self.tools_module.set_llm_module(self.llm)
        
        self.tts = TTSModule(
            self.api_key,
            Config.TTS_MODEL,
            Config.TTS_VOICE,
            ws_url,
            Config.TTS_SPEED
        )
        
        self.audio_io = AudioIO(
            Config.ASR_SAMPLE_RATE,
            Config.TTS_SAMPLE_RATE,
            Config.AUDIO_CHUNK_SIZE,
            Config.AUDIO_CHANNELS
        )

        # 初始化环境监控器
        self.environment_monitor = EnvironmentMonitor(
            alert_callback=self._on_environment_alert
        )
        
        # 状态管理
        self.is_running = False
        self.is_listening = False
        self.is_speaking = False
        
        # 线程和队列
        self.asr_thread: Optional[threading.Thread] = None
        self.llm_thread: Optional[threading.Thread] = None
        self.tts_thread: Optional[threading.Thread] = None
        self.health_check_thread: Optional[threading.Thread] = None
        self.text_queue = queue.Queue()
        
        # TTS工作线程事件驱动
        self.tts_audio_available_event = threading.Event()
        self.tts_backpressure_threshold = 0.8  # 背压阈值（队列使用率）
        
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """初始化所有模块"""
        try:
            self.asr.initialize(final_text_callback=self._on_final_text)
            self.llm.initialize()
            self.tts.initialize()
            self.audio_io.start_recording(callback=self._on_audio_input)
            self.audio_io.start_playback()
            self.is_running = True
            self.logger.info("语音助手初始化成功")
        except Exception as e:
            self.logger.error(f"语音助手初始化失败: {e}", exc_info=True)
            raise
        
    def start(self):
        """启动语音助手"""
        if not self.is_running:
            self.initialize()
        
        self.is_listening = True
        
        # 启动工作线程
        self.asr_thread = threading.Thread(target=self._asr_worker, daemon=True)
        self.llm_thread = threading.Thread(target=self._llm_worker, daemon=True)
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.health_check_thread = threading.Thread(target=self._health_check_worker, daemon=True)
        
        self.asr_thread.start()
        self.llm_thread.start()
        self.tts_thread.start()
        self.health_check_thread.start()

        # 启动环境监控
        self.environment_monitor.start()

        self.logger.info("语音助手已启动")
    
    def stop(self):
        """停止语音助手"""
        self.is_running = False
        self.is_listening = False
        
        # 停止环境监控
        self.environment_monitor.stop()

        # 等待线程结束
        threads = [self.asr_thread, self.llm_thread, self.tts_thread, self.health_check_thread]
        for thread in threads:
            if thread:
                thread.join(timeout=2.0)

        # 关闭各个模块
        try:
            self.asr.close()
            self.llm.close()
            self.tts.close()
            self.audio_io.close()
        except Exception as e:
            self.logger.error(f"关闭模块时出错: {e}", exc_info=True)
        
        self.logger.info("语音助手已停止")
    
    def _on_audio_input(self, audio_data: bytes):
        """
        音频输入回调
        
        Args:
            audio_data: 音频数据
        """
        if self.is_listening and not self.is_speaking and self.is_running:
            self.asr.send_audio_chunk(audio_data)
    
    def _on_final_text(self, text: str):
        """
        最终文本识别回调
        
        Args:
            text: 识别的文本
        """
        if text.strip():
            self.logger.info(f"用户说: {text}")
            self.text_queue.put(text)
    
    def _asr_worker(self):
        """ASR工作线程"""
        while self.is_running:
            try:
                result = self.asr.get_text(timeout=0.1)
                # 可以在这里处理识别结果
            except Exception as e:
                self.logger.error(f"ASR工作线程错误: {e}", exc_info=True)
                time.sleep(0.1)
    
    def _llm_worker(self):
        """LLM工作线程"""
        while self.is_running:
            try:
                user_text = self.text_queue.get(timeout=0.1)
                if user_text:
                    self.logger.info(f"处理用户输入: {user_text}")
                    
                    # 停止录音，避免回声
                    self.is_listening = False
                    self.is_speaking = True
                    self.audio_io.stop_recording()
                    
                    try:
                        # 初始缓冲机制：先累积一些文本再开始上传
                        initial_buffer = []
                        initial_buffer_size = Config.TTS_INITIAL_BUFFER_SIZE
                        buffer_sent = False
                        
                        # 分段缓冲：按标点符号分段累积
                        segment_buffer = []
                        segment_punctuation = Config.TTS_SEGMENT_PUNCTUATION
                        # 记录已发送的初始缓冲内容，用于后续分段时避免重复发送
                        sent_initial_buffer = ""
                        
                        def is_incomplete_number(text: str) -> bool:
                            """
                            检查文本末尾是否可能是不完整的数字
                            如果末尾是短数字（1-3位），可能是长数字的一部分，继续累积
                            例如："气压是10" -> True (可能后面还有"23.3"，形成"1023.3")
                            例如："1023.3" -> False (数字已完整)
                            例如："温度23" -> True (可能后面还有".9"，形成"23.9")
                            """
                            if not text:
                                return False
                            
                            # 去除末尾空白
                            text = text.rstrip()
                            if not text:
                                return False
                            
                            # 从末尾提取连续的数字序列（包括小数点）
                            num_chars = []
                            for i in range(len(text) - 1, -1, -1):
                                char = text[i]
                                if char.isdigit() or char == '.':
                                    num_chars.insert(0, char)
                                else:
                                    break
                            
                            if not num_chars:
                                return False
                            
                            # 如果末尾数字序列很短（1-3位），且包含数字（不只是小数点），可能是不完整的
                            num_str = ''.join(num_chars)
                            # 检查是否至少包含一个数字（不只是小数点）
                            has_digit = any(c.isdigit() for c in num_str)
                            
                            if has_digit and len(num_str) <= 3:
                                # 短数字序列，可能是长数字的一部分
                                return True
                            
                            return False
                        
                        def stream_callback(text_chunk: str):
                            nonlocal initial_buffer, buffer_sent, segment_buffer, sent_initial_buffer
                            if not text_chunk or not self.is_running:
                                return
                            
                            # 如果缓冲区还未发送，先累积文本
                            if not buffer_sent:
                                initial_buffer.append(text_chunk)
                                total_length = sum(len(chunk) for chunk in initial_buffer)
                                
                                # 当累积长度达到阈值时，检查是否在数字中间
                                if total_length >= initial_buffer_size:
                                    buffered_text = ''.join(initial_buffer)
                                    # 如果末尾是不完整的数字，继续累积（最多再累积10个字符避免无限等待）
                                    if is_incomplete_number(buffered_text) and total_length < initial_buffer_size + 10:
                                        return  # 继续累积
                                    
                                    if buffered_text.strip():
                                        self.logger.info(f"[TTS初始缓冲] ({total_length} 字符): {buffered_text}")
                                        self.tts.synthesize_text_stream(buffered_text)
                                    buffer_sent = True
                                    # 记录已发送的初始缓冲内容
                                    sent_initial_buffer = buffered_text
                                    # 如果初始缓冲末尾没有标点，保留在segment_buffer中以便后续分段
                                    if buffered_text and buffered_text[-1] not in segment_punctuation:
                                        segment_buffer = [buffered_text]
                                    else:
                                        segment_buffer = []
                                    initial_buffer = []  # 清空缓冲区
                            else:
                                # 缓冲区已发送，按标点符号分段累积
                                segment_buffer.append(text_chunk)
                                current_segment = ''.join(segment_buffer)
                                
                                # 检查是否包含分段标点符号
                                segment_end_index = -1
                                for i, char in enumerate(current_segment):
                                    if char in segment_punctuation:
                                        segment_end_index = i + 1
                                        break
                                
                                # 如果找到分段标点，检查分段点前是否在数字中间
                                if segment_end_index > 0:
                                    segment_to_check = current_segment[:segment_end_index]
                                    # 如果分段点前是不完整的数字，继续累积（最多再累积20个字符）
                                    if is_incomplete_number(segment_to_check) and len(current_segment) < len(segment_buffer) * 2 + 20:
                                        return  # 继续累积，不发送
                                    
                                    # 如果segment_to_check以sent_initial_buffer开头，说明包含已发送的初始缓冲
                                    # 这种情况下，只发送新增的部分（从sent_initial_buffer之后到标点的内容）
                                    if sent_initial_buffer and current_segment.startswith(sent_initial_buffer):
                                        # 计算新增部分的起始位置
                                        new_part_start = len(sent_initial_buffer)
                                        if segment_end_index > new_part_start:
                                            # 只发送新增部分（包括标点）
                                            segment_to_send = current_segment[new_part_start:segment_end_index]
                                            if segment_to_send.strip():
                                                self.logger.info(f"[TTS分段上传] ({len(segment_to_send)} 字符): {segment_to_send}")
                                                self.tts.synthesize_text_stream(segment_to_send)
                                            # 保留分段标点后的内容
                                            segment_buffer = [current_segment[segment_end_index:]] if segment_end_index < len(current_segment) else []
                                            sent_initial_buffer = ""  # 清除已发送标记
                                        else:
                                            # 标点在已发送内容中，不重复发送
                                            segment_buffer = [current_segment[segment_end_index:]] if segment_end_index < len(current_segment) else []
                                            sent_initial_buffer = ""
                                    else:
                                        # 正常分段发送
                                        segment_to_send = segment_to_check
                                        if segment_to_send.strip():
                                            self.logger.info(f"[TTS分段上传] ({len(segment_to_send)} 字符): {segment_to_send}")
                                            self.tts.synthesize_text_stream(segment_to_send)
                                        # 保留分段标点后的内容
                                        segment_buffer = [current_segment[segment_end_index:]] if segment_end_index < len(current_segment) else []
                                        sent_initial_buffer = ""  # 清除已发送标记
                        
                        response = self.llm.generate_response(
                            user_text,
                            stream_callback=stream_callback
                        )
                        
                        # 如果还有未发送的初始缓冲文本，在生成完成后发送
                        if initial_buffer and not buffer_sent:
                            buffered_text = ''.join(initial_buffer)
                            if buffered_text.strip():
                                self.logger.info(f"[TTS剩余初始缓冲] ({len(buffered_text)} 字符): {buffered_text}")
                                self.tts.synthesize_text_stream(buffered_text)
                        
                        # 如果还有未发送的分段缓冲文本，在生成完成后发送
                        if segment_buffer:
                            remaining_segment = ''.join(segment_buffer)
                            if remaining_segment.strip():
                                self.logger.info(f"[TTS剩余分段] ({len(remaining_segment)} 字符): {remaining_segment}")
                                self.tts.synthesize_text_stream(remaining_segment)
                        
                        # 完成TTS合成
                        if self.is_running:
                            try:
                                self.tts.finish_synthesis()
                                
                                # 智能超时：根据队列状态动态调整超时时间
                                tts_stats = self.tts.get_queue_stats()
                                audio_stats = self.audio_io.get_queue_stats()
                                
                                # 估算剩余音频数据量（粗略估算）
                                estimated_audio_duration = 0
                                if tts_stats.get('queue_size', 0) > 0:
                                    # 假设每个音频块约0.1秒（24000采样率，2400样本/块）
                                    estimated_audio_duration += tts_stats['queue_size'] * 0.1
                                if audio_stats.get('queue_size', 0) > 0:
                                    estimated_audio_duration += audio_stats['queue_size'] * 0.1
                                
                                # 动态超时：基础60秒 + 估算的音频时长 + 10秒缓冲
                                dynamic_timeout = max(60.0, estimated_audio_duration + 10.0)
                                dynamic_timeout = min(dynamic_timeout, 3000.0)  # 最多3000秒
                                
                                self.logger.debug(
                                    f"等待TTS完成（动态超时: {dynamic_timeout:.1f}秒，"
                                    f"TTS队列: {tts_stats.get('queue_size', 0)}, "
                                    f"音频队列: {audio_stats.get('queue_size', 0)}）"
                                )
                                
                                # 等待TTS完成
                                tts_completed = self.tts.wait_for_completion(timeout=dynamic_timeout)
                                if not tts_completed:
                                    self.logger.warning(
                                        f"等待TTS完成超时（{dynamic_timeout:.1f}秒），"
                                        f"TTS统计: {tts_stats}"
                                    )
                                
                                # 等待播放完成（使用相同的动态超时）
                                self.logger.debug(
                                    f"等待播放完成（动态超时: {dynamic_timeout:.1f}秒，"
                                    f"音频队列: {audio_stats.get('queue_size', 0)}）"
                                )
                                playback_completed = self.audio_io.wait_for_playback_complete(timeout=dynamic_timeout)
                                if not playback_completed:
                                    self.logger.warning(
                                        f"等待播放完成超时（{dynamic_timeout:.1f}秒），"
                                        f"音频统计: {audio_stats}"
                                    )
                                
                                # 记录最终统计信息
                                final_tts_stats = self.tts.get_queue_stats()
                                final_audio_stats = self.audio_io.get_queue_stats()
                                self.logger.debug(
                                    f"播放完成统计 - TTS: {final_tts_stats}, 音频: {final_audio_stats}"
                                )
                                
                            except Exception as e:
                                self.logger.error(f"完成TTS合成时出错: {e}", exc_info=True)
                                # 即使出错也继续，避免阻塞
                        
                        self.logger.info(f"助手回复: {response}")
                    finally:
                        # 恢复录音和监听
                        if self.is_running:
                            self.audio_io.start_recording(callback=self._on_audio_input)
                        self.is_speaking = False
                        self.is_listening = True
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"LLM工作线程错误: {e}", exc_info=True)
                if self.is_running and not self.audio_io.is_recording:
                    try:
                        self.audio_io.start_recording(callback=self._on_audio_input)
                    except Exception as e2:
                        self.logger.error(f"重启录音失败: {e2}", exc_info=True)
                self.is_listening = True
                self.is_speaking = False
                time.sleep(0.1)
    
    def _tts_worker(self):
        """TTS工作线程 - 播放音频（事件驱动版本，带背压控制）"""
        consecutive_errors = 0
        max_consecutive_errors = 10
        backpressure_wait_time = 0.1  # 背压时的等待时间
        
        while self.is_running:
            try:
                # 检查背压：如果音频输出队列接近满，等待一段时间
                audio_stats = self.audio_io.get_queue_stats()
                queue_size = audio_stats.get('queue_size', 0)
                queue_maxsize = audio_stats.get('queue_maxsize', 0)
                
                if queue_maxsize > 0:
                    queue_usage = queue_size / queue_maxsize
                    if queue_usage >= self.tts_backpressure_threshold:
                        # 背压：队列使用率过高，等待一段时间
                        self.logger.debug(
                            f"TTS背压：音频队列使用率 {queue_usage*100:.1f}% "
                            f"({queue_size}/{queue_maxsize})，等待中..."
                        )
                        time.sleep(backpressure_wait_time)
                        continue
                
                # 尝试获取音频数据（使用较短的超时，以便能够响应背压）
                audio_data = self.tts.get_audio(timeout=0.1)
                if audio_data:
                    self.audio_io.play_audio_chunk(audio_data)
                    consecutive_errors = 0  # 重置错误计数
                    # 设置事件，表示有音频数据可用（用于其他线程的同步）
                    self.tts_audio_available_event.set()
                else:
                    # 没有音频数据，清除事件并等待
                    self.tts_audio_available_event.clear()
                    # 使用事件等待，而不是固定sleep
                    time.sleep(0.05)
                    
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(
                    f"TTS工作线程错误 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}",
                    exc_info=True
                )
                
                # 如果连续错误过多，尝试重新初始化TTS
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error("TTS工作线程连续错误过多，尝试重新初始化TTS模块")
                    try:
                        self.tts.close()
                        time.sleep(0.5)
                        self.tts.initialize()
                        consecutive_errors = 0
                        self.logger.info("TTS模块重新初始化成功")
                    except Exception as e2:
                        self.logger.error(f"重新初始化TTS模块失败: {e2}", exc_info=True)
                        time.sleep(1.0)  # 等待更长时间再重试
                else:
                    time.sleep(0.1)
    
    def _health_check_worker(self):
        """健康检查工作线程 - 定期检查系统状态"""
        while self.is_running:
            try:
                time.sleep(5.0)  # 每5秒检查一次
                
                if not self.is_running:
                    break
                
                # 检查播放线程健康状态
                if self.audio_io.is_playing:
                    # 这会自动检查并重启播放线程（如果需要）
                    self.audio_io._check_and_restart_playback()
                
                # 检查TTS模块状态
                if not self.tts.is_running:
                    self.logger.warning("TTS模块未运行，尝试重新初始化")
                    try:
                        self.tts.initialize()
                        self.logger.info("TTS模块重新初始化成功")
                    except Exception as e:
                        self.logger.error(f"重新初始化TTS模块失败: {e}", exc_info=True)
                
            except Exception as e:
                self.logger.error(f"健康检查线程错误: {e}", exc_info=True)
                time.sleep(5.0)  # 出错后等待再继续
    
    def _on_environment_alert(self, alert_message: str):
        """
        环境警告回调
        
        Args:
            alert_message: 警告消息
        """
        self.logger.warning(f"环境警告: {alert_message}")

        # 在新线程中处理警告，避免阻塞监控线程
        alert_thread = threading.Thread(
            target=self._handle_alert,
            args=(alert_message,),
            daemon=True
        )
        alert_thread.start()

    def _handle_alert(self, alert_message: str):
        """
        处理警告消息
        
        Args:
            alert_message: 警告消息
        """
        try:
            # 等待当前对话完成（如果正在进行中）
            while self.is_speaking and self.is_running:
                time.sleep(0.1)

            if not self.is_running:
                return

            # 临时停止录音，避免干扰
            was_listening = self.is_listening
            if was_listening:
                self.is_listening = False
                self.audio_io.stop_recording()

            # 设置为说话状态
            self.is_speaking = True

            try:
                # 直接通过TTS播放警告消息
                self.tts.synthesize_text_stream(alert_message)

                # 完成TTS合成
                try:
                    self.tts.finish_synthesis()

                    # 等待TTS完成（使用较长的超时，但不无限等待）
                    tts_completed = self.tts.wait_for_completion(timeout=120.0)
                    if not tts_completed:
                        self.logger.warning("环境警告TTS完成超时")
                    
                    # 等待播放完成（使用较长的超时）
                    playback_completed = self.audio_io.wait_for_playback_complete(timeout=120.0)
                    if not playback_completed:
                        self.logger.warning("环境警告播放完成超时")
                except Exception as e:
                    self.logger.error(f"处理环境警告TTS时出错: {e}", exc_info=True)

            finally:
                # 恢复录音状态
                self.is_speaking = False
                if was_listening and self.is_running:
                    self.audio_io.start_recording(callback=self._on_audio_input)
                    self.is_listening = True

        except Exception as e:
            self.logger.error(f"处理环境警告失败: {e}", exc_info=True)

    def clear_history(self):
        """清空对话历史"""
        self.llm.clear_history()
        self.logger.info("对话历史已清空")

