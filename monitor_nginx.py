import os
import requests
import telebot
import socket
import time
from datetime import datetime

# --- 基础配置 ---
pushdeer_key = "use your key"
telegram_token = 'use your token'
telegram_chat_id = id

def check_nginx_status():
    # 方式：检查 systemd 服务状态
    # 如果服务是 active 状态，返回 0
    exit_code = os.system("systemctl is-active --quiet nginx")
    return exit_code == 0

def send_notifications(message):
    try:
        tb = telebot.TeleBot(telegram_token)
        tb.send_message(telegram_chat_id, message)
    except Exception as e:
        print(f"TG推送失败: {e}")

    try:
        push_url = "https://api2.pushdeer.com/message/push"
        payload = {"pushkey": pushdeer_key, "text": message}
        requests.post(push_url, data=payload)
    except Exception as e:
        print(f"Pushdeer推送失败: {e}")

def main():
    hostname = socket.gethostname()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 调试信息：运行脚本时你可以看到当前的判断结果
    is_running = check_nginx_status()
    print(f"[{now}] 正在检查 Nginx 状态... 运行中: {is_running}")

    if not is_running:
        print("检测到异常，尝试重启...")
        os.system("systemctl restart nginx")
        time.sleep(3)
        
        if check_nginx_status():
            send_notifications(f"✅ Nginx 自动修复成功\n主机: {hostname}\n时间: {now}")
        else:
            send_notifications(f"🚨 Nginx 自动修复失败！\n主机: {hostname}\n时间: {now}")

if __name__ == "__main__":
    main()