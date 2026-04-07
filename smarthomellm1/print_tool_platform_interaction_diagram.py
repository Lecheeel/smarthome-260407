"""
模拟工具调用时的真实日志输出（与 main.py 的 logging 格式一致）

日志格式来自 main.py：
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'

每条日志内容来自实际代码中的 logger 调用，不编造。

运行：
  python smarthomellm1/print_tool_platform_interaction_diagram.py
  python smarthomellm1/print_tool_platform_interaction_diagram.py --speed 0.02
  python smarthomellm1/print_tool_platform_interaction_diagram.py --no-sleep
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
import time


def _log_time() -> str:
    """与 logging 默认 asctime 格式一致"""
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ",000"


def _log_line(name: str, level: str, message: str) -> str:
    return f"{_log_time()} - {name} - {level} - {message}"


def _type_print(line: str, speed_s: float) -> None:
    if speed_s <= 0:
        print(line)
        return
    for ch in line:
        print(ch, end="", flush=True)
        time.sleep(speed_s)
    print()


def _print_block(lines: list[str], line_sleep_s: float, char_speed_s: float) -> None:
    for line in lines:
        _type_print(line, char_speed_s)
        if line_sleep_s > 0:
            time.sleep(line_sleep_s)


def build_simulated_log_lines() -> list[str]:
    """
    仅包含代码中真实存在的日志文案（voice_assistant / llm_module / tools_module / memory_module）。
    """
    t = _log_time()
    voice = "voice_assistant.voice_assistant"
    llm = "voice_assistant.llm_module"
    tools = "voice_assistant.tools_module"
    memory = "voice_assistant.memory_module"

    return [
        # "# 场景1：用户问温度 -> 环境监测查询工具",
        _log_line(voice, "INFO", "用户说: 现在温度多少"),
        _log_line(voice, "INFO", "处理用户输入: 现在温度多少"),
        _log_line(llm, "INFO", "[工具调用] get_latest_sensor_data, 参数: {}"),
        _log_line(tools, "INFO", "[工具执行] 开始执行工具: get_latest_sensor_data"),
        _log_line(tools, "INFO", "[工具执行] 工具 get_latest_sensor_data 执行完成"),
        _log_line(
            llm,
            "INFO",
            "[工具调用] get_latest_sensor_data 执行结果: 智能家居最新环境数据：温度25.3°C，湿度60.5%，气压1013.2hPa，VOC浓度125ppm",
        ),
        "",
        # "# 场景2：用户问天气（未说城市）-> 从记忆取位置 + 天气查询工具",
        _log_line(voice, "INFO", "用户说: 今天天气怎么样"),
        _log_line(voice, "INFO", "处理用户输入: 今天天气怎么样"),
        _log_line(llm, "INFO", "[工具调用] get_current_weather, 参数: {}"),
        _log_line(tools, "INFO", "[工具执行] 开始执行工具: get_current_weather"),
        _log_line(tools, "INFO", "从记忆中获取用户位置: 北京市"),
        _log_line(tools, "INFO", "[工具执行] 工具 get_current_weather 执行完成"),
        _log_line(
            llm,
            "INFO",
            "[工具调用] get_current_weather 执行结果: 北京市的实时天气：晴，温度15°C，体感温度14°C。风向东风，风力2级。相对湿度45%，大气压强1015百帕，能见度10公里。",
        ),
        "",
        # "# 场景3：用户说“记住我在北京” -> 记忆管理工具 + 刷新系统提示词",
        _log_line(voice, "INFO", "用户说: 记住我在北京"),
        _log_line(voice, "INFO", "处理用户输入: 记住我在北京"),
        _log_line(llm, "INFO", "[工具调用] save_memory, 参数: {'key': 'location', 'value': '北京市'}"),
        _log_line(tools, "INFO", "[工具执行] 开始执行工具: save_memory"),
        _log_line(memory, "INFO", "保存记忆: location = 北京市"),
        _log_line(memory, "INFO", "成功保存记忆到文件: user_memory.json"),
        _log_line(tools, "INFO", "[工具执行] 工具 save_memory 执行完成"),
        _log_line(llm, "INFO", "[工具调用] save_memory 执行结果: 已成功保存记忆：location = 北京市"),
        _log_line(llm, "INFO", "系统提示词中的记忆信息已刷新"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="模拟工具调用时的真实日志（可截图）")
    parser.add_argument(
        "--speed",
        type=float,
        default=0.0,
        help="逐字符打印速度（秒/字符），0 表示整行输出",
    )
    parser.add_argument(
        "--line-sleep",
        type=float,
        default=0.06,
        help="每行输出后停顿（秒）",
    )
    parser.add_argument("--no-sleep", action="store_true", help="不 sleep，立即输出")
    args = parser.parse_args()

    char_speed_s = 0.0 if args.no_sleep else max(args.speed, 0.0)
    line_sleep_s = 0.0 if args.no_sleep else max(args.line_sleep, 0.0)

    lines = build_simulated_log_lines()
    _print_block(lines, line_sleep_s=line_sleep_s, char_speed_s=char_speed_s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
