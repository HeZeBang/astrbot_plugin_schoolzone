import shutil
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.star.star_tools import StarTools

from .qzone import QZoneAPI, QZoneAPIError, SessionExpiredError


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class Contribution:
    """投稿收集（仅存在于会话中，不持久化）"""

    uin: str
    name: str = ""
    anon: bool = False
    texts: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    awaiting_confirm: bool = False

    @property
    def merged_text(self) -> str:
        return "\n".join(t for t in self.texts if t.strip())

    @property
    def is_empty(self) -> bool:
        return not any(t.strip() for t in self.texts) and not self.images


# ── 工具函数 ──────────────────────────────────────────────────


def get_image_urls(event: AstrMessageEvent) -> list[str]:
    """从消息链中提取图片 URL"""
    return [
        seg.url
        for seg in event.get_messages()
        if isinstance(seg, Comp.Image) and seg.url
    ]


async def download_images_to_temp(
    urls: list[str], cache_dir: Path
) -> list[str]:
    """下载图片 URL 到临时文件，返回文件路径列表"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(urls):
            try:
                async with session.get(url) as resp:
                    data = await resp.read()
                    path = cache_dir / f"img_{i}.jpg"
                    path.write_bytes(data)
                    paths.append(str(path))
            except Exception as e:
                logger.error(f"下载图片失败: {url} - {e}")
    return paths


# ── 插件主体 ──────────────────────────────────────────────────


@register(
    "astrbot_plugin_schoolzone",
    "zambar",
    "校园表白墙投稿插件",
    "0.1.0",
)
class SchoolZonePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        self.cookies_str: str = config.get("cookies_str", "")
        self.show_name: bool = config.get("show_name", True)

        self.qzone = QZoneAPI(self.cookies_str or None)
        self.cache_dir = StarTools.get_data_dir("astrbot_plugin_schoolzone") / "cache"

        self.contrib_sessions: dict[str, Contribution] = {}

    async def initialize(self):
        """插件加载"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("SchoolZone 插件已加载")

    async def terminate(self):
        """插件卸载"""
        await self.qzone.close()
        if self.cache_dir.exists():
            try:
                shutil.rmtree(self.cache_dir)
            except Exception as e:
                logger.error(f"清理缓存失败: {e}")

    # ── Cookie 管理 ──────────────────────────────────────────

    async def _ensure_qzone_ready(self, event: AstrMessageEvent):
        """确保 QZone API 可用（cookie 已设置）"""
        if self.qzone.is_ready:
            return

        cookie_str = self.cookies_str
        if not cookie_str:
            bot = getattr(event, "bot", None)
            if bot is None:
                raise RuntimeError("CQHttp 客户端未初始化，无法获取 Cookie")
            result = await bot.get_cookies(domain="h5.qzone.qq.com")
            cookie_str = result.get("cookies", "")
            if not cookie_str:
                raise RuntimeError("自动获取 Cookie 失败，请在配置中手动填写")

        ok = await self.qzone.update_cookie(cookie_str)
        if not ok:
            raise RuntimeError("Cookie 无效或已过期，请更新")

    # ── 发布逻辑 ─────────────────────────────────────────────

    async def _do_publish(
        self, event: AstrMessageEvent, contrib: Contribution
    ) -> str:
        """下载图片 → 上传 → 发布说说，返回结果消息"""
        try:
            await self._ensure_qzone_ready(event)

            pub_text = contrib.merged_text
            if self.show_name:
                name = "匿名者" if contrib.anon else contrib.name
                pub_text = f"【来自 {name} 的投稿】\n\n{pub_text}"

            uploaded_images = None
            if contrib.images:
                paths = await download_images_to_temp(
                    contrib.images, self.cache_dir
                )
                if paths:
                    uploaded_images = await self.qzone.upload_images(paths)

            await self.qzone.publish_mood(pub_text, images=uploaded_images)
            return "发布成功!"
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return f"发布失败: {e}"
        finally:
            for f in self.cache_dir.glob("img_*"):
                f.unlink(missing_ok=True)

    # ── 投稿命令 ─────────────────────────────────────────────

    @filter.command("投稿")
    async def cmd_contribute(self, event: AstrMessageEvent):
        """投稿文本/图片到QQ空间"""
        session_id = event.unified_msg_origin
        if session_id in self.contrib_sessions:
            del self.contrib_sessions[session_id]
            yield event.plain_result("上一次投稿已取消，开始新投稿。")

        self.contrib_sessions[session_id] = Contribution(
            uin=event.get_sender_id(),
            name=event.get_sender_name(),
            anon=False,
        )
        yield event.plain_result(
            "开始投稿，请发送文本/图片，完成请发送 /完成，取消请发送 /取消"
        )

    @filter.command("匿名投稿")
    async def cmd_anon_contribute(self, event: AstrMessageEvent):
        """匿名投稿文本/图片到QQ空间"""
        session_id = event.unified_msg_origin
        if session_id in self.contrib_sessions:
            del self.contrib_sessions[session_id]
            yield event.plain_result("上一次投稿已取消，开始新匿名投稿。")

        self.contrib_sessions[session_id] = Contribution(
            uin=event.get_sender_id(),
            name=event.get_sender_name(),
            anon=True,
        )
        yield event.plain_result(
            "开始匿名投稿，请发送文本/图片，完成请发送 /完成，取消请发送 /取消"
        )

    # ── 全局消息监听：收集投稿内容 + 会话内命令 ─────────────────

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_contribute_message(self, event: AstrMessageEvent):
        """在投稿进行中时：处理 /完成、/取消、/确认，以及收集文本和图片"""
        session_id = event.unified_msg_origin
        if session_id not in self.contrib_sessions:
            return

        # 跳过 /投稿 /匿名投稿 本身（已由命令处理器处理）
        text = event.message_str.strip()
        if text in ("投稿", "匿名投稿"):
            return

        contrib = self.contrib_sessions[session_id]
        raw_text = event.message_obj.message_str.strip()

        # ── 会话内命令（必须以 / 开头） ──

        if raw_text == "/完成":
            if contrib.is_empty:
                yield event.plain_result("投稿内容为空，请先发送文本或图片。")
            else:
                preview = contrib.merged_text or "(无文字)"
                n_img = len(contrib.images)
                img_hint = f"\n共 {n_img} 张图片" if n_img else ""
                contrib.awaiting_confirm = True
                yield event.plain_result(
                    f"--- 投稿预览 ---\n{preview}{img_hint}"
                    "\n\n确认发布请发送 /确认，取消请发送 /取消"
                )
            event.stop_event()
            return

        if raw_text == "/取消":
            del self.contrib_sessions[session_id]
            yield event.plain_result("已取消投稿。")
            event.stop_event()
            return

        if raw_text == "/确认":
            if not contrib.awaiting_confirm:
                yield event.plain_result("请先发送 /完成 进行预览。")
            else:
                yield event.plain_result("正在发布到QQ空间...")
                result_msg = await self._do_publish(event, contrib)
                del self.contrib_sessions[session_id]
                yield event.plain_result(result_msg)
            event.stop_event()
            return

        # 等待确认阶段，忽略非命令消息
        if contrib.awaiting_confirm:
            return

        # ── 收集文本和图片 ──

        images = get_image_urls(event)

        if not text and not images:
            return

        if text:
            contrib.texts.append(text)
        contrib.images.extend(images)

        parts = []
        if text:
            parts.append("文本")
        if images:
            parts.append(f"{len(images)} 张图片")
        yield event.plain_result(
            f"已收到{'、'.join(parts)}。继续发送或输入 /完成"
        )
        event.stop_event()

    # ── LLM Tool ─────────────────────────────────────────────

    @filter.llm_tool()
    async def llm_publish_shuoshuo(
        self,
        event: AstrMessageEvent,
        text: str = "",
        get_image: bool = True,
    ):
        """
        发布一条说说到QQ空间
        Args:
            text(string): 要发布的说说内容
            get_image(boolean): 是否获取当前对话中的图片附加到说说里, 默认为True
        """
        try:
            await self._ensure_qzone_ready(event)

            uploaded_images = None
            if get_image:
                img_urls = get_image_urls(event)
                if img_urls:
                    paths = await download_images_to_temp(
                        img_urls, self.cache_dir
                    )
                    if paths:
                        uploaded_images = await self.qzone.upload_images(paths)

            await self.qzone.publish_mood(text, images=uploaded_images)
            msg = f"已发布说说到QQ空间:\n{text}"
            if uploaded_images:
                msg += f"\n附带 {len(uploaded_images)} 张图片"
            return msg
        except Exception as e:
            logger.error(f"LLM 发布说说失败: {e}")
            return f"发布失败: {e}"
        finally:
            for f in self.cache_dir.glob("img_*"):
                try:
                    f.unlink()
                except Exception:
                    pass
