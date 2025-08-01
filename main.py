from cookie import BilibiliQRLogin
from download import BiliVideoDownloader


def main_menu():
    print("""
          ====== Bilibili Video Downloader ======
          1. 账号管理
          2. 视频下载
          3. 退出
          =======================================""")
    choice: int = int(input("请输入选项："))
    if choice == 1:
        user_menu()
    elif choice == 2:
        video_menu()
    elif choice == 3:
        exit()
    else:
        print("输入错误，请重新输入！")
        main_menu()

def user_menu():
    login = BilibiliQRLogin()
    print("""
          ====== Bilibili Video Downloader ======
          1. 扫码登陆并获取cookie
          2. 显示当前登陆状态
          3. 显示当前cookie
          4. 转换为Playwright格式Cookie
          5. 注销登录
          6. 上一步
          7. 退出
          =======================================""")
    choice: int = int(input("请输入选项："))
    if choice == 7:
        exit()
    elif choice == 6:
        main_menu()
    elif choice == 1:
        login.qr_login()
        user_menu()
    elif choice == 2:
        login.is_logged_in()
        user_menu()
    elif choice == 3:
        login.show_cookies()
        user_menu()
    elif choice == 4:
        login.convert_cookies_for_playwright()
        user_menu()
    elif choice == 5:
        if login.is_logged_in():
            confirm = input("确定要注销吗? (y/n): ").strip().lower()
            if confirm == "y":
                login.logout()
        else:
            print("当前未登录")
        user_menu()
    else:
        print("输入错误，请重新输入")
    
        
def video_menu():
    downloader = BiliVideoDownloader()
    print("""
          ====== Bilibili Video Downloader ======
          1. 下载视频
          2. 上一步
          =======================================""")
    choice: int = int(input("请输入选项："))
    if choice == 2:
        main_menu()
    elif choice == 1:
        downloader.download()
        video_menu()
    else:
        print("输入错误，请重新输入！")
        video_menu()
    
def main():
    main_menu()

if __name__ == "__main__":
    main()