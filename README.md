# 妖火论坛自动化操作脚本

## 文件说明

- `yaohuo_slider_captcha.py` - 滑块验证模块
- `yaohuo_login.py` - 自动登录模块
- `SendNotify.py` - 通知推送模块【自行准备，这里不提供】
- `yaohuo_config.json` - 配置文件（包含token和私信历史记录）【首次登录会自动创建】
- `yaohuo_message_monitor.py` - 站内私信监控脚本

[![43B2052BB48A8CA140F99513763BDC82.jpg](https://file.icve.com.cn/file_doc/270/129/43B2052BB48A8CA140F99513763BDC82.jpg)](https://file.icve.com.cn/file_doc/270/129/43B2052BB48A8CA140F99513763BDC82.jpg)

## 环境变量设置

在运行脚本前，需要设置环境变量 `yaohuo`
格式：`ID或手机号&密码`
仅支持单账号登录，且密码不能包含&符号

## 依赖安装

确保已安装所需的依赖：

```bash
pip install httpx[http2] opencv-python pillow numpy beautifulsoup4
```

## 配置文件结构

`yaohuo_config.json` 包含以下字段【首次登录会自动创建文件】：

```json
{
  "token": "登录token值",
  "expires": "token过期时间",
  "message_history": ["已推送的私信ID列表"]
}
```

## 脚本流程

1. **获取滑块验证Token**
   - 调用 `SliderCaptchaSolver` 类
   - 自动完成滑块验证
   - 获取 verificationToken

2. **执行登录请求**
   - 从环境变量获取用户名和密码
   - 构建登录请求数据
   - 发起 POST 请求到 `/waplogin.aspx`

3. **处理登录响应**
   - 提取响应头 Set-Cookie 参数中的 sidyaohuo 值
   - 格式化过期时间为中国当地时间

## 注意事项

1. 确保环境变量 `yaohuo` 格式正确
2. 网络连接稳定
3. 滑块验证**可能需要多次尝试**
4. 登录失败时会显示详细的错误信息