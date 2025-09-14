import numpy as np
from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册KDJ基础策略
kdj_metadata = StrategyMetadata(
    name='basic_kdj',
    display_name='基础KDJ策略',
    description='基于KDJ指标金叉死叉的基础策略',
    params_schema={
        'n': {'type': 'int', 'default': 9, 'min': 1, 'max': 30, 'description': 'KDJ计算周期'},
        'm1': {'type': 'int', 'default': 3, 'min': 1, 'max': 10, 'description': 'K值平滑系数'},
        'm2': {'type': 'int', 'default': 3, 'min': 1, 'max': 10, 'description': 'D值平滑系数'}
    }
)

@register_strategy(kdj_metadata)
class KDJStrategy(BaseStrategy):
    """KDJ策略回测类"""
    def __init__(self, stock_code: str, data_dir: str = 'data', 
                 start_date: str = None, end_date: str = None, 
                 initial_cash: float = 100000, position_ratio: float = 0.5, 
                 n: int = 9, m1: int = 3, m2: int = 3):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash, position_ratio)
        self.strategy_name = "KDJ策略"
        self.strategy_params = {'n': n, 'm1': m1, 'm2': m2}
        self.n = n
        self.m1 = m1
        self.m2 = m2
    
    def calculate_kdj(self):
        """计算KDJ指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算RSV
        low_n = self.data['low'].rolling(window=self.n).min()
        high_n = self.data['high'].rolling(window=self.n).max()
        rsv = (self.data['close'] - low_n) / (high_n - low_n) * 100
        
        # 计算K和D
        self.data['K'] = rsv.ewm(alpha=1/self.m1, adjust=False).mean()
        self.data['D'] = self.data['K'].ewm(alpha=1/self.m2, adjust=False).mean()
        
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
        
    def _generate_buy_reason(self, row):
        """生成KDJ策略的买入原因"""
        params_str = ", ".join([f"{k}={v}" for k, v in self.strategy_params.items()])
        current_k = row['K']
        current_d = row['D']
        prev_k = self.data['K'].shift(1).loc[row.name] if row.name in self.data.index[1:] else 0
        prev_d = self.data['D'].shift(1).loc[row.name] if row.name in self.data.index[1:] else 0
        return f"KDJ策略买入信号 (参数: {params_str})：K({current_k:.2f})上穿D({current_d:.2f})"
    
    def _generate_sell_reason(self, row):
        """生成KDJ策略的卖出原因"""
        params_str = ", ".join([f"{k}={v}" for k, v in self.strategy_params.items()])
        current_k = row['K']
        current_d = row['D']
        prev_k = self.data['K'].shift(1).loc[row.name] if row.name in self.data.index[1:] else 0
        prev_d = self.data['D'].shift(1).loc[row.name] if row.name in self.data.index[1:] else 0
        return f"KDJ策略卖出信号 (参数: {params_str})：K({current_k:.2f})下穿D({current_d:.2f})"