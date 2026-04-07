"""记忆模块 - 保存和读取用户的重要信息"""
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime


class MemoryModule:
    """记忆模块 - 管理用户信息的持久化存储"""
    
    def __init__(self, memory_file: str = "user_memory.json"):
        """
        初始化记忆模块
        
        Args:
            memory_file: 记忆文件的路径
        """
        self.memory_file = memory_file
        self.logger = logging.getLogger(__name__)
        self.memories: Dict[str, Any] = {}
        self._load_memories()
    
    def _load_memories(self):
        """从文件加载记忆"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                self.logger.info(f"成功加载记忆文件: {self.memory_file}")
            else:
                self.memories = {}
                self.logger.info("记忆文件不存在，创建新的记忆存储")
        except json.JSONDecodeError as e:
            self.logger.error(f"解析记忆文件失败: {e}")
            self.memories = {}
        except Exception as e:
            self.logger.error(f"加载记忆文件失败: {e}", exc_info=True)
            self.memories = {}
    
    def _save_memories(self) -> bool:
        """
        保存记忆到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            memory_dir = os.path.dirname(self.memory_file)
            if memory_dir and not os.path.exists(memory_dir):
                os.makedirs(memory_dir, exist_ok=True)
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
            self.logger.info(f"成功保存记忆到文件: {self.memory_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存记忆文件失败: {e}", exc_info=True)
            return False
    
    def save_memory(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None
    ) -> bool:
        """
        保存一条记忆
        
        Args:
            key: 记忆的键（例如：'location', 'name', 'preference'）
            value: 记忆的值
            description: 可选的描述信息
        
        Returns:
            是否保存成功
        """
        try:
            memory_entry = {
                'value': value,
                'description': description,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.memories[key] = memory_entry
            success = self._save_memories()
            if success:
                self.logger.info(f"保存记忆: {key} = {value}")
            return success
        except Exception as e:
            self.logger.error(f"保存记忆失败: {e}", exc_info=True)
            return False
    
    def get_memory(self, key: str) -> Optional[Any]:
        """
        获取一条记忆
        
        Args:
            key: 记忆的键
        
        Returns:
            记忆的值，如果不存在则返回None
        """
        if key in self.memories:
            return self.memories[key].get('value')
        return None
    
    def get_all_memories(self) -> Dict[str, Any]:
        """
        获取所有记忆
        
        Returns:
            所有记忆的字典
        """
        return self.memories.copy()
    
    def get_memory_summary(self) -> str:
        """
        获取记忆的文本摘要，用于添加到系统提示词
        
        Returns:
            记忆的文本摘要
        """
        if not self.memories:
            return ""
        
        summary_parts = ["用户的重要信息："]
        for key, entry in self.memories.items():
            value = entry.get('value', '')
            description = entry.get('description', '')
            
            if description:
                summary_parts.append(f"- {key}: {value} ({description})")
            else:
                summary_parts.append(f"- {key}: {value}")
        
        return "\n".join(summary_parts)
    
    def delete_memory(self, key: str) -> bool:
        """
        删除一条记忆
        
        Args:
            key: 要删除的记忆的键
        
        Returns:
            是否删除成功
        """
        if key in self.memories:
            del self.memories[key]
            success = self._save_memories()
            if success:
                self.logger.info(f"删除记忆: {key}")
            return success
        return False
    
    def clear_all_memories(self) -> bool:
        """
        清空所有记忆
        
        Returns:
            是否清空成功
        """
        self.memories = {}
        success = self._save_memories()
        if success:
            self.logger.info("清空所有记忆")
        return success

