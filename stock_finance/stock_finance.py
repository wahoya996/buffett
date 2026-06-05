#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票财务分析图表生成 — 营收 & 净利润 & 同比增速
=============================================
功能：
  1. 利用 akshare 获取指定股票近 10 年年度财务数据
  2. 提取营业收入、归母净利润、营收同比增速、净利润同比增速
  3. 营收与净利润 → 柱状图（左轴）
     营收同比增速与净利润同比增速 → 折线图（右轴）
  4. 双 Y 轴融合在一张图上

依赖:
  pip install akshare pandas matplotlib

用法:
  python stock_finance.py
  按提示输入股票代码（如 600887 或 600887.SH）
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import akshare as ak
from datetime import datetime

# ================= 全局配置 =================
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 输出目录（可自行修改）
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
# ===========================================


def convert_symbol(symbol: str) -> str:
    """
    将用户输入的股票代码转为 akshare 需要的带市场标识格式。
    支持格式：
      - 600887          → SH600887
      - 600887.SH       → SH600887
      - 000858          → SZ000858
      - 000858.SZ       → SZ000858
      - SH600887        → 原样返回
      - sz000858        → SZ000858
    """
    symbol = symbol.strip().upper().replace(".", "")
    if symbol.startswith("SH") or symbol.startswith("SZ") or symbol.startswith("BJ"):
        return symbol
    # 判断交易所
    if symbol.startswith("6"):
        return f"SH{symbol}"
    elif symbol.startswith(("0", "3")):
        return f"SZ{symbol}"
    elif symbol.startswith(("8", "4")):
        return f"BJ{symbol}"
    else:
        # 默认沪市
        return f"SH{symbol}"


def fetch_financial_data(symbol: str) -> pd.DataFrame:
    """
    从东方财富获取利润表数据，返回年度报告 DataFrame。
    保留列：
      REPORT_DATE, REPORT_DATE_NAME,
      TOTAL_OPERATE_INCOME (营收), TOTAL_OPERATE_INCOME_YOY (营收同比%),
      PARENT_NETPROFIT (归母净利润), PARENT_NETPROFIT_YOY (净利润同比%)
    """
    print(f"⏳ 正在获取 {symbol} 的财务数据...")
    df = ak.stock_profit_sheet_by_report_em(symbol=symbol)

    # 选取需要的列
    cols = [
        "REPORT_DATE",
        "REPORT_DATE_NAME",
        "REPORT_TYPE",
        "TOTAL_OPERATE_INCOME",
        "TOTAL_OPERATE_INCOME_YOY",
        "PARENT_NETPROFIT",
        "PARENT_NETPROFIT_YOY",
    ]
    df = df[cols].copy()
    df.rename(
        columns={
            "TOTAL_OPERATE_INCOME": "营业收入",
            "TOTAL_OPERATE_INCOME_YOY": "营收同比增速",
            "PARENT_NETPROFIT": "归母净利润",
            "PARENT_NETPROFIT_YOY": "净利润同比增速",
        },
        inplace=True,
    )

    # 解析日期
    df["REPORT_DATE"] = pd.to_datetime(df["REPORT_DATE"])

    # 只保留年报
    df_annual = df[df["REPORT_TYPE"] == "年报"].copy()
    if df_annual.empty:
        print("❌ 未找到年报数据，请检查股票代码是否正确。")
        sys.exit(1)

    # 提取年份便于筛选
    df_annual["年份"] = df_annual["REPORT_DATE"].dt.year

    # 按年份降序排列取最近 10 年
    df_annual.sort_values("年份", ascending=True, inplace=True)
    df_annual = df_annual.tail(11)  # 多取一点防止最新一年未完整披露

    # 数值列单位转换（元 → 亿元）并保留 2 位小数
    for col in ["营业收入", "归母净利润"]:
        df_annual[col] = (df_annual[col] / 1e8).round(2)

    # 同比增速已经是百分比数值（如 5.47 表示 5.47%），保留 2 位小数
    for col in ["营收同比增速", "净利润同比增速"]:
        df_annual[col] = df_annual[col].round(2)

    df_annual.reset_index(drop=True, inplace=True)
    return df_annual


def plot_finance_chart(df: pd.DataFrame, symbol_raw: str):
    """
    绘制双 Y 轴组合图：
      - 左轴：营业收入（蓝柱）、归母净利润（橙柱）
      - 右轴：营收同比增速（红折线）、净利润同比增速（绿折线）
    """
    years = df["年份"].astype(str).tolist()
    revenue = df["营业收入"].tolist()
    net_profit = df["归母净利润"].tolist()
    revenue_yoy = df["营收同比增速"].tolist()
    net_profit_yoy = df["净利润同比增速"].tolist()

    # 获取股票名称
    stock_name = df["REPORT_DATE_NAME"].iloc[-1]
    # 从 REPORT_DATE_NAME 提取名称部分（去掉末尾年份标记）
    if len(stock_name) >= 6:
        stock_name = stock_name[:4]  # 取前4字作为名称抬头，实际上会用证券简称

    fig, ax1 = plt.subplots(figsize=(16, 8))

    # ---- 左轴：柱状图 ----
    x = range(len(years))
    bar_width = 0.35

    bars1 = ax1.bar(
        [i - bar_width / 2 for i in x],
        revenue,
        width=bar_width,
        color="#1f77b4",
        edgecolor="white",
        alpha=0.85,
        label="营业收入（亿元）",
        zorder=3,
    )
    bars2 = ax1.bar(
        [i + bar_width / 2 for i in x],
        net_profit,
        width=bar_width,
        color="#ff7f0e",
        edgecolor="white",
        alpha=0.85,
        label="归母净利润（亿元）",
        zorder=3,
    )

    ax1.set_xlabel("年度", fontsize=13)
    ax1.set_ylabel("营业收入 / 净利润（亿元）", fontsize=13, color="#333333")
    ax1.tick_params(axis="y", labelcolor="#333333")
    ax1.set_xticks(x)
    ax1.set_xticklabels(years, fontsize=11)

    # 柱状图数值标签
    for bar in bars1:
        h = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            h,
            f"{h:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#1f77b4",
        )
    for bar in bars2:
        h = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            h,
            f"{h:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#ff7f0e",
        )

    # ---- 右轴：折线图 ----
    ax2 = ax1.twinx()
    (line1,) = ax2.plot(
        x,
        revenue_yoy,
        color="#d62728",
        marker="o",
        markersize=7,
        linewidth=2,
        label="营收同比增速（%）",
        zorder=5,
    )
    (line2,) = ax2.plot(
        x,
        net_profit_yoy,
        color="#2ca02c",
        marker="s",
        markersize=7,
        linewidth=2,
        linestyle="--",
        label="净利润同比增速（%）",
        zorder=5,
    )

    ax2.set_ylabel("同比增速（%）", fontsize=13, color="#333333")
    ax2.tick_params(axis="y", labelcolor="#333333")

    # 折线图数值标签
    for i, (ry, ny) in enumerate(zip(revenue_yoy, net_profit_yoy)):
        ax2.annotate(
            f"{ry:.1f}%",
            (x[i], ry),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=8,
            color="#d62728",
        )
        ax2.annotate(
            f"{ny:.1f}%",
            (x[i], ny),
            textcoords="offset points",
            xytext=(0, -15),
            ha="center",
            fontsize=8,
            color="#2ca02c",
        )

    # 零线（辅助观察正负增长）
    ax2.axhline(y=0, color="gray", linewidth=0.8, linestyle=":", zorder=1)

    # ---- 统一图例 ----
    bars = [bars1, bars2]
    lines = [line1, line2]
    # 合并图例
    legend_handles = [b for b in bars] + lines
    legend_labels = [
        "营业收入（亿元）",
        "归母净利润（亿元）",
        "营收同比增速（%）",
        "净利润同比增速（%）",
    ]
    ax1.legend(
        legend_handles,
        legend_labels,
        loc="upper left",
        fontsize=10,
        frameon=True,
        framealpha=0.9,
        edgecolor="#cccccc",
    )

    # ---- 标题与网格 ----
    plt.title(
        f"{symbol_raw} 十年财务数据分析图表",
        fontsize=16,
        fontweight="bold",
        pad=12,
    )
    ax1.grid(True, alpha=0.25, linestyle="--", axis="y", zorder=0)
    ax2.grid(False)  # 不重复网格

    # 背景色微调
    fig.patch.set_facecolor("#fafafa")

    plt.tight_layout()
    return fig


def main():
    print("=" * 55)
    print("  股票财务分析 — 营收 & 净利润 & 同比增速")
    print("=" * 55)

    # 1. 读入股票代码
    raw = input("\n请输入股票代码（如 600887 或 600887.SH）: ").strip()
    if not raw:
        print("❌ 股票代码不能为空。")
        sys.exit(1)

    symbol_api = convert_symbol(raw)

    # 2. 获取数据
    df = fetch_financial_data(symbol_api)

    # 显示数据摘要
    print(f"\n📋 获取到 {len(df)} 年年度数据（最近 {len(df)} 年）：")
    summary = df[["年份", "营业收入", "归母净利润", "营收同比增速", "净利润同比增速"]]
    print(summary.to_string(index=False))

    # 3. 绘图
    print("\n🎨 正在生成图表...")
    fig = plot_finance_chart(df, raw)

    # 4. 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    filename = f"{raw}_财务分析_{today}.png"
    output_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"✅ 图表已保存至：{output_path}")

    # 5. 显示（非交互环境自动跳过）
    try:
        plt.show()
    except Exception:
        pass
    print("\n✅ 分析完成！")


if __name__ == "__main__":
    main()
