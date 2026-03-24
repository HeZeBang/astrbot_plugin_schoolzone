"""QZone API 测试 CLI 工具

支持的命令：
  feeds       - 获取说说列表
  upload      - 上传图片
  publish     - 发布说说
  test-all    - 测试所有功能（需要图片和文本）
"""

import argparse
import asyncio
import sys
from pathlib import Path
from .api import QZoneAPI, QZoneAPIError, SessionExpiredError


def _print_feed(index: int, feed: dict):
    """格式化输出单条说说，包括点赞、评论、回复"""
    summary = feed.get("summary", {}).get("summary", "N/A")
    comm = feed.get("comm", {})
    like = feed.get("like", {})
    comment_info = feed.get("comment", {})
    userinfo = feed.get("userinfo", {})
    nickname = userinfo.get("user", {}).get("nickname", "未知")
    feed_time = comm.get("time", "N/A")

    print(f"\n{'─' * 50}")
    print(f"说说 {index}  [{nickname}]  时间: {feed_time}")
    print(f"  {summary}")

    # 点赞
    like_num = like.get("num", 0)
    print(f"  👍 {like_num}", end="")
    likemans = like.get("likemans", [])
    if likemans:
        names = [lm.get("user", {}).get("nickname", "") for lm in likemans[:5]]
        names = [n for n in names if n]
        if names:
            print(f"  ({', '.join(names)}{'...' if len(likemans) > 5 else ''})", end="")
    print()

    # 评论
    comments = comment_info.get("comments", [])
    comment_num = comment_info.get("num", len(comments))
    if comment_num:
        print(f"  💬 {comment_num} 条评论:")
    for cmt in comments:
        _print_comment(cmt, indent=2)


def _print_comment(cmt: dict, indent: int = 2):
    """输出单条评论及其回复"""
    prefix = "  " * indent
    user = cmt.get("user", {})
    nickname = user.get("nickname", "匿名") if user else "匿名"
    content = cmt.get("content", "")
    date = cmt.get("date", "")
    like_num = cmt.get("like_num", 0)

    like_str = f"  👍{like_num}" if like_num else ""
    print(f"{prefix}├─ {nickname}: {content}  [{date}]{like_str}")

    # 回复列表
    replys = cmt.get("replys", [])
    for reply in replys:
        _print_reply(reply, indent=indent + 1)


def _print_reply(reply: dict, indent: int = 3):
    """输出单条回复"""
    prefix = "  " * indent
    user = reply.get("user", {})
    target = reply.get("target", {})
    nickname = user.get("nickname", "匿名") if user else "匿名"
    target_name = target.get("nickname", "") if target else ""
    content = reply.get("content", "")
    date = reply.get("date", "")
    like_num = reply.get("like_num", 0)

    like_str = f"  👍{like_num}" if like_num else ""
    reply_to = f" → {target_name}" if target_name else ""
    print(f"{prefix}└─ {nickname}{reply_to}: {content}  [{date}]{like_str}")


async def test_get_feeds(cookie: str, timestamp: int = None):
    """测试获取说说列表"""
    try:
        async with QZoneAPI(cookie) as api:
            print("📝 正在获取说说列表...")
            result = await api.get_active_feeds(timestamp=timestamp)

            if result.get("code") == 0 or result.get("ret") == 0:
                feeds = result.get("data", {}).get("vFeeds", [])
                print(f"✅ 成功获取 {len(feeds)} 条说说")
                for i, feed in enumerate(feeds, 1):
                    _print_feed(i, feed)
            else:
                print(f"❌ 获取失败: {result.get('message', result)}")
                return False
            return True
    except QZoneAPIError as e:
        print(f"❌ API 错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


async def test_upload_images(cookie: str, image_paths: list[str]):
    """测试上传图片"""
    # 验证文件存在
    valid_paths = []
    for path in image_paths:
        if not Path(path).exists():
            print(f"⚠️  文件不存在: {path}")
        else:
            valid_paths.append(path)

    if not valid_paths:
        print("❌ 没有有效的图片文件")
        return False

    try:
        async with QZoneAPI(cookie) as api:
            print(f"📸 正在上传 {len(valid_paths)} 张图片...")
            images = await api.upload_images(valid_paths)

            print(f"✅ 成功上传 {len(images)} 张图片")
            for i, img in enumerate(images, 1):
                print(f"\n图片 {i}:")
                print(f"  宽度: {img['width']}")
                print(f"  高度: {img['height']}")
                print(f"  URL: {img['url'][:80] if img['url'] else 'N/A'}")
            return images
    except QZoneAPIError as e:
        print(f"❌ API 错误: {e}")
        return None
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return None


async def test_publish_mood(cookie: str, content: str, image_paths: list[str] = None):
    """测试发布说说"""
    images = None

    # 如果提供了图片，先上传
    if image_paths:
        print("📸 首先上传图片...")
        images = await test_upload_images(cookie, image_paths)
        if images is None:
            return False
        print()

    try:
        async with QZoneAPI(cookie) as api:
            print(f"📤 正在发布说说...")
            result = await api.publish_mood(content, images=images)

            if result.get("code") == 0:
                print(f"✅ 成功发布说说")
                print(f"  内容: {content[:100]}")
                if images:
                    print(f"  附带 {len(images)} 张图片")
                return True
            else:
                print(f"❌ 发布失败: {result.get('message', result)}")
                return False
    except QZoneAPIError as e:
        print(f"❌ API 错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


async def test_all(cookie: str, content: str = None, image_paths: list[str] = None):
    """测试所有功能"""
    print("🚀 开始全功能测试\n")
    print("=" * 50)

    # 测试 1: 获取说说列表
    print("测试 1/3: 获取说说列表")
    print("-" * 50)
    success1 = await test_get_feeds(cookie)
    print()

    # 测试 2: 上传图片（如果提供了）
    success2 = True
    if image_paths:
        print("测试 2/3: 上传图片")
        print("-" * 50)
        success2 = await test_upload_images(cookie, image_paths) is not None
        print()

    # 测试 3: 发布说说（如果提供了内容）
    success3 = True
    if content:
        print("测试 3/3: 发布说说")
        print("-" * 50)
        success3 = await test_publish_mood(cookie, content, image_paths)
        print()

    # 总结
    print("=" * 50)
    print("📊 测试结果总结")
    print(f"  获取说说: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"  上传图片: {'✅ 成功' if success2 else '❌ 失败' if image_paths else '⏭️  跳过'}")
    print(f"  发布说说: {'✅ 成功' if success3 else '❌ 失败' if content else '⏭️  跳过'}")

    return success1 and success2 and success3


def main():
    parser = argparse.ArgumentParser(
        description="QZone API 测试 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：

  # 测试获取说说列表
  python -m qzone.cli feeds --cookie "your_cookie_string"

  # 上传图片
  python -m qzone.cli upload --cookie "your_cookie_string" image1.jpg image2.jpg

  # 发布纯文本说说
  python -m qzone.cli publish --cookie "your_cookie_string" --content "你好，这是一条测试说说"

  # 发布带图片的说说
  python -m qzone.cli publish --cookie "your_cookie_string" --content "带图片的说说" image1.jpg

  # 全功能测试
  python -m qzone.cli test-all --cookie "your_cookie_string" --content "测试" image1.jpg
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # feeds 命令
    feeds_parser = subparsers.add_parser("feeds", help="获取说说列表")
    feeds_parser.add_argument("--cookie", required=True, help="QQ 空间 cookie 字符串")
    feeds_parser.add_argument("--timestamp", type=int, help="Unix 时间戳（可选）")

    # upload 命令
    upload_parser = subparsers.add_parser("upload", help="上传图片")
    upload_parser.add_argument("--cookie", required=True, help="QQ 空间 cookie 字符串")
    upload_parser.add_argument("images", nargs="+", help="图片文件路径")

    # publish 命令
    publish_parser = subparsers.add_parser("publish", help="发布说说")
    publish_parser.add_argument("--cookie", required=True, help="QQ 空间 cookie 字符串")
    publish_parser.add_argument("--content", required=True, help="说说内容")
    publish_parser.add_argument("images", nargs="*", help="图片文件路径（可选）")

    # test-all 命令
    testall_parser = subparsers.add_parser("test-all", help="测试所有功能")
    testall_parser.add_argument("--cookie", required=True, help="QQ 空间 cookie 字符串")
    testall_parser.add_argument("--content", help="说说内容（可选，用于发布测试）")
    testall_parser.add_argument("images", nargs="*", help="图片文件路径（可选）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 运行对应的命令
    try:
        if args.command == "feeds":
            success = asyncio.run(test_get_feeds(args.cookie, args.timestamp))
            return 0 if success else 1

        elif args.command == "upload":
            result = asyncio.run(test_upload_images(args.cookie, args.images))
            return 0 if result is not None else 1

        elif args.command == "publish":
            success = asyncio.run(test_publish_mood(args.cookie, args.content, args.images or None))
            return 0 if success else 1

        elif args.command == "test-all":
            success = asyncio.run(test_all(args.cookie, args.content, args.images or None))
            return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        return 130
    except Exception as e:
        print(f"\n❌ 发生错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
