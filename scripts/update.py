#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四数关系分析 - 每日自动更新脚本
直接用GitHub Contents API读写repo数据文件，不再依赖Gist
"""

import json
import os
import base64
from datetime import datetime
from urllib.request import Request, urlopen

# ========== 配置 ==========
GH_TOKEN = os.environ.get('GH_TOKEN', os.environ.get('GIST_TOKEN', ''))
REPO = 'ebupuba099-lang/num-relations'
DATA_FILE = 'data/relations_data.json'

# 体彩官方API - 排列五
SPORTTERY_URL = 'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=350133&provinceId=0&pageSize=5&is11=0'
# 灰鸟API - 备用
HUINIAO_URL = 'http://api.huiniao.top/interface/home/lotteryHistory?type=plw&page=1&limit=5'

def log(msg):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] {msg}", flush=True)

def load_data():
    headers = {'Authorization': f'token {GH_TOKEN}', 'Accept': 'application/vnd.github.v3.raw'}
    req = Request(f'https://api.github.com/repos/{REPO}/contents/{DATA_FILE}', headers=headers)
    resp = urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))

def save_data(data):
    headers = {
        'Authorization': f'token {GH_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }
    # 获取当前SHA
    sha_req = Request(f'https://api.github.com/repos/{REPO}/contents/{DATA_FILE}', headers=headers)
    sha_resp = urlopen(sha_req, timeout=30)
    sha = json.loads(sha_resp.read().decode('utf-8'))['sha']
    
    content = json.dumps(data, ensure_ascii=False)
    b64 = base64.b64encode(content.encode('utf-8')).decode()
    body = json.dumps({'message': 'auto: update num-relations data', 'content': b64, 'sha': sha}).encode('utf-8')
    put_req = Request(f'https://api.github.com/repos/{REPO}/contents/{DATA_FILE}', data=body, method='PUT', headers=headers)
    resp = urlopen(put_req, timeout=30)
    return resp.status == 200

def fetch_new_records():
    """从多个API获取最新开奖记录"""
    
    # 方案1: 体彩官方API
    try:
        req = Request(SPORTTERY_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.lottery.gov.cn/',
            'Accept': 'application/json'
        })
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('value') and data['value'].get('list'):
            records = []
            for item in data['value']['list']:
                result = item.get('lotteryDrawResult', '')
                parts = result.split()
                if len(parts) >= 4:
                    draw_num = item.get('lotteryDrawNum', '')
                    # 期号格式: "26137" → 26137
                    period = int(draw_num) if draw_num else 0
                    records.append({
                        'period': period,
                        'date': item.get('lotteryDrawTime', ''),
                        'n1': int(parts[0]),
                        'n2': int(parts[1]),
                        'n3': int(parts[2]),
                        'n4': int(parts[3])
                    })
            if records:
                log(f"体彩官方获取成功: {len(records)}期")
                for r in records[:3]:
                    log(f"  期{r['period']} {r['n1']}{r['n2']}{r['n3']}{r['n4']}")
                return records
    except Exception as e:
        log(f"体彩官方失败: {e}")
    
    # 方案2: 灰鸟API
    try:
        req = Request(HUINIAO_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        records = []
        d = data.get('data', {})
        # 灰鸟API结构: data.data.list 或 data.last
        items = []
        if isinstance(d, dict):
            if d.get('data') and isinstance(d['data'], dict) and d['data'].get('list'):
                items = d['data']['list']
            elif d.get('last'):
                items = [d['last']]
        elif isinstance(d, list):
            items = d
        
        for item in items:
            code = item.get('code', '')
            if not code:
                continue
            one = item.get('one', '')
            two = item.get('two', '')
            three = item.get('three', '')
            four = item.get('four', '')
            if one and two and three and four:
                period = int(code)  # "26137" → 26137
                records.append({
                    'period': period,
                    'date': item.get('day', item.get('date', '')),
                    'n1': int(one),
                    'n2': int(two),
                    'n3': int(three),
                    'n4': int(four)
                })
        if records:
            log(f"灰鸟API获取成功: {len(records)}期")
            for r in records[:3]:
                log(f"  期{r['period']} {r['n1']}{r['n2']}{r['n3']}{r['n4']}")
            return records
    except Exception as e:
        log(f"灰鸟API失败: {e}")
    
    return []

def main():
    log("=" * 50)
    log("四数关系分析自动更新任务开始")
    
    new_records = fetch_new_records()
    if not new_records:
        log("获取开奖数据失败，跳过更新")
        return True
    
    try:
        cloud_data = load_data()
    except Exception as e:
        log(f"读取数据失败: {e}")
        return False
    
    existing = cloud_data.get('records', [])
    last_period = max((r.get('period', 0) for r in existing), default=0)
    log(f"当前: {len(existing)}条, 最新期: {last_period}")
    
    new_ones = [r for r in new_records if r['period'] > last_period]
    new_ones.sort(key=lambda r: r['period'], reverse=True)
    
    if not new_ones:
        log("没有新数据需要添加")
    else:
        for r in new_ones:
            existing.insert(0, r)
            log(f"添加 期{r['period']}: {r['n1']}{r['n2']}{r['n3']}{r['n4']} ({r['date']})")
        
        # 最多保留100条
        if len(existing) > 100:
            cloud_data['records'] = existing[:100]
        else:
            cloud_data['records'] = existing
        cloud_data['lastUpdate'] = int(datetime.now().timestamp() * 1000)
        
        try:
            success = save_data(cloud_data)
            if success:
                log(f"推送成功！新增 {len(new_ones)} 条，总计 {len(cloud_data['records'])} 条")
            else:
                log("推送失败")
        except Exception as e:
            log(f"推送异常: {e}")
    
    log("任务完成")
    return True

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
