import copy
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
from astrbot.core.utils.session_waiter import (
    SessionController,
    SessionFilter,
    session_waiter,
)

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


class SchoolZoneSessionFilter(SessionFilter):
    """Use group id in groups, otherwise fall back to unified origin."""

    def filter(self, event: AstrMessageEvent) -> str:
        group_id = event.get_group_id()
        return group_id if group_id else event.unified_msg_origin


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
    try:
        chain = Comp.Plain(text)
        from astrbot.core.message.message_event_result import MessageChain
        await event.send(MessageChain(chain=[chain]))
        logger.debug(f"[SchoolZone] _send_text 成功: {text[:30]}")
    except Exception as e:
        logger.error(f"[SchoolZone] _send_text 失败: {e}")


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
        self.cache_dir = StarTools.get_data_dir("astrbot_plugin_schoolzone") / "cache"

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

    async def _publish_contribution(
        self, event: AstrMessageEvent, contrib: Contribution
    ):
        """下载图片 → 上传 → 发布说说"""
        await _send_text(event, "正在发布到QQ空间...")
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
            await _send_text(event, "发布成功!")
        except Exception as e:
            logger.error(f"发布失败: {e}")
            await _send_text(event, f"发布失败: {e}")
        finally:
            for f in self.cache_dir.glob("img_*"):
                f.unlink(missing_ok=True)

    # ── 投稿命令 ─────────────────────────────────────────────

    @filter.command("投稿")
    async def cmd_contribute(self, event: AstrMessageEvent):
        """投稿文本/图片到QQ空间"""
        logger.info("[SchoolZone] 收到 /投稿 命令")
        contrib = Contribution(
            uin=event.get_sender_id(),
            name=event.get_sender_name(),
            anon=False,
        )
        yield event.plain_result(
            "开始投稿，请发送文本/图片，完成请发送 /完成，取消请发送 /取消"
        )
        async for msg in self._collect_and_publish(event, contrib):
            yield msg

    @filter.command("匿名投稿")
    async def cmd_anon_contribute(self, event: AstrMessageEvent):
        """匿名投稿文本/图片到QQ空间"""
        logger.info("[SchoolZone] 收到 /匿名投稿 命令")
        contrib = Contribution(
            uin=event.get_sender_id(),
            name=event.get_sender_name(),
            anon=True,
        )
        yield event.plain_result(
            "开始匿名投稿，请发送文本/图片，完成请发送 /完成，取消请发送 /取消"
        )
        async for msg in self._collect_and_publish(event, contrib):
            yield msg

    async def _collect_and_publish(
        self, event: AstrMessageEvent, contrib: Contribution
    ):
        """会话控制：收集投稿内容 → 预览 → 确认发布"""
        awaiting_confirm = False
        timeout = self.contribute_timeout

        @session_waiter(timeout=timeout)
        async def waiter(
            controller: SessionController, event: AstrMessageEvent
        ):
            nonlocal awaiting_confirm
            text = event.message_str.strip()
            raw_text = event.message_obj.message_str.strip()
            logger.debug(f"[SchoolZone] waiter 收到: text={text}, raw={raw_text}")

            # --- 取消 ---
            if text in ("取消", "/取消"):
                await _send_text(event, "已取消投稿")
                controller.stop()
                return

            # --- 完成 → 预览 ---
            if text in ("完成", "/完成"):
                if contrib.is_empty:
                    await _send_text(event, "投稿内容为空，请先发送文本或图片")
                    controller.keep(timeout=timeout, reset_timeout=True)
                    return

                preview = contrib.merged_text or "(无文字)"
                await _send_text(event, f"--- 投稿预览 ---\n{preview}")

                for img_url in contrib.images:
                    await event.send(event.image_result(img_url))

                n_img = len(contrib.images)
                img_hint = f"共 {n_img} 张图片\n" if n_img else ""
                await _send_text(
                    event,
                    f"{img_hint}确认发布请发送「确认」，取消请发送「取消」",
                )
                awaiting_confirm = True
                controller.keep(timeout=60, reset_timeout=True)
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
                    controller.keep(timeout=60, reset_timeout=True)
                    return

            # --- 未知命令兜底：取消当前投稿并重新分发 ---
            if raw_text.startswith("/"):
                await _send_text(event, "当前投稿已取消，正在处理新命令...")
                controller.stop()
                new_event = copy.copy(event)
                self.context.get_event_queue().put_nowait(new_event)
                return

            # --- 收集文本和图片 ---
            if text:
                contrib.texts.append(text)
            images = get_image_urls(event)
            contrib.images.extend(images)
            controller.keep(timeout=timeout, reset_timeout=True)

        try:
            await waiter(event, session_filter=SchoolZoneSessionFilter())
        except TimeoutError:
            yield event.plain_result("投稿超时，已取消")
        finally:
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
