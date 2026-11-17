"""生成「念一遍」用的离线语音片段。

手机上并不是每台都有中文语音引擎 —— 有的精简 ROM 根本没装，点播报只会提示
「还没准备好朗读」。所以把播报里用得到的**词和数字**提前录成小段音频打进 APK，
系统没有语音引擎时就用这些片段拼出一句话。

为什么只录词、不录整句：整句是组合出来的（线路号 + 分钟 + 站数 + 判断），
不可能穷举。而站名是开放集合，几万个，录不了 —— 所以离线版播报**不含站名**，
只说「三十六路，还有十四分钟，车在前面九站。该出门了。」这样一句。

依赖 edge-tts（微软的在线语音合成，只在生成本地文件时用，App 运行时不需要网络）：
    python -m pip install edge-tts

用法：
    python gen_audio.py          # 生成到 web/audio/
    python gen_audio.py --check  # 只列出缺哪些，不生成
"""

import asyncio
import os
import sys

try:
    import edge_tts
except ImportError:
    sys.exit("缺少 edge-tts：python -m pip install edge-tts")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "web", "audio")

# 音色：晓晓，普通话女声，吐字清楚。
# 语速 +8%（比正常略快一点点，拼句后总时长才压得住）—— 原来 -12% 用在整句上还行，但拼句时每段的
# 拖音叠在一起，听起来又快又顿。要慢也是靠段与段之间留间隔，不是每段拖长。
VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+12%"

CN = "零一二三四五六七八九"


def cn_num(n):
    """0-99 的中文读法。100 以上由 JS 用「一 + 百 + 五十九」这样的片段拼。"""
    if n < 10:
        return CN[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + CN[n % 10]
    t, o = divmod(n, 10)
    return CN[t] + "十" + (CN[o] if o else "")


# 播报里会用到的固定短语。id 是打包进 APK 的文件名，值是念出来的字。
WORDS = {
    "p_road": "路",
    "p_have": "还有",
    "p_min": "分钟",
    "p_ahead": "车在前面",
    "p_stop": "站",
    "p_now": "马上到",
    "p_go": "该出门了",
    "p_ready": "可以准备走了",
    "p_wait": "不着急，坐一会儿再走",
    "p_here": "车已经在站上，快上车",
    "p_closed": "今天收班了",
    "p_nocar": "暂时没有车",
    "p_notstart": "车还没发车",
    "p_dirs": "个方向",
    "p_tapdir": "点一个方向，看几分钟到",
    "p_buses": "辆车在路上",
    "p_found": "找到",
    "p_lines": "条线路",
    "p_and": "和",
    "p_stops": "个站",
    "p_notfound": "没找到",
    "p_hundred": "百",
    "p_late": "赶不上了，等下一趟",
}


def items():
    """(文件名, 要念的字) 的完整清单。"""
    out = []
    for n in range(100):
        out.append(("n%d" % n, cn_num(n)))
    # 线路号里的字母：K125、B105、JD36 这些
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        out.append(("l" + ch, ch))
    for k, v in WORDS.items():
        out.append((k, v))
    return out


async def one(name, text, sem):
    path = os.path.join(OUT, name + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 0 and "--force" not in sys.argv:
        return name, "skip"
    async with sem:
        for attempt in range(3):
            try:
                c = edge_tts.Communicate(text, VOICE, rate=RATE)
                await c.save(path)
                if os.path.getsize(path) > 0:
                    return name, "ok"
            except Exception as e:
                if attempt == 2:
                    return name, "fail:%s" % str(e)[:60]
                await asyncio.sleep(1.2)
    return name, "fail"


async def main():
    os.makedirs(OUT, exist_ok=True)
    all_items = items()
    if "--check" in sys.argv:
        miss = [n for n, _ in all_items
                if not os.path.exists(os.path.join(OUT, n + ".mp3"))]
        print("应有 %d 段，缺 %d 段" % (len(all_items), len(miss)))
        print("缺的：", " ".join(miss[:30]))
        return

    sem = asyncio.Semaphore(5)
    res = await asyncio.gather(*[one(n, t, sem) for n, t in all_items])
    ok = sum(1 for _, r in res if r in ("ok", "skip"))
    bad = [(n, r) for n, r in res if r.startswith("fail")]
    total = sum(os.path.getsize(os.path.join(OUT, n + ".mp3"))
                for n, _ in all_items
                if os.path.exists(os.path.join(OUT, n + ".mp3")))
    print("生成 %d/%d 段，共 %.0f KB" % (ok, len(all_items), total / 1024))
    for n, r in bad[:8]:
        print("  失败", n, r)
    if bad:
        print("有失败就再跑一次（已生成的会跳过）")


if __name__ == "__main__":
    asyncio.run(main())
