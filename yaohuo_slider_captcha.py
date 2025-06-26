#!/usr/bin/env python3
"""
妖火论坛 登录滑块验证自动化脚本
使用图像处理技术检测缺口位置并自动完成滑块验证
作者：3iXi
创建时间：2025/06/25
"""

import asyncio
import base64
import io
import re
import random
from typing import Optional

import httpx
import cv2
import numpy as np
from PIL import Image




class SliderCaptchaSolver:
    def __init__(self):
        self.base_url = "https://www.yaohuo.me"
        self.headers = {
            "Host": "www.yaohuo.me",
            "Connection": "keep-alive",
            "sec-ch-ua-platform": '"Windows"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Referer": "https://www.yaohuo.me/WapLogin.aspx",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        # 存储从第一次请求获取的Cookie
        self.session_cookies = {}

    def extract_cookies_from_response(self, response) -> dict:
        """从响应头中提取Cookie值"""
        cookies = {}
        set_cookie_headers = response.headers.get_list("set-cookie")

        for cookie_header in set_cookie_headers:
            # 提取ASP.NET_SessionId
            if "ASP.NET_SessionId=" in cookie_header:
                session_match = re.search(r'ASP\.NET_SessionId=([^;]+)', cookie_header)
                if session_match:
                    cookies['ASP.NET_SessionId'] = session_match.group(1)
                    print(f"提取到ASP.NET_SessionId: {cookies['ASP.NET_SessionId']}")

            # 提取_d_id
            if "_d_id=" in cookie_header:
                d_id_match = re.search(r'_d_id=([^;]+)', cookie_header)
                if d_id_match:
                    cookies['_d_id'] = d_id_match.group(1)
                    print(f"提取到_d_id: {cookies['_d_id']}")

        return cookies

    def get_cookie_header(self) -> str:
        """生成Cookie请求头字符串"""
        if not self.session_cookies:
            return ""

        cookie_parts = []
        for name, value in self.session_cookies.items():
            cookie_parts.append(f"{name}={value}")

        return "; ".join(cookie_parts)

    async def get_captcha_data(self) -> Optional[dict]:
        """获取滑块验证数据"""
        url = f"{self.base_url}/GoCaptchaProxy.ashx?path=get-data&id=slide-default"

        # 准备请求头
        headers = self.headers.copy()

        # 如果已有Cookie，添加到请求头中
        if self.session_cookies:
            cookie_header = self.get_cookie_header()
            if cookie_header:
                headers["Cookie"] = cookie_header
                print(f"会话保持Cookie: {cookie_header}")

        async with httpx.AsyncClient(http2=True, verify=False) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # 如果是第一次请求，提取Cookie
                if not self.session_cookies:
                    extracted_cookies = self.extract_cookies_from_response(response)
                    if extracted_cookies:
                        self.session_cookies.update(extracted_cookies)
                        print(f"已保存Cookie: {self.session_cookies}")

                data = response.json()

                if data.get("code") == 200:
                    return data.get("data")
                else:
                    print(f"获取验证数据失败: {data}")
                    return None

            except Exception as e:
                print(f"请求验证数据时出错: {e}")
                return None
    
    def base64_to_image(self, base64_str: str) -> np.ndarray:
        """将base64字符串转换为OpenCV图像"""
        # 移除data:image前缀
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        
        # 解码base64
        image_data = base64.b64decode(base64_str)
        
        # 转换为PIL图像
        pil_image = Image.open(io.BytesIO(image_data))
        
        # 转换为OpenCV格式
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        return cv_image
    


    def detect_gap_position_template(self, master_image: np.ndarray) -> int:
        """
        使用模板匹配方法检测缺口位置
        """
        # 转换为灰度图
        master_gray = cv2.cvtColor(master_image, cv2.COLOR_BGR2GRAY)

        # 多种方法尝试检测缺口
        methods = [
            self.detect_gap_by_edges,
            self.detect_gap_by_brightness,
            self.detect_gap_simple
        ]

        for method in methods:
            try:
                gap_x = method(master_gray)
                if gap_x > 0:  # 有效的缺口位置
                    print(f"使用方法 {method.__name__} 检测到缺口位置: {gap_x}")
                    return gap_x
            except Exception as e:
                print(f"方法 {method.__name__} 失败: {e}")
                continue

        # 所有方法都失败，返回默认值
        print("所有检测方法都失败，使用默认位置")
        return 150  # 默认位置

    def detect_gap_by_edges(self, master_gray: np.ndarray) -> int:
        """
        基于边缘检测的缺口检测
        """
        # 使用边缘检测
        edges = cv2.Canny(master_gray, 30, 100)

        # 查找轮廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 寻找可能的缺口区域
        gap_candidates = []
        height, width = master_gray.shape

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 缺口特征：宽度适中，高度适中，位置在图像中部
            if (30 < w < 100 and 30 < h < 100 and
                height * 0.2 < y < height * 0.8 and
                width * 0.2 < x < width * 0.8):
                gap_candidates.append((x, y, w, h))

        if gap_candidates:
            # 选择面积最大的候选缺口
            gap_candidates.sort(key=lambda x: x[2] * x[3], reverse=True)
            return gap_candidates[0][0]

        return 0

    def detect_gap_by_brightness(self, master_gray: np.ndarray) -> int:
        """
        基于亮度变化的缺口检测
        """
        height, width = master_gray.shape

        # 在图像中部区域寻找亮度异常
        middle_start = height // 3
        middle_end = height * 2 // 3

        # 计算每列的平均亮度
        col_brightness = []
        for x in range(width):
            col_avg = np.mean(master_gray[middle_start:middle_end, x])
            col_brightness.append(col_avg)

        # 寻找亮度突变点
        brightness_diff = np.diff(col_brightness)

        # 找到最大的负变化（从亮到暗）
        min_diff_idx = np.argmin(brightness_diff)

        # 验证这个位置是否合理
        if min_diff_idx > width * 0.1 and min_diff_idx < width * 0.9:
            return int(min_diff_idx)

        return 0

    def detect_gap_simple(self, master_gray: np.ndarray) -> int:
        """
        简单的缺口检测方法
        """
        height, _ = master_gray.shape

        # 在图像中间水平线上寻找亮度变化最大的位置
        middle_row = height // 2
        row_data = master_gray[middle_row, :]

        # 计算梯度
        gradient = np.gradient(row_data)

        # 找到梯度绝对值最大的位置
        max_gradient_idx = np.argmax(np.abs(gradient))

        return int(max_gradient_idx)

    def detect_gap_position(self, master_image: np.ndarray) -> int:
        """
        检测缺口位置的主方法
        """
        return self.detect_gap_position_template(master_image)
    
    def calculate_distance(self, captcha_data: dict) -> int:
        """计算滑块需要移动的距离"""
        try:
            # 解码图像
            master_image = self.base64_to_image(captcha_data["master_image_base64"])

            # 获取滑块当前位置和尺寸
            current_x = captcha_data["display_x"]
            current_y = captcha_data["display_y"]
            thumb_width = captcha_data["thumb_width"]
            thumb_height = captcha_data["thumb_height"]

            # 检测缺口位置
            gap_x = self.detect_gap_position(master_image)

            # 根据图片描述，需要计算滑块最右侧到缺口最左侧的距离
            # 滑块当前右侧位置
            slider_right = current_x + thumb_width

            # 计算需要移动的距离
            # 这里gap_x是缺口的左侧位置
            distance = gap_x - slider_right

            print(f"滑块当前位置: ({current_x}, {current_y})")
            print(f"滑块尺寸: {thumb_width}x{thumb_height}")
            print(f"滑块右侧位置: {slider_right}")
            print(f"检测到的缺口左侧位置: {gap_x}")
            print(f"计算出的移动距离: {distance}")

            # 添加一些随机偏移，模拟人工操作
            offset = random.randint(-2, 2)
            # 确保最终距离为整数
            final_distance = max(0, int(round(distance + offset)))

            print(f"添加随机偏移 {offset}，最终距离: {final_distance}")

            return final_distance

        except Exception as e:
            print(f"计算距离时出错: {e}")
            # 返回一个随机距离作为备选
            fallback_distance = random.randint(120, 180)
            print(f"使用备选距离: {fallback_distance}")
            return fallback_distance
    
    async def submit_verification(self, captcha_key: str, x: int, y: int) -> Optional[str]:
        """提交验证请求"""
        url = f"{self.base_url}/GoCaptchaProxy.ashx?path=check-data"

        payload = {
            "id": "slide-default",
            "captchaKey": captcha_key,
            "value": f"{x},{y}"
        }

        # 准备请求头
        headers = self.headers.copy()

        # 添加Cookie到请求头
        if self.session_cookies:
            cookie_header = self.get_cookie_header()
            if cookie_header:
                headers["Cookie"] = cookie_header

        async with httpx.AsyncClient(http2=True, verify=False) as client:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                print(f"验证响应: {data}")

                if data.get("code") == 200 and data.get("data") == "ok":
                    return data.get("verificationToken")
                else:
                    return None

            except Exception as e:
                print(f"提交验证时出错: {e}")
                return None
    
    async def solve_captcha(self) -> Optional[str]:
        """解决滑块验证"""
        max_attempts = 10
        max_cycles = 100  # 最大循环次数，防止无限循环
        
        for cycle in range(max_cycles):
            print(f"\n=== 第 {cycle + 1} 轮尝试 ===")
            
            for attempt in range(max_attempts):
                print(f"\n--- 尝试 {attempt + 1}/{max_attempts} ---")
                
                # 获取验证数据
                captcha_data = await self.get_captcha_data()
                if not captcha_data:
                    print("获取验证数据失败，等待3秒后重试...")
                    await asyncio.sleep(3)
                    continue
                
                # 计算移动距离
                distance = self.calculate_distance(captcha_data)
                
                # 提交验证
                verification_token = await self.submit_verification(
                    captcha_data["captcha_key"],
                    distance,
                    captcha_data["display_y"]
                )
                
                if verification_token:
                    print(f"\n🎉 验证成功！")
                    print(f"verificationToken: {verification_token}")
                    return verification_token
                else:
                    print(f"验证失败，等待3-5秒后重试...")
                    await asyncio.sleep(random.uniform(3, 5))
            
            # 10次尝试都失败了，等待3分钟
            print(f"\n⏰ 第 {cycle + 1} 轮的10次尝试都失败了，等待3分钟后继续...")
            await asyncio.sleep(180)  # 等待3分钟
        
        print("达到最大循环次数，停止尝试")
        return None


async def main():
    """主函数"""
    print("🚀 启动滑块验证自动化脚本...")
    
    solver = SliderCaptchaSolver()
    verification_token = await solver.solve_captcha()
    
    if verification_token:
        print(f"\n✅ 最终获取到的 verificationToken: {verification_token}")
    else:
        print("\n❌ 未能成功获取 verificationToken")


if __name__ == "__main__":
    asyncio.run(main())
