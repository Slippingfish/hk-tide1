#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港天文台验潮站水位高度采集程序（GitHub Actions版）
=====================================================
此脚本被 GitHub Actions 每10分钟调用一次，
每次运行只做一件事：拉取最新数据，追加到 hk_tide_data.csv。
不需要循环，不需要 sleep。
"""

import requests
import pandas as pd
import os
from datetime import datetime
from io import StringIO

LIVE_URL   = "https://data.weather.gov.hk/weatherAPI/hko_data/tide/ALL_sc.csv"
OUTPUT_CSV = "hk_tide_data.csv"   # GitHub Actions 工作目录下的相对路径
ENCODING   = "utf-8-sig"
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; TideScraper/GHA)"}


def decode_content(raw):
    for enc in ("utf-8-sig", "big5", "utf-8"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return None


def fetch():
    resp = requests.get(LIVE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    text = decode_content(resp.content)
    if not text:
        raise ValueError("编码识别失败")

    df = pd.read_csv(StringIO(text), header=0,
                     skipinitialspace=True, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    df = df.iloc[:, :4].copy()
    df.columns = ["验潮站", "日期", "时间", "高度_米"]
    df["高度_米"] = pd.to_numeric(
        df["高度_米"].astype(str).str.strip().replace({"---": None}),
        errors="coerce"
    )
    df = df.dropna(subset=["高度_米"])
    df["验潮站"] = df["验潮站"].astype(str).str.strip()
    df["日期"]   = df["日期"].astype(str).str.strip()
    df["时间"]   = df["时间"].astype(str).str.strip()
    df["抓取时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return df


def save(new_df):
    keys = ["验潮站", "日期", "时间"]
    if os.path.exists(OUTPUT_CSV) and os.path.getsize(OUTPUT_CSV) > 50:
        old = pd.read_csv(OUTPUT_CSV, encoding=ENCODING)
        combined = pd.concat([old, new_df], ignore_index=True)
        combined.drop_duplicates(subset=keys, keep="first", inplace=True)
        added = len(combined) - len(old)
    else:
        combined = new_df.copy()
        added = len(new_df)
    combined.to_csv(OUTPUT_CSV, index=False, encoding=ENCODING)
    return added


def report(added):
    if not os.path.exists(OUTPUT_CSV):
        return
    df = pd.read_csv(OUTPUT_CSV, encoding=ENCODING)
    df["dt"] = pd.to_datetime(
        df["日期"].astype(str) + " " + df["时间"].astype(str),
        format="%Y-%m-%d %H:%M", errors="coerce"
    )
    df = df.dropna(subset=["dt"])
    if df.empty:
        return
    span = (df["dt"].max() - df["dt"].min()).total_seconds() / 3600
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
          f"新增 {added} 条 | 总计 {len(df)} 条 | "
          f"跨度 {span:.1f}h | 站点 {df['验潮站'].unique().tolist()}")


if __name__ == "__main__":
    try:
        new_df = fetch()
        added  = save(new_df)
        report(added)
    except Exception as e:
        print(f"ERROR: {e}")
        raise
