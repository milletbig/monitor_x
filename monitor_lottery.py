import requests
import telebot
from bs4 import BeautifulSoup

# --- 基础配置 ---
pushdeer_key = "use your key"
telegram_token = 'use your token'
telegram_chat_id = id
my_nums_file = '/home/lottery/my_num.txt'
result_file = "/home/lottery/zhongjianglema.txt"

# 【重要】奖池资金开关：True 代表奖池 >= 8亿元 (对应图片右侧奖金)，False 代表 < 8亿元
# 目前大乐透奖池通常都在 8 亿以上，建议保持为 True
high_pool = True 

# --- 获取开奖数据 ---
url = 'http://zx.500.com/dlt/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

try:
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    redballs = soup.find_all('li', {'class': 'redball'})
    blueballs = soup.find_all('li', {'class': 'blueball'})

    redball_numbers = [ball.text for ball in redballs]
    blueball_numbers = [ball.text for ball in blueballs]
    
    last_results = redball_numbers + blueball_numbers
    
    if not last_results:
        raise Exception("未获取到开奖号码")
        
    print(f"本期开奖号码：{last_results}")

except Exception as e:
    print(f"获取开奖信息失败: {e}")
    exit()

# --- 核心判定逻辑 ---
text_title = "恭喜您中奖！本期中：\n"
text_head = f"本期开奖号码：{'-'.join(redball_numbers)} + {'-'.join(blueball_numbers)}\n"
win_num = 0

try:
    with open(my_nums_file, 'r') as f:
        my_nums = f.readlines()
except FileNotFoundError:
    print(f"找不到号码文件: {my_nums_file}")
    exit()

with open(result_file, "w") as f:
    for my_num in my_nums:
        my_num_str = my_num.strip()
        if not my_num_str: continue
        
        # 兼容逗号或空格分隔
        if ',' in my_num_str:
            nums = my_num_str.split(',')
        else:
            nums = my_num_str.split()
            
        if len(nums) < 7: continue

        my_redballs = nums[:5]
        my_blueballs = nums[5:]
        
        # 计算匹配数
        r = len(set(my_redballs) & set(redball_numbers))
        b = len(set(my_blueballs) & set(blueball_numbers))
        
        print(f"号码:{my_num_str} -> 红:{r} 蓝:{b}")
        
        result = "未中奖"
        money = 0
        
        # 根据图片规则判定
        if r == 5 and b == 2:
            result = "一等奖"
            money = "浮动奖"
            
        elif r == 5 and b == 1:
            result = "二等奖"
            money = "浮动奖"
            
        # 三等奖 (5+0, 4+2)
        elif (r == 5 and b == 0) or (r == 4 and b == 2):
            result = "三等奖"
            money = "6,666元" if high_pool else "5,000元"
            
        # 四等奖 (4+1)
        elif r == 4 and b == 1:
            result = "四等奖"
            money = "380元" if high_pool else "300元"
            
        # 五等奖 (4+0, 3+2)
        elif (r == 4 and b == 0) or (r == 3 and b == 2):
            result = "五等奖"
            money = "200元" if high_pool else "150元"
            
        # 六等奖 (3+1, 2+2)
        elif (r == 3 and b == 1) or (r == 2 and b == 2):
            result = "六等奖"
            money = "18元" if high_pool else "15元"
            
        # 七等奖 (3+0, 1+2, 2+1, 0+2)
        elif (r == 3 and b == 0) or (r == 1 and b == 2) or (r == 2 and b == 1) or (r == 0 and b == 2):
            result = "七等奖"
            money = "7元" if high_pool else "5元"
            
        # 写入并统计
        f.write(f"{my_num_str} : {result}({money})\n")
        
        if result != "未中奖":
            win_num += 1
            text_title += f"{result}({money}) 一注！\n"

# --- 推送消息 ---
if win_num == 0:
    message = text_head + '本期遗憾未中奖。'
else:
    message = text_head + text_title

print("-" * 30)
print(message)

# Telegram 推送
try:
    tb = telebot.TeleBot(telegram_token)
    tb.send_message(telegram_chat_id, message)
except Exception as e:
    print(f"TG推送失败: {e}")

# Pushdeer 推送
try:
    push_url = f"https://api2.pushdeer.com/message/push?pushkey={pushdeer_key}&text={message}"
    requests.post(push_url)
except Exception as e:
    print(f"Pushdeer推送失败: {e}")