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
from astrbot.core.utils.session_waiter import SessionController, session_waiter

from .qzone import QZoneAPI, QZoneAPIError, SessionExpiredError


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class Contribution:
    """投稿收集（仅存在于会话闭包中，不持久化）"""

    uin: str
    name: str = ""
    anon: bool = False
    texts: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

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


async def _send_text(event: AstrMessageEvent, text: str):
    """在 session_waiter 内部发送文本消息"""
    await event.send(event.chain_result([Comp.Plain(text)]))


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
        self.contribute_timeout: int = config.get("contribute_timeout", 300)

        self.qzone = QZoneAPI(self.cookies_str or None)
        self.bot = None  # CQHttp 客户端，首次消息时捕获
        self.cache_dir = StarTools.get_data_dir("astrbot_plugin_schoolzone") / "cache"

    async def initialize(self):
        """插件加载"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def terminate(self):
        """插件卸载"""
        await self.qzone.close()
        if self.cache_dir.exists():
            try:
                shutil.rmtree(self.cache_dir)
            except Exception as e:
                logger.error(f"清理缓存失败: {e}")

    # ── Cookie / 客户端管理 ───────────────────────────────────

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def _capture_bot(self, event: AstrMessageEvent):
        """捕获 CQHttp 客户端实例"""
        if self.bot is None:
            self.bot = event.bot
            logger.debug("CQHttp 客户端已捕获")

    async def _ensure_qzone_ready(self, event: AstrMessageEvent):
        """确保 QZone API 可用（cookie 已设置）"""
        if self.qzone.is_ready:
            return

        cookie_str = self.cookies_str
        if not cookie_str:
            # 尝试从 CQHttp 客户端获取
            bot = getattr(event, "bot", None) or self.bot
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

    async def _publish_contribution(
        self, event: AstrMessageEvent, contrib: Contribution
    ):
        """下载图片 → 上传 → 发布说说"""
        await _send_text(event, "正在发布到QQ空间...")
        try:
            await self._ensure_qzone_ready(event)

            # 构建发布文本
            pub_text = contrib.merged_text
            if self.show_name:
                name = "匿名者" if contrib.anon else contrib.name
                pub_text = f"【来自 {name} 的投稿】\n\n{pub_text}"

            # 处理图片
            uploaded_images = None
            if contrib.images:
                paths = await download_images_to_temp(
                    contrib.images, self.cache_dir
                )
                if paths:
                    uploaded_images = await self.qzone.upload_images(paths)

            # 发布
            await self.qzone.publish_mood(pub_text, images=uploaded_images)
            await _send_text(event, "发布成功!")
        except Exception as e:
            logger.error(f"发布失败: {e}")
            await _send_text(event, f"发布失败: {e}")
        finally:
            # 清理临时文件
            for f in self.cache_dir.glob("img_*"):
                try:
                    f.unlink()
                except Exception:
                    pass

    # ── 投稿命令 ─────────────────────────────────────────────

    @filter.command("投稿")
    async def cmd_contribute(self, event: AstrMessageEvent):
        """投稿文本/图片到QQ空间"""
        async for msg in self._do_contribute(event, anon=False):
            yield msg

    @filter.command("匿名投稿")
    async def cmd_anon_contribute(self, event: AstrMessageEvent):
        """匿名投稿文本/图片到QQ空间"""
        async for msg in self._do_contribute(event, anon=True):
            yield msg

    async def _do_contribute(self, event: AstrMessageEvent, anon: bool):
        contrib = Contribution(
            uin=event.get_sender_id(),
            name=event.get_sender_name(),
            anon=anon,
        )

        label = "匿名投稿" if anon else "投稿"
        yield event.plain_result(
            f"开始{label}，请发送文本/图片，完成请发送 /完成，取消请发送 /取消"
        )

        awaiting_confirm = False
        timeout = self.contribute_timeout

        @session_waiter(timeout=timeout)
        async def waiter(
            controller: SessionController, event: AstrMessageEvent
        ):
            nonlocal awaiting_confirm
            text = event.message_str.strip()

            # --- 取消 ---
            if text == "/取消":
                await _send_text(event, "已取消投稿")
                controller.stop()
                return

            # --- 完成 → 预览 ---
            if text == "/完成":
                if contrib.is_empty:
                    await _send_text(event, "投稿内容为空，请先发送文本或图片")
                    controller.keep(timeout=timeout)
                    return

                # 发送文本预览
                preview = contrib.merged_text or "(无文字)"
                await _send_text(event, f"--- 投稿预览 ---\n{preview}")

                # 发送图片预览
                for img_url in contrib.images:
                    await event.send(
                        event.chain_result([Comp.Image.fromURL(img_url)])
                    )

                n_img = len(contrib.images)
                img_hint = f"共 {n_img} 张图片\n" if n_img else ""
                await _send_text(
                    event,
                    f"{img_hint}确认发布请发送「确认」，取消请发送「取消」",
                )
                awaiting_confirm = True
                controller.keep(timeout=60)
                return

            # --- 确认/取消发布 ---
            if awaiting_confirm:
                if text in ("确认", "是", "发布"):
                    await self._publish_contribution(event, contrib)
                    controller.stop()
                    return
                elif text in ("取消", "否"):
                    await _send_text(event, "已取消发布")
                    controller.stop()
                    return
                else:
                    await _send_text(event, "请发送「确认」或「取消」")
                    controller.keep(timeout=60)
                    return

            # --- 收集文本和图片 ---
            if text and not text.startswith("/"):
                contrib.texts.append(text)
            images = get_image_urls(event)
            contrib.images.extend(images)
            controller.keep(timeout=timeout)

        try:
            await waiter(event)
        except TimeoutError:
            yield event.plain_result("投稿超时，已取消")

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
