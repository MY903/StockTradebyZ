from strategy_manager import register_strategy, StrategyMetadata, StrategyManager
from .base_strategy import BaseStrategy  # 添加对BaseStrategy的导入
from typing import List, Dict, Any

# 注册组合策略
combined_metadata = StrategyMetadata(
    name='combined_strategy',
    display_name='组合策略',
    description='可自由组合多个策略的复合策略',
    params_schema={}
)

@register_strategy(combined_metadata)
class CombinedStrategy(BaseStrategy):
    """组合多个策略的策略类"""
    def __init__(self, stock_code, data_dir='data', start_date=None, end_date=None,
                 initial_cash=100000, position_ratio=0.5, selected_strategies: List[str] = None, strategy_params: Dict[str, Dict] = None):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash, position_ratio)
        
        # 初始化子策略列表
        self.selected_strategies = selected_strategies or ['basic_kdj']
        self.strategy_params = strategy_params or {}
        self.sub_strategies = []
        self.strategy_name = "组合策略"
    
    def initialize_sub_strategies(self):
        """初始化所有选择的子策略"""
        for strategy_name in self.selected_strategies:
            # 获取该策略的参数
            params = self.strategy_params.get(strategy_name, {})
            
            # 创建子策略实例
            sub_strategy = StrategyManager.create_strategy(
                name=strategy_name,
                stock_code=self.stock_code,
                data_dir=self.data_dir,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_cash=self.initial_cash,
                position_ratio=self.position_ratio,
                **params
            )
            
            # 共享数据对象，避免重复加载和计算
            if hasattr(sub_strategy, 'data'):
                sub_strategy.data = self.data
            if hasattr(sub_strategy, 'is_initialized'):
                sub_strategy.is_initialized = self.is_initialized
            
            self.sub_strategies.append((strategy_name, sub_strategy))
    
    def calculate_indicators(self):
        """计算所有子策略需要的指标"""
        # 初始化子策略
        if not self.sub_strategies:
            self.initialize_sub_strategies()
        
        # 计算每个子策略的特定指标
        for _, sub_strategy in self.sub_strategies:
            if hasattr(sub_strategy, 'calculate_indicators'):
                try:
                    sub_strategy.calculate_indicators()
                except:
                    pass  # 如果有指标已经被计算，可能会有异常，这里忽略
    
    def generate_signals(self):
        """基于所有子策略的信号生成最终信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if not self.sub_strategies:
            self.initialize_sub_strategies()
        
        # 初始化信号列和触发策略记录列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        self.data['trigger_strategies'] = ''  # 记录触发买卖的策略
        
        # 为每个子策略创建单独的信号列
        for strategy_name, sub_strategy in self.sub_strategies:
            # 为子策略生成信号
            sub_strategy.generate_signals()
            
            # 保存子策略的信号
            signal_col = f"signal_{strategy_name}"
            if hasattr(sub_strategy, 'data') and 'signal' in sub_strategy.data.columns:
                self.data[signal_col] = sub_strategy.data['signal']
        
        # 计算买入信号：所有选中的策略都确认买入信号
        buy_conditions = []
        for strategy_name, _ in self.sub_strategies:
            signal_col = f"signal_{strategy_name}"
            if signal_col in self.data.columns:
                buy_conditions.append(self.data[signal_col] == 1)
        
        # 如果有买入条件，将它们组合起来
        if buy_conditions:
            # 使用逻辑与来组合买入条件，表示所有选中的策略都确认买入信号
            combined_buy = buy_conditions[0]
            for cond in buy_conditions[1:]:
                combined_buy &= cond
            
            self.data.loc[combined_buy, 'signal'] = 1
            # 记录触发买入的策略
            trigger_strategies = ", ".join(self.selected_strategies)
            self.data.loc[combined_buy, 'trigger_strategies'] = trigger_strategies
        
        # 计算卖出信号：任一子策略发出卖出信号
        sell_conditions = []
        for strategy_name, _ in self.sub_strategies:
            signal_col = f"signal_{strategy_name}"
            if signal_col in self.data.columns:
                sell_conditions.append(self.data[signal_col] == -1)
        
        # 如果有卖出条件，将它们组合起来
        if sell_conditions:
            # 使用逻辑或来组合卖出条件，表示任一选中的策略发出卖出信号就执行卖出
            combined_sell = sell_conditions[0]
            for cond in sell_conditions[1:]:
                combined_sell |= cond
            
            self.data.loc[combined_sell, 'signal'] = -1
            # 记录触发卖出的策略
            for i, (strategy_name, _) in enumerate(self.sub_strategies):
                signal_col = f"signal_{strategy_name}"
                if signal_col in self.data.columns:
                    # 对于每个触发卖出的策略，更新trigger_strategies
                    mask = (self.data[signal_col] == -1) & (self.data['signal'] == -1)
                    existing_triggers = self.data.loc[mask, 'trigger_strategies']
                    self.data.loc[mask, 'trigger_strategies'] = existing_triggers.apply(
                        lambda x: f"{x}, {strategy_name}" if x else strategy_name
                    )
    
    def _generate_buy_reason(self, row):
        """生成组合策略的买入原因"""
        # 获取触发买入的策略
        trigger_strategies = row.get('trigger_strategies', '').split(', ')
        if not trigger_strategies or trigger_strategies == ['']:
            trigger_strategies = self.selected_strategies
            
        # 构建详细的买入原因
        reasons = []
        for strategy_name in trigger_strategies:
            # 查找对应的子策略实例
            sub_strategy = next((s for n, s in self.sub_strategies if n == strategy_name), None)
            if sub_strategy:
                # 获取子策略的参数
                params = self.strategy_params.get(strategy_name, {})
                params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                # 获取策略的显示名称
                try:
                    metadata = StrategyManager.get_strategy_metadata(strategy_name)
                    display_name = metadata.display_name
                except:
                    display_name = strategy_name
                
                reasons.append(f"{display_name} (参数: {params_str})")
        
        return f"组合策略买入信号：所有[{', '.join(reasons)}]策略均发出买入信号"
    
    def _generate_sell_reason(self, row):
        """生成组合策略的卖出原因"""
        # 获取触发卖出的策略
        trigger_strategies = row.get('trigger_strategies', '').split(', ')
        if not trigger_strategies or trigger_strategies == ['']:
            trigger_strategies = self.selected_strategies[:1]  # 默认取第一个策略
            
        # 构建详细的卖出原因
        reasons = []
        for strategy_name in trigger_strategies:
            # 查找对应的子策略实例
            sub_strategy = next((s for n, s in self.sub_strategies if n == strategy_name), None)
            if sub_strategy:
                # 获取子策略的参数
                params = self.strategy_params.get(strategy_name, {})
                params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                # 获取策略的显示名称
                try:
                    metadata = StrategyManager.get_strategy_metadata(strategy_name)
                    display_name = metadata.display_name
                except:
                    display_name = strategy_name
                
                reasons.append(f"{display_name} (参数: {params_str})")
        
        return f"组合策略卖出信号：[{', '.join(reasons)}]策略发出卖出信号"

# 为了向后兼容，保留原有的组合策略创建函数
def create_combined_strategy(selected_strategies, **kwargs):
    """创建组合策略实例"""
    # 提取每个策略的特定参数
    strategy_params = {}
    for strategy_name in selected_strategies:
        # 从kwargs中提取该策略的参数
        strategy_specific_params = {}
        for key, value in list(kwargs.items()):
            if key.startswith(f"{strategy_name}_"):
                # 去除策略名称前缀
                param_name = key[len(f"{strategy_name}_"):]
                strategy_specific_params[param_name] = value
                # 从kwargs中移除，避免传递给CombinedStrategy构造函数
                del kwargs[key]
        
        strategy_params[strategy_name] = strategy_specific_params
    
    # 创建组合策略实例
    return CombinedStrategy(
        selected_strategies=selected_strategies,
        strategy_params=strategy_params,
        **kwargs
    )