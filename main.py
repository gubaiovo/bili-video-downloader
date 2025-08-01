import re
import os
import requests
from urllib.parse import urlparse, unquote

HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}
DOWNLOAD_INFO_RAW_URL = "https://api.bilibili.com/x/player/playurl?"
VIDEO_DATA_INTERFACE = "https://api.bilibili.com/x/web-interface/view?"

def _bv_parser(text: str) -> str:
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
    
def _video_data_get(bv: str) -> dict:
    json_response: dict = {}
    interface_url:str = f"{VIDEO_DATA_INTERFACE}{bv}"
    raw_response = requests.get(interface_url, headers=HEADER)
    if raw_response.status_code == 200:
        json_response = raw_response.json()
    else:
        print(f"请求失败，状态码为{raw_response.status_code}")
    data: dict = json_response.get("data", {})
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
        "up_url": f"https://space.bilibili.com/{up.get("mid", "")}",
        "pages": page_list
    }

    return result
        
def print_video_data(video_data: dict):
    print(f"""=== 视频信息 ===
    标题: {video_data['title']}
    av号: {video_data['aid']}
    BV号: {video_data['bvid']}
    up: {video_data['up']}
    up主页: {video_data['up_url']}
    分P数: {video_data['pages_number']}
    分P列表: """)
    for page in video_data['pages']:
        print(f"        {page['page_number']}. {page['page_title']}  CID: {page['cid']}")
    print("================")
            
def _get_download_url_list(video_data: dict, bv: str) -> tuple:
    download_url_list: list = []
    print("请输入要下载的分P序号, 多个分P用空格分隔, 输入q/Q退出")
    download_pages_required: str = input()
    # print(f"LOG: 下载分P{download_pages}")
    if download_pages_required == "q":
        return ([], {})
    # print(f"LOG: 开始下载分P{download_pages}")
    download_pages_list: list = download_pages_required.split()
    for page_number in download_pages_list:
        page_index: int = int(page_number) - 1
        if page_index < 0 or page_index >= len(video_data['pages']):
            print(f"输入错误，分P序号{page_number}不存在")
            continue
        page_data: dict = video_data['pages'][page_index]
        DOWNLOAD_INFO_URL: str = DOWNLOAD_INFO_RAW_URL + bv + f"&cid={page_data['cid']}"
        # print(f"LOG: {url}")
        if video_data['pages_number'] == 1:
            header: dict = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
                "Referer": f"https://www.bilibili.com/video/{video_data['bvid']}"
            }
        elif video_data['pages_number'] > 1:
            header: dict = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
                "Referer": f"https://www.bilibili.com/video/{video_data['bvid']}?p={page_number}"
            }
        download_info: dict = requests.get(DOWNLOAD_INFO_URL, headers=header).json()
        download_url: str = download_info.get("data", []).get("durl", [])[0]["url"]
        download_url_list.append(download_url)
        # print("LOG:", header)
    return (download_url_list, header)

def download_video(video_data: dict, download_url_list: list, download_header: dict):
    if not download_url_list:
        print("没有可下载的视频地址！")
        return
    download_dir = "bilibili_downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    for idx, url in enumerate(download_url_list):
        try:
            # 从 URL 提取文件名（或使用视频标题 + 分P名）
            page_title = video_data['pages'][idx]['page_title']
            safe_title = re.sub(r'[\\/:*?"<>|]', "", page_title)  # 移除非法文件名字符
            filename = f"{video_data['title']}_{safe_title}.mp4" if video_data['pages_number'] > 1 else f"{video_data['title']}.mp4"
            filepath = os.path.join(download_dir, unquote(filename))
            response = requests.get(url, headers=download_header, stream=True)
            response.raise_for_status()  

            total_size = int(response.headers.get('content-length', 0))
            print(f"正在下载: {filename} ({total_size // 1024 // 1024} MB)")

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"下载完成: {filename}")

        except Exception as e:
            print(f"下载分P{idx + 1}失败: {e}")
            
            
            
            
def main():
    while True:
        text: str = input("输入视频BV/URL:\n")
        bv: str = _bv_parser(text)
        if bv:
            pass
        else:
            print("输入错误，请重新输入")
            
        video_data: dict = _video_data_get(bv)
        print_video_data(video_data)
        download_url_list, download_header = _get_download_url_list(video_data, bv)
        # for download_url in download_url_list:
            # print(f"分P{download_url_list.index(download_url)+1}下载地址: {download_url}")
        download_video(video_data, download_url_list, download_header)
        
        # print(f"LOG: 开始下载分P{download_pages_list}")

            
if __name__ == '__main__':
    main()

    