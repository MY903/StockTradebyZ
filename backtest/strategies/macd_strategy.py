from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册MACD策略
macd_metadata = StrategyMetadata(
    name='macd',
    display_name='单纯MACD动量策略',
    description='基于MACD动量指标的趋势策略',
    params_schema={}
)

@register_strategy(macd_metadata)
class MACDStrategy(BaseStrategy):
    """单纯MACD动量策略"""
    def calculate_indicators(self):
        """计算MACD指标"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 计算12日和26日指数移动平均线
        ema12 = self.data['close'].ewm(span=12, adjust=False).mean()
        ema26 = self.data['close'].ewm(span=26, adjust=False).mean()
        
        # 计算DIF（离差值）
        self.data['MACD_DIF'] = ema12 - ema26
        
        # 计算DEA（信号线）
        self.data['MACD_DEA'] = self.data['MACD_DIF'].ewm(span=9, adjust=False).mean()
        
        # 计算MACD柱状图
        self.data['MACD_BAR'] = 2 * (self.data['MACD_DIF'] - self.data['MACD_DEA'])
    
    def generate_signals(self):
        """基于MACD交叉和柱状图变化生成买卖信号"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 确保指标已计算
        if 'MACD_DIF' not in self.data.columns:
            self.calculate_indicators()
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入, -1: 卖出
        
        # 买入信号：MACD金叉（DIF上穿DEA）且MACD柱状图在0轴以上
        macd_gold_cross = (self.data['MACD_DIF'] > self.data['MACD_DEA']) & (self.data['MACD_DIF'].shift(1) <= self.data['MACD_DEA'].shift(1))
        macd_bar_positive = self.data['MACD_BAR'] > 0
        self.data.loc[macd_gold_cross & macd_bar_positive, 'signal'] = 1
        
        # 卖出信号：MACD死叉（DIF下穿DEA）或MACD柱状图在0轴以下
        macd_dead_cross = (self.data['MACD_DIF'] < self.data['MACD_DEA']) & (self.data['MACD_DIF'].shift(1) >= self.data['MACD_DEA'].shift(1))
        macd_bar_negative = self.data['MACD_BAR'] < 0
        self.data.loc[macd_dead_cross | macd_bar_negative, 'signal'] = -1