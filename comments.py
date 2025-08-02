import os
import re
from urllib.parse import urlparse, unquote
from http.cookiejar import LWPCookieJar
import requests
from tqdm import tqdm
import json
import datetime

COOKIES_DIR = "cookies"
COOKIE_FILE = os.path.join(COOKIES_DIR, "bilibili_cookies.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

DOWNLOADS_DIR = "bilibili_downloads"

class BiliCommentsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.cookie_jar = LWPCookieJar(COOKIE_FILE)
        self._load_cookies()
        
    def _load_cookies(self):
        os.makedirs(COOKIES_DIR, exist_ok=True)
        if os.path.exists(COOKIE_FILE):
            try:
                self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
                for cookie in self.cookie_jar:
                    self.session.cookies.set_cookie(cookie)
                print("检测到已保存的Cookie文件，已加载登录状态")
            except Exception as e:
                print(f"加载Cookie文件出错: {e}")
                
    def is_logged_in(self) -> bool:
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
            print("登录状态无效，将以游客身份下载(可能无法下载高画质视频)")
            return False
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False
        
    def _bv_parser(self, text: str) -> str:
        bv_pattern = re.compile(r'^BV[0-9A-Za-z]+$')
        if bv_pattern.fullmatch(text):
            return f"bvid={text}"
        
        parsed_url = urlparse(text)
        path_parts: list = parsed_url.path.split('/')  
        for part in path_parts:
            if bv_pattern.fullmatch(part):
                return f"bvid={part}"
        return ""
    
    def _get_video_aid(self, bv: str) -> tuple[str, str]:
        interface_url: str = f"https://api.bilibili.com/x/web-interface/view?{bv}"
        try:
            raw_response = self.session.get(interface_url, headers=HEADERS)
            raw_response.raise_for_status()
            data = raw_response.json().get("data", {})
            if not data:
                print("获取视频数据失败")
                return "", ""
            return str(data.get("aid", "")), data.get("title", "无标题")
        except Exception as e:
            print(f"请求视频信息失败: {e}")
            return "", ""
        
    def _get_comments(self, oid: str, page: int, page_size: int, sort: int) -> dict:
        params = {
            "type": 1, 
            "oid": oid,
            "pn": page,
            "ps": page_size,
            "sort": sort
        }
        try:
            response = self.session.get(
                "https://api.bilibili.com/x/v2/reply",
                params=params,
                headers=HEADERS,
                timeout=10
            )
            # print(f"LOG: 请求评论数据: {response.url}")
            response.raise_for_status()
            return response.json()  
        except Exception as e:
            print(f"请求评论数据失败: {e}")
            return {}
        
    def save_comments_to_json(self, comments: dict, filename: str):
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=4)
            print(f"评论数据已保存到 {filename}")
        except Exception as e:
            print(f"保存评论数据失败: {e}")
            
    def save_comments_to_txt(self, comments_data: dict, filename: str):
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        if comments_data.get("code") != 0:
            error_msg = f"错误: {comments_data.get('message', '未知错误')}"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(error_msg)
                print(f"评论错误信息已保存到: {filename}")
            except Exception as e:
                print(f"保存评论错误信息失败: {e}")
            return
            
        data = comments_data.get("data", {})
        
        output_lines = []
        current_page = data.get("page", {}).get("num", 1)
        
        page_info = data.get("page", {})
        output_lines.append(f"====== 评论信息 (第 {current_page} 页) ======")
        output_lines.append(f"页码: {current_page}/{page_info.get('count', 1)}")
        output_lines.append(f"总计评论数: {page_info.get('acount', 0)}")
        output_lines.append(f"根评论数: {page_info.get('count', 0)}")
        output_lines.append("")
         
        upper = data.get("upper", {})
        if upper and upper.get("top"):
            top_comment = upper["top"]
            output_lines.append(f"====== 置顶评论 ======")
            output_lines.append(f"用户: {top_comment['member']['uname']}")
            output_lines.append(f"内容: {top_comment['content']['message']}")
            output_lines.append(f"点赞数: {top_comment['like']}")
            output_lines.append(f"时间: {self._format_time(top_comment['ctime'])}")
            output_lines.append("")
        
        hots = data.get("hots", [])
        if hots:
            output_lines.append("====== 热门评论 ======")
            for i, hot in enumerate(hots, 1):
                output_lines.append(f"{i}. {hot['member']['uname']}: {hot['content']['message']} (👍 {hot['like']})")
            output_lines.append("")
        
        replies = data.get("replies", [])
        if replies:
            output_lines.append("====== 普通评论 ======")
            for i, reply in enumerate(replies, 1):
                output_lines.append(f"{i}. {reply['member']['uname']}: {reply['content']['message']} (👍 {reply['like']})")
        
        
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            print(f"评论已保存到: {filename}")
        except Exception as e:
            print(f"保存评论失败: {e}")
            
    def _format_time(self, timestamp: int) -> str:
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    def _sanitize_filename(self, filename: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', '', filename)
    
    def _parse_page_range(self, input_str: str, total_pages: int) -> list[int]:
        pages: list[int] = []
        try:
            parts = input_str.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    pages.extend(range(start, end+1))
                else:
                    pages.append(int(part))
            pages = sorted(set(pages))
            return [p for p in pages if 1 <= p <= total_pages]
        except Exception as e:
            print(f"解析页码范围失败: {e}")
            return []
    
    def _get_page_count(self, comments_data: dict, page_size: int) -> int:
        data: dict = comments_data.get("data", {})
        page_info = data.get("page", {})
        total_comments = page_info.get("count", 0)
        return max(1, (total_comments + page_size - 1) // page_size)
        
        
        
        
    def run(self):
        self.is_logged_in()
        while True:
            bv = input("请输入视频BV号或链接(输入q退出): ").strip()
            if bv.lower() == 'q':
                return
                
            bv = unquote(bv)
            bv_param = self._bv_parser(bv)
            if not bv_param:
                print("输入格式不正确，请重新输入")
                continue
                
            aid, title = self._get_video_aid(bv_param)
            if not aid:
                print("获取视频AID失败，请检查输入是否正确")
                continue
                
            print(f"视频AID: {aid}, 标题: {title}")
            
            
            safe_title = self._sanitize_filename(title)
            if not safe_title:
                safe_title = "无标题"
                
            
            comment_dir = os.path.join(DOWNLOADS_DIR, safe_title, "comments")
            os.makedirs(comment_dir, exist_ok=True)
            
            page_size = 20
            first_page = self._get_comments(oid=aid, page=1, page_size=page_size, sort=1)
            if not first_page or first_page.get("code") != 0:
                print("获取评论失败，请检查输入是否正确")
                continue
                
            total_pages = self._get_page_count(first_page, page_size)
            print(f"视频共 {total_pages} 页")
            
            while True:
                page_input = input("请输入要下载的页数范围(如: 1, 1-3, 1,3,5, 或输入all下载全部): ").strip()
                if page_input.lower() == 'all':
                    pages_to_download = list(range(1, total_pages + 1))
                    break
                elif page_input:
                    pages_to_download = self._parse_page_range(page_input, total_pages)
                    if pages_to_download:
                        break
                print(f"请输入有效的页数范围(1-{total_pages})")
            
            print(f"准备下载第 {', '.join(map(str, pages_to_download))} 页评论...")
            txt_filename = os.path.join(comment_dir, f"{safe_title}.txt")
            open(txt_filename, 'w', encoding='utf-8').close()
            for page_num in tqdm(pages_to_download, desc="下载评论页"):
                if page_num == 1:
                    comments = first_page  
                else:
                    comments = self._get_comments(oid=aid, page=page_num, page_size=page_size, sort=1)
                
                if not comments or comments.get("code") != 0:
                    print(f"获取第 {page_num} 页评论失败，跳过")
                    continue
                    
                json_filename = os.path.join(comment_dir, f"{safe_title}_page{page_num}.json")
                
                self.save_comments_to_json(comments, json_filename)
                self.save_comments_to_txt(comments, txt_filename)
            
            print(f"所有选择的评论页已保存到目录: {comment_dir}")

            
            
            
def main():
    fetcher = BiliCommentsFetcher()
    fetcher.run()

if __name__ == "__main__":
    main()