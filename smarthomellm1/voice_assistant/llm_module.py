"""LLM模块 - 大语言模型对话处理"""
import json
import logging
from typing import Optional, List, Dict, Callable, Any
from openai import OpenAI


class LLMModule:
    """LLM模块 - 处理对话和工具调用"""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        use_stream: bool,
        tools_module: Optional[Any] = None,
        memory_module: Optional[Any] = None
    ):
        """
        初始化LLM模块
        
        Args:
            api_key: API密钥
            model: 模型名称
            system_prompt: 系统提示词
            use_stream: 是否使用流式输出
            tools_module: 工具模块实例
            memory_module: 记忆模块实例
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
        self.use_stream = use_stream
        self.tools_module = tools_module
        self.memory_module = memory_module
        
        # 构建包含记忆的系统提示词
        full_system_prompt = self._build_system_prompt(system_prompt)
        
        self.conversation_history: List[Dict[str, Any]] = [
            {'role': 'system', 'content': full_system_prompt}
        ]
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
    def _build_system_prompt(self, base_prompt: str) -> str:
        """
        构建包含记忆的系统提示词
        
        Args:
            base_prompt: 基础系统提示词
            
        Returns:
            完整的系统提示词
        """
        if self.memory_module:
            memory_summary = self.memory_module.get_memory_summary()
            if memory_summary:
                return f"{base_prompt}\n\n{memory_summary}"
        return base_prompt
        
    def initialize(self):
        """初始化LLM模块"""
        self.is_running = True
        self.logger.info("LLM模块初始化成功")
        
    def generate_response(
        self,
        user_input: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        生成回复（支持工具调用）
        
        Args:
            user_input: 用户输入
            stream_callback: 流式输出回调函数
            
        Returns:
            LLM生成的回复文本
        """
        if not self.is_running:
            return ""
        
        self.conversation_history.append({'role': 'user', 'content': user_input})
        
        try:
            if self.use_stream and stream_callback:
                return self._generate_stream_response(stream_callback)
            else:
                return self._generate_non_stream_response()
        except Exception as e:
            self.logger.error(f"生成回复失败: {e}", exc_info=True)
            return f"抱歉，处理请求时出现错误: {str(e)}"
    
    def _generate_stream_response(self, stream_callback: Callable[[str], None]) -> str:
        """
        流式生成回复（支持工具调用）
        
        Args:
            stream_callback: 流式输出回调函数
            
        Returns:
            完整的回复文本
        """
        max_iterations = 5
        
        for iteration in range(max_iterations):
            params = {
                'model': self.model,
                'messages': self.conversation_history,
                'stream': True
            }
            
            if self.tools_module:
                params['tools'] = self.tools_module.get_tools()
            
            try:
                completion = self.client.chat.completions.create(**params)
                full_response = ""
                tool_calls_accumulated = []
                
                for chunk in completion:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        
                        if delta.content:
                            full_response += delta.content
                            stream_callback(delta.content)
                        
                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                while len(tool_calls_accumulated) <= tc.index:
                                    tool_calls_accumulated.append({
                                        'id': '',
                                        'type': 'function',
                                        'function': {'name': '', 'arguments': ''}
                                    })
                                
                                tool_call = tool_calls_accumulated[tc.index]
                                if tc.id:
                                    tool_call['id'] = tc.id
                                if tc.function:
                                    if tc.function.name:
                                        tool_call['function']['name'] = tc.function.name
                                    if tc.function.arguments:
                                        tool_call['function']['arguments'] += tc.function.arguments
                
                # 处理工具调用
                if tool_calls_accumulated:
                    self.conversation_history.append({
                        'role': 'assistant',
                        'content': full_response or None,
                        'tool_calls': tool_calls_accumulated
                    })
                    
                    for tool_call in tool_calls_accumulated:
                        tool_name = tool_call['function']['name']
                        try:
                            tool_args = json.loads(tool_call['function']['arguments'] or '{}')
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"解析工具参数失败: {e}")
                            tool_args = {}
                        
                        self.logger.info(f"[工具调用] {tool_name}, 参数: {tool_args}")
                        
                        tool_result = (
                            self.tools_module.execute_tool(tool_name, tool_args)
                            if self.tools_module
                            else "工具模块未配置"
                        )
                        
                        self.logger.info(f"[工具调用] {tool_name} 执行结果: {tool_result}")
                        
                        self.conversation_history.append({
                            'role': 'tool',
                            'content': tool_result,
                            'tool_call_id': tool_call['id']
                        })
                    
                    continue  # 继续迭代处理工具调用结果
                else:
                    # 没有工具调用，返回最终回复
                    if full_response:
                        self.conversation_history.append({
                            'role': 'assistant',
                            'content': full_response
                        })
                    return full_response
                    
            except Exception as e:
                self.logger.error(f"流式生成错误 (迭代 {iteration + 1}): {e}", exc_info=True)
                if iteration == max_iterations - 1:
                    raise
                continue
        
        return ""
    
    def _generate_non_stream_response(self) -> str:
        """
        非流式生成回复（支持工具调用）
        
        Returns:
            完整的回复文本
        """
        max_iterations = 5
        
        for iteration in range(max_iterations):
            params = {
                'model': self.model,
                'messages': self.conversation_history,
                'stream': False
            }
            
            if self.tools_module:
                params['tools'] = self.tools_module.get_tools()
            
            try:
                completion = self.client.chat.completions.create(**params)
                message = completion.choices[0].message
                response_text = message.content
                tool_calls = message.tool_calls
                
                if tool_calls:
                    tool_calls_list = [
                        {
                            'id': tc.id,
                            'type': tc.type,
                            'function': {
                                'name': tc.function.name,
                                'arguments': tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                    
                    self.conversation_history.append({
                        'role': 'assistant',
                        'content': response_text or None,
                        'tool_calls': tool_calls_list
                    })
                    
                    for tool_call in tool_calls:
                        try:
                            tool_args = json.loads(tool_call.function.arguments or '{}')
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"解析工具参数失败: {e}")
                            tool_args = {}
                        
                        self.logger.info(
                            f"[工具调用] {tool_call.function.name}, 参数: {tool_args}"
                        )
                        
                        tool_result = (
                            self.tools_module.execute_tool(tool_call.function.name, tool_args)
                            if self.tools_module
                            else "工具模块未配置"
                        )
                        
                        self.logger.info(
                            f"[工具调用] {tool_call.function.name} 执行结果: {tool_result}"
                        )
                        
                        self.conversation_history.append({
                            'role': 'tool',
                            'content': tool_result,
                            'tool_call_id': tool_call.id
                        })
                    
                    continue  # 继续迭代处理工具调用结果
                else:
                    if response_text:
                        self.conversation_history.append({
                            'role': 'assistant',
                            'content': response_text
                        })
                    return response_text or ""
                    
            except Exception as e:
                self.logger.error(f"非流式生成错误 (迭代 {iteration + 1}): {e}", exc_info=True)
                if iteration == max_iterations - 1:
                    raise
                continue
        
        return ""
    
    def clear_history(self):
        """清空对话历史"""
        # 重新构建系统提示词（包含最新的记忆）
        original_prompt = (
            '你是一个AI智能家居助手，你的自然语言模型是DeepSeek，'
            '你需要用**简洁自然**的语言回答问题，不要输出颜文字，表情符号emoji，'
            '要连贯回答，像说出一段话一样回答。'
        )
        
        # 尝试从当前系统消息中提取原始提示词
        current_system = self.conversation_history[0]['content']
        if '用户的重要信息：' in current_system:
            original_prompt = current_system.split('用户的重要信息：')[0].strip()
        
        system_prompt = self._build_system_prompt(original_prompt)
        self.conversation_history = [{'role': 'system', 'content': system_prompt}]
        self.logger.info("对话历史已清空")
    
    def refresh_memory_in_prompt(self):
        """刷新系统提示词中的记忆信息"""
        if not self.memory_module or len(self.conversation_history) == 0:
            return
        
        # 获取原始系统提示词
        current_system = self.conversation_history[0]['content']
        if '用户的重要信息：' in current_system:
            original_prompt = current_system.split('用户的重要信息：')[0].strip()
        else:
            original_prompt = current_system
        
        system_prompt = self._build_system_prompt(original_prompt)
        self.conversation_history[0]['content'] = system_prompt
        self.logger.info("系统提示词中的记忆信息已刷新")
    
    def close(self):
        """关闭LLM模块"""
        self.is_running = False
        self.logger.info("LLM模块已关闭")

