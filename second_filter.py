from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import datetime as dt
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd
import tushare as ts

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("second_filter_results.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("second_filter")

def _to_ts_code(code: str) -> str:
    """把6位code映射到标准 ts_code 后缀"""
    # 清理代码，移除非数字字符并补零
    code = re.sub(r'[^0-9]', '', str(code))
    code = code.zfill(6)
    if code.startswith(("60", "68")):
        return f"{code}.SH"
    elif code.startswith(("4", "8")):
        return f"{code}.BJ"
    else:
        return f"{code}.SZ"

def load_first_round_results(result_file: Path) -> Set[str]:
    """从第一轮结果文件中加载选股结果"""
    try:
        stocks = set()
        with open(result_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 查找包含股票代码的行
                if "[INFO]" in line and "," in line and "无符合条件股票" not in line:
                    # 使用正则表达式提取所有6位数字的股票代码
                    codes = re.findall(r'\b\d{6}\b', line)
                    if codes:
                        stocks.update(codes)
        logger.info(f"从第一轮结果文件中总共解析到 {len(stocks)} 只股票")
        return stocks
    except Exception as e:
        logger.error("读取第一轮结果失败: %s", e)
        return set()

def extract_latest_trade_date(result_file: Path) -> str:
    """从日志文件中提取最近的交易日期，如果失败则使用默认日期"""
    latest_date = None
    
    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 查找包含交易日信息的行
                if "交易日: " in line:
                    # 提取日期格式 YYYY-MM-DD
                    date_match = re.search(r'交易日: (\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        date_str = date_match.group(1)
                        # 更新为找到的最新日期
                        latest_date = date_str.replace('-', '')
        
        if latest_date:
            logger.info(f"从日志中提取到交易日期: {latest_date}")
            return latest_date
        else:
            # 如果没有从日志中提取到，使用当前日期的前一个交易日逻辑
            logger.warning("无法从日志中提取交易日期，使用默认逻辑")
            # 获取当前日期
            today = dt.date.today()
            # 如果是周末，回滚到周五
            if today.weekday() == 5:  # 周六
                latest_date = (today - dt.timedelta(days=1)).strftime('%Y%m%d')
            elif today.weekday() == 6:  # 周日
                latest_date = (today - dt.timedelta(days=2)).strftime('%Y%m%d')
            else:
                latest_date = today.strftime('%Y%m%d')
            
            logger.warning(f"使用计算的默认交易日期: {latest_date}")
            return latest_date
    except Exception as e:
        logger.error(f"提取交易日期失败: {e}")
        # 出错时使用当前日期
        today = dt.date.today()
        latest_date = today.strftime('%Y%m%d')
        logger.warning(f"使用当前日期作为默认值: {latest_date}")
        return latest_date

def get_stock_data(pro, codes: Set[str], trade_date: str) -> Dict[str, Dict]:
    """使用Tushare API获取股票数据，按照接口要求使用daily_basic"""
    stock_data = {}
    valid_codes = []
    
    # 先验证并过滤有效的股票代码
    for code in codes:
        # 清理股票代码，只保留数字并补零
        clean_code = re.sub(r'[^0-9]', '', str(code))
        if len(clean_code) >= 6:
            valid_codes.append(clean_code[:6])  # 取前6位
        else:
            logger.warning("跳过无效的股票代码: %s", code)
    
    if not valid_codes:
        logger.error("没有有效的股票代码")
        return {}
    
    logger.info(f"开始获取 {len(valid_codes)} 只股票的数据")
    
    # 严格按照Tushare API文档要求调用接口
    try:
        # 1. 先获取所有需要的股票代码列表，转换为带后缀的标准格式
        ts_codes = [_to_ts_code(code) for code in valid_codes]
        
        # 2. 批量获取股票基本面数据
        daily_basic_data = pro.daily_basic(
            ts_code=','.join(ts_codes),  # 用逗号分隔的股票代码列表
            trade_date=trade_date,
            fields='ts_code,close,turnover_rate,circ_mv'  # 严格按照API文档的字段顺序和名称
        )
        
        if daily_basic_data.empty:
            logger.warning(f"在 {trade_date} 没有获取到任何基本面数据")
        else:
            # 处理获取到的数据
            for _, row in daily_basic_data.iterrows():
                # 从带后缀的代码中提取6位数字代码
                ts_code = row['ts_code']
                code = ts_code.split('.')[0]  # 提取不带后缀的6位数字代码
                
                # 构建股票数据字典
                stock_info = {
                    'close': row['close'],  # 收盘价
                    'turnover_rate': row['turnover_rate'],  # 换手率（%）
                    'circ_mv': row['circ_mv']  # 流通市值（万元）
                }
                
                stock_data[code] = stock_info
                logger.debug("获取到 %s 数据: 收盘价=%.2f, 换手率=%.2f%%, 流通市值=%.2f万元", 
                            code, stock_info['close'], stock_info['turnover_rate'], stock_info['circ_mv'])
            
            # 记录哪些股票没有获取到数据
            for code in valid_codes:
                if code not in stock_data:
                    logger.warning("%s 在 %s 没有获取到数据", code, trade_date)
                    
    except Exception as e:
        logger.error("批量获取数据时出错: %s", e)
        
        # 如果批量获取失败，尝试逐个获取（作为备选方案）
        logger.info("尝试逐个获取股票数据")
        for code in valid_codes:
            try:
                ts_code = _to_ts_code(code)
                
                # 严格按照API文档要求的格式调用
                basic_data = pro.daily_basic(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    fields='ts_code,close,turnover_rate,circ_mv'
                )
                
                if basic_data.empty:
                    logger.warning("%s 在 %s 没有基本面数据", code, trade_date)
                    continue
                
                # 构建股票数据字典
                stock_info = {
                    'close': basic_data['close'].iloc[0],
                    'turnover_rate': basic_data['turnover_rate'].iloc[0],
                    'circ_mv': basic_data['circ_mv'].iloc[0]  # 流通市值（万元）
                }
                stock_data[code] = stock_info
                
            except Exception as e:
                logger.error("获取 %s 数据时出错: %s", code, e)
                continue
    
    logger.info(f"成功获取 {len(stock_data)} 只股票的数据")
    return stock_data

def filter_stocks(
    stock_data: Dict[str, Dict],
    max_price: float = 30.0,
    min_turnover: float = 3.0,
    max_turnover: float = 15.0,
    min_market_cap: float = 20.0,
    max_market_cap: float = 100.0
) -> List[str]:
    """应用第二轮筛选条件"""
    filtered_stocks = []
    
    for code, data in stock_data.items():
        try:
            # 获取所需指标
            current_price = data.get("close", None)  # 收盘价作为现价
            turnover_rate = data.get("turnover_rate", None)  # 换手率（%）
            circ_mv = data.get("circ_mv", None)  # 流通市值（万元）
            
            # 计算流通市值（亿元）
            if circ_mv:
                market_cap = circ_mv / 10000  # 转换为亿元
            else:
                market_cap = None
                logger.warning("%s 无法获取流通市值", code)
                continue
            
            # 应用筛选条件
            if (current_price and current_price <= max_price and
                turnover_rate and min_turnover <= turnover_rate <= max_turnover and
                market_cap and min_market_cap <= market_cap <= max_market_cap):
                filtered_stocks.append(code)
                logger.debug("%s 通过筛选 - 价格: %.2f, 换手率: %.2f%%, 流通市值: %.2f亿元", 
                             code, current_price, turnover_rate, market_cap)
            
        except Exception as e:
            logger.error("处理 %s 数据时出错: %s", code, e)
            continue
    
    return filtered_stocks

def main():
    parser = argparse.ArgumentParser(description="第二轮股票筛选工具")
    parser.add_argument("--result-file", default="./select_results.log", help="第一轮选股结果文件")
    parser.add_argument("--date", help="交易日 YYYYMMDD；缺省=从日志中提取或使用最近交易日")
    parser.add_argument("--max-price", type=float, default=30.0, help="最大价格，默认30元")
    parser.add_argument("--min-turnover", type=float, default=3.0, help="最小换手率(%)，默认3%%")
    parser.add_argument("--max-turnover", type=float, default=15.0, help="最大换手率(%)，默认15%%")
    parser.add_argument("--min-market-cap", type=float, default=20.0, help="最小流通市值(亿元)，默认20亿元")
    parser.add_argument("--max-market-cap", type=float, default=100.0, help="最大流通市值(亿元)，默认100亿元")
    parser.add_argument("--stocks", help="直接指定股票代码列表，用逗号分隔，优先级高于结果文件")
    
    args = parser.parse_args()
    
    # ---------- Tushare Token ---------- #
    os.environ["NO_PROXY"] = "api.waditu.com,.waditu.com,waditu.com"
    os.environ["no_proxy"] = os.environ["NO_PROXY"]
    ts_token = os.environ.get("TUSHARE_TOKEN")
    if not ts_token:
        raise ValueError("请先设置环境变量 TUSHARE_TOKEN，例如：export TUSHARE_TOKEN=你的token")
    ts.set_token(ts_token)
    pro = ts.pro_api()
    
    # 加载第一轮选股结果
    if args.stocks:
        # 如果直接指定了股票代码列表
        first_round_stocks = set([s.strip() for s in args.stocks.split(",") if s.strip()])
    else:
        # 从结果文件中读取
        first_round_stocks = load_first_round_results(Path(args.result_file))
    
    if not first_round_stocks:
        logger.error("未能加载任何第一轮选股结果")
        sys.exit(1)
    
    logger.info("第一轮选股结果数量: %d", len(first_round_stocks))
    
    # 确定交易日期
    if args.date:
        trade_date = args.date
    else:
        # 首先尝试从日志文件中提取交易日期
        trade_date = extract_latest_trade_date(Path(args.result_file))
    
    # 获取股票数据（严格按照Tushare接口要求）
    stock_data = get_stock_data(pro, first_round_stocks, trade_date)
    
    if not stock_data:
        logger.error("未能获取任何股票数据")
        sys.exit(1)
    
    # 应用第二轮筛选
    filtered_stocks = filter_stocks(
        stock_data,
        args.max_price,
        args.min_turnover,
        args.max_turnover,
        args.min_market_cap,
        args.max_market_cap
    )
    
    # 输出结果
    logger.info("")
    logger.info("============== 第二轮筛选结果 ==============")
    logger.info("交易日: %s", trade_date)
    logger.info("符合条件股票数: %d", len(filtered_stocks))
    logger.info("筛选条件:")
    logger.info("- 现价 <= %.2f元", args.max_price)
    logger.info("- 日换手率在 %.2f%% - %.2f%% 之间", args.min_turnover, args.max_turnover)
    logger.info("- 流通市值在 %.2f - %.2f 亿元之间", args.min_market_cap, args.max_market_cap)
    logger.info("筛选结果: %s", ", ".join(filtered_stocks) if filtered_stocks else "无符合条件股票")
    
    # 输出更详细的核心指标信息
    if filtered_stocks:
        logger.info("")
        logger.info("============== 详细核心指标 ==============")
        logger.info("股票代码, 收盘价(元), 换手率(%%), 流通市值(亿元)")
        
        # 对结果按某种指标排序（这里按市值排序）
        sorted_stocks = sorted(filtered_stocks, key=lambda x: stock_data[x].get('circ_mv', 0) / 10000)
        
        for code in sorted_stocks:
            data = stock_data[code]
            price = data.get('close', 0)
            turnover = data.get('turnover_rate', 0)
            market_cap = data.get('circ_mv', 0) / 10000  # 转换为亿元
            logger.info(f"{code}, {price:.2f}, {turnover:.2f}, {market_cap:.2f}")
    
    # 保存结果到文件，方便后续使用
    with open("second_filter_results.json", "w", encoding="utf-8") as f:
        # 构建包含详细信息的结果
        detailed_results = {
            "date": trade_date,
            "conditions": {
                "max_price": args.max_price,
                "min_turnover": args.min_turnover,
                "max_turnover": args.max_turnover,
                "min_market_cap": args.min_market_cap,
                "max_market_cap": args.max_market_cap
            },
            "summary": {
                "total_stocks": len(first_round_stocks),
                "filtered_stocks_count": len(filtered_stocks),
                "pass_rate": f"{len(filtered_stocks)/len(first_round_stocks)*100:.2f}%" if first_round_stocks else "0%"
            },
            "stocks": filtered_stocks,
            "detailed_stock_data": {}
        }
        
        # 添加每只股票的详细数据
        for code in filtered_stocks:
            data = stock_data[code]
            detailed_results["detailed_stock_data"][code] = {
                "close": data.get('close', None),
                "turnover_rate": data.get('turnover_rate', None),
                "market_cap": data.get('circ_mv', None) / 10000 if data.get('circ_mv') else None
            }
        
        json.dump(detailed_results, f, ensure_ascii=False, indent=2)
    
    logger.info("结果已保存到 second_filter_results.json")


if __name__ == "__main__":
    main()