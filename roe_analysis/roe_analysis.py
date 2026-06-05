#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROE 杜邦分析图表生成器 (AKShare 自动版)
========================================
功能：
  1. 根据用户输入的 A 股股票代码，自动获取近 5 年财务数据
  2. 计算杜邦分解：ROE = 销售净利率 × 总资产周转率 × 权益乘数
  3. 生成 4 面板分析图表（ROE 趋势、三因子对比、实际 vs 分解值、微分归因）
  4. 以 "股票代码_ROE分析.png" 保存到脚本所在目录

依赖：
  - akshare（自动安装）
  - matplotlib
  - pandas

使用示例：
  python roe_analysis.py
  然后输入股票代码（如 600887）
"""

import subprocess
import sys
import os

# ================= 自动安装依赖 =================
_REQUIRED_PACKAGES = ['akshare', 'matplotlib', 'pandas']
for _pkg in _REQUIRED_PACKAGES:
    try:
        __import__(_pkg.replace('-', '_'))
    except ImportError:
        print(f"正在安装 {_pkg}...")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', _pkg, '-q', '--break-system-packages']
        )

import akshare as ak
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 无头模式，避免 GUI 依赖
import matplotlib.pyplot as plt
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# ================= 配置 =================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'MiSans']
plt.rcParams['axes.unicode_minus'] = False

# 脚本所在目录（输出图片保存到这里）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ================= 数据获取 =================
def parse_pct(value: str) -> float:
    """解析百分比字符串 '15.81%' → 15.81"""
    return float(str(value).replace('%', '').strip())


def parse_num(value: str) -> float:
    """解析带单位的数字字符串 '1157.80亿' → 1157.80"""
    s = str(value).strip()
    if '万亿' in s:
        return float(s.replace('万亿', '')) * 10000
    if '亿' in s:
        return float(s.replace('亿', ''))
    if '万' in s:
        return float(s.replace('万', '')) / 10000
    return float(s)


def get_stock_name(code: str) -> str:
    """通过 业绩报表 获取股票简称"""
    try:
        df = ak.stock_yjbb_em(date='20241231')
        stock = df[df['股票代码'] == code]
        if not stock.empty:
            return str(stock.iloc[0]['股票简称'])
    except Exception:
        pass
    return code


def fetch_dupont_data(code: str):
    """
    使用 AKShare 获取近 5 年财务数据，返回 DataFrame
    列：年份, ROE%, 销售净利率%, 总资产周转率, 资产负债率%, 权益乘数, ROE_分解%

    ⚠ 总资产周转率从资产负债表独立获取（vs 原版用杜邦恒等式反推），
      因此实际 ROE 与杜邦分解 ROE 之间存在自然差异（加权平均效应等），图 3 对比有意义。
    """
    # 统一股票代码格式（balance sheet 需要小写前缀）
    bs_code = code.lower()
    if not bs_code.startswith(('sh', 'sz', 'bj')):
        if code.startswith(('6', '9')):
            bs_code = 'sh' + code
        else:
            bs_code = 'sz' + code

    # ----- 1. 财务摘要（同花顺）-----
    try:
        df_fa = ak.stock_financial_abstract_ths(symbol=code)
    except Exception as e:
        raise RuntimeError(f"获取财务摘要失败：{e}")

    # 筛选年报数据（报告期包含 12-31）
    df_annual = df_fa[df_fa['报告期'].str.contains('12-31')].copy()
    if df_annual.empty:
        raise RuntimeError("未获取到年报数据，请检查股票代码。")

    # ----- 2. 资产负债表（独立获取总资产）-----
    # 目的：用实际总资产计算周转率，而非从 ROE 反推
    try:
        df_bs = ak.stock_balance_sheet_by_report_em(symbol=bs_code)
        # 总资产单位是 元，转为 亿 方便与营收匹配
        df_bs['_year'] = pd.to_datetime(df_bs['REPORT_DATE']).dt.year
        total_assets_map = {}
        for _, bs_row in df_bs.iterrows():
            if str(bs_row['REPORT_DATE']).endswith('12-31 00:00:00'):
                year = int(bs_row['_year'])
                # TOTAL_ASSETS 单位是元 → 除以 1e8 转为亿
                total_assets_map[year] = bs_row['TOTAL_ASSETS'] / 1e8
    except Exception:
        total_assets_map = {}

    # ----- 3. 整理近 5 年数据 -----
    records = []
    current_year = datetime.now().year
    target_years = list(range(current_year - 5, current_year))  # 例如 [2021,2022,2023,2024,2025]

    for year in target_years:
        # 在财务摘要中匹配该年年报
        row = df_annual[df_annual['报告期'].str.startswith(str(year))]
        if row.empty:
            continue

        r = row.iloc[0]
        try:
            roe = parse_pct(r['净资产收益率'])
            npm = parse_pct(r['销售净利率'])
            dr = parse_pct(r['资产负债率'])
            revenue = parse_num(r['营业总收入'])   # 亿
            net_profit = parse_num(r['净利润'])     # 亿

            # 权益乘数（从资产负债率推导，恒等）
            em = 1 / (1 - dr / 100)

            # 总资产周转率 = 营业收入 / 总资产（独立计算）
            total_assets = total_assets_map.get(year)
            if total_assets and total_assets > 0:
                at = revenue / total_assets
            else:
                # 无资产负债表数据时回退：从杜邦恒等式推导
                if npm != 0 and em != 0:
                    at = (roe / 100) / ((npm / 100) * em)
                else:
                    at = 0.0

            # 分解 ROE = 净利率 × 周转率 × 权益乘数
            roe_decomp = (npm / 100) * at * em * 100
        except (ValueError, KeyError, TypeError) as e:
            print(f"  ⚠ {year} 年数据解析失败：{e}")
            continue

        records.append({
            '年份': str(year),
            'ROE(加权)%': round(roe, 2),
            '销售净利率%': round(npm, 2),
            '总资产周转率': round(at, 4),
            '资产负债率%': round(dr, 2),
            '权益乘数': round(em, 3),
            'ROE_分解%': round(roe_decomp, 2),
            '营业总收入(亿)': round(revenue, 2),
            '总资产(亿)': round(total_assets, 2) if total_assets is not None else None,
            '净利润(亿)': round(net_profit, 2),
        })

    if len(records) < 3:
        raise RuntimeError(f"有效数据不足（仅 {len(records)} 年），至少需要 3 年。")

    df_result = pd.DataFrame(records)
    return df_result


# ================= 微分归因分析 =================
def differential_contribution(df: pd.DataFrame):
    """
    微分法计算各因素对 ROE 变动的贡献
    返回 (label_years, 贡献列表) 用于绘图
    """
    factors = ['销售净利率\n贡献', '总资产周转率\n贡献', '权益乘数\n贡献']
    contributions = []
    label_years = []

    for i in range(1, len(df)):
        A0 = df['销售净利率%'].iloc[i - 1] / 100
        B0 = df['总资产周转率'].iloc[i - 1]
        C0 = df['权益乘数'].iloc[i - 1]

        A1 = df['销售净利率%'].iloc[i] / 100
        B1 = df['总资产周转率'].iloc[i]
        C1 = df['权益乘数'].iloc[i]

        dA, dB, dC = A1 - A0, B1 - B0, C1 - C0
        mean_A, mean_B, mean_C = (A0 + A1) / 2, (B0 + B1) / 2, (C0 + C1) / 2

        contrib_A = (mean_B * mean_C) * dA * 100
        contrib_B = (mean_A * mean_C) * dB * 100
        contrib_C = (mean_A * mean_B) * dC * 100

        contributions.append([contrib_A, contrib_B, contrib_C])
        label_years.append(f"{df['年份'].iloc[i-1]}→{df['年份'].iloc[i]}")

    return label_years, factors, contributions


# ================= 绘图 =================
def create_chart(df: pd.DataFrame, stock_code: str, stock_name: str) -> str:
    """生成 2×2 杜邦分析图表，返回保存路径"""
    years = df['年份'].tolist()

    # ---- 微分归因 ----
    label_years, factors, contributions = differential_contribution(df)

    # ---- 创建子图 ----
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    title_text = f'{stock_name} ({stock_code}) 杜邦分析 ({years[0]}-{years[-1]})'
    fig.suptitle(title_text, fontsize=16, fontweight='bold', y=0.98)

    # --- 图 1: ROE 趋势 ---
    ax1 = axes[0, 0]
    ax1.plot(years, df['ROE(加权)%'], marker='o', linewidth=2, markersize=8, color='#d62728', label='ROE(加权)')
    ax1.fill_between(years, df['ROE(加权)%'], alpha=0.3, color='#d62728')
    ax1.set_ylabel('ROE (%)', fontsize=12)
    ax1.set_title('净资产收益率 (ROE) 趋势', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='best')
    for i, v in enumerate(df['ROE(加权)%']):
        ax1.annotate(f'{v}%', (years[i], v), textcoords="offset points",
                     xytext=(0, 10), ha='center', fontsize=9)
    y_max = max(df['ROE(加权)%'])
    ax1.set_ylim(0, y_max * 1.25 if y_max > 0 else 10)

    # --- 图 2: 杜邦三因子对比 ---
    ax2 = axes[0, 1]
    x = range(len(years))
    width = 0.25
    bar1 = ax2.bar([i - width for i in x], df['销售净利率%'], width,
                   label='销售净利率 (%)', color='#1f77b4')
    bar2 = ax2.bar(x, df['总资产周转率'] * 100, width,
                   label='总资产周转率 (×100)', color='#2ca02c')
    bar3 = ax2.bar([i + width for i in x], df['权益乘数'] * 10, width,
                   label='权益乘数 (×10)', color='#ff7f0e')

    ax2.set_ylabel('标准化数值', fontsize=12)
    ax2.set_title('杜邦三因子趋势对比', fontsize=13, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(years)
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')

    for bar in bar1:
        h = bar.get_height()
        ax2.annotate(f'{h:.1f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7)
    for bar in bar2:
        h = bar.get_height()
        ax2.annotate(f'{h:.0f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7)
    for bar in bar3:
        h = bar.get_height()
        ax2.annotate(f'{h:.1f}', xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7)

    # --- 图 3: ROE 实际值 vs 分解值 ---
    ax3 = axes[1, 0]
    ax3.plot(years, df['ROE(加权)%'], marker='o', linewidth=2, label='实际 ROE', color='#d62728')
    ax3.plot(years, df['ROE_分解%'], marker='s', linewidth=2, linestyle='--',
             label='分解计算 ROE', color='#1f77b4')
    ax3.set_ylabel('ROE (%)', fontsize=12)
    ax3.set_title('ROE 实际值 vs 杜邦公式计算值', fontsize=13, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3, linestyle='--')
    for i, (v1, v2) in enumerate(zip(df['ROE(加权)%'], df['ROE_分解%'])):
        if abs(v1 - v2) > 0.5:
            ax3.annotate(f'差:{v1 - v2:.1f}', (years[i], (v1 + v2) / 2),
                         fontsize=8, color='gray')

    # --- 图 4: 微分归因 ---
    ax4 = axes[1, 1]
    contrib_df = pd.DataFrame(contributions, columns=factors, index=label_years)
    contrib_df.plot(kind='bar', stacked=True, ax=ax4, colormap='RdYlGn',
                    width=0.7, edgecolor='black')

    ax4.set_ylabel('ROE 变动贡献 (pp)', fontsize=12)
    ax4.set_title('各因素对 ROE 变动的贡献 (微分归因)', fontsize=13, fontweight='bold')
    ax4.axhline(0, color='black', linewidth=1)
    ax4.legend(loc='best', fontsize=9)
    ax4.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax4.tick_params(axis='x', rotation=0)

    for container in ax4.containers:
        labels = []
        for v in container.datavalues:
            if abs(v) < 0.05:
                labels.append('')
            else:
                sign = '+' if v > 0 else ''
                labels.append(f'{sign}{v:.1f}')
        ax4.bar_label(container, labels=labels, label_type='center',
                      fontsize=8, color='black')

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    # ---- 保存 ----
    output_filename = f'{stock_code}_ROE分析.png'
    output_path = os.path.join(SCRIPT_DIR, output_filename)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return output_path


# ================= 主程序 =================
def main():
    print('=' * 56)
    print('   ROE 杜邦分析图表生成器 (AKShare 自动版)')
    print('=' * 56)

    # 输入股票代码
    stock_code = input('\n请输入股票代码（例如 600887）：').strip()
    if not stock_code.isdigit() or len(stock_code) != 6:
        print('❌ 请输入 6 位数字股票代码。')
        sys.exit(1)

    print(f'\n正在获取 {stock_code} 的财务数据...')

    # 获取股票名称
    try:
        stock_name = get_stock_name(stock_code)
        print(f'股票名称：{stock_name}')
    except Exception as e:
        print(f'⚠ 获取股票名称失败：{e}')
        stock_name = stock_code

    # 获取杜邦分析数据
    try:
        df = fetch_dupont_data(stock_code)
        print(f'成功获取 {len(df)} 年年报数据：{", ".join(df["年份"].tolist())}')
    except Exception as e:
        print(f'❌ 数据获取失败：{e}')
        sys.exit(1)

    # 打印数据表
    print('\n' + '=' * 80)
    print('杜邦分析数据表')
    print('=' * 80)
    display_cols = ['年份', 'ROE(加权)%', '销售净利率%', '总资产周转率',
                    '资产负债率%', '权益乘数', 'ROE_分解%']
    print(df[display_cols].to_string(index=False))

    # 验证误差
    diff = (df['ROE(加权)%'] - df['ROE_分解%']).abs()
    print(f'\n✅ 最大分解误差：{diff.max():.4f}%')

    # 生成图表
    print('\n正在生成杜邦分析图表...')
    try:
        output_path = create_chart(df, stock_code, stock_name)
        print(f'\n✅ 图表已保存至：{output_path}')
    except Exception as e:
        print(f'❌ 图表生成失败：{e}')
        sys.exit(1)

    print('\n✅ 杜邦分析完成！')


if __name__ == '__main__':
    main()
