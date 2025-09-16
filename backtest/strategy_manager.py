import os
import importlib
from typing import Dict, Type, Any, List, Optional

# 全局策略注册表
global_strategy_registry = {}

class StrategyMetadata:
    """策略元数据类"""
    def __init__(self, name: str, display_name: str, description: str, params_schema: Dict = None):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.params_schema = params_schema or {}

class StrategyManager:
    """策略管理器，负责动态加载和注册策略"""
    
    @classmethod
    def register_strategy(cls, metadata: StrategyMetadata):
        """注册策略的装饰器"""
        def decorator(strategy_class):
            global_strategy_registry[metadata.name] = {
                'class': strategy_class,
                'metadata': metadata
            }
            return strategy_class
        return decorator
    
    @classmethod
    def get_strategy(cls, name: str):
        """获取指定名称的策略类"""
        if name not in global_strategy_registry:
            raise ValueError(f"未找到策略: {name}")
        return global_strategy_registry[name]['class']
    
    @classmethod
    def get_strategy_metadata(cls, name: str):
        """获取指定名称的策略元数据"""
        if name not in global_strategy_registry:
            raise ValueError(f"未找到策略: {name}")
        return global_strategy_registry[name]['metadata']
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """列出所有注册的策略名称"""
        return list(global_strategy_registry.keys())
    
    @classmethod
    def list_strategies_with_metadata(cls) -> Dict[str, Dict]:
        """列出所有注册的策略及其元数据"""
        return {
            name: {
                'display_name': info['metadata'].display_name,
                'description': info['metadata'].description,
                'params_schema': info['metadata'].params_schema
            } 
            for name, info in global_strategy_registry.items()
        }
    
    @classmethod
    def create_strategy(cls, name: str, **kwargs) -> Any:
        """创建策略实例，自动过滤不被策略类接受的参数"""
        strategy_class = cls.get_strategy(name)
        
        # 获取策略类构造函数接受的参数名
        import inspect
        sig = inspect.signature(strategy_class.__init__)
        # 过滤出策略类接受的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        
        return strategy_class(**filtered_kwargs)
    
    @classmethod
    def load_strategies_from_directory(cls, directory: str):
        """从目录动态加载所有策略"""
        # 确保目录存在
        if not os.path.exists(directory):
            return
        
        # 获取目录中的所有Python文件
        for filename in os.listdir(directory):
            if filename.endswith('.py') and filename != '__init__.py':
                # 导入模块
                module_name = f"{directory.replace('/', '.').replace('\\', '.')}.{filename[:-3]}"
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"加载策略模块 {module_name} 失败: {e}")

# 导出注册装饰器供策略使用
register_strategy = StrategyManager.register_strategy