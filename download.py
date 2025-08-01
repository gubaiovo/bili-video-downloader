import re
import os
from tqdm import tqdm
import requests
from urllib.parse import urlparse, unquote
from http.cookiejar import LWPCookieJar

HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}
DOWNLOAD_INFO_RAW_URL = "https://api.bilibili.com/x/player/playurl?"
VIDEO_DATA_INTERFACE = "https://api.bilibili.com/x/web-interface/view?"

COOKIES_DIR = "cookies"
COOKIE_FILE = os.path.join(COOKIES_DIR, "bilibili_cookies.txt")
JSON_COOKIE_FILE = os.path.join(COOKIES_DIR, "bilibili_cookies.json")

class BiliVideoDownloader:
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
                headers=HEADER,
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
        # print(parsed_url)
        path_parts: list = parsed_url.path.split('/')  
        for part in path_parts:
            if bv_pattern.fullmatch(part):
                return f"bvid={part}"

        return ""
        
    def _video_data_get(self, bv: str) -> dict:
        json_response: dict = {}
        interface_url: str = f"https://api.bilibili.com/x/web-interface/view?{bv}"
        try:
            raw_response = self.session.get(interface_url, headers=HEADER)
            raw_response.raise_for_status()
            json_response = raw_response.json()
        except Exception as e:
            print(f"请求视频信息失败: {e}")
            return {}
        
        data: dict = json_response.get("data", {})
        if not data:
            print("获取视频数据失败")
            return {}
            
        up: dict = data.get("owner", {})
        pages: list = data.get("pages", [])
        page_list: list = []
        
        for page in pages:
            page_list.append({
                "page_number": page.get("page", 0), 
                "cid": page.get("cid", ""),
                "page_title": page.get("part", ""),
            })
            
        result: dict = {
            "bvid": data.get("bvid", ""),
            "aid": data.get("aid", ""),
            "title": data.get("title", ""),
            "pages_number": data.get("videos", 0),
            "up": up.get("name", ""),
            "up_url": f"https://space.bilibili.com/{up.get('mid', '')}",
            "pages": page_list
        }
        
        return result
            
    def print_video_data(self, video_data: dict):
        print(f"""
          ====== Bilibili Video Downloader ======
        标题: {video_data['title']}
        av号: {video_data['aid']}
        BV号: {video_data['bvid']}
        up: {video_data['up']}
        up主页: {video_data['up_url']}
        分P数: {video_data['pages_number']}
        分P列表: """)
        for page in video_data['pages']:
            print(f"            {page['page_number']}. {page['page_title']}  CID: {page['cid']}")
        print("          =======================================")
                
    def _get_download_info(self, video_data: dict, bv: str) -> list:
        download_info_list: list = []
        print("请输入要下载的分P序号, 多个分P用空格分隔, 输入q/Q退出")
        download_pages_required: str = input().strip()
        
        if download_pages_required.lower() == 'q':
            return []
        
        download_pages_list: list = download_pages_required.split()
        
        for page_number in download_pages_list:
            try:
                page_index = int(page_number) - 1
                if page_index < 0 or page_index >= len(video_data['pages']):
                    print(f"输入错误，分P序号{page_number}不存在")
                    continue
                    
                page_data = video_data['pages'][page_index]
                cid = page_data['cid']
                
                if video_data['pages_number'] == 1:
                    referer = f"https://www.bilibili.com/video/{bv}"
                else:
                    referer = f"https://www.bilibili.com/video/{bv}?p={page_number}"
                    
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
                    "Referer": referer
                }
                
                print(f"\n获取分P{page_number}支持的画质...")
                resp = self.session.get(
                    f"https://api.bilibili.com/x/player/playurl?{bv}&cid={cid}",
                    headers=headers
                )
                # print(f"log: {resp.url}")
                # print(f"log: {resp}")
                resp.raise_for_status()
                data = resp.json().get('data', {})
                # print(f"log: {data}")
                if not data:
                    print(f"分P{page_number}获取画质信息失败")
                    continue
                    
                format_list = data.get('support_formats', [])
                if not format_list:
                    print(f"分P{page_number}没有可用的画质选项")
                    continue
                    
                print(f"\n为分P{page_number}选择画质:")
                quality, fmt = self._choose_format(format_list)

                print(f"获取分P{page_number}的下载链接...")
                resp = self.session.get(
                    f"https://api.bilibili.com/x/player/playurl?{bv}&cid={cid}&qn={quality}",
                    headers=headers
                )
                resp.raise_for_status()
                data = resp.json().get('data', {})
                
                if not data.get('durl'):
                    print(f"分P{page_number}获取下载链接失败")
                    continue
                    
                download_url = data['durl'][0]['url']
                
                download_info_list.append({
                    'url': download_url,
                    'quality': quality,
                    'format': fmt,
                    'page_index': page_index,
                    'header': headers,
                    'page_title': page_data['page_title']
                })
                
            except Exception as e:
                print(f"处理分P{page_number}时出错: {str(e)}")
                continue
                
        return download_info_list

    def _choose_format(self, format_list: list) -> tuple[str, str]:
        if not format_list:
            print("没有可用的视频格式！")
            return ("", "")
        
        print("请选择视频质量:")
        for idx, fmt in enumerate(format_list):
            print(f"{idx+1}. {fmt['new_description']} (qn={fmt['quality']}, 格式: {fmt['format']})")
        
        while True:
            try:
                choice = input("请输入选择(1-{}): ".format(len(format_list)))
                if choice.lower() == 'q':
                    return ("", "")
                    
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(format_list):
                    selected = format_list[choice_idx]
                    return (str(selected['quality']), selected['format'])
                else:
                    print("输入无效，请输入有效的数字或q退出")
            except ValueError:
                print("请输入有效的数字或q退出")

    def _download_video(self, video_data: dict, download_info_list: list):
        if not download_info_list:
            print("没有可下载的视频！")
            return
        
        download_dir = "bilibili_downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        for info in download_info_list:
            try:
                safe_title = re.sub(r'[\\/:*?"<>|]', "", info['page_title'])
                filename = f"{video_data['title']}_{safe_title}.{info['format']}" if video_data['pages_number'] > 1 else f"{video_data['title']}.{info['format']}"
                filepath = os.path.join(download_dir, unquote(filename))
                
                print(f"\n开始下载分P{info['page_index']+1} [{info['quality']} {info['format']}]: {filename}")
                
                with self.session.get(info['url'], headers=info['header'], stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))
                    
                    with open(filepath, 'wb') as f, tqdm(
                        total=total_size, unit='B', unit_scale=True, unit_divisor=1024
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                
                print(f"下载完成: {filename}")
                
            except Exception as e:
                print(f"下载分P{info['page_index'] + 1}失败: {str(e)}")
                
    def download(self):
        self.is_logged_in()
        while True:
            text: str = input("输入视频BV/URL(输入q退出):\n").strip()
            if text.lower() == 'q':
                print("退出下载")
                return
            bv: str = self._bv_parser(text)
            if not bv:
                print("输入错误，请重新输入")
                continue
            try:
                video_data: dict = self._video_data_get(bv)
                if not video_data:
                    print("获取视频信息失败，请检查BV号是否正确")
                    continue
                self.print_video_data(video_data)

                download_info_list = self._get_download_info(video_data, bv)
                if not download_info_list:
                    print("没有可下载的内容")
                    continue

                self._download_video(video_data, download_info_list)
                
                print("\n下载任务完成!")
                
            except Exception as e:
                print(f"发生错误: {str(e)}")
                continue
           
            
def main():
    downloader = BiliVideoDownloader()
    while True:
        downloader.download()

            
if __name__ == '__main__':
    main()

    