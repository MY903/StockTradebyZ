import pandas as pd
from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册成交量策略
volume_metadata = StrategyMetadata(
    name='volume',
    display_name='单纯成交量策略',
    description='基于成交量变化的量价策略',
    params_schema={
        'volume_factor': {'type': 'float', 'default': 1.5, 'min': 1.0, 'max': 3.0, 'step': 0.1}
    }
)

@register_strategy(volume_metadata)
class VolumeStrategy(BaseStrategy):
    """单纯成交量策略"""
    def __init__(self, stock_code, data_dir='data', start_date=None, end_date=None,
                 initial_cash=100000, position_ratio=0.5, volume_factor=1.5):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash, position_ratio)
        self.volume_factor = volume_factor  # 成交量放大倍数
    
    def calculate_indicators(self):
        """计算成交量相关指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算5日均量和10日均量
        self.data['MA_V5'] = self.data['volume'].rolling(window=5).mean()
        self.data['MA_V10'] = self.data['volume'].rolling(window=10).mean()
        
        # 判断是否放量
        self.data['is_volume_expanding'] = self.data['volume'] / self.data['MA_V5'] > self.volume_factor
    
    def generate_signals(self):
        """基于成交量变化生成买卖信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if 'is_volume_expanding' not in self.data.columns:
            self.calculate_indicators()
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        
        # 买入信号：成交量显著放大且价格上涨
        price_rise = self.data['close'] > self.data['open']
        self.data.loc[self.data['is_volume_expanding'] & price_rise, 'signal'] = 1
        
        # 卖出信号：成交量萎缩且价格下跌，或成交量异常放大（警惕顶部）
        volume_contraction = self.data['volume'] / self.data['MA_V5'] < 0.5
        price_fall = self.data['close'] < self.data['open']
        extreme_volume = self.data['volume'] / self.data['MA_V10'] > 3.0
        self.data.loc[(volume_contraction & price_fall) | extreme_volume, 'signal'] = -1