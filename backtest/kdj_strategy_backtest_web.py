from datetime import datetime
from backtest_utils import PlotlyVisualizer
from strategy_manager import StrategyManager
from strategies.combined_strategy import create_combined_strategy
import os
import pandas as pd
import streamlit as st

# 设置页面配置，增加宽度
st.set_page_config(page_title="股票回测系统", layout="wide")

# 确保中文显示正常
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["SimHei", "Alibaba Sans", "Microsoft YaHei UI", "SimSun"]

# 加载所有策略
StrategyManager.load_strategies_from_directory('strategies')

# 创建应用标题
st.title('股票策略回测工具')

# 创建用户输入界面
with st.sidebar:
    st.header('回测参数设置')
    
    # 添加策略选择模式
    strategy_mode = st.radio(
        '策略选择模式',
        options=['单一策略', '组合策略']
    )
    
    # 获取所有可用策略
    strategies_info = StrategyManager.list_strategies_with_metadata()
    
    if strategy_mode == '单一策略':
        # 单一策略选择界面
        strategy_name = st.selectbox(
            '选择回测策略',
            options=list(strategies_info.keys()),
            format_func=lambda x: strategies_info[x]['display_name']
        )
        
        # 根据选择的策略显示特定参数
        strategy_params = {}
        strategy_metadata = StrategyManager.get_strategy_metadata(strategy_name)
        
        # 显示策略描述
        st.markdown(f"**策略描述**：{strategy_metadata.description}")
        
        # 动态生成参数输入界面
        for param_name, param_schema in strategy_metadata.params_schema.items():
            param_type = param_schema.get('type', 'float')
            param_default = param_schema.get('default', 0)
            param_min = param_schema.get('min', 0)
            param_max = param_schema.get('max', 100)
            param_step = param_schema.get('step', 0.1)
            param_key = f"{strategy_name}_{param_name}"
            
            if param_type == 'float':
                value = st.slider(
                    f'{param_name}',
                    min_value=param_min,
                    max_value=param_max,
                    value=param_default,
                    step=param_step,
                    key=param_key
                )
            elif param_type == 'int':
                # 将步长值转换为整数类型，确保类型匹配
                int_step = int(param_step) if param_step >= 1 else 1
                value = st.slider(
                    f'{param_name}',
                    min_value=param_min,
                    max_value=param_max,
                    value=param_default,
                    step=int_step,
                    format="%d",
                    key=param_key
                )
            else:
                value = st.text_input(f'{param_name}', value=str(param_default))
            
            strategy_params[param_name] = value
    
    elif strategy_mode == '组合策略':
        # 组合策略选择界面
        st.markdown('### 选择要组合的策略')
        
        # 让用户选择多个策略
        selected_strategies = st.multiselect(
            '选择策略',
            options=list(strategies_info.keys()),
            format_func=lambda x: strategies_info[x]['display_name']
        )
        
        # 为每个选中的策略显示其参数设置
        strategy_params = {}
        if selected_strategies:
            for strategy_name in selected_strategies:
                st.markdown(f"#### {strategies_info[strategy_name]['display_name']} 参数")
                st.markdown(f"{strategies_info[strategy_name]['description']}")
                
                # 获取该策略的参数 schema
                strategy_metadata = StrategyManager.get_strategy_metadata(strategy_name)
                
                # 为每个参数创建输入框，参数名加上策略前缀
                for param_name, param_schema in strategy_metadata.params_schema.items():
                    param_type = param_schema.get('type', 'float')
                    param_default = param_schema.get('default', 0)
                    param_min = param_schema.get('min', 0)
                    param_max = param_schema.get('max', 100)
                    param_step = param_schema.get('step', 0.1)
                    param_key = f"{strategy_name}_{param_name}"
                    
                    if param_type == 'float':
                        value = st.slider(
                            f'{param_name}',
                            min_value=param_min,
                            max_value=param_max,
                            value=param_default,
                            step=param_step,
                            key=param_key
                        )
                    elif param_type == 'int':
                        # 将步长值转换为整数类型，确保类型匹配
                        int_step = int(param_step) if param_step >= 1 else 1
                        value = st.slider(
                            f'{param_name}',
                            min_value=param_min,
                            max_value=param_max,
                            value=param_default,
                            step=int_step,
                            format="%d",
                            key=param_key
                        )
                    else:
                        value = st.text_input(f'{param_name}', value=str(param_default), key=param_key)
                    
                    strategy_params[param_key] = value
    
    # 股票代码输入
    stock_code = st.text_input('股票代码', '600000')
    
    # 日期范围选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input('开始日期', datetime(2020, 1, 1))
    with col2:
        end_date = st.date_input('结束日期', datetime(2023, 12, 31))
    
    # 初始资金和仓位比例
    initial_cash = st.number_input('初始资金', min_value=10000, max_value=1000000, value=100000, step=10000)
    position_ratio = st.slider('买入仓位比例', min_value=0.1, max_value=1.0, value=0.5, step=0.1)
    sell_ratio = st.slider('卖出仓位比例', min_value=0.1, max_value=1.0, value=1.0, step=0.1)
    
    # 回测按钮
    run_backtest = st.button('运行回测')

# 回测逻辑
if run_backtest:
    try:
        # 创建策略实例
        if strategy_mode == '单一策略':
            # 创建单一策略
            strategy = StrategyManager.create_strategy(
                name=strategy_name,
                stock_code=stock_code,
                start_date=str(start_date),
                end_date=str(end_date),
                initial_cash=initial_cash,
                position_ratio=position_ratio,
                sell_ratio=sell_ratio,
                **strategy_params
            )
        else:
            # 创建组合策略
            strategy = create_combined_strategy(
                selected_strategies=selected_strategies,
                stock_code=stock_code,
                start_date=str(start_date),
                end_date=str(end_date),
                initial_cash=initial_cash,
                position_ratio=position_ratio,
                sell_ratio=sell_ratio,
                **strategy_params
            )
        
        # 模拟加载数据（实际应用中需要实现真实的数据加载逻辑）
        # 这里仅作为示例
        def mock_load_data():
            # 创建模拟数据
            dates = pd.date_range(start=start_date, end=end_date, freq='B')
            n = len(dates)
            
            # 生成随机价格数据
            np.random.seed(42)  # 设置随机种子，使结果可复现
            price_changes = np.random.normal(0, 0.02, n)  # 每日价格变化率
            base_price = 10.0
            prices = [base_price]
            for change in price_changes[1:]:
                new_price = prices[-1] * (1 + change)
                prices.append(new_price)
            
            # 创建DataFrame
            data = pd.DataFrame({
                'open': prices,
                'high': [p * (1 + np.random.uniform(0, 0.03)) for p in prices],
                'low': [p * (1 - np.random.uniform(0, 0.03)) for p in prices],
                'close': prices,
                'volume': np.random.randint(1000000, 5000000, n)
            }, index=dates)
            
            return data
        
        # 为策略设置模拟数据
        if hasattr(strategy, 'load_data'):
            # 尝试调用实际的load_data方法
            try:
                strategy.load_data()
            except:
                # 如果失败，使用模拟数据
                strategy.data = mock_load_data()
                strategy.is_initialized = True
        else:
            # 直接设置模拟数据
            strategy.data = mock_load_data()
            strategy.is_initialized = True
        
        # 执行回测
        backtest_result = strategy.backtest()
        
        # 显示回测结果
        st.header('回测结果')
        
        # 计算绩效指标
        initial_equity = backtest_result['initial_equity']
        final_equity = backtest_result['final_equity']
        return_rate = backtest_result['return_rate'] * 100  # 转换为百分比
        
        # 计算最大回撤（简化计算）
        equity_curve = backtest_result['equity_curve']
        max_equity = max(equity_curve)
        drawdown = (max_equity - min(equity_curve)) / max_equity * 100 if max_equity > 0 else 0
        
        # 计算交易次数
        trades = backtest_result['trades']
        trade_count = len(trades)
        sell_trades = [t for t in trades if t['type'] == 'sell']
        win_count = len([t for t in sell_trades if t['position_profit'] > 0])
        win_rate = (win_count / len(sell_trades) * 100) if sell_trades else 0
        
        # 计算总交易成本
        total_trading_cost = sum(t['cost'] for t in trades) if trades else 0
        
        # 显示绩效指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('初始资金', f'{initial_equity:.2f}')
            st.metric('最终资金', f'{final_equity:.2f}')
        with col2:
            st.metric('收益率', f'{return_rate:.2f}%')
            st.metric('最大回撤', f'{drawdown:.2f}%')
        with col3:
            st.metric('交易次数', trade_count)
            st.metric('胜率', f'{win_rate:.2f}%')
            # 添加总交易成本指标
            st.metric('总交易成本', f'{total_trading_cost:.2f}元')

        # 绘制回测结果图表
        st.subheader('资产曲线')
        try:
            # 尝试使用PlotlyVisualizer
            visualizer = PlotlyVisualizer()
            fig = visualizer.plot_backtest_results(strategy)
            st.plotly_chart(fig, use_container_width=True)
        except:
            # 如果失败，使用简单的Matplotlib图表
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(strategy.data.index, equity_curve)
            ax.set_title('资产曲线')
            ax.set_xlabel('日期')
            ax.set_ylabel('资产价值')
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
        
        # 显示交易记录
        if trade_count > 0:
            st.subheader('交易记录')
            # 创建交易记录表
            trade_df = pd.DataFrame(trades)
            # 只显示重要的列
            if not trade_df.empty:
                display_columns = ['date', 'type', 'price', 'quantity', 'cost', 'stock_value', 'position_profit','deal_reason','total_asset']
                display_df = trade_df[display_columns].copy()
        
        # 格式化列 - 使用pandas的方法进行格式化
        for col in ['price', 'cost', 'stock_value', 'total_asset', 'position_profit']:
            if col in display_df.columns:
                # 将数字转换为带千分位、两位小数的字符串
                display_df[col] = display_df[col].apply(lambda x: '{:,.2f}'.format(x))
        
        # 设置列的显示顺序和样式
        display_df = display_df.rename(columns={
            'date': '日期',
            'type': '交易类型',
            'price': '价格',
            'quantity': '数量',
            'cost': '交易成本',
            'stock_value': '股票市值',
            'position_profit': '持仓盈亏',
            'total_asset': '总资产',
            'deal_reason': '交易原因'
        })
        
        # 使用dataframe的style属性设置右对齐和处理长文本
        styled_df = display_df.style.set_properties(**{
            'text-align': 'right'
        }).set_properties(subset=['日期', '交易类型', '交易原因'], **{
            'text-align': 'left'
        }).set_properties(subset=['交易原因'], **{
            'white-space': 'pre-wrap',
            'word-break': 'break-word'
        })
        
        # 设置列宽
        st.dataframe(styled_df, use_container_width=True, height=600)
        
        # 显示策略说明
        if strategy_mode == '单一策略':
            st.markdown(f"### {strategies_info[strategy_name]['display_name']}")
            st.markdown(f"**核心逻辑**：{strategies_info[strategy_name]['description']}")
            
            # 添加KDJ策略的详细说明
            if strategy_name == 'basic_kdj':
                st.markdown("**KDJ指标说明**：")
                st.markdown("- KDJ指标是一种常用的技术分析工具，通过计算最高价、最低价和收盘价的关系来反映市场的超买超卖状态")
                st.markdown("- **买入信号**：当K线上穿D线（金叉）时产生买入信号")
                st.markdown("- **卖出信号**：当K线下穿D线（死叉）时产生卖出信号")
                st.markdown("- 参数设置：默认使用n=9, m1=3, m2=3的参数组合")
            
            st.markdown("**资金管理**：")
            st.markdown(f"- 初始资金：{initial_cash}元")
            st.markdown(f"- 仓位比例：{position_ratio*100}%")
            st.markdown(f"- 交易成本：佣金率0.03%（最低5元）、印花税0.1%（卖出时收取）、过户费0.002%")
            st.markdown(f"- 总交易成本：{total_trading_cost:.2f}元")
        else:
            st.markdown("### 资金管理")
            st.markdown(f"- 初始资金：{initial_cash}元")
            st.markdown(f"- 仓位比例：{position_ratio*100}%")
            st.markdown(f"- 交易成本：佣金率0.03%（最低5元）、印花税0.1%（卖出时收取）、过户费0.002%")
            st.markdown(f"- 总交易成本：{total_trading_cost:.2f}元")
            
            # 列出所有选中的策略及其详细说明
            st.markdown("### 选中的策略详情")
            for s in selected_strategies:
                st.markdown(f"#### {strategies_info[s]['display_name']}")
                st.markdown(f"{strategies_info[s]['description']}")
                
                # 获取并显示每个策略的详细参数设置
                strategy_metadata = StrategyManager.get_strategy_metadata(s)
                if strategy_metadata.params_schema:
                    st.markdown("**参数配置**：")
                    for param_name, param_schema in strategy_metadata.params_schema.items():
                        param_key = f"{s}_{param_name}"
                        param_value = strategy_params.get(param_key, param_schema.get('default', '未设置'))
                        param_desc = param_schema.get('description', '')
                        if param_desc:
                            st.markdown(f"- **{param_name}**: {param_value} ({param_desc})")
                        else:
                            st.markdown(f"- **{param_name}**: {param_value}")
                
                # 添加各策略的详细解读
                if s == 'basic_kdj':
                    st.markdown("**核心逻辑**：基于KDJ指标的金叉死叉信号进行买卖决策")
                    st.markdown("**买入信号**：当K线上穿D线（金叉）时产生买入信号")
                    st.markdown("**卖出信号**：当K线下穿D线（死叉）时产生卖出信号")
                elif s == 'sma20_strategy':
                    st.markdown("**核心逻辑**：基于价格与20日均线的位置关系进行买卖决策")
                    st.markdown("**买入信号**：当价格上穿20日均线时产生买入信号")
                    st.markdown("**卖出信号**：当价格下穿20日均线时产生卖出信号")
                elif s == 'volume_strategy':
                    st.markdown("**核心逻辑**：基于成交量的变化识别主力资金动向")
                    st.markdown("**买入信号**：成交量显著放大且价格上涨时产生买入信号")
                    st.markdown("**卖出信号**：成交量显著放大但价格下跌时产生卖出信号")
                
            st.markdown("### 资金管理")
            st.markdown(f"- 初始资金：{initial_cash}元")
            st.markdown(f"- 仓位比例：{position_ratio*100}%")
            st.markdown(f"- 交易成本：佣金率0.03%（最低5元）、印花税0.1%（卖出时收取）、过户费0.002%")
    except Exception as e:
        st.error(f"回测过程中发生错误：{str(e)}")
        # 打印详细的错误信息用于调试
        import traceback
        st.text(traceback.format_exc())