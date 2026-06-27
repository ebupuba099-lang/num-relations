#!/usr/bin/env python3
"""
四数关系 - 开奖号码获取 v11
7数据源全量降级，适配 relations_data.json 格式
"""

import json, os, sys, ssl, re, time, base64, traceback
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

REPO = os.environ.get('GITHUB_REPOSITORY', 'ebupuba099-lang/num-relations')
DATA_FILE = 'data/relations_data.json'
TZ = timezone(timedelta(hours=8))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
HEADERS = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*', 'Accept-Language': 'zh-CN,zh;q=0.9'}

def log(msg):
    print(f'[{datetime.now(TZ).strftime("%H:%M:%S")}] {msg}', flush=True)

def http_get(url, retries=2, timeout=20):
    for i in range(retries):
        try:
            resp = urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx)
            return resp.read().decode('utf-8', errors='ignore'), resp.status
        except HTTPError as e:
            if i == retries - 1: raise
            time.sleep(2)
        except URLError as e:
            if i == retries - 1: raise
            time.sleep(2)
    return None, 0

def valid(period, digits):
    return 26000 < period < 30000 and len(digits) == 4 and digits.isdigit()

# ==========================================
# 7数据源
# ==========================================

def fetch_js_lottery():
    try:
        html, _ = http_get('https://api.js-lottery.com/')
        if not html: return None, None
        posts = re.findall(r'(post-\d+\.html)', html)
        for post in posts[:5]:
            try:
                detail, _ = http_get(f'https://api.js-lottery.com/{post}')
                if not detail: continue
                t = re.search(r'排列[5五]第\s*(\d{5})\s*期', detail)
                if not t: continue
                period = int(t.group(1))  # 5位期号，如 26168
                n = re.search(r'(?:本期)?开奖号码[：:]\s*(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)', detail)
                if n:
                    digits = ''.join(n.groups())[:4]  # 只取前4位
                    if valid(period, digits):
                        return digits, period
            except: continue
    except Exception as e: log(f'  江苏体彩: {e}')
    return None, None

def fetch_cjcp():
    for url in ['https://m.cjcp.com.cn/kaijiang/pl5/', 'https://m.cjcp.cn/kaijiang/pl5/']:
        try:
            html, _ = http_get(url, retries=1)
            if not html or len(html) < 3000: continue
            
            # 格式1: 传统文本
            m = re.search(r'第\s*(\d{7})\s*期[\s\S]*?开奖号码[：:]?\s*(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)', html)
            if m:
                period = int(str(m.group(1))[3:])
                digits = ''.join(m.groups()[1:5])
                if valid(period, digits): return digits, period
            
            # 格式2: span标签
            period_m = re.search(r'第(\d{7})期开奖', html)
            num_ms = re.findall(r'qiu_red\">(\d)</span>', html)
            if period_m and len(num_ms) >= 5:
                period = int(str(period_m.group(1))[3:])
                digits = ''.join(num_ms[:4])
                if valid(period, digits): return digits, period
        except: continue
    return None, None
def fetch_500():
    try:
        html, _ = http_get('https://datachart.500.com/plw/history/newinc/history.php?start=26001&end=26999')
        if not html: return None, None
        rows = re.findall(r'(\d{5})\s+(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)', html)
        if rows:
            last = rows[-1]
            period = int(last[0])
            digits = ''.join(last[1:5])
            if valid(period, digits): return digits, period
    except Exception as e: log(f'  500网: {e}')
    return None, None

def fetch_sporttery():
    try:
        html, _ = http_get('https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=350133&provinceId=0&pageSize=1&isVerify=1&pageNo=1', timeout=10)
        if not html: return None, None
        data = json.loads(html)
        if data.get('errorCode') == '0':
            r = data.get('value', {}).get('list', [{}])[0]
            num = r.get('lotteryDrawResult', '').replace(' ', '')
            period = int(str(r.get('lotteryDrawNum', 0))[3:])
            if valid(period, num[:4]): return num[:4], period
    except: pass
    return None, None

def fetch_baidu():
    try:
        html, _ = http_get(f'https://www.baidu.com/s?wd={quote("排列5开奖结果")}', timeout=10)
        if not html: return None, None
        m = re.search(r'第\s*(\d{7})\s*期[\s\S]{0,50}?(\d)\s+(\d)\s+(\d)\s+(\d)', html)
        if m:
            period = int(str(m.group(1))[3:])
            digits = m.group(2)+m.group(3)+m.group(4)+m.group(5)
            if valid(period, digits): return digits, period
    except: pass
    return None, None

def fetch_bing():
    try:
        html, _ = http_get(f'https://www.bing.com/search?q={quote("排列5 开奖号码")}', timeout=10)
        if not html: return None, None
        m = re.search(r'(\d{7})\s*期[\s\S]{0,30}?(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)', html)
        if m:
            period = int(str(m.group(1))[3:])
            digits = m.group(2)+m.group(3)+m.group(4)+m.group(5)
            if valid(period, digits): return digits, period
    except: pass
    return None, None

def fetch_cache():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
            records = d.get('records', [])
            if records:
                r = records[0]
                n = f'{r.get("n1","")}{r.get("n2","")}{r.get("n3","")}{r.get("n4","")}'
                return n, r.get('period', 0)
    except: pass
    return None, None

# ==========================================
# GitHub API
# ==========================================
def github_get(path):
    token = os.environ.get('GH_TOKEN', '')
    req = Request(f'https://api.github.com/repos/{REPO}/contents/{path}',
                  headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'})
    resp = urlopen(req, timeout=30, context=ctx)
    info = json.loads(resp.read().decode())
    return info['sha'], json.loads(base64.b64decode(info['content']).decode('utf-8'))

def github_put(path, content, sha, msg):
    token = os.environ.get('GH_TOKEN', '')
    b64 = base64.b64encode(json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')).decode('utf-8')
    payload = {'message': msg, 'content': b64, 'sha': sha}
    req = Request(f'https://api.github.com/repos/{REPO}/contents/{path}',
                  data=json.dumps(payload).encode('utf-8'),
                  headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json',
                           'Content-Type': 'application/json'}, method='PUT')
    resp = urlopen(req, timeout=30, context=ctx)
    return json.loads(resp.read().decode())

# ==========================================
# 主流程
# ==========================================
def main():
    log(f'===== 四数关系 v11 | {REPO} =====')
    
    sha, data = github_get(DATA_FILE)
    records = data.get('records', [])
    
    # 找最大期号
    max_period = max((r['period'] for r in records), default=0)
    log(f'当前最大期号: {max_period}')
    
    # 计算今天应该追到哪一期（期号规则：26131 = 2026-05-21）
    base = datetime(2026, 5, 21, tzinfo=TZ)
    today = datetime.now(TZ)
    expected = 26131 + (today - base).days
    log(f'预期今日期号: {expected}')
    
    # 找最新一期，如果已开奖则更新下一期
    if records:
        latest = records[0]  # 降序，第一条是最新的
        latest_period = latest['period']
        
        # 检查最新期是否已有数据
        n1, n2, n3, n4 = latest.get('n1'), latest.get('n2'), latest.get('n3'), latest.get('n4')
        if n1 is not None and n2 is not None and n3 is not None and n4 is not None:
            # 最新期已有数据，需要获取下一期
            target_period = latest_period + 1
            log(f'最新期 {latest_period} 已有数据，获取 {target_period}')
        else:
            target_period = latest_period
            log(f'最新期 {latest_period} 无数据，获取本期')
    else:
        target_period = expected
        log(f'无数据，从 {target_period} 开始')
    
    # 7源降级
    sources = [
        ('江苏体彩网', fetch_js_lottery),
        ('彩经网移动端', fetch_cjcp),
        ('500彩票网', fetch_500),
        ('体彩官方API', fetch_sporttery),
        ('百度搜索', fetch_baidu),
        ('必应搜索', fetch_bing),
        ('缓存兜底', fetch_cache),
    ]
    
    result = None
    for name, fn in sources:
        try:
            log(f'尝试: {name}')
            w, p = fn()
            if w and p:
                if abs(p - target_period) > 5:
                    log(f'  期号不符 (获取{p}, 目标{target_period})')
                    continue
                result = (w, p, name)
                log(f'  ✅ {name}: 期{p} 号码{w}')
                break
        except Exception as e:
            log(f'  ❌ {e}')
    
    if not result:
        log('❌ 全部失败')
        sys.exit(1)
    
    winning4, period, source = result
    
    # 写入数据
    n1, n2, n3, n4 = int(winning4[0]), int(winning4[1]), int(winning4[2]), int(winning4[3])
    today_str = datetime.now(TZ).strftime('%Y-%m-%d')
    
    # 查找或创建记录
    existing = {r['period']: r for r in records}
    if period in existing:
        r = existing[period]
        r['n1'], r['n2'], r['n3'], r['n4'] = n1, n2, n3, n4
        r['date'] = today_str
        log(f'更新 {period} 期')
    else:
        records.append({
            'period': period,
            'date': today_str,
            'n1': n1, 'n2': n2, 'n3': n3, 'n4': n4
        })
        log(f'新增 {period} 期')
    
    # 降序 + 限制100条
    records.sort(key=lambda r: r['period'], reverse=True)
    if len(records) > 100:
        records = records[:100]
    data['records'] = records
    data['lastUpdate'] = int(datetime.now().timestamp() * 1000)
    data['version'] = int(time.time())
    
    # 推送
    try:
        r = github_put(DATA_FILE, data, sha, f'更新开奖号码: {winning4} (期{period}, 源{source})')
        log(f'✅ 数据已推送: {r["content"]["sha"][:8]}')
    except Exception as e:
        log(f'❌ 推送失败: {e}')
        sys.exit(1)
    
    log(f'===== 完成: 期{period} 号码{winning4} ({source}) =====')

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        log(f'❌ {traceback.format_exc()}')
        sys.exit(1)
