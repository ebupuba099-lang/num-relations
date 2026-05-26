#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四数关系分析 - 每日自动更新脚本
每天21:40执行：从体彩官方API获取最新开奖号码(前4位) → 添加到Gist → 同步
"""

import json
import os
from datetime import datetime
from urllib.request import Request, urlopen

# ========== 配置 ==========
GIST_TOKEN = os.environ.get('GIST_TOKEN', '')
GIST_ID = 'b63a528e91eba6d15dd3da06056dab0f'
GIST_FILENAME = 'relations_data.json'
GIST_API = f'https://api.github.com/gists/{GIST_ID}'

# 体彩官方API - 排列五
SPORTTERY_URL = 'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=350133&provinceId=0&pageSize=5&is11=0'
# 灰鸟API - 备用
HUINIAO_URL = 'http://api.huiniao.top/interface/home/lotteryHistory?type=plw&page=1&limit=5'

def log(msg):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}", flush=True)

def fetch_gist():
    headers = {'User-Agent': 'Python'}
    if GIST_TOKEN:
        headers['Authorization'] = f'token {GIST_TOKEN}'
    req = Request(GIST_API, headers=headers)
    resp = urlopen(req, timeout=30)
    data = json.loads(resp.read().decode('utf-8'))
    content = data['files'][GIST_FILENAME]['content']
    return json.loads(content)

def push_gist(data):
    body = json.dumps({
        'files': {
            GIST_FILENAME: {
                'content': json.dumps(data, ensure_ascii=False, indent=2)
            }
        }
    }).encode('utf-8')
    headers = {
        'Authorization': f'token {GIST_TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': 'Python'
    }
    req = Request(GIST_API, data=body, method='PATCH', headers=headers)
    resp = urlopen(req, timeout=30)
    return resp.status == 200

def fetch_new_records(retry=3):
    """从API获取最新几期数据，返回 records 列表"""
    # 优先体彩官方
    apis = [
        {
            'name': '体彩官方',
            'url': SPORTTERY_URL,
            'parse': lambda data: [
                {
                    'period': int(item['lotteryDrawNum']),
                    'date': item['lotteryDrawTime'],
                    'n1': int(item['lotteryDrawResult'].split()[0]),
                    'n2': int(item['lotteryDrawResult'].split()[1]),
                    'n3': int(item['lotteryDrawResult'].split()[2]),
                    'n4': int(item['lotteryDrawResult'].split()[3])
                }
                for item in data.get('value', {}).get('list', [])
                if len(item.get('lotteryDrawResult', '').split()) >= 5
            ]
        },
        {
            'name': '灰鸟API',
            'url': HUINIAO_URL,
            'parse': lambda data: []
            # 灰鸟API格式不同，简化处理
        }
    ]

    for api in apis:
        for attempt in range(retry):
            try:
                req = Request(api['url'], headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Referer': 'https://www.lottery.gov.cn/'
                })
                resp = urlopen(req, timeout=15)
                data = json.loads(resp.read().decode('utf-8'))
                records = api['parse'](data)
                if records:
                    log(f"{api['name']}获取成功: {len(records)}期")
                    for r in records[:3]:
                        log(f"  期{r['period']} {r['n1']}{r['n2']}{r['n3']}{r['n4']}")
                    return records
                else:
                    log(f"{api['name']}: 无数据")
                    break
            except Exception as e:
                log(f"{api['name']}失败 (第{attempt+1}次): {e}")
                if attempt < retry - 1:
                    import time; time.sleep(5)
    return []

def main():
    log("=" * 50)
    log("四数关系分析自动更新任务开始")

    # 1. 获取最新开奖数据
    new_records = fetch_new_records(retry=3)
    if not new_records:
        log("获取开奖数据失败，任务终止")
        return False

    # 2. 从Gist读取当前数据
    for attempt in range(3):
        try:
            cloud_data = fetch_gist()
            break
        except Exception as e:
            log(f"读取Gist失败 (第{attempt+1}次): {e}")
            if attempt == 2:
                log("读取Gist彻底失败，任务终止")
                return False
            import time; time.sleep(5)

    existing = cloud_data.get('records', [])
    last_period = max((r.get('period', 0) for r in existing), default=0)
    log(f"Gist当前: {len(existing)}条, 最新期: {last_period}")

    # 3. 筛选新数据
    new_ones = [r for r in new_records if r['period'] > last_period]
    new_ones.sort(key=lambda r: r['period'], reverse=True)

    if not new_ones:
        log("没有新数据需要添加")
        return True

    for r in new_ones:
        existing.insert(0, r)
        log(f"添加 期{r['period']}: {r['n1']}{r['n2']}{r['n3']}{r['n4']} ({r['date']})")

    # 4. 推送到Gist
    cloud_data['records'] = existing
    cloud_data['lastUpdate'] = int(datetime.now().timestamp() * 1000)

    for attempt in range(3):
        try:
            success = push_gist(cloud_data)
            if success:
                log(f"推送成功！新增 {len(new_ones)} 条，总计 {len(existing)} 条")
                return True
            else:
                log(f"推送失败 (第{attempt+1}次)")
        except Exception as e:
            log(f"推送异常 (第{attempt+1}次): {e}")
        if attempt < 2:
            import time; time.sleep(5)

    log("推送彻底失败")
    return False

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
