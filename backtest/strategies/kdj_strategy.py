import numpy as np
from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册KDJ基础策略
kdj_metadata = StrategyMetadata(
    name='basic_kdj',
    display_name='基础KDJ策略',
    description='基于KDJ指标金叉死叉的基础策略',
    params_schema={}
)

@register_strategy(kdj_metadata)
class KDJStrategy(BaseStrategy):
    """KDJ策略回测类"""
    def calculate_kdj(self, n=9, m1=3, m2=3):
        """计算KDJ指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算RSV
        low_n = self.data['low'].rolling(window=n).min()
        high_n = self.data['high'].rolling(window=n).max()
        rsv = (self.data['close'] - low_n) / (high_n - low_n) * 100
        
        # 计算K和D
        self.data['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
        self.data['D'] = self.data['K'].ewm(alpha=1/m2, adjust=False).mean()
        
        # 计算J
        self.data['J'] = 3 * self.data['K'] - 2 * self.data['D']
        
        # 填充NaN值
        self.data.fillna(0, inplace=True)
        
    def calculate_indicators(self):
        """计算KDJ指标"""
        self.calculate_kdj()
    
    def generate_signals(self):
        """基于KDJ交叉生成买卖信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if 'K' not in self.data.columns:
            self.calculate_indicators()
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        
        # K线上穿D线，买入信号
        self.data.loc[(self.data['K'] > self.data['D']) & (self.data['K'].shift(1) <= self.data['D'].shift(1)), 'signal'] = 1
        
        # K线下穿D线，卖出信号
        self.data.loc[(self.data['K'] < self.data['D']) & (self.data['K'].shift(1) >= self.data['D'].shift(1)), 'signal'] = -1