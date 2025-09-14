import pandas as pd
import numpy as np
import os
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class BacktestBase:
    """回测基础类"""
    def __init__(self, stock_code, data_dir='data', start_date=None, end_date=None, initial_cash=100000):
        self.stock_code = stock_code
        self.data_dir = data_dir
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.current_cash = initial_cash
        self.position = 0  # 当前持仓数量
        self.lot_size = 100  # 1手=100股
        self.trades = []  # 交易记录
        self.equity_curve = []  # 资产净值曲线
        self.current_equity = initial_cash
        self.is_initialized = False
        self.data = None
        
    def load_data(self):
        """加载股票数据"""
        # 这里应该有加载数据的逻辑
        # 由于没有实际的数据文件，这里提供一个简单的示例实现
        # 实际应用中，您需要根据自己的数据格式修改这部分代码
        
        # 尝试加载本地数据文件
        file_path = os.path.join(self.data_dir, f'{self.stock_code}.csv')
        
        if os.path.exists(file_path):
            # 加载本地CSV文件
            self.data = pd.read_csv(file_path)
            
            # 假设数据中有日期列，需要转换为datetime并设置为索引
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
                self.data.set_index('date', inplace=True)
            elif 'datetime' in self.data.columns:
                self.data['datetime'] = pd.to_datetime(self.data['datetime'])
                self.data.set_index('datetime', inplace=True)
            
            # 根据日期范围筛选数据
            if self.start_date:
                self.data = self.data[self.data.index >= pd.to_datetime(self.start_date)]
            if self.end_date:
                self.data = self.data[self.data.index <= pd.to_datetime(self.end_date)]
            
            self.is_initialized = True
        else:
            # 如果没有本地数据，创建一些模拟数据用于演示
            date_range = pd.date_range(start=pd.to_datetime(self.start_date) if self.start_date else '2023-01-01',
                                      end=pd.to_datetime(self.end_date) if self.end_date else '2025-01-01',
                                      freq='B')  # 工作日
            
            # 生成模拟的开盘价、收盘价、最高价、最低价和成交量
            np.random.seed(42)  # 设置随机种子，确保结果可复现
            close_prices = np.cumprod(1 + np.random.normal(0, 0.01, len(date_range))) * 100
            open_prices = close_prices * (1 + np.random.normal(0, 0.005, len(date_range)))
            high_prices = np.maximum(open_prices, close_prices) * (1 + np.random.normal(0, 0.005, len(date_range)))
            low_prices = np.minimum(open_prices, close_prices) * (1 - np.random.normal(0, 0.005, len(date_range)))
            volumes = np.abs(np.random.normal(1000000, 500000, len(date_range))).astype(int)
            
            # 创建DataFrame
            self.data = pd.DataFrame({
                'open': open_prices,
                'high': high_prices,
                'low': low_prices,
                'close': close_prices,
                'volume': volumes
            }, index=date_range)
            
            self.is_initialized = True
        
    def calculate_equity(self, current_price):
        """计算当前总资产价值"""
        stock_value = self.position * current_price
        return self.current_cash + stock_value
    
    def calculate_trading_cost(self, price, quantity, is_buy=True):
        """计算交易成本"""
        # 佣金率：0.03%
        commission_rate = 0.0003
        # 印花税：卖出时收取0.1%
        stamp_duty_rate = 0.001 if not is_buy else 0
        # 过户费：0.002%（仅沪市股票收取，这里简化处理）
        transfer_fee_rate = 0.00002
        # 最低佣金：5元
        min_commission = 5
        
        # 计算佣金
        commission = max(price * quantity * commission_rate, min_commission)
        # 计算印花税
        stamp_duty = price * quantity * stamp_duty_rate
        # 计算过户费
        transfer_fee = price * quantity * transfer_fee_rate
        # 总交易成本
        total_cost = commission + stamp_duty + transfer_fee
        
        return total_cost, commission, stamp_duty
    
    def calculate_performance_metrics(self):
        """计算绩效指标"""
        if not self.equity_curve:
            return {}
        
        # 计算最终资金
        final_cash = self.current_cash
        # 计算总收益率
        total_return = (final_cash - self.initial_cash) / self.initial_cash
        # 计算最大回撤
        rolling_max = pd.Series(self.equity_curve).cummax()
        drawdown = (pd.Series(self.equity_curve) - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        # 计算胜率
        if self.trades:
            win_trades = [trade for trade in self.trades if trade['type'] == 'sell' and trade.get('position_profit', 0) > 0]
            win_rate = len(win_trades) / len([trade for trade in self.trades if trade['type'] == 'sell']) if [trade for trade in self.trades if trade['type'] == 'sell'] else 0
        else:
            win_rate = 0
        
        return {
            'initial_cash': self.initial_cash,
            'final_cash': final_cash,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': len(self.trades)
        }
    
    def get_trade_summary(self):
        """获取交易记录摘要"""
        if not self.trades:
            return pd.DataFrame()
        
        # 将交易记录转换为DataFrame
        trade_df = pd.DataFrame(self.trades)
        
        # 格式化日期
        if 'date' in trade_df.columns:
            trade_df['date'] = pd.to_datetime(trade_df['date']).dt.strftime('%Y-%m-%d')
        
        # 重排序列
        columns = ['date', 'type', 'price', 'quantity', 'cost', 'stock_value', 'total_asset', 'position_profit']
        trade_df = trade_df.reindex(columns=columns)
        
        return trade_df

class PlotlyVisualizer:
    """Plotly可视化工具类"""
    @staticmethod
    def plot_backtest_results(backtest_instance):
        """绘制回测结果图表"""
        if not backtest_instance.is_initialized:
            raise ValueError("请先加载数据")
        
        # 创建子图（根据策略类型动态调整子图数量）
        # 基础KDJ策略：3个子图
        # 其他策略：可能需要额外子图显示组合指标
        row_count = 3  # 默认3个子图
        
        # 检查是否需要额外的子图
        if hasattr(backtest_instance, 'strategy_name') and backtest_instance.strategy_name in ['kdj_sma20', 'kdj_volume']:
            row_count = 4
        elif hasattr(backtest_instance, 'strategy_name') and backtest_instance.strategy_name in ['kdj_macd', 'kdj_divergence']:
            row_count = 4
        
        fig = make_subplots(
            rows=row_count, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(
                f'{backtest_instance.stock_code} 股价与买卖点',
                'KDJ指标',
                '资产净值曲线',
                '组合指标' if row_count > 3 else None
            )[:row_count],  # 移除None值
            row_heights=[0.4, 0.2, 0.2, 0.2] if row_count > 3 else [0.4, 0.3, 0.3]
        )
        
        # 获取日期字符串格式
        dates = backtest_instance.data.index.strftime('%Y-%m-%d')
        
        # 子图1：绘制K线和买卖点
        # 添加蜡烛图
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=backtest_instance.data['open'],
                high=backtest_instance.data['high'],
                low=backtest_instance.data['low'],
                close=backtest_instance.data['close'],
                name='K线'
            ),
            row=1, col=1
        )
        
        # 添加20日均线（如果存在）
        if 'MA20' in backtest_instance.data.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=backtest_instance.data['MA20'],
                    mode='lines',
                    line=dict(color='purple', width=1.5),
                    name='20日均线'
                ),
                row=1, col=1
            )
        
        # 标记买卖点
        buy_signals = [trade for trade in backtest_instance.trades if trade['type'] == 'buy']
        sell_signals = [trade for trade in backtest_instance.trades if trade['type'] == 'sell']
        
        if buy_signals:
            buy_dates = [trade['date'].strftime('%Y-%m-%d') for trade in buy_signals]
            buy_prices = [trade['price'] for trade in buy_signals]
            fig.add_trace(
                go.Scatter(
                    x=buy_dates,
                    y=buy_prices,
                    mode='markers',
                    marker=dict(
                        color='green',
                        size=10,
                        symbol='triangle-up'
                    ),
                    name='买入信号'
                ),
                row=1, col=1
            )
        
        if sell_signals:
            sell_dates = [trade['date'].strftime('%Y-%m-%d') for trade in sell_signals]
            sell_prices = [trade['price'] for trade in sell_signals]
            fig.add_trace(
                go.Scatter(
                    x=sell_dates,
                    y=sell_prices,
                    mode='markers',
                    marker=dict(
                        color='red',
                        size=10,
                        symbol='triangle-down'
                    ),
                    name='卖出信号'
                ),
                row=1, col=1
            )
        
        # 子图2：绘制KDJ指标
        # 根据不同策略选择合适的KDJ列名
        k_col, d_col, j_col = 'K', 'D', 'J'  # 默认列名
        
        # 检查是否存在多周期KDJ
        if 'K_daily' in backtest_instance.data.columns:
            k_col, d_col, j_col = 'K_daily', 'D_daily', 'J_daily'
        
        if k_col in backtest_instance.data.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=backtest_instance.data[k_col],
                    mode='lines',
                    line=dict(color='blue', width=1.5),
                    name='K线'
                ),
                row=2, col=1
            )
        
        if d_col in backtest_instance.data.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=backtest_instance.data[d_col],
                    mode='lines',
                    line=dict(color='orange', width=1.5),
                    name='D线'
                ),
                row=2, col=1
            )
        
        if j_col in backtest_instance.data.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=backtest_instance.data[j_col],
                    mode='lines',
                    line=dict(color='green', width=1.5),
                    name='J线'
                ),
                row=2, col=1
            )
        
        # 添加KDJ参考线（20和80）
        fig.add_hline(y=20, line_dash="dash", line_color="gray", row=2, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="gray", row=2, col=1)
        
        # 子图3：绘制资产净值曲线
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=backtest_instance.equity_curve,
                mode='lines',
                line=dict(color='black', width=2),
                name='资产净值'
            ),
            row=3, col=1
        )
        
        # 子图4：绘制组合指标（如果有）
        if row_count > 3:
            # 根据不同策略显示不同的组合指标
            if 'MA_V5' in backtest_instance.data.columns and 'volume' in backtest_instance.data.columns:
                # 成交量相关指标
                fig.add_trace(
                    go.Bar(
                        x=dates,
                        y=backtest_instance.data['volume'],
                        name='成交量'
                    ),
                    row=4, col=1
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=backtest_instance.data['MA_V5'],
                        mode='lines',
                        line=dict(color='red', width=1.5),
                        name='5日均量'
                    ),
                    row=4, col=1
                )
            elif 'MACD_DIF' in backtest_instance.data.columns:
                # MACD指标
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=backtest_instance.data['MACD_DIF'],
                        mode='lines',
                        line=dict(color='blue', width=1.5),
                        name='MACD DIF'
                    ),
                    row=4, col=1
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=backtest_instance.data['MACD_DEA'],
                        mode='lines',
                        line=dict(color='orange', width=1.5),
                        name='MACD DEA'
                    ),
                    row=4, col=1
                )
                
                # MACD柱状图
                fig.add_trace(
                    go.Bar(
                        x=dates,
                        y=backtest_instance.data['MACD_BAR'],
                        name='MACD BAR',
                        marker_color=['green' if x > 0 else 'red' for x in backtest_instance.data['MACD_BAR']]
                    ),
                    row=4, col=1
                )
            elif 'CCI' in backtest_instance.data.columns:
                # CCI指标
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=backtest_instance.data['CCI'],
                        mode='lines',
                        line=dict(color='purple', width=1.5),
                        name='CCI'
                    ),
                    row=4, col=1
                )
                
                # 添加CCI参考线
                fig.add_hline(y=100, line_dash="dash", line_color="gray", row=4, col=1)
                fig.add_hline(y=-100, line_dash="dash", line_color="gray", row=4, col=1)
        
        # 获取策略名称（如果有）
        strategy_name = getattr(backtest_instance, 'strategy_name', 'strategy')
        
        # 更新布局
        fig.update_layout(
            height=900 if row_count > 3 else 700,
            margin=dict(l=50, r=50, t=100, b=50),
            title={
                'text': f'{backtest_instance.stock_code} 策略回测结果',
                'font': {
                    'size': 24,
                    'family': 'SimHei, Microsoft YaHei, SimSun'
                },
                'x': 0.5,
                'xanchor': 'center'
            },
            font={
                'family': 'SimHei, Microsoft YaHei, SimSun',
                'size': 12
            },
            hovermode='x unified',
            legend={
                'orientation': 'h',
                'yanchor': 'bottom',
                'y': 1.02,
                'xanchor': 'right',
                'x': 1
            }
        )
        
        # 更新坐标轴设置
        fig.update_xaxes(
            rangeslider_visible=False,
            showticklabels=True,
            tickformat='%Y-%m-%d'
        )
        
        # 保存图表
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = f'results/{backtest_instance.stock_code}_{strategy_name}_{current_time}.html'
        png_file = f'results/{backtest_instance.stock_code}_{strategy_name}_{current_time}.png'
        
        # 确保results目录存在
        os.makedirs('results', exist_ok=True)
        
        # 保存为HTML文件
        fig.write_html(html_file)
        
        # 保存为PNG文件
        fig.write_image(png_file)
        
        return fig  # 只返回figure对象，不再返回文件路径