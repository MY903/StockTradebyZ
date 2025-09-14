import numpy as np
from .base_strategy import BaseStrategy
from strategy_manager import register_strategy, StrategyMetadata

# 注册短线止损策略
stop_loss_metadata = StrategyMetadata(
    name='short_term_stop_loss',
    display_name='短线通用止损策略',
    description='包含固定止损（买入价下方3%-5%）和时间止损（3个交易日未涨1%）的通用止损策略',
    params_schema={
        'stop_loss_pct': {
            'type': 'number',
            'default': 0.04,
            'min': 0.03,
            'max': 0.05,
            'step': 0.005,
            'description': '止损百分比（3%-5%）'
        },
        'days_threshold': {
            'type': 'integer',
            'default': 3,
            'description': '时间止损的交易天数阈值'
        },
        'min_profit_pct': {
            'type': 'number',
            'default': 0.01,
            'description': '最小盈利百分比要求'
        }
    }
)

@register_strategy(stop_loss_metadata)
class StopLossStrategy(BaseStrategy):
    """短线通用止损策略实现"""
    def __init__(self, stock_code: str, data_dir: str = 'data', 
                 start_date: str = None, end_date: str = None, 
                 initial_cash: float = 100000, position_ratio: float = 0.5,
                 stop_loss_pct: float = 0.04, days_threshold: int = 3,
                 min_profit_pct: float = 0.01):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash, position_ratio)
        self.stop_loss_pct = stop_loss_pct  # 止损百分比（3%-5%）
        self.days_threshold = days_threshold  # 时间止损天数
        self.min_profit_pct = min_profit_pct  # 最小盈利要求
        self.buy_date = None  # 买入日期
        self.buy_price = 0  # 买入价格
        self.holding_days = 0  # 持有天数
        self.strategy_name = 'short_term_stop_loss'  # 策略名称，用于图表显示
    
    def calculate_indicators(self):
        """计算策略所需指标"""
        # 该策略不需要额外指标计算
        pass
    
    def generate_signals(self):
        """生成交易信号（仅包含买入信号，卖出信号在backtest方法中根据止损条件生成）"""
        if not self.is_initialized:
            raise ValueError("请先加载数据")
        
        # 初始化信号列
        self.data['signal'] = 0  # 0: 无操作, 1: 买入
        
        # 这里可以添加简单的买入条件，或者该策略可以作为其他策略的补充
        # 示例：当价格低于5日移动平均线时买入
        self.data['ma5'] = self.data['close'].rolling(window=5).mean()
        self.data.loc[self.data['close'] > self.data['ma5'], 'signal'] = 1
        
        # 填充NaN值
        self.data.fillna(0, inplace=True)
    
    def backtest(self):
        """执行回测，包含固定止损和时间止损逻辑"""
        if not self.is_initialized:
            self.load_data()
            self.is_initialized = True
        
        # 重置回测参数
        self.trades = []
        self.current_cash = self.initial_cash
        self.position = 0
        self.equity_curve = []
        self.current_equity = self.initial_cash
        self.avg_cost = 0  # 重置平均成本
        self.buy_date = None
        self.buy_price = 0
        self.holding_days = 0
        
        # 确保指标已计算
        self.generate_signals()
        
        # 遍历每一天的数据
        for index, row in self.data.iterrows():
            # 记录当前资产价值
            self.current_equity = self.calculate_equity(row['close'])
            self.equity_curve.append(self.current_equity)
            
            # 如果持有仓位，更新持有天数和检查止损条件
            if self.position > 0:
                self.holding_days += 1
                
                # 计算当前价格相对于买入价的涨幅
                price_change_pct = (row['close'] - self.buy_price) / self.buy_price
                
                # 1. 固定止损条件：价格低于买入价的(1-止损百分比)
                stop_loss_price = self.buy_price * (1 - self.stop_loss_pct)
                stop_loss_condition = row['close'] <= stop_loss_price
                
                # 2. 时间止损条件：持有超过指定天数且涨幅未达到最小盈利要求
                time_stop_condition = self.holding_days >= self.days_threshold and price_change_pct < self.min_profit_pct
                
                # 如果触发任何一个止损条件，卖出全部持仓
                if stop_loss_condition or time_stop_condition:
                    # 记录卖出原因
                    sell_reason = "固定止损" if stop_loss_condition else "时间止损"
                    
                    # 计算交易成本
                    total_cost, fee, stamp_duty = self.calculate_trading_cost(row['close'], self.position, is_buy=False)
                    
                    # 计算收入
                    revenue = self.position * row['close']
                    net_revenue = revenue - total_cost
                    
                    # 计算持仓盈亏
                    position_profit = (row['close'] - self.avg_cost) * self.position if self.position > 0 else 0
                    
                    # 记录交易
                    trade_record = {
                        'date': index,
                        'price': row['close'],
                        'quantity': self.position,
                        'type': 'sell',
                        'cost': total_cost,
                        'stock_value': 0,
                        'total_asset': self.current_cash + net_revenue,
                        'position_profit': position_profit,
                        'sell_reason': sell_reason  # 添加卖出原因
                    }
                    self.trades.append(trade_record)
                    
                    # 更新持仓和现金
                    self.position = 0
                    self.current_cash += net_revenue
                    self.avg_cost = 0
                    self.buy_date = None
                    self.buy_price = 0
                    self.holding_days = 0
            
            # 处理买入信号
            elif row['signal'] == 1:
                # 计算最大可买入金额（使用现金的指定比例）
                max_buy_amount = self.current_cash * self.position_ratio
                
                # 计算可买入的手数（向下取整）
                buy_amount_per_lot = row['close'] * self.lot_size
                max_buy_lots = int(max_buy_amount / buy_amount_per_lot)
                
                if max_buy_lots > 0:
                    buy_quantity = max_buy_lots * self.lot_size
                    
                    # 计算交易成本
                    total_cost, fee, stamp_duty = self.calculate_trading_cost(row['close'], buy_quantity, is_buy=True)
                    
                    # 检查资金是否足够（包括费用）
                    total_required = buy_quantity * row['close'] + total_cost
                    if total_required <= self.current_cash:
                        # 计算当前持仓市值和盈亏
                        stock_value = (self.position + buy_quantity) * row['close']
                        avg_cost = self.calculate_average_cost(buy_quantity, row['close'])
                        position_profit = (row['close'] - avg_cost) * (self.position + buy_quantity)
                        
                        # 记录交易
                        self.trades.append({
                            'date': index,
                            'price': row['close'],
                            'quantity': buy_quantity,
                            'type': 'buy',
                            'cost': total_cost,
                            'stock_value': stock_value,
                            'total_asset': self.current_cash - total_required + stock_value,
                            'position_profit': position_profit
                        })
                        
                        # 更新持仓和现金
                        self.position += buy_quantity
                        self.current_cash -= total_required
                        
                        # 记录买入信息用于止损判断
                        self.buy_date = index
                        self.buy_price = row['close']
                        self.holding_days = 0
        
        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_equity': self.current_equity,
            'initial_equity': self.initial_cash,
            'return_rate': (self.current_equity - self.initial_cash) / self.initial_cash
        }