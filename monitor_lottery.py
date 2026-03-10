import os
import re
import requests
import telebot
from bs4 import BeautifulSoup

# --- 基础文件路径配置 ---
my_nums_file = '/home/shawn/lottery/my_num.txt'
result_file = "/home/shawn/lottery/zhongjianglema.txt"
state_file = "/home/shawn/lottery/lottery_state.txt" 

# 奖池资金开关：True 代表奖池 >= 8亿元，False 代表 < 8亿元
high_pool = False 

# --- 读取/初始化状态与配置 ---
if os.path.exists(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        parts = f.read().strip().split(',')
        if len(parts) >= 7:
            start_draw = parts[0]
            last_draw = parts[1]
            acc_draws = int(parts[2])
            acc_money = int(parts[3])
            pushdeer_key = parts[4]
            telegram_token = parts[5]
            telegram_chat_id = parts[6]
        else:
            print("配置文件格式错误，请检查或删除 lottery_state.txt 后重试。")
            exit()
else:
    start_draw = "26002"
    last_draw = "未知"
    acc_draws = 0
    acc_money = 0
    pushdeer_key = "***"
    telegram_token = "***"
    telegram_chat_id = "***"
    
    with open(state_file, 'w', encoding='utf-8') as f:
        f.write(f"{start_draw},{last_draw},{acc_draws},{acc_money},{pushdeer_key},{telegram_token},{telegram_chat_id}")
    print(f"首次运行，已自动创建配置文件：{state_file}。请前往该文件填入您的实际推送密钥。")

# --- 获取开奖数据与当前期数 (双引擎获取) ---
current_draw = "未知"
last_results = []
redball_numbers = []
blueball_numbers = []

def fetch_from_api():
    url = 'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&provinceId=0&pageSize=1&isVerify=1&pageNo=1'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://static.sporttery.cn/',
        'Origin': 'https://static.sporttery.cn',
        'Connection': 'keep-alive'
    }
    response = requests.get(url, headers=headers, timeout=10)
    data = response.json()
    latest_data = data.get("value", {}).get("list", [])[0]
    c_draw = latest_data.get("lotteryDrawNum")
    res_str = latest_data.get("lotteryDrawResult").split()
    return c_draw, res_str[:5], res_str[5:]

def fetch_from_500():
    # 换用全新的网页地址
    url = 'https://www.500.com/kaijiang/dlt/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    response = requests.get(url, headers=headers, timeout=10)
    
    # 自动识别编码，防止中文变成乱码导致正则失效
    response.encoding = response.apparent_encoding 
    if '期开机号' not in response.text:
        response.encoding = 'gbk' # 强制 fallback
        
    soup = BeautifulSoup(response.text, 'html.parser')
    page_text = soup.get_text()
    
    # 【核心修复 1】根据您提供的 "26024期开机号" 提取期数
    c_draw = "未知"
    text_match = re.search(r'(\d{5})\s*期开机号', page_text)
    if text_match:
        c_draw = text_match.group(1)
    else:
        # 备用容错提取
        all_draws = re.findall(r'(?<!\d)(\d{5})(?:\s*期)', page_text)
        valid_draws = [d for d in all_draws if d.startswith('2') and len(d) == 5]
        if valid_draws:
            c_draw = max(valid_draws)

    # 【核心修复 2】自适应提取最新的开奖号码（屏蔽下方的历史期数）
    # 模糊匹配包含 red/blue 的类名，并过滤出所有两位数
    red_nodes = soup.find_all(class_=re.compile(r'red|ball_red|redball', re.I))
    blue_nodes = soup.find_all(class_=re.compile(r'blue|ball_blue|blueball', re.I))
    
    reds = [n.text.strip() for n in red_nodes if n.text.strip().isdigit() and len(n.text.strip()) == 2]
    blues = [n.text.strip() for n in blue_nodes if n.text.strip().isdigit() and len(n.text.strip()) == 2]
    
    # 网页从上到下第一个就是最新一期，截取前 5 红 2 蓝
    if len(reds) >= 5 and len(blues) >= 2:
        reds = reds[:5]
        blues = blues[:2]
    else:
        raise Exception("未能抓取到新网页上的红蓝球节点")
            
    return c_draw, reds, blues

try:
    print("尝试通过官方 API 获取数据...")
    current_draw, redball_numbers, blueball_numbers = fetch_from_api()
    print("✅ 官方 API 获取成功！")
except Exception as api_e:
    print(f"⚠️ 官方 API 访问受阻 ({type(api_e).__name__})，正在切换至备用网页抓取通道...")
    try:
        current_draw, redball_numbers, blueball_numbers = fetch_from_500()
        print("✅ 备用通道获取成功！")
    except Exception as web_e:
        print(f"❌ 备用通道也获取失败: {web_e}")
        exit()

last_results = redball_numbers + blueball_numbers
print(f"当前开奖期数：{current_draw}")
print(f"本期开奖号码：{last_results}")

# --- 核心判定逻辑 ---
try:
    with open(my_nums_file, 'r', encoding='utf-8') as f:
        my_nums = f.readlines()
except FileNotFoundError:
    print(f"找不到号码文件: {my_nums_file}")
    exit()

win_num = 0
current_win_money = 0
text_title = "恭喜您中奖！本期中：\n"

with open(result_file, "w", encoding='utf-8') as f:
    for my_num in my_nums:
        my_num_str = my_num.strip()
        if not my_num_str: continue
        
        nums = my_num_str.split(',') if ',' in my_num_str else my_num_str.split()
        if len(nums) < 7: continue

        my_redballs = nums[:5]
        my_blueballs = nums[5:]
        
        r = len(set(my_redballs) & set(redball_numbers))
        b = len(set(my_blueballs) & set(blueball_numbers))
        
        result = "未中奖"
        money = "0"
        
        # 判定级别与金额 (新规七级)
        if r == 5 and b == 2:
            result, money = "一等奖", "浮动奖"
        elif r == 5 and b == 1:
            result, money = "二等奖", "浮动奖"
        elif (r == 5 and b == 0) or (r == 4 and b == 2):
            result, money = "三等奖", ("6666" if high_pool else "5000")
        elif r == 4 and b == 1:
            result, money = "四等奖", ("380" if high_pool else "300")
        elif (r == 4 and b == 0) or (r == 3 and b == 2):
            result, money = "五等奖", ("200" if high_pool else "150")
        elif (r == 3 and b == 1) or (r == 2 and b == 2):
            result, money = "六等奖", ("18" if high_pool else "15")
        elif (r == 3 and b == 0) or (r == 1 and b == 2) or (r == 2 and b == 1) or (r == 0 and b == 2):
            result, money = "七等奖", ("7" if high_pool else "5")
            
        money_display = f"{money}元" if money != "浮动奖" and money != "0" else money
        f.write(f"{my_num_str} : {result}({money_display})\n")
        
        if result != "未中奖":
            win_num += 1
            text_title += f"{result}({money_display}) 一注！\n"
            if money != "浮动奖":
                current_win_money += int(money)

# --- 更新累计状态并保存 ---
if current_draw != last_draw and current_draw != "未知":
    acc_draws += 1
    acc_money += current_win_money
    last_draw = current_draw
    
    with open(state_file, 'w', encoding='utf-8') as f:
        f.write(f"{start_draw},{last_draw},{acc_draws},{acc_money},{pushdeer_key},{telegram_token},{telegram_chat_id}")
else:
    print("提示：当前期数已统计过，或者未抓取到期数，累计数据不再增加。")

# --- 组装推送消息 ---
# 1. 开奖号码部分
part1 = f"【第{current_draw}期 开奖结果】\n"
part1 += f"号码：{'-'.join(redball_numbers)} + {'-'.join(blueball_numbers)}\n"
part1 += f"-----------------\n"

# 2. 本期中奖情况部分
if win_num == 0:
    part2 = "本期遗憾未中奖。\n"
else:
    part2 = text_title

part2 += "-----------------\n"

# 3. 累计数据部分
part3 = f"起始期数：第{start_draw}期\n"
part3 += f"已累计期数：{acc_draws}期\n"
part3 += f"已累计中奖：{acc_money}元\n"

# 合并消息
message = part1 + part2 + part3

print("-" * 30)
print(message)

# Telegram 推送
try:
    if telegram_token != "***" and telegram_chat_id != "***":
        tb = telebot.TeleBot(telegram_token)
        tb.send_message(telegram_chat_id, message)
        print("Telegram 推送已发送")
    else:
        print("Telegram 推送未配置，跳过发送。")
except Exception as e:
    print(f"TG推送失败: {e}")

# Pushdeer 推送
try:
    if pushdeer_key != "***":
        push_url = f"https://api2.pushdeer.com/message/push?pushkey={pushdeer_key}&text={message}"
        requests.post(push_url)
        print("Pushdeer 推送已发送")
    else:
        print("Pushdeer 推送未配置，跳过发送。")
except Exception as e:
    print(f"Pushdeer推送失败: {e}")