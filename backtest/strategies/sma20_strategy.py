from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册20日均线策略
sma20_metadata = StrategyMetadata(
    name='sma20',
    display_name='单纯20日均线策略',
    description='基于20日均线的趋势跟踪策略',
    params_schema={}
)

@register_strategy(sma20_metadata)
class SMA20Strategy(BaseStrategy):
    """单纯20日均线策略"""
    def calculate_indicators(self):
        """计算20日均线指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算20日均线
        self.data['MA20'] = self.data['close'].rolling(window=20).mean()
        
        # 判断均线趋势
        self.data['ma20_slope'] = self.data['MA20'].diff()
    
    def generate_signals(self):
        """基于20日均线生成买卖信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if 'MA20' not in self.data.columns:
            self.calculate_indicators()
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        
        # 买入信号：价格上穿20日均线且均线向上
        price_above_ma = (self.data['close'] > self.data['MA20']) & (self.data['close'].shift(1) <= self.data['MA20'].shift(1))
        ma_upward = self.data['ma20_slope'] > 0
        self.data.loc[price_above_ma & ma_upward, 'signal'] = 1
        
        # 卖出信号：价格下穿20日均线或均线向下
        price_below_ma = (self.data['close'] < self.data['MA20']) & (self.data['close'].shift(1) >= self.data['MA20'].shift(1))
        ma_downward = self.data['ma20_slope'] < 0
        self.data.loc[price_below_ma | ma_downward, 'signal'] = -1