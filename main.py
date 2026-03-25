import asyncio
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import typst
import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.star.star_tools import StarTools

from .qzone import QZoneAPI, QZoneAPIError, SessionExpiredError

MAX_PUBLISH_RETRIES = 3


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class ContentItem:
    """单条投稿内容（保持用户发送顺序）"""

    type: str  # "text" | "image"
    content: str  # 文本内容 或 图片 URL


@dataclass
class Contribution:
    """投稿收集（仅存在于会话中，不持久化）"""

    uin: str
    name: str = ""
    anon: bool = False
    texts: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    local_images: list[str] = field(default_factory=list)
    items: list[ContentItem] = field(default_factory=list)
    awaiting_confirm: bool = False
    mode: str = "post"  # "post" | "dialog"

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


def _detect_image_ext(data: bytes) -> str:
    """根据文件头检测图片格式"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"GIF8":
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


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
                    ext = _detect_image_ext(data)
                    path = cache_dir / f"img_{i}{ext}"
                    path.write_bytes(data)
                    paths.append(str(path))
            except Exception as e:
                logger.error(f"下载图片失败: {url} - {e}")
    return paths


_PLUGIN_DIR = Path(__file__).parent
_FONT_DIR = str(_PLUGIN_DIR / "fonts")
_TEMPLATE_DIR = _PLUGIN_DIR / "template"


def _get_author(contrib: "Contribution", show_name: bool) -> str:
    if not show_name:
        return ""
    return "匿名者" if contrib.anon else contrib.name


def render_post(
    contrib: "Contribution",
    show_name: bool,
    work_dir: Path,
) -> bytes:
    """帖子模式：用 preview.typ 渲染预览卡片"""
    template_dst = work_dir / "preview.typ"
    shutil.copy2(_TEMPLATE_DIR / "preview.typ", template_dst)

    img_files = ",".join(Path(p).name for p in contrib.local_images)

    return typst.compile(
        str(template_dst),
        root=str(work_dir),
        sys_inputs={
            "author": _get_author(contrib, show_name),
            "content": contrib.merged_text or "",
            "img_files": img_files,
        },
        font_paths=[_FONT_DIR],
        format="png",
        ppi=144,
    )


def _build_dialog_json(contrib: "Contribution", work_dir: Path) -> Path:
    """根据投稿内容生成 dialog.typ 所需的 JSON 文件"""
    # 构建有序 content 列表，图片路径映射到本地文件
    img_url_to_local: dict[str, str] = {}
    for url, local in zip(contrib.images, contrib.local_images):
        img_url_to_local[url] = f"./{Path(local).name}"

    content: list[dict] = []
    for item in contrib.items:
        if item.type == "text":
            content.append({"type": "text", "content": item.content})
        elif item.type == "image" and item.content in img_url_to_local:
            content.append({"type": "image", "content": img_url_to_local[item.content]})

    avatar_file = next(work_dir.glob("avatar.*"), None)
    avatar_rel = f"./{avatar_file.name}" if avatar_file else "./avatar.png"

    data = {
        "name": contrib.name,
        "avatar": avatar_rel,
        "is_anon": contrib.anon,
        "content": content,
    }

    json_path = work_dir / "data.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return json_path


def render_dialog(
    contrib: "Contribution",
    work_dir: Path,
) -> bytes:
    """对话模式：用 dialog.typ 渲染聊天记录截图"""
    # 复制 dialog 模板 + ourchat 库到工作目录
    template_dst = work_dir / "dialog.typ"
    shutil.copy2(_TEMPLATE_DIR / "dialog.typ", template_dst)
    ourchat_dst = work_dir / "ourchat"
    if not ourchat_dst.exists():
        shutil.copytree(_TEMPLATE_DIR / "ourchat", ourchat_dst)

    json_path = _build_dialog_json(contrib, work_dir)

    return typst.compile(
        str(template_dst),
        root=str(work_dir),
        sys_inputs={"json": f"./{json_path.name}"},
        font_paths=[_FONT_DIR],
        format="png",
        ppi=144,
    )


async def download_avatar(uin: str, work_dir: Path) -> str:
    """下载 QQ 头像到工作目录，返回本地路径"""
    url = f"https://q1.qlogo.cn/g?b=qq&nk={uin}&s=640"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                data = await resp.read()
                ext = _detect_image_ext(data)
                path = work_dir / f"avatar{ext}"
                path.write_bytes(data)
                return str(path)
        except Exception as e:
            logger.warning(f"下载头像失败: {e}")
            # 使用占位头像
            placeholder = _TEMPLATE_DIR / "placeholder.png"
            dst = work_dir / "avatar.png"
            shutil.copy2(placeholder, dst)
            return str(dst)


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
        self.admin_notify_group: str = config.get("admin_notify_group", "")

        self.qzone = QZoneAPI(self.cookies_str or None)
        self.cache_dir = StarTools.get_data_dir("astrbot_plugin_schoolzone") / "cache"

        self.contrib_sessions: dict[str, Contribution] = {}

        # 管理员 ID 列表（用于失败通知兜底）
        self._admins_id: list[str] = context.get_config().get("admins_id", [])
        # bot 客户端引用，延迟获取
        self._bot = None

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

    def _get_bot(self, event: AstrMessageEvent):
        """获取并缓存 bot 客户端引用"""
        if self._bot is None:
            self._bot = getattr(event, "bot", None)
        return self._bot

    async def _ensure_qzone_ready(self, event: AstrMessageEvent):
        """确保 QZone API 可用（cookie 已设置）"""
        if self.qzone.is_ready:
            return

        cookie_str = self.cookies_str
        if not cookie_str:
            bot = self._get_bot(event)
            if bot is None:
                raise RuntimeError("CQHttp 客户端未初始化，无法获取 Cookie")
            result = await bot.get_cookies(domain="h5.qzone.qq.com")
            cookie_str = result.get("cookies", "")
            if not cookie_str:
                raise RuntimeError("自动获取 Cookie 失败，请在配置中手动填写")

        ok = await self.qzone.update_cookie(cookie_str)
        if not ok:
            raise RuntimeError("Cookie 无效或已过期，请更新")

    async def _refresh_cookie(self, event: AstrMessageEvent) -> bool:
        """尝试重新获取 cookie 并刷新会话，成功返回 True"""
        bot = self._get_bot(event)
        if bot is None:
            return False
        try:
            result = await bot.get_cookies(domain="h5.qzone.qq.com")
            cookie_str = result.get("cookies", "")
            if cookie_str:
                return await self.qzone.update_cookie(cookie_str)
        except Exception as e:
            logger.warning(f"刷新 Cookie 失败: {e}")
        return False

    # ── 管理员通知 ────────────────────────────────────────────

    async def _notify_admin(self, event: AstrMessageEvent, message: str):
        """发布失败后通知管理员群或管理员私聊"""
        bot = self._get_bot(event)
        if bot is None:
            logger.error(f"无法通知管理员（bot 未初始化）: {message}")
            return

        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
            AiocqhttpMessageEvent,
        )
        from astrbot.core.message.message_event_result import MessageChain

        chain = [Comp.Plain(message)]
        obmsg = await AiocqhttpMessageEvent._parse_onebot_json(MessageChain(chain))

        # 优先发送到配置的管理群
        if self.admin_notify_group and self.admin_notify_group.isdigit():
            try:
                await bot.send_group_msg(
                    group_id=int(self.admin_notify_group), message=obmsg
                )
                return
            except Exception as e:
                logger.error(f"通知管理群失败: {e}")

        # 兜底：私聊通知 AstrBot 管理员
        for admin_id in self._admins_id:
            if admin_id.isdigit():
                try:
                    await bot.send_private_msg(
                        user_id=int(admin_id), message=obmsg
                    )
                except Exception as e:
                    logger.error(f"通知管理员 {admin_id} 失败: {e}")

    # ── 发布逻辑（含重试） ───────────────────────────────────

    async def _do_publish(
        self, event: AstrMessageEvent, contrib: Contribution,
        session_id: str = "",
    ) -> str:
        """下载图片 → 上传 → 发布说说，最多重试 3 次，仍失败则通知管理员"""
        try:
            await self._ensure_qzone_ready(event)
        except Exception as e:
            logger.error(f"QZone 初始化失败: {e}")
            return f"发布失败: {e}"

        name = "匿名者" if contrib.anon else contrib.name

        if contrib.mode == "dialog":
            # 对话模式：正文只有署名，图片为渲染出的对话截图
            pub_text = f"【来自 {name} 的投稿】" if self.show_name else ""
            try:
                work_dir = self._get_work_dir(session_id) if session_id else self.cache_dir
                dialog_png = self._render_current_mode(contrib, work_dir)
                dialog_path = work_dir / "dialog_publish.png"
                dialog_path.write_bytes(dialog_png)
                uploaded_images = await self.qzone.upload_images([str(dialog_path)])
            except Exception as e:
                logger.error(f"对话模式渲染/上传失败: {e}")
                self._cleanup_cache()
                return f"发布失败（对话图片生成出错）: {e}"
        else:
            # 帖子模式：原有逻辑
            pub_text = contrib.merged_text
            if self.show_name:
                pub_text = f"【来自 {name} 的投稿】\n\n{pub_text}"

            uploaded_images = None
            if contrib.images:
                try:
                    paths = contrib.local_images or await download_images_to_temp(
                        contrib.images, self.cache_dir
                    )
                    if paths:
                        uploaded_images = await self.qzone.upload_images(paths)
                except Exception as e:
                    logger.error(f"图片上传失败: {e}")
                    self._cleanup_cache()
                    return f"发布失败（图片上传出错）: {e}"

        last_error: Exception | None = None
        for attempt in range(1, MAX_PUBLISH_RETRIES + 1):
            try:
                await self.qzone.publish_mood(pub_text, images=uploaded_images)
                self._cleanup_cache()
                return "发布成功!"
            except SessionExpiredError as e:
                last_error = e
                logger.warning(f"发布第 {attempt} 次失败（会话过期）: {e}")
                if not await self._refresh_cookie(event):
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"发布第 {attempt} 次失败: {e}")
                if attempt < MAX_PUBLISH_RETRIES:
                    await asyncio.sleep(2 * attempt)

        # 所有重试均失败
        error_msg = (
            f"[SchoolZone] 投稿发布失败（重试 {MAX_PUBLISH_RETRIES} 次后放弃）\n"
            f"投稿者: {contrib.name}（{'匿名' if contrib.anon else '署名'}）\n"
            f"内容: {pub_text[:100]}{'...' if len(pub_text) > 100 else ''}\n"
            f"错误: {last_error}"
        )
        logger.error(error_msg)
        await self._notify_admin(event, error_msg)
        self._cleanup_cache()

        return f"发布失败，已通知管理员。错误: {last_error}"

    def _cleanup_cache(self):
        """清理缓存目录内容"""
        if not self.cache_dir.exists():
            return
        for item in self.cache_dir.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception:
                pass

    # ── 渲染辅助 ─────────────────────────────────────────────

    def _get_work_dir(self, session_id: str) -> Path:
        sid_safe = session_id.replace(":", "_").replace("/", "_")
        return self.cache_dir / sid_safe

    async def _prepare_work_dir(
        self, contrib: Contribution, session_id: str
    ) -> Path:
        """准备工作目录：下载图片 + 头像"""
        work_dir = self._get_work_dir(session_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        if contrib.images and not contrib.local_images:
            contrib.local_images = await download_images_to_temp(
                contrib.images, work_dir
            )

        # 预下载头像（对话模式需要，提前准备以便切换时无延迟）
        if not any(work_dir.glob("avatar.*")):
            await download_avatar(contrib.uin, work_dir)

        return work_dir

    def _render_current_mode(
        self, contrib: Contribution, work_dir: Path
    ) -> bytes:
        """根据当前模式渲染预览图"""
        if contrib.mode == "dialog":
            return render_dialog(contrib, work_dir)
        return render_post(contrib, self.show_name, work_dir)

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
            "开始投稿，请发送文本/图片\n完成: /完成  取消: /取消"
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
            "开始匿名投稿，请发送文本/图片\n完成: /完成  取消: /取消"
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
                contrib.awaiting_confirm = True
                try:
                    work_dir = await self._prepare_work_dir(contrib, session_id)
                    png_data = self._render_current_mode(contrib, work_dir)
                    preview_path = work_dir / "preview.png"
                    preview_path.write_bytes(png_data)
                    yield event.image_result(str(preview_path))
                    mode_hint = "帖子模式" if contrib.mode == "post" else "对话模式"
                    yield event.plain_result(
                        f"当前: {mode_hint}\n"
                        "切换样式: /帖子模式 /对话模式\n"
                        "确认发布: /确认  取消: /取消"
                    )
                except Exception as e:
                    logger.warning(f"Typst 渲染预览失败，回退到纯文本: {e}")
                    preview = contrib.merged_text or "(无文字)"
                    n_img = len(contrib.images)
                    img_hint = f"\n共 {n_img} 张图片" if n_img else ""
                    yield event.plain_result(
                        f"--- 投稿预览 ---\n{preview}{img_hint}"
                        "\n\n确认发布: /确认  取消: /取消"
                    )
            event.stop_event()
            return

        if raw_text == "/取消":
            del self.contrib_sessions[session_id]
            self._cleanup_cache()
            yield event.plain_result("已取消投稿。")
            event.stop_event()
            return

        if raw_text in ("/帖子模式", "/对话模式"):
            if not contrib.awaiting_confirm:
                yield event.plain_result("请先发送 /完成 进行预览。")
            else:
                new_mode = "post" if raw_text == "/帖子模式" else "dialog"
                if contrib.mode == new_mode:
                    yield event.plain_result(
                        f"已经是{'帖子' if new_mode == 'post' else '对话'}模式了。"
                    )
                else:
                    contrib.mode = new_mode
                    try:
                        work_dir = self._get_work_dir(session_id)
                        png_data = self._render_current_mode(contrib, work_dir)
                        preview_path = work_dir / "preview.png"
                        preview_path.write_bytes(png_data)
                        yield event.image_result(str(preview_path))
                        mode_hint = "帖子模式" if new_mode == "post" else "对话模式"
                        yield event.plain_result(
                            f"已切换到{mode_hint}\n"
                            "确认发布: /确认  取消: /取消"
                        )
                    except Exception as e:
                        logger.warning(f"切换模式渲染失败: {e}")
                        yield event.plain_result(f"渲染失败: {e}")
            event.stop_event()
            return

        if raw_text == "/确认":
            if not contrib.awaiting_confirm:
                yield event.plain_result("请先发送 /完成 进行预览。")
            else:
                yield event.plain_result("正在发布到QQ空间...")
                result_msg = await self._do_publish(event, contrib, session_id)
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
            contrib.items.append(ContentItem("text", text))
        for url in images:
            contrib.items.append(ContentItem("image", url))
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
