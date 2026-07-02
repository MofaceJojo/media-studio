"""Lightweight Media Studio shell helpers."""

from __future__ import annotations

from html import escape

import streamlit as st


def inject_studio_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --studio-bg: #11161f;
          --studio-sidebar: #161c25;
          --studio-surface: #1b2330;
          --studio-surface-soft: #202a38;
          --studio-panel: rgba(245, 247, 250, 0.96);
          --studio-panel-soft: rgba(236, 240, 245, 0.92);
          --studio-border: rgba(100, 116, 139, 0.18);
          --studio-border-strong: rgba(96, 165, 250, 0.28);
          --studio-ink: #e6edf7;
          --studio-ink-soft: #9aa7bb;
          --studio-copy: #516072;
          --studio-copy-strong: #1f2937;
          --studio-accent: #58b6ff;
          --studio-accent-strong: #2f81f7;
          --studio-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        }
        header[data-testid="stHeader"] {
          display: none;
        }
        .stAppToolbar {
          display: none;
        }
        .stDeployButton {
          display: none;
        }
        #MainMenu, footer {
          visibility: hidden;
        }
        .stApp {
          background: linear-gradient(180deg, #edf2f8 0%, #e8edf5 100%);
        }
        .block-container {
          max-width: 1280px;
          padding-top: 1rem;
          padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
          background: var(--studio-sidebar);
          border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        section[data-testid="stSidebar"] .block-container {
          padding-top: 0.8rem;
        }
        section[data-testid="stSidebar"] * {
          color: var(--studio-ink);
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          background: rgba(255, 255, 255, 0.02);
        }
        .studio-hero {
          border: 1px solid rgba(96, 165, 250, 0.14);
          border-radius: 14px;
          background: linear-gradient(135deg, #1a2332 0%, #0f1724 100%);
          padding: 18px 20px;
          margin-bottom: 14px;
          box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
        }
        .studio-hero-copy {
          max-width: 960px;
          padding: 0;
          margin: 0;
        }
        .studio-kicker {
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--studio-accent);
          margin-bottom: 8px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-title {
          font-size: 26px;
          line-height: 1.15;
          font-weight: 650;
          color: #f8fbff;
          margin-bottom: 6px;
        }
        .studio-subtitle {
          font-size: 14px;
          line-height: 1.55;
          color: rgba(226, 232, 240, 0.92);
          max-width: 900px;
        }
        @media (max-width: 900px) {
          .studio-hero-copy {
            max-width: 100%;
          }
        }
        .studio-card {
          border: 1px solid var(--studio-border);
          border-radius: 12px;
          background: var(--studio-panel);
          padding: 14px 16px;
          min-height: 120px;
          box-shadow: var(--studio-shadow);
        }
        .studio-card-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--studio-copy-strong);
          margin-bottom: 8px;
        }
        .studio-card-copy {
          font-size: 13px;
          line-height: 1.55;
          color: var(--studio-copy);
        }
        .studio-panel {
          border: 1px solid var(--studio-border);
          border-radius: 12px;
          background: var(--studio-panel);
          padding: 14px 16px;
          margin-bottom: 16px;
          box-shadow: var(--studio-shadow);
        }
        .studio-panel-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--studio-copy-strong);
          margin-bottom: 10px;
        }
        .studio-context-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px;
        }
        .studio-context-item {
          border: 1px solid rgba(100, 116, 139, 0.12);
          border-radius: 10px;
          background: var(--studio-panel-soft);
          padding: 10px 12px;
          min-height: 72px;
        }
        .studio-context-label {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #64748b;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-context-value {
          font-size: 14px;
          font-weight: 600;
          color: var(--studio-copy-strong);
          margin-top: 4px;
          line-height: 1.35;
        }
        .studio-context-copy {
          font-size: 12px;
          color: var(--studio-copy);
          margin-top: 4px;
          line-height: 1.45;
        }
        .studio-note {
          font-size: 13px;
          line-height: 1.55;
          color: var(--studio-copy);
        }
        .studio-metric {
          border: 1px solid rgba(96, 165, 250, 0.16);
          border-radius: 12px;
          background: linear-gradient(180deg, #182231 0%, #111923 100%);
          padding: 12px 14px;
          box-shadow: 0 8px 20px rgba(15, 23, 42, 0.14);
        }
        .studio-metric-label {
          font-size: 11px;
          text-transform: uppercase;
          color: rgba(125, 211, 252, 0.74);
          letter-spacing: 0.06em;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-metric-value {
          font-size: 22px;
          font-weight: 650;
          color: #f8fbff;
          margin-top: 2px;
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        button[kind="secondary"],
        button[kind="primary"] {
          border-radius: 10px !important;
          border: 1px solid rgba(96, 165, 250, 0.16) !important;
          background: linear-gradient(180deg, #1a2432 0%, #131c28 100%) !important;
          color: #e5eefb !important;
          box-shadow: 0 6px 18px rgba(15, 23, 42, 0.14) !important;
          transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease !important;
        }
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover {
          border-color: rgba(125, 211, 252, 0.46) !important;
          background: linear-gradient(180deg, rgba(20, 36, 62, 0.98) 0%, rgba(31, 53, 90, 1) 100%) !important;
          color: #f8fbff !important;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18) !important;
        }
        div[data-testid="stButton"] > button:active,
        div[data-testid="stDownloadButton"] > button:active,
        button[kind="secondary"]:active,
        button[kind="primary"]:active {
          box-shadow: 0 4px 12px rgba(15, 23, 42, 0.14) !important;
        }
        div[data-testid="stButton"] > button p,
        div[data-testid="stDownloadButton"] > button p {
          color: inherit !important;
        }
        div[data-testid="stPageLink-NavLinkContainer"] a,
        a[data-testid="stPageLink-NavLink"] {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 42px;
          border-radius: 10px;
          border: 1px solid rgba(100, 116, 139, 0.18);
          background: rgba(248, 250, 252, 0.88);
          color: var(--studio-copy-strong) !important;
          text-decoration: none !important;
          font-weight: 600;
          transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
          box-shadow: none;
        }
        div[data-testid="stPageLink-NavLinkContainer"] a:hover,
        a[data-testid="stPageLink-NavLink"]:hover {
          border-color: rgba(56, 189, 248, 0.42);
          background: rgba(224, 242, 254, 0.84);
          color: #082f49 !important;
          box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
        }
        div[data-testid="stPageLink-NavLinkContainer"] a p,
        a[data-testid="stPageLink-NavLink"] p {
          color: inherit !important;
          font-weight: inherit !important;
        }
        button[role="tab"] {
          border-radius: 999px !important;
          border: 1px solid rgba(100, 116, 139, 0.16) !important;
          background: rgba(255, 255, 255, 0.72) !important;
          color: #334155 !important;
        }
        button[role="tab"][aria-selected="true"] {
          border-color: rgba(56, 189, 248, 0.34) !important;
          background: rgba(233, 243, 255, 0.96) !important;
          color: #0f172a !important;
          box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
        }
        [data-baseweb="tab-highlight"] {
          background: linear-gradient(90deg, #38bdf8 0%, #7dd3fc 100%) !important;
          height: 3px !important;
          border-radius: 999px !important;
        }
        [data-baseweb="tab-border"] {
          background: rgba(148, 163, 184, 0.18) !important;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] textarea,
        input, textarea {
          border-radius: 12px !important;
        }
        div[data-baseweb="radio"] label,
        div[data-baseweb="checkbox"] label {
          color: #0f172a !important;
        }
        input[type="radio"],
        input[type="checkbox"] {
          accent-color: #38bdf8 !important;
        }
        label[data-baseweb="radio"] > div:first-child,
        label[data-baseweb="checkbox"] > span:first-child {
          background: rgba(255, 255, 255, 0.96) !important;
          border-color: rgba(56, 189, 248, 0.28) !important;
          box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.12) !important;
        }
        label[data-baseweb="radio"] > div:first-child > div {
          background: transparent !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-child {
          background: rgba(56, 189, 248, 0.16) !important;
          border-color: #38bdf8 !important;
          box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14) !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-child > div {
          background: #38bdf8 !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
          background: #38bdf8 !important;
          border-color: #38bdf8 !important;
          box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14) !important;
        }
        div[data-baseweb="slider"] [role="slider"] {
          background: #38bdf8 !important;
          border-color: #0f172a !important;
          box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14) !important;
        }
        div[data-baseweb="slider"] > div {
          background: transparent !important;
        }
        div[data-baseweb="slider"] > div > div {
          background-color: rgba(56, 189, 248, 0.18) !important;
          background-image: none !important;
          border-radius: 999px !important;
          overflow: hidden !important;
        }
        div[data-baseweb="slider"] > div > div > div {
          background-color: #38bdf8 !important;
          background-image: none !important;
          border-radius: 999px !important;
        }
        div[data-baseweb="slider"] > div > div > div:first-child,
        div[data-baseweb="slider"] > div > div > div:last-child {
          background-color: #38bdf8 !important;
        }
        div[data-baseweb="slider"] > div > div + div {
          background: transparent !important;
          background-image: none !important;
        }
        div[data-baseweb="slider"] [data-testid="stSliderTickBar"] {
          background: transparent !important;
        }
        div[data-baseweb="slider"] [data-testid="stSliderTickBar"] [data-testid="stMarkdownContainer"] {
          background: transparent !important;
        }
        [data-testid="stSliderThumbValue"] {
          border: 1px solid rgba(56, 189, 248, 0.46) !important;
          background: rgba(240, 249, 255, 0.98) !important;
          color: #0c4a6e !important;
          box-shadow: 0 10px 20px rgba(8, 47, 73, 0.12) !important;
        }
        [data-testid="stSliderThumbValue"] [data-testid="stMarkdownContainer"],
        [data-testid="stSliderThumbValue"] p {
          color: #0c4a6e !important;
          border-color: rgba(56, 189, 248, 0.46) !important;
        }
        span[data-baseweb="tag"] {
          background: linear-gradient(180deg, rgba(14, 116, 144, 0.94) 0%, rgba(3, 105, 161, 0.94) 100%) !important;
          border: 1px solid rgba(186, 230, 253, 0.82) !important;
          color: #eff6ff !important;
          box-shadow: 0 10px 20px rgba(8, 47, 73, 0.14) !important;
        }
        span[data-baseweb="tag"] *,
        span[data-baseweb="tag"] [data-baseweb="icon"],
        span[data-baseweb="tag"] svg,
        span[data-baseweb="tag"] path,
        span[data-baseweb="tag"] span {
          color: #eff6ff !important;
          fill: #eff6ff !important;
        }
        div[data-baseweb="select"] svg,
        div[data-baseweb="radio"] svg,
        div[data-baseweb="checkbox"] svg {
          color: #38bdf8 !important;
          fill: #38bdf8 !important;
        }
        div[data-testid="stAlert"] {
          border-radius: 12px;
          border: 1px solid rgba(96, 165, 250, 0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_studio_hero(title: str, subtitle: str, kicker: str = "Media Studio") -> None:
    st.markdown(
        f"""
        <div class="studio-hero">
          <div class="studio-hero-copy">
            <div class="studio-kicker">{kicker}</div>
            <div class="studio-title">{title}</div>
            <div class="studio-subtitle">{subtitle}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: list[tuple[str, str]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(
                f"""
                <div class="studio-metric">
                  <div class="studio-metric-label">{label}</div>
                  <div class="studio-metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_module_cards(cards: list[tuple[str, str, str]]) -> None:
    cards_per_row = 3
    for start in range(0, len(cards), cards_per_row):
        row = cards[start : start + cards_per_row]
        cols = st.columns(cards_per_row)
        for idx, col in enumerate(cols):
            if idx >= len(row):
                continue
            title, copy, page = row[idx]
            with col:
                st.markdown(
                    f"""
                    <div class="studio-card">
                      <div class="studio-card-title">{title}</div>
                      <div class="studio-card-copy">{copy}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.page_link(page, label=f"打开 {title}", width="stretch")


def render_workspace_context(
    items: list[tuple[str, str, str | None]],
    *,
    title: str = "当前工作上下文",
    note: str | None = None,
) -> None:
    valid_items = [(label, value, hint) for label, value, hint in items if value]
    if not valid_items and not note:
        return

    item_html = "".join(
        f"""
        <div class="studio-context-item">
          <div class="studio-context-label">{escape(label)}</div>
          <div class="studio-context-value">{escape(value)}</div>
          {f'<div class="studio-context-copy">{escape(hint)}</div>' if hint else ''}
        </div>
        """
        for label, value, hint in valid_items
    )

    note_html = f'<div class="studio-note">{escape(note)}</div>' if note else ""
    grid_html = f'<div class="studio-context-grid">{item_html}</div>' if item_html else ""
    st.markdown(
        f"""
        <div class="studio-panel">
          <div class="studio-panel-title">{escape(title)}</div>
          {grid_html}
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
