"""语音助手主程序入口"""
import sys
import logging
import signal
from voice_assistant.voice_assistant import VoiceAssistant
from voice_assistant.config import Config


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 验证配置
    if not Config.validate():
        logger.error("配置验证失败，请检查配置")
        sys.exit(1)
    
    api_key = Config.API_KEY
    if not api_key:
        logger.error("请设置 DASHSCOPE_API_KEY 环境变量或在 config.py 中配置")
        sys.exit(1)
    
    assistant = None
    try:
        assistant = VoiceAssistant(
            api_key=api_key,
            region=Config.REGION,
            memory_file=Config.MEMORY_FILE
        )
    except Exception as e:
        logger.error(f"创建语音助手失败: {e}", exc_info=True)
        sys.exit(1)
    
    shutdown_requested = False
    
    def signal_handler(sig, frame):
        """信号处理"""
        nonlocal shutdown_requested
        if shutdown_requested:
            return
        shutdown_requested = True
        logger.info("\n正在关闭...")
        if assistant:
            try:
                assistant.stop()
            except Exception as e:
                logger.error(f"停止助手时出错: {e}", exc_info=True)
        sys.exit(0)
    
    # 注册信号处理器（Windows上可能不支持）
    if sys.platform != 'win32':
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError) as e:
            logger.warning(f"注册信号处理器失败: {e}")
    
    try:
        logger.info("启动语音助手...")
        logger.info("按 Ctrl+C 停止")
        
        assistant.start()
        logger.info(f"助手已启动，运行中: {assistant.is_running}")
        
        # 保持运行
        while True:
            try:
                if not assistant.is_running:
                    logger.warning("语音助手意外停止")
                    break
                import time
                time.sleep(1)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"主循环错误: {e}", exc_info=True)
                import time
                time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"致命错误: {e}", exc_info=True)
    finally:
        if assistant:
            try:
                assistant.stop()
            except Exception as e:
                logger.error(f"停止助手时出错: {e}", exc_info=True)
        logger.info("语音助手已停止")


if __name__ == '__main__':
    main()

