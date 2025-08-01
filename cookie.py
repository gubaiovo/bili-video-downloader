import requests
from http.cookiejar import LWPCookieJar
import qrcode
import os
import time
import re
from urllib.parse import unquote
from typing import Optional
import json

# COOKIE_FILE = "bilibili_cookies.txt"

COOKIES_DIR = "cookies"
COOKIE_FILE = os.path.join(COOKIES_DIR, "bilibili_cookies.txt")
JSON_COOKIE_FILE = os.path.join(COOKIES_DIR, "bilibili_cookies.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

class BilibiliQRLogin:
    def __init__(self):
        self.session = requests.Session()
        self.cookie_jar = LWPCookieJar(COOKIE_FILE)
        self.bili_jct: Optional[str] = None
        
        self.session.cookies = self.cookie_jar
        
        os.makedirs(COOKIES_DIR, exist_ok=True)
        # 如果cookie文件存在则尝试加载
        if os.path.exists(COOKIE_FILE):
            try:
                self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
                print("检测到已保存的Cookie文件，尝试恢复登录状态...")
                
                # 将cookie加载到session
                for cookie in self.cookie_jar:
                    self.session.cookies.set_cookie(cookie)
            except Exception as e:
                print(f"加载Cookie文件出错: {e}")
    
    def is_logged_in(self) -> bool:
        """检查登录状态"""
        try:
            response = self.session.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=HEADERS,
                timeout=10
            )
            data = response.json()
            if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                print(f"登录状态有效! 用户名: {data['data']['uname']}")
                return True
            print("登录状态无效，需要重新登录")
            return False
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False
    
    def generate_qr_code(self, url: str) -> None:
        """生成二维码并保存为文件"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 使用文件对象保存
            with open("bilibili_qrcode.png", "wb") as f:
                img.save(f)
            
            print("二维码已保存为: bilibili_qrcode.png")
            print("请使用B站手机APP扫描二维码登录")
        except Exception as e:
            print(f"生成二维码失败: {e}")
            print(f"请手动访问以下链接登录: {url}")
    
    def qr_login(self) -> bool:
        """扫码登录主流程"""
        if self.is_logged_in():
            self.show_cookies()
            self.convert_cookies_for_playwright()
            return True
            
        print("需要登录，正在获取二维码...")
        
        try:
            # 获取二维码信息
            response = self.session.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?source=main-fe-header",
                headers=HEADERS,
                timeout=10
            )
            data = response.json()
            
            if data.get("code") != 0:
                print(f"获取二维码失败: {data.get('message')}")
                return False
                
            qrcode_url = data["data"]["url"]
            qrcode_key = data["data"]["qrcode_key"]
            
            # 生成二维码图片
            self.generate_qr_code(qrcode_url)
            
            # 轮询扫码状态
            print("等待扫码... (按Ctrl+C取消)")
            start_time = time.time()
            timeout = 180  # 3分钟超时
            
            while time.time() - start_time < timeout:
                try:
                    response = self.session.get(
                        f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}&source=main-fe-header",
                        headers=HEADERS,
                        timeout=10
                    )
                    data = response.json()
                    
                    if data["code"] != 0:
                        print(f"状态检查失败: {data.get('message')}")
                        time.sleep(2)
                        continue
                    
                    status = data["data"]["code"]
                    message = data["data"]["message"]
                    
                    if status == 0:  # 登录成功
                        # 获取cookie
                        confirm_url = data["data"]["url"]
                        self.session.get(confirm_url, headers=HEADERS, timeout=10)
                        
                        # 保存cookie到文件
                        self.cookie_jar.save(filename=COOKIE_FILE, ignore_discard=True, ignore_expires=True)
                        print("登录成功! Cookie已保存")
                        
                        # 提取bili_jct
                        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                            cookies = f.read()
                        match = re.search(r"bili_jct=([^;]+)", cookies)
                        if match:
                            self.bili_jct = match.group(1)
                        else:
                            print("警告: 未在Cookie中找到bili_jct")
                        
                        # 显示用户信息
                        self.is_logged_in()
                        self.show_cookies()
                        
                        # 转换为Playwright可用的JSON格式
                        self.convert_cookies_for_playwright()
                        return True
                    
                    elif status == 86101:  # 未扫码
                        print(f"状态: {message}")
                    elif status == 86090:  # 已扫码未确认
                        print(f"状态: {message} - 请在手机APP上确认登录")
                    elif status == 86038:  # 二维码过期
                        print(f"状态: {message}")
                        return False
                    else:
                        print(f"未知状态: {message}")
                    
                    time.sleep(2)
                except Exception as e:
                    print(f"状态检查出错: {e}")
                    time.sleep(2)
            
            print("登录超时，请重试")
            return False
        except Exception as e:
            print(f"登录过程中出错: {e}")
            return False
    
    def convert_cookies_for_playwright(self) -> None:
        """将LWPCookieJar格式转换为Playwright可用的JSON格式"""
        if not hasattr(self, 'cookie_jar') or not self.cookie_jar:
            print("未找到CookieJar对象，无法转换")
            return
        
        playwright_cookies = []
        
        # 直接从CookieJar对象获取Cookie
        for cookie in self.cookie_jar:
            # 创建Playwright兼容的cookie对象
            playwright_cookie = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires,  # 已经是时间戳格式
                "httpOnly": False,  # 标准库不提供此信息，设为False
                "secure": cookie.secure,
                "sameSite": "Lax"  # B站cookie通常使用Lax
            }
            
            # 如果expires为0，表示会话Cookie，设为None
            if playwright_cookie["expires"] == 0:
                playwright_cookie["expires"] = None
            
            playwright_cookies.append(playwright_cookie)
        
        # 保存为JSON文件
        with open(JSON_COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(playwright_cookies, f, indent=2, ensure_ascii=False)
        
        print(f"Cookie已转换为Playwright兼容格式并保存到 {JSON_COOKIE_FILE}")
        print(f"转换了 {len(playwright_cookies)} 个Cookie")
    
    def show_cookies(self) -> None:
        """显示已保存的Cookie"""
        if not os.path.exists(COOKIE_FILE):
            print("未找到Cookie文件")
            return
            
        print("\n保存的Cookie内容:")
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                # 解码URL编码的特殊字符
                decoded_line = unquote(line.strip())
                print(decoded_line)
    
    def logout(self) -> bool:
        """注销登录"""
        # 尝试获取bili_jct
        if not self.bili_jct:
            # 尝试从cookie文件读取bili_jct
            if os.path.exists(COOKIE_FILE):
                with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                    cookies = f.read()
                match = re.search(r"bili_jct=([^;]+)", cookies)
                if match:
                    self.bili_jct = match.group(1)
        
        if not self.bili_jct:
            print("未找到bili_jct，无法注销")
            return False
        
        try:
            response = self.session.post(
                "https://passport.bilibili.com/login/exit/v2",
                headers=HEADERS,
                data={"biliCSRF": self.bili_jct},
                timeout=10
            )
            data = response.json()
            
            if data.get("code") == 0:
                print("注销成功")
                # 删除cookie文件
                if os.path.exists(COOKIE_FILE):
                    os.remove(COOKIE_FILE)
                    print("Cookie文件已删除")
                if os.path.exists(JSON_COOKIE_FILE):
                    os.remove(JSON_COOKIE_FILE)
                    print("JSON Cookie文件已删除")
                self.bili_jct = None
                return True
            else:
                print(f"注销失败: {data.get('message')}")
                return False
        except Exception as e:
            print(f"注销过程中出错: {e}")
            return False

def main():
    login = BilibiliQRLogin()
    
    while True:
        print("\n===== B站扫码登录工具 =====")
        print("1. 扫码登录并获取Cookie")
        print("2. 显示当前登录状态")
        print("3. 显示保存的Cookie")
        print("4. 转换为Playwright格式Cookie")
        print("5. 注销登录")
        print("6. 退出")
        
        choice = input("请选择操作: ").strip()
        
        if choice == "1":
            login.qr_login()
        elif choice == "2":
            login.is_logged_in()
        elif choice == "3":
            login.show_cookies()
        elif choice == "4":
            login.convert_cookies_for_playwright()
        elif choice == "5":
            if login.is_logged_in():
                confirm = input("确定要注销吗? (y/n): ").strip().lower()
                if confirm == "y":
                    login.logout()
            else:
                print("当前未登录")
        elif choice == "6":
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()