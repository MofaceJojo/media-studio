import asyncio

from morpheus_video_studio.utils.content_generators import generate_title


class _FakeLLM:
    def __init__(self, reply: str):
        self._reply = reply

    async def __call__(self, prompt, **kwargs):
        return self._reply


def _title(content: str, reply: str) -> str:
    return asyncio.run(generate_title(_FakeLLM(reply), content, strategy="llm", max_length=15))


def test_english_title_on_chinese_content_falls_back_to_content():
    # 复现 "We need to" bug:中文内容 + 英文标题 → 回退到内容(取首行,≤15字)
    title = _title("圣母玛利亚的故事", "We need to")
    assert title == "圣母玛利亚的故事"
    assert any('一' <= c <= '鿿' for c in title)


def test_chinese_title_on_chinese_content_kept():
    assert _title("绿茶的功效与作用", "绿茶的养生秘密") == "绿茶的养生秘密"


def test_english_title_on_english_content_kept():
    assert _title("the benefits of green tea", "Green Tea Tips") == "Green Tea Tips"
