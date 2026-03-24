"""QZone H5 API 客户端库

基于 h5.qzone.qq.com 实现，提供
- g_tk 计算（DJBX33A 哈希）
- qzonetoken 获取
- 获取说说列表
- 上传图片并发布说说
"""

import base64
import json
import re
import struct
import time
from urllib.parse import quote

import aiohttp


BASE_URL = "https://h5.qzone.qq.com"
API_URL = "https://mobile.qzone.qq.com"

COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; MAA-AN00 Build/HONORMAA-AN00; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.179 "
        "Mobile Safari/537.36 cpdaily/9.9.6 wisedu/9.9.6"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,zh-TW;q=0.7,zh-HK;q=0.6,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
}


class QZoneAPIError(Exception):
    """QZone API 请求异常基类"""


class SessionExpiredError(QZoneAPIError):
    """会话过期（cookie 失效、qzonetoken 获取失败、API 返回非 200 等）"""


class QZoneAPI:
    """QQ 空间 H5 API 客户端"""

    def __init__(self, cookie: str | None = None):
        """
        Args:
            cookie: 完整的 cookie 字符串，需包含 p_skey 和 p_uin 字段。
                    可不传，后续通过 update_cookie() 设置。
        """
        self._cookie_str: str = ""
        self._cookie_dict: dict = {}
        self._g_tk: str = ""
        self._uin: str = ""
        self._qzonetoken: str | None = None
        self._session: aiohttp.ClientSession | None = None

        if cookie:
            self._apply_cookie(cookie)

    def _apply_cookie(self, cookie: str):
        """解析并应用 cookie，计算 g_tk 和 uin（不获取 qzonetoken）"""
        self._cookie_str = cookie
        self._cookie_dict = self._parse_cookie(cookie)

        p_skey = self._cookie_dict.get("p_skey")
        if not p_skey:
            raise SessionExpiredError("cookie 中缺少 p_skey 字段")

        self._g_tk = self._compute_gtk2(p_skey)
        self._uin = self._get_uin()
        # 新 cookie 需要重新获取 qzonetoken
        self._qzonetoken = None

    async def update_cookie(self, cookie: str) -> bool:
        """更新 cookie 并验证会话有效性

        解析 cookie、计算 g_tk、获取 qzonetoken。
        全部成功返回 True，任一步骤失败返回 False。

        Args:
            cookie: 新的完整 cookie 字符串
        """
        try:
            self._apply_cookie(cookie)
            self._qzonetoken = await self._fetch_qzonetoken()
            return True
        except QZoneAPIError:
            return False

    @property
    def is_ready(self) -> bool:
        """cookie 和 qzonetoken 是否都已就绪"""
        return bool(self._cookie_str and self._g_tk and self._qzonetoken)

    @staticmethod
    def _parse_cookie(cookie: str) -> dict:
        """将 cookie 字符串解析为 dict"""
        result = {}
        for item in cookie.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    @staticmethod
    def _compute_gtk2(p_skey: str) -> str:
        """通过 p_skey 计算 g_tk（DJBX33A 哈希）"""
        hash_val = 5381
        for ch in p_skey:
            hash_val += (hash_val << 5) + ord(ch)
        return str(hash_val & 0x7FFFFFFF)

    def _get_uin(self) -> str:
        """从 cookie 中的 p_uin 提取纯数字 QQ 号"""
        p_uin = self._cookie_dict.get("p_uin", "")
        return p_uin.lstrip("o")

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=COMMON_HEADERS,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
        return self._session

    async def _ensure_qzonetoken(self):
        """确保已获取 qzonetoken，若未获取则自动请求"""
        if self._qzonetoken is None:
            self._qzonetoken = await self._fetch_qzonetoken()

    async def _fetch_qzonetoken(self) -> str:
        """请求 QQ 空间主页，从 HTML 中提取 qzonetoken

        Raises:
            SessionExpiredError: 页面返回非 200 或无法提取 token
        """
        session = self._get_session()
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://ui.ptlogin2.qq.com/",
            "Cookie": self._cookie_str,
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-User": "?1",
        }
        async with session.get(f"{BASE_URL}/", headers=headers) as resp:
            if resp.status != 200:
                raise SessionExpiredError(f"获取 qzonetoken 失败: HTTP {resp.status}")
            html = await resp.text()

        match = re.search(r'window\.shine0callback\s*=\s*\(function\(\)\{\s*try\{return\s*"([0-9a-f]+)"', html)
        if not match:
            raise SessionExpiredError("无法从主页 HTML 中提取 qzonetoken，cookie 可能已过期")
        return match.group(1)

    @staticmethod
    def _parse_response(raw: str):
        """尝试解析 API 响应，兼容纯 JSON 和 JSONP callback 格式"""
        raw = raw.strip()
        # 纯 JSON
        if raw.startswith("{") or raw.startswith("["):
            return json.loads(raw)
        # JSONP: callback({...}) 或 _Callback({...});
        match = re.search(r"^\w+\((.+)\);?\s*$", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise QZoneAPIError(f"无法解析响应: {raw[:200]}")

    async def _post_api(self, url: str, *, params: dict, data: dict, headers: dict) -> str:
        """发送 POST 请求并返回原始响应文本

        Raises:
            SessionExpiredError: HTTP 状态码非 200
        """
        session = self._get_session()
        async with session.post(url, params=params, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise SessionExpiredError(
                    f"API 请求失败: HTTP {resp.status} ({url})"
                )
            return await resp.text()

    @staticmethod
    def _check_mobile_api_result(result: dict, action: str = "请求"):
        """检查 mobile API 返回的 code 字段

        code == -3000 → SessionExpiredError
        code != 0     → QZoneAPIError
        """
        code = result.get("code", -1)
        if code == 0:
            return
        msg = result.get("message", result)
        if code == -3000:
            raise SessionExpiredError(f"{action}失败（会话过期）: {msg}")
        raise QZoneAPIError(f"{action}失败 (code={code}): {msg}")

    def _common_api_headers(self, *, content_type: str = "application/x-www-form-urlencoded") -> dict:
        """构造 API 请求通用 headers"""
        return {
            "Accept": "application/json",
            "Content-Type": content_type,
            "Origin": "https://h5.qzone.qq.com",
            "Referer": "https://h5.qzone.qq.com/",
            "Cookie": self._cookie_str,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    async def get_active_feeds(self, timestamp: int | None = None) -> dict:
        """获取从某一时间戳往前的最新 10 条说说

        Args:
            timestamp: Unix 时间戳（秒），默认为当前时间

        Returns:
            API 原始返回的 JSON dict，说说列表在 data.vFeeds 中

        Raises:
            SessionExpiredError: 请求失败或会话过期
        """
        await self._ensure_qzonetoken()

        if timestamp is None:
            timestamp = int(time.time())

        back_server_info = quote(f"basetime={timestamp}")
        res_attach = f"back_server_info={back_server_info}"
        attach_info = f"back_server_info={back_server_info}"

        params = {
            "qzonetoken": self._qzonetoken,
            "g_tk": self._g_tk,
        }
        data = {
            "res_type": "0",
            "res_attach": res_attach,
            "refresh_type": "2",
            "format": "json",
            "attach_info": attach_info,
        }

        headers = self._common_api_headers()
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Sec-Fetch-Site"] = "same-origin"

        url = f"{BASE_URL}/webapp/json/mqzone_feeds/getActiveFeeds"
        raw = await self._post_api(url, params=params, data=data, headers=headers)
        result = self._parse_response(raw)

        if result.get("code", -1) != 0 and result.get("ret", -1) != 0:
            raise SessionExpiredError(f"获取说说失败: {result.get('message', result)}")
        return result

    async def _preupload_image(self, image_data: bytes, width: int, height: int) -> dict:
        """预上传单张图片（preupload=1），获取服务端 filemd5 和 filelen

        Args:
            image_data: 图片二进制数据
            width: 图片宽度
            height: 图片高度

        Returns:
            dict 包含 filemd5 和 filelen

        Raises:
            SessionExpiredError: 请求失败或会话过期
        """
        b64_data = base64.b64encode(image_data).decode("ascii")

        params = {
            "g_tk": self._g_tk,
            "qzonetoken": self._qzonetoken,
        }
        data = {
            "picture": b64_data,
            "base64": "1",
            "hd_height": str(height),
            "hd_width": str(width),
            "hd_quality": "96",
            "output_type": "json",
            "preupload": "1",
            "charset": "utf-8",
            "output_charset": "utf-8",
            "logintype": "sid",
            "Exif_CameraMaker": "",
            "Exif_CameraModel": "",
            "Exif_Time": "",
            "uin": self._uin,
        }

        headers = self._common_api_headers()
        headers["Accept"] = "*/*"
        headers["Sec-Fetch-Site"] = "same-site"

        url = f"{API_URL}/up/cgi-bin/upload/cgi_upload_pic_v2"
        raw = await self._post_api(url, params=params, data=data, headers=headers)
        result = self._parse_response(raw)

        # 预上传成功返回 {"filemd5": ..., "filelen": ...}
        # 失败返回 {"code": -3000, ...} 等
        if isinstance(result, dict) and "code" in result:
            self._check_mobile_api_result(result, "预上传图片")
        if not isinstance(result, dict) or "filemd5" not in result:
            raise QZoneAPIError(f"预上传图片失败: 意外的响应格式")
        return result

    @staticmethod
    def _get_image_size(data: bytes) -> tuple[int, int]:
        """从图片二进制数据中读取宽高（支持 PNG/JPEG/GIF/BMP）"""
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 1:
                if data[i] != 0xFF:
                    break
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                    return w, h
                length = struct.unpack(">H", data[i + 2 : i + 4])[0]
                i += 2 + length
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return w, h
        if data[:2] == b"BM":
            w, h = struct.unpack("<ii", data[18:26])
            return w, abs(h)
        return 0, 0

    async def upload_images(self, image_paths: list[str]) -> list[dict]:
        """上传多张图片到 QQ 空间

        两步流程:
        1. 预上传 (preupload=1): 发送 base64 图片数据，服务端返回 filemd5 和 filelen
        2. 正式上传 (preupload=2): 使用服务端返回的 filemd5/filelen 获取 picinfo

        Args:
            image_paths: 图片文件路径列表

        Returns:
            每张图片的信息列表，每个元素包含:
            - sloc: 小图地址标识
            - lloc: 大图地址标识
            - albumid: 相册 ID
            - width: 图片宽度
            - height: 图片高度
            - pre: 预览 URL
            - url: 原图 URL

        Raises:
            SessionExpiredError: 请求失败或会话过期
        """
        await self._ensure_qzonetoken()

        # Step 1: 逐张预上传，获取服务端 filemd5 和 filelen
        md5_list = []
        size_list = []
        for path in image_paths:
            with open(path, "rb") as f:
                image_data = f.read()
            w, h = self._get_image_size(image_data)
            pre_result = await self._preupload_image(image_data, w, h)
            md5_list.append(pre_result["filemd5"])
            size_list.append(str(pre_result["filelen"]))

        # Step 2: 正式上传
        now_ms = int(time.time() * 1000)
        now_s = int(time.time())

        params = {
            "g_tk": self._g_tk,
            "qzonetoken": self._qzonetoken,
        }
        data = {
            "output_type": "json",
            "preupload": "2",
            "md5": "|".join(md5_list),
            "filelen": "|".join(size_list),
            "batchid": str(now_ms * 1000),
            "currnum": "0",
            "uploadNum": str(len(image_paths)),
            "uploadtime": str(now_s),
            "uploadtype": "1",
            "upload_hd": "1",
            "albumtype": "7",
            "big_style": "1",
            "op_src": "15003",
            "charset": "utf-8",
            "output_charset": "utf-8",
            "uin": self._uin,
            "refer": "shuoshuo",
        }

        headers = self._common_api_headers()
        headers["Accept"] = "*/*"
        headers["Sec-Fetch-Site"] = "same-site"

        url = f"{API_URL}/up/cgi-bin/upload/cgi_upload_pic_v2"
        raw = await self._post_api(url, params=params, data=data, headers=headers)
        result = self._parse_response(raw)

        # 正式上传成功返回 list，如果返回 dict 则检查 code
        if isinstance(result, dict):
            self._check_mobile_api_result(result, "上传图片")
        if not isinstance(result, list):
            raise QZoneAPIError(f"上传图片失败: 意外的响应格式")

        images = []
        for item in result:
            pic = item.get("picinfo", {})
            images.append({
                "sloc": pic.get("sloc", ""),
                "lloc": pic.get("lloc", ""),
                "albumid": pic.get("albumid", ""),
                "width": pic.get("width", 0),
                "height": pic.get("height", 0),
                "pre": pic.get("pre", ""),
                "url": pic.get("url", ""),
            })
        return images

    async def publish_mood(self, content: str, images: list[dict] | None = None) -> dict:
        """发布说说

        Args:
            content: 说说文本内容
            images: upload_images 返回的图片信息列表（可选，不传则发布纯文本说说）

        Returns:
            API 原始返回的 JSON dict

        Raises:
            SessionExpiredError: 请求失败或会话过期
        """
        await self._ensure_qzonetoken()

        params = {
            "qzonetoken": self._qzonetoken,
            "g_tk": self._g_tk,
        }

        data = {
            "opr_type": "publish_shuoshuo",
            "res_uin": self._uin,
            "content": content,
            "lat": "0",
            "lon": "0",
            "lbsid": "",
            "issyncweibo": "0",
            "format": "json",
        }

        if images:
            richval_parts = []
            for img in images:
                part = f"{img['albumid']},{img['sloc']},{img['lloc']},,{img['width']},{img['height']},,,"
                richval_parts.append(part)
            data["richval"] = " ".join(richval_parts)

        headers = self._common_api_headers()

        url = f"{API_URL}/mood/publish_mood"
        raw = await self._post_api(url, params=params, data=data, headers=headers)
        result = self._parse_response(raw)
        self._check_mobile_api_result(result, "发布说说")
        return result

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
