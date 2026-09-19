from contextlib import contextmanager
from unittest.mock import patch

from web.components.faq import render_faq_sidebar


class _Sidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _StreamlitWithoutNestedExpanders:
    def __init__(self) -> None:
        self.sidebar = _Sidebar()
        self.expander_depth = 0
        self.expander_labels: list[str] = []
        self.markdown_calls: list[str] = []

    @contextmanager
    def expander(self, label: str, *, expanded: bool = False):
        if self.expander_depth:
            raise RuntimeError("nested expanders are unsupported")
        self.expander_labels.append(label)
        self.expander_depth += 1
        try:
            yield
        finally:
            self.expander_depth -= 1

    def markdown(self, text: str, **_kwargs) -> None:
        self.markdown_calls.append(text)


def test_faq_sidebar_renders_questions_without_nested_expanders() -> None:
    streamlit = _StreamlitWithoutNestedExpanders()
    content = "# FAQ\n### 问题一\n答案一\n### 问题二\n答案二"

    with (
        patch("web.components.faq.st", streamlit),
        patch("web.components.faq.get_language", return_value="zh_CN"),
        patch("web.components.faq.load_faq_content", return_value=content),
        patch(
            "web.components.faq.tr",
            side_effect=lambda _key, *, fallback: fallback,
        ),
    ):
        render_faq_sidebar()

    assert streamlit.expander_labels == ["FAQ"]
    assert streamlit.markdown_calls == [
        "**问题一**",
        "答案一",
        "**问题二**",
        "答案二",
    ]
