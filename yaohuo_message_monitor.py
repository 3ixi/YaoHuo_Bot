#!/usr/bin/env python3
"""
妖火论坛私信监控脚本
自动获取新私信并推送通知
作者：3iXi
创建时间：2025/06/26
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

# 尝试导入 SendNotify，如果不存在则设置标志
try:
    from SendNotify import send
    SENDNOTIFY_AVAILABLE = True
    print("✅ SendNotify 模块加载成功，将启用推送通知")
except ImportError:
    SENDNOTIFY_AVAILABLE = False
    print("⚠️ 未找到 SendNotify.py 文件，将仅监控私信但不推送通知")
    print("   如需推送通知功能，请确保 SendNotify.py 文件存在于同一目录下")

import yaohuo_login


class YaohuoMessageMonitor:
    """妖火论坛私信监控器"""
    
    def __init__(self):
        self.base_url = "https://www.yaohuo.me"
        self.config_path = Path(__file__).parent.absolute() / "yaohuo_config.json"
        self.headers = {
            "Host": "www.yaohuo.me",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
    
    def load_config(self) -> Dict:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保message_history字段存在
                    if 'message_history' not in config:
                        config['message_history'] = []
                    return config
            else:
                # 创建默认配置
                default_config = {
                    "token": "",
                    "expires": "",
                    "message_history": []
                }
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {"token": "", "expires": "", "message_history": []}
    
    def save_config(self, config: Dict) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def clean_message_history(self, config: Dict) -> Dict:
        """清理消息历史记录，保持在100条以内"""
        message_history = config.get('message_history', [])
        
        if len(message_history) > 100:
            # 删除最早的70条记录
            config['message_history'] = message_history[70:]
            print(f"清理了70条旧记录，当前剩余{len(config['message_history'])}条")
        
        return config
    
    def add_message_to_history(self, config: Dict, message_id: str) -> Dict:
        """添加消息ID到历史记录"""
        if 'message_history' not in config:
            config['message_history'] = []
        
        if message_id not in config['message_history']:
            config['message_history'].append(message_id)
            print(f"添加消息ID到历史记录: {message_id}")
        
        return config
    
    def is_message_processed(self, config: Dict, message_id: str) -> bool:
        """检查消息是否已经处理过"""
        return message_id in config.get('message_history', [])
    
    async def get_message_list(self, token: str) -> Optional[str]:
        """获取私信列表页面"""
        url = f"{self.base_url}/bbs/messagelist.aspx"
        
        headers = self.headers.copy()
        headers["Cookie"] = f"sidyaohuo={token}"
        
        try:
            async with httpx.AsyncClient(http2=True, verify=False) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    return response.text
                else:
                    print(f"获取私信列表失败，状态码: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"请求私信列表时出错: {e}")
            return None
    
    def parse_message_list(self, html_content: str) -> Tuple[List[Dict], bool]:
        """
        解析私信列表页面
        
        Returns:
            Tuple[List[Dict], bool]: (新私信列表, 是否需要重新登录)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检查是否需要重新登录
            tip_div = soup.find('div', class_='tip')
            if tip_div and '/waplogin.aspx' in str(tip_div):
                print("检测到token过期，需要重新登录")
                return [], True
            
            # 查找私信元素
            message_elements = soup.find_all('div', class_=['listmms line1', 'listmms line2'])
            
            if not message_elements:
                print("未找到私信元素")
                return [], False
            
            new_messages = []
            
            for element in message_elements:
                # 检查是否有新消息标识
                new_img = element.find('img', src='/NetImages/new.gif', alt='新')
                if not new_img:
                    continue
                
                # 提取消息链接和ID
                link = element.find('a', href=True)
                if not link:
                    continue
                
                href = link.get('href')
                # 修正ID提取正则表达式
                id_match = re.search(r'[&?]id=(\d+)', href)
                if not id_match:
                    continue

                message_id = id_match.group(1)
                message_title = link.get_text(strip=True)

                # 提取发送者 - 使用正则表达式从HTML中提取
                html_str = str(element)
                sender_match = re.search(r'来自</span>([^<]+)', html_str)
                sender = sender_match.group(1).strip() if sender_match else "未知发送者"

                # 提取时间
                text_content = element.get_text()
                time_match = re.search(r'(\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2})', text_content)
                send_time = time_match.group(1) if time_match else "未知时间"
                
                new_messages.append({
                    'id': message_id,
                    'title': message_title,
                    'sender': sender,
                    'time': send_time,
                    'href': href
                })
            
            return new_messages, False
            
        except Exception as e:
            print(f"解析私信列表时出错: {e}")
            return [], False
    
    async def process_new_messages(self, new_messages: List[Dict], config: Dict) -> int:
        """处理新私信并发送通知"""
        processed_count = 0

        for message in new_messages:
            message_id = message['id']

            # 检查是否已经处理过
            if self.is_message_processed(config, message_id):
                print(f"消息ID {message_id} 已经处理过，跳过")
                continue

            print(f"发现新私信 - ID: {message_id}, 发送者: {message['sender']}, 标题: {message['title']}, 时间: {message['time']}")

            # 尝试发送通知
            notification_sent = False
            if SENDNOTIFY_AVAILABLE:
                title = f'[妖火]"{message["sender"]}"发来新私信'
                content = f"{message['title']}\n{message['time']}"

                try:
                    if send(title, content):
                        notification_sent = True
                        print(f"✅ 私信通知发送成功")
                    else:
                        print(f"❌ 私信通知发送失败")
                except Exception as e:
                    print(f"❌ 发送通知时出错: {e}")
            else:
                print(f"ℹ️ SendNotify 不可用，跳过推送通知")

            # 无论是否发送通知成功，都添加到历史记录
            config = self.add_message_to_history(config, message_id)
            processed_count += 1

            if SENDNOTIFY_AVAILABLE and notification_sent:
                print(f"📱 已处理并推送私信")
            else:
                print(f"📝 已记录私信（未推送）")

        return processed_count
    
    async def monitor_messages(self) -> bool:
        """监控私信的主函数"""
        print("🚀 开始监控妖火论坛私信...")

        # 显示通知状态
        if SENDNOTIFY_AVAILABLE:
            print("📱 推送通知功能：已启用")
        else:
            print("📝 推送通知功能：已禁用（未找到 SendNotify.py）")
            print("   将继续监控私信并记录到历史，但不会发送推送通知")

        # 加载配置
        config = self.load_config()
        
        # 清理历史记录
        config = self.clean_message_history(config)
        
        token = config.get('token', '')
        if not token:
            print("🔐 配置文件中没有token，开始自动登录...")
            login_client = yaohuo_login.YaohuoLogin()
            login_success = await login_client.auto_login()

            if login_success:
                print("✅ 自动登录成功，重新加载配置...")
                # 重新加载配置获取新token
                config = self.load_config()
                token = config.get('token', '')

                if not token:
                    print("❌ 登录成功但未获取到token")
                    return False
            else:
                print("❌ 自动登录失败")
                return False
        
        # 获取私信列表
        html_content = await self.get_message_list(token)
        if not html_content:
            print("❌ 获取私信列表失败")
            return False
        
        # 解析私信列表
        new_messages, need_relogin = self.parse_message_list(html_content)
        
        # 如果需要重新登录
        if need_relogin:
            print("🔐 Token过期，开始重新登录...")
            login_client = yaohuo_login.YaohuoLogin()
            login_success = await login_client.auto_login()
            
            if login_success:
                print("✅ 重新登录成功，重新获取私信列表...")
                # 重新加载配置获取新token
                config = self.load_config()
                token = config.get('token', '')
                
                # 重新获取私信列表
                html_content = await self.get_message_list(token)
                if html_content:
                    new_messages, _ = self.parse_message_list(html_content)
                else:
                    print("❌ 重新登录后仍无法获取私信列表")
                    return False
            else:
                print("❌ 重新登录失败")
                return False
        
        # 处理新私信
        if new_messages:
            processed_count = await self.process_new_messages(new_messages, config)
            
            # 保存配置
            self.save_config(config)
            
            print(f"✅ 本轮处理了 {processed_count} 条新私信")
        else:
            print("ℹ️ 本轮没有获取到新私信")
        
        return True


async def main():
    """主函数"""
    monitor = YaohuoMessageMonitor()
    success = await monitor.monitor_messages()
    
    if success:
        print("\n✅ 私信监控完成")
    else:
        print("\n❌ 私信监控失败")


if __name__ == "__main__":
    asyncio.run(main())
