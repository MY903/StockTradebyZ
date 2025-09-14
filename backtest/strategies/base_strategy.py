import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from backtest_utils import BacktestBase

class BaseStrategy(BacktestBase):
    """交易策略基础类"""
    def __init__(self, stock_code: str, data_dir: str = 'data', 
                 start_date: str = None, end_date: str = None, 
                 initial_cash: float = 100000, position_ratio: float = 0.5):
        super().__init__(stock_code, data_dir, start_date, end_date, initial_cash)
        self.position_ratio = position_ratio  # 仓位比例
        self.avg_cost = 0  # 新增：初始化平均成本
    
    @abstractmethod
    def calculate_indicators(self):
        """计算策略所需指标"""
        pass
    
    @abstractmethod
    def generate_signals(self):
        """生成交易信号"""
        pass

    def calculate_average_cost(self, new_quantity: int, new_price: float):
        """计算平均持仓成本"""
        if self.position == 0:
            # 如果当前没有持仓，平均成本就是新买入的价格
            self.avg_cost = new_price
            return new_price
        else:
            # 如果有持仓，计算加权平均成本
            total_cost_before = self.position * self.avg_cost  # 修改：直接使用self.avg_cost
            total_cost_new = new_quantity * new_price
            total_quantity = self.position + new_quantity
            
            # 保存新的平均成本
            self.avg_cost = (total_cost_before + total_cost_new) / total_quantity
            return self.avg_cost
    
    def backtest(self):
        """执行回测"""
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
        
        # 确保指标已计算
        self.generate_signals()
        
        # 遍历每一天的数据
        for index, row in self.data.iterrows():
            # 记录当前资产价值
            self.current_equity = self.calculate_equity(row['close'])
            self.equity_curve.append(self.current_equity)
            
            # 处理交易信号
            if row['signal'] == 1:
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
            elif row['signal'] == -1 and self.position > 0:
                # 卖出全部持仓
                sell_quantity = self.position
                
                # 计算交易成本
                total_cost, fee, stamp_duty = self.calculate_trading_cost(row['close'], sell_quantity, is_buy=False)
                
                # 计算收入
                revenue = sell_quantity * row['close']
                net_revenue = revenue - total_cost
                
                # 计算当前持仓市值和盈亏 - 修改：直接使用self.avg_cost
                position_profit = (row['close'] - self.avg_cost) * sell_quantity if self.position > 0 else 0
                
                # 记录交易
                self.trades.append({
                    'date': index,
                    'price': row['close'],
                    'quantity': sell_quantity,
                    'type': 'sell',
                    'cost': total_cost,
                    'stock_value': 0,
                    'total_asset': self.current_cash + net_revenue,
                    'position_profit': position_profit
                })
                
                # 更新持仓和现金
                self.position = 0
                self.current_cash += net_revenue
                # 卖出后重置平均成本
                self.avg_cost = 0

        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_equity': self.current_equity,
            'initial_equity': self.initial_cash,
            'return_rate': (self.current_equity - self.initial_cash) / self.initial_cash
        }