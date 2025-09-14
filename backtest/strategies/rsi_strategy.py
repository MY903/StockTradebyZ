import pandas as pd
from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册RSI策略
rsi_metadata = StrategyMetadata(
    name='rsi',
    display_name='单纯RSI相对强弱策略',
    description='基于RSI超买超卖指标的策略',
    params_schema={
        'rsi_period': {'type': 'int', 'default': 14, 'min': 6, 'max': 24, 'step': 2},
        'oversold_threshold': {'type': 'int', 'default': 30, 'min': 10, 'max': 40, 'step': 5},
        'overbought_threshold': {'type': 'int', 'default': 70, 'min': 60, 'max': 90, 'step': 5}
    }
)

@register_strategy(rsi_metadata)
class RSIStrategy(BaseStrategy):
    """单纯RSI相对强弱策略"""
    def __init__(self, stock_code, data_dir='data', start_date=None, end_date=None,
                 initial_cash=100000, position_ratio=0.5, rsi_period=14, oversold_threshold=30, overbought_threshold=70):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash, position_ratio)
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
    
    def calculate_indicators(self):
        """计算RSI指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算价格变化
        delta = self.data['close'].diff()
        
        # 分离上涨和下跌的变化
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        # 计算RS和RSI
        rs = gain / loss
        self.data['RSI'] = 100 - (100 / (1 + rs))
        
        # 填充NaN值
        self.data.fillna(0, inplace=True)
    
    def generate_signals(self):
        """基于RSI超买超卖和背离生成买卖信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if 'RSI' not in self.data.columns:
            self.calculate_indicators()
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        
        # 买入信号：RSI下穿超卖阈值后回升
        oversold_recovery = (self.data['RSI'] > self.oversold_threshold) & (self.data['RSI'].shift(1) <= self.oversold_threshold)
        self.data.loc[oversold_recovery, 'signal'] = 1
        
        # 卖出信号：RSI上穿超买阈值后回落
        overbought_recovery = (self.data['RSI'] < self.overbought_threshold) & (self.data['RSI'].shift(1) >= self.overbought_threshold)
        self.data.loc[overbought_recovery, 'signal'] = -1