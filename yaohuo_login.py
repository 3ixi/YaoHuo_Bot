#!/usr/bin/env python3
"""
妖火论坛自动登录脚本
使用滑块验证模块获取verificationToken后进行登录
作者：3iXi
创建时间：2025/06/25
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from yaohuo_slider_captcha import SliderCaptchaSolver

class YaohuoLogin:
    def __init__(self):
        self.base_url = "https://www.yaohuo.me"
        self.headers = {
            "Host": "www.yaohuo.me",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Origin": "https://www.yaohuo.me",
            "Content-Type": "application/x-www-form-urlencoded",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Referer": "https://www.yaohuo.me/WapLogin.aspx",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        
    def get_credentials(self) -> Tuple[str, str]:
        """从环境变量获取登录凭据"""
        yaohuo_env = os.getenv("yaohuo")
        if not yaohuo_env:
            raise ValueError("环境变量 'yaohuo' 未设置")

        try:
            username, password = yaohuo_env.split("&", 1)
            return username, password
        except ValueError:
            raise ValueError("环境变量 'yaohuo' 格式错误，应为 'username&password'")

    def update_config_token(self, token: str, expires: Optional[str] = None) -> bool:
        """更新配置文件中的token值"""
        try:
            # 获取脚本所在目录的绝对路径
            script_dir = Path(__file__).parent.absolute()
            config_path = script_dir / "yaohuo_config.json"

            # 读取现有配置或创建新配置
            config = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"读取配置文件失败，将创建新配置: {e}")
                    config = {}

            # 更新token信息
            config['token'] = token
            if expires:
                config['expires'] = expires

            # 写入配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            print(f"✅ 配置文件已更新: {config_path}")
            print(f"Token: {token}")
            if expires:
                print(f"过期时间: {expires}")

            return True

        except Exception as e:
            print(f"❌ 更新配置文件失败: {e}")
            return False
    
    def format_gmt_to_china_time(self, gmt_time_str: str) -> str:
        """将GMT时间格式化为中国当地时间"""
        try:
            # 解析GMT时间字符串，例如: "Thu, 25-Jun-2026 07:44:06 GMT"
            # 移除GMT后缀
            time_part = gmt_time_str.replace(" GMT", "")
            
            # 解析时间
            dt = datetime.strptime(time_part, "%a, %d-%b-%Y %H:%M:%S")
            
            # 设置为UTC时区
            dt_utc = dt.replace(tzinfo=timezone.utc)
            
            # 转换为中国时区 (UTC+8)
            china_tz = timezone(timedelta(hours=8))
            dt_china = dt_utc.astimezone(china_tz)
            
            # 格式化为指定格式
            return dt_china.strftime("%Y/%m/%d %H:%M:%S")
        except Exception as e:
            print(f"时间格式化失败: {e}")
            return gmt_time_str
    
    def extract_cookie_info(self, set_cookie_header: str) -> Tuple[Optional[str], Optional[str]]:
        """从Set-Cookie头中提取sidyaohuo值和expires时间"""
        sidyaohuo_value = None
        expires_time = None
        
        # 查找sidyaohuo cookie
        sidyaohuo_match = re.search(r'sidyaohuo=([^;]+)', set_cookie_header)
        if sidyaohuo_match:
            sidyaohuo_value = sidyaohuo_match.group(1)
        
        # 查找expires时间
        expires_match = re.search(r'expires=([^;]+)', set_cookie_header)
        if expires_match:
            expires_gmt = expires_match.group(1)
            expires_time = self.format_gmt_to_china_time(expires_gmt)
        
        return sidyaohuo_value, expires_time

    def extract_error_message(self, html_content: str) -> str:
        """从HTML响应中提取错误信息"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找 <div class="tip"> 元素
            tip_div = soup.find('div', class_='tip')

            if tip_div:
                # 提取文字内容并去除前后空白
                error_message = tip_div.get_text(strip=True)
                return error_message
            else:
                return "未找到错误信息"

        except Exception as e:
            return f"解析错误信息失败: {e}"

    def get_session_cookies_from_solver(self, solver) -> str:
        """从滑块验证器获取Cookie字符串"""
        if hasattr(solver, 'session_cookies') and solver.session_cookies:
            cookie_parts = []
            for name, value in solver.session_cookies.items():
                cookie_parts.append(f"{name}={value}")
            return "; ".join(cookie_parts)
        return ""

    async def login(self, verification_token: str, solver=None) -> bool:
        """执行登录请求"""
        try:
            # 获取登录凭据
            username, password = self.get_credentials()
            
            # 构建登录数据
            login_data = {
                "logname": username,
                "logpass": password,
                "action": "login",
                "classid": "0",
                "siteid": "1000",
                "backurl": "",
                "savesid": "0",
                "gocaptchaToken": verification_token,
                "captchaType": "gocaptcha"
            }
            
            # 将数据编码为URL编码格式
            payload = "&".join([f"{k}={v}" for k, v in login_data.items()])
            
            # 动态计算Content-Length
            content_length = len(payload.encode('utf-8'))
            
            # 更新headers中的Content-Length
            headers = self.headers.copy()
            headers["Content-Length"] = str(content_length)

            # 添加从滑块验证器获取的Cookie
            if solver:
                session_cookies = self.get_session_cookies_from_solver(solver)
                if session_cookies:
                    headers["Cookie"] = session_cookies
                    print(f"使用Cookie: {session_cookies}")

            print(f"登录用户: {username}")
            print(f"验证Token: {verification_token}")
            print(f"请求数据长度: {content_length}")
            
            # 发起登录请求
            async with httpx.AsyncClient(http2=True, verify=False) as client:
                response = await client.post(
                    f"{self.base_url}/waplogin.aspx",
                    headers=headers,
                    content=payload
                )
                
                print(f"响应状态码: {response.status_code}")
                print(f"响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    # 检查Set-Cookie头
                    set_cookie_headers = response.headers.get_list("set-cookie")
                    
                    for cookie_header in set_cookie_headers:
                        if "sidyaohuo=" in cookie_header:
                            sidyaohuo_value, expires_time = self.extract_cookie_info(cookie_header)

                            if sidyaohuo_value:
                                print(f"\n🎉 登录成功！")
                                print(f"sidyaohuo值: {sidyaohuo_value}")
                                if expires_time:
                                    print(f"Cookie过期时间: {expires_time}")

                                # 更新配置文件中的token
                                print(f"\n📝 更新配置文件...")
                                config_updated = self.update_config_token(sidyaohuo_value, expires_time)
                                if config_updated:
                                    print("✅ Token已保存到配置文件")
                                else:
                                    print("⚠️ Token保存失败，但登录成功")

                                return True
                    
                    print("❌ 登录失败：未找到sidyaohuo cookie")
                    # 提取并显示错误信息
                    error_message = self.extract_error_message(response.text)
                    print(f"错误信息: {error_message}")
                    return False
                else:
                    print(f"❌ 登录请求失败，状态码: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"登录过程中出错: {e}")
            return False
    
    async def auto_login(self) -> bool:
        """自动完成滑块验证并登录"""
        print("🚀 开始自动登录流程...")
        
        # 1. 获取验证Token
        print("\n📝 步骤1: 获取滑块验证Token...")
        solver = SliderCaptchaSolver()
        verification_token = await solver.solve_captcha()
        
        if not verification_token:
            print("❌ 获取验证Token失败")
            return False
        
        print(f"✅ 成功获取验证Token: {verification_token}")
        
        # 2. 执行登录
        print("\n🔐 步骤2: 执行登录...")
        login_success = await self.login(verification_token, solver)

        return login_success


async def main():
    """主函数"""
    login_client = YaohuoLogin()
    success = await login_client.auto_login()
    
    if success:
        print("\n✅ 自动登录完成！")
    else:
        print("\n❌ 自动登录失败！")


if __name__ == "__main__":
    asyncio.run(main())
