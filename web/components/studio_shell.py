"""Lightweight Media Studio shell helpers.

Design tokens follow design-system/morpheus-video-studio/MASTER.md
(Navy professional light, chosen by the user 2026-07-06: navy primary
#1E3A5F, confirm-green accent #059669, off-white background #F8FAFC,
deep-navy sidebar, Inter typography).
"""

from __future__ import annotations

from html import escape

import streamlit as st


def inject_studio_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
          /* Design-system tokens (MASTER.md, 2026-07-06 海军蓝浅色商务风) */
          --color-primary: #1E3A5F;
          --color-primary-soft: rgba(30, 58, 95, 0.08);
          --color-primary-ring: rgba(30, 58, 95, 0.4);
          --color-secondary: #2563EB;
          --color-accent: #059669;
          --color-bg: #F8FAFC;
          --color-surface: #FFFFFF;
          --color-surface-soft: #F1F3F5;
          --color-border: #E4E7EB;
          --color-border-strong: rgba(30, 58, 95, 0.35);
          --color-ink: #0F172A;
          --color-ink-body: #334155;
          --color-ink-soft: #64748B;
          --color-destructive: #DC2626;
          --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.06);
          --shadow-md: 0 8px 24px rgba(15, 23, 42, 0.10);
          --radius-card: 12px;
          --radius-control: 10px;

          /* Legacy aliases kept for older page CSS */
          --studio-bg: var(--color-bg);
          --studio-sidebar: #16304D;
          --studio-surface: var(--color-surface);
          --studio-surface-soft: var(--color-surface-soft);
          --studio-panel: var(--color-surface);
          --studio-panel-soft: rgba(255, 255, 255, 0.03);
          --studio-border: var(--color-border);
          --studio-border-strong: var(--color-border-strong);
          --studio-ink: var(--color-ink);
          --studio-ink-soft: var(--color-ink-soft);
          --studio-copy: var(--color-ink-body);
          --studio-copy-strong: var(--color-ink);
          --studio-accent: var(--color-primary);
          --studio-accent-strong: var(--color-secondary);
          --studio-shadow: var(--shadow-sm);
        }
        html, body, .stApp, [class*="css"] {
          font-family: 'Inter', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
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
          background: linear-gradient(180deg, #FAFCFE 0%, var(--color-bg) 100%);
          color: var(--color-ink-body);
        }
        .block-container {
          max-width: 1280px;
          padding-top: 1rem;
          padding-bottom: 2rem;
        }

        /* ── Sidebar ─────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {
          background: var(--studio-sidebar);
          border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        section[data-testid="stSidebar"] .block-container {
          padding-top: 0.8rem;
        }
        section[data-testid="stSidebar"] * {
          color: #E6EDF7;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
          border: 1px solid rgba(255, 255, 255, 0.10);
          border-radius: var(--radius-card);
          background: rgba(255, 255, 255, 0.04);
        }
        /* Active page highlighted in sidebar nav (nav-state-active) */
        section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {
          border-radius: var(--radius-control);
          min-height: 44px;
          transition: background 0.18s ease-out, color 0.18s ease-out;
        }
        section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {
          background: rgba(255, 255, 255, 0.10);
        }
        section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] {
          background: rgba(255, 255, 255, 0.12);
          border-left: 3px solid #34D399;
        }

        /* ── Hero ────────────────────────────────────────────────── */
        .studio-hero {
          border: 1px solid rgba(30, 58, 95, 0.5);
          border-radius: 14px;
          background: linear-gradient(135deg, #24466E 0%, var(--color-primary) 55%, #16304D 100%);
          padding: 18px 20px;
          margin-bottom: 14px;
          box-shadow: var(--shadow-md);
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
          color: #34D399;
          margin-bottom: 8px;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-title {
          font-size: 26px;
          line-height: 1.15;
          font-weight: 700;
          color: #FFFFFF;
          margin-bottom: 6px;
        }
        .studio-subtitle {
          font-size: 14px;
          line-height: 1.55;
          color: #D7E3F2;
          max-width: 900px;
        }
        @media (max-width: 900px) {
          .studio-hero-copy {
            max-width: 100%;
          }
        }

        /* ── Cards & panels ──────────────────────────────────────── */
        .studio-card {
          border: 1px solid var(--color-border);
          border-radius: var(--radius-card);
          background: var(--color-surface);
          padding: 14px 16px;
          min-height: 120px;
          box-shadow: var(--shadow-sm);
          transition: border-color 0.18s ease-out, transform 0.18s ease-out;
        }
        .studio-card:hover {
          border-color: var(--color-border-strong);
          transform: translateY(-2px);
        }
        .studio-card-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--color-ink);
          margin-bottom: 8px;
        }
        .studio-card-copy {
          font-size: 13px;
          line-height: 1.55;
          color: var(--color-ink-body);
        }
        .studio-panel {
          border: 1px solid var(--color-border);
          border-radius: var(--radius-card);
          background: var(--color-surface);
          padding: 14px 16px;
          margin-bottom: 16px;
          box-shadow: var(--shadow-sm);
        }
        .studio-panel-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--color-ink);
          margin-bottom: 10px;
        }
        .studio-context-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px;
        }
        .studio-context-item {
          border: 1px solid var(--color-border);
          border-radius: var(--radius-control);
          background: var(--color-surface-soft);
          padding: 10px 12px;
          min-height: 72px;
        }
        .studio-context-label {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--color-ink-soft);
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-context-value {
          font-size: 14px;
          font-weight: 600;
          color: var(--color-ink);
          margin-top: 4px;
          line-height: 1.35;
        }
        .studio-context-copy {
          font-size: 12px;
          color: var(--color-ink-body);
          margin-top: 4px;
          line-height: 1.45;
        }
        .studio-note {
          font-size: 13px;
          line-height: 1.55;
          color: var(--color-ink-body);
        }
        .studio-metric {
          border: 1px solid var(--color-border);
          border-left: 3px solid var(--color-accent);
          border-radius: var(--radius-card);
          background: var(--color-surface);
          padding: 12px 14px;
          box-shadow: var(--shadow-sm);
        }
        .studio-metric-label {
          font-size: 11px;
          text-transform: uppercase;
          color: var(--color-accent);
          letter-spacing: 0.06em;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .studio-metric-value {
          font-size: 22px;
          font-weight: 700;
          color: var(--color-ink);
          margin-top: 2px;
          font-variant-numeric: tabular-nums;
        }

        /* ── Buttons (44px touch target, distinct states, focus ring) ── */
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        button[kind="secondary"] {
          min-height: 44px;
          border-radius: var(--radius-control) !important;
          border: 1px solid var(--color-border) !important;
          background: var(--color-surface) !important;
          color: var(--color-ink) !important;
          box-shadow: var(--shadow-sm) !important;
          cursor: pointer;
          transition: border-color 0.18s ease-out, background 0.18s ease-out, box-shadow 0.18s ease-out !important;
        }
        button[kind="primary"],
        div[data-testid="stButton"] > button[kind="primary"] {
          min-height: 44px;
          border-radius: var(--radius-control) !important;
          border: 1px solid var(--color-primary) !important;
          background: linear-gradient(180deg, #2B4C77 0%, var(--color-primary) 100%) !important;
          color: #FFFFFF !important;
          box-shadow: 0 6px 18px rgba(30, 58, 95, 0.28) !important;
          cursor: pointer;
          transition: filter 0.18s ease-out, box-shadow 0.18s ease-out !important;
        }
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        button[kind="secondary"]:hover {
          border-color: var(--color-border-strong) !important;
          background: var(--color-primary-soft) !important;
          color: var(--color-ink) !important;
          box-shadow: var(--shadow-md) !important;
        }
        button[kind="primary"]:hover {
          filter: brightness(1.12);
          box-shadow: 0 8px 22px rgba(30, 58, 95, 0.38) !important;
        }
        div[data-testid="stButton"] > button:active,
        div[data-testid="stDownloadButton"] > button:active,
        button[kind="secondary"]:active,
        button[kind="primary"]:active {
          box-shadow: var(--shadow-sm) !important;
          transform: translateY(1px);
        }
        div[data-testid="stButton"] > button:focus-visible,
        div[data-testid="stDownloadButton"] > button:focus-visible,
        a[data-testid="stPageLink-NavLink"]:focus-visible {
          outline: 2px solid var(--color-primary-ring) !important;
          outline-offset: 2px !important;
        }
        div[data-testid="stButton"] > button:disabled {
          opacity: 0.45 !important;
          cursor: not-allowed !important;
        }
        div[data-testid="stButton"] > button p,
        div[data-testid="stDownloadButton"] > button p {
          color: inherit !important;
        }

        /* ── Page links (module cards) ───────────────────────────── */
        div[data-testid="stPageLink-NavLinkContainer"] a,
        a[data-testid="stPageLink-NavLink"] {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 44px;
          border-radius: var(--radius-control);
          border: 1px solid var(--color-border);
          background: var(--color-surface-soft);
          color: var(--color-ink) !important;
          text-decoration: none !important;
          font-weight: 600;
          cursor: pointer;
          transition: border-color 0.18s ease-out, background 0.18s ease-out;
          box-shadow: none;
        }
        div[data-testid="stPageLink-NavLinkContainer"] a:hover,
        a[data-testid="stPageLink-NavLink"]:hover {
          border-color: var(--color-primary) !important;
          background: var(--color-primary-soft);
          color: var(--color-ink) !important;
        }
        div[data-testid="stPageLink-NavLinkContainer"] a p,
        a[data-testid="stPageLink-NavLink"] p {
          color: inherit !important;
          font-weight: inherit !important;
        }

        /* ── Tabs ────────────────────────────────────────────────── */
        button[role="tab"] {
          border-radius: 999px !important;
          border: 1px solid var(--color-border) !important;
          background: var(--color-surface-soft) !important;
          color: var(--color-ink-body) !important;
          transition: background 0.18s ease-out, color 0.18s ease-out !important;
        }
        button[role="tab"][aria-selected="true"] {
          border-color: var(--color-border-strong) !important;
          background: var(--color-primary-soft) !important;
          color: var(--color-ink) !important;
        }
        [data-baseweb="tab-highlight"] {
          background: linear-gradient(90deg, var(--color-primary) 0%, var(--color-secondary) 100%) !important;
          height: 3px !important;
          border-radius: 999px !important;
        }
        [data-baseweb="tab-border"] {
          background: var(--color-border) !important;
        }

        /* ── Inputs ──────────────────────────────────────────────── */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] textarea,
        input, textarea {
          border-radius: var(--radius-control) !important;
        }
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="textarea"]:focus-within {
          border-color: var(--color-primary) !important;
          box-shadow: 0 0 0 3px var(--color-primary-soft) !important;
        }
        div[data-baseweb="radio"] label,
        div[data-baseweb="checkbox"] label {
          color: var(--color-ink-body) !important;
        }
        input[type="radio"],
        input[type="checkbox"] {
          accent-color: var(--color-primary) !important;
        }
        label[data-baseweb="radio"] > div:first-child,
        label[data-baseweb="checkbox"] > span:first-child {
          background: var(--color-surface) !important;
          border-color: var(--color-border) !important;
          box-shadow: inset 0 0 0 1px var(--color-border) !important;
        }
        label[data-baseweb="radio"] > div:first-child > div {
          background: transparent !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-child {
          background: var(--color-primary-soft) !important;
          border-color: var(--color-primary) !important;
          box-shadow: 0 0 0 4px var(--color-primary-soft) !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-child > div {
          background: var(--color-primary) !important;
        }
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
          background: var(--color-primary) !important;
          border-color: var(--color-primary) !important;
          box-shadow: 0 0 0 4px var(--color-primary-soft) !important;
        }

        /* ── Slider ──────────────────────────────────────────────── */
        div[data-baseweb="slider"] [role="slider"] {
          background: var(--color-primary) !important;
          border-color: var(--color-bg) !important;
          box-shadow: 0 0 0 4px var(--color-primary-soft) !important;
        }
        div[data-baseweb="slider"] > div {
          background: transparent !important;
        }
        div[data-baseweb="slider"] > div > div {
          background-color: rgba(30, 58, 95, 0.18) !important;
          background-image: none !important;
          border-radius: 999px !important;
          overflow: hidden !important;
        }
        div[data-baseweb="slider"] > div > div > div {
          background-color: var(--color-primary) !important;
          background-image: none !important;
          border-radius: 999px !important;
        }
        div[data-baseweb="slider"] > div > div > div:first-child,
        div[data-baseweb="slider"] > div > div > div:last-child {
          background-color: var(--color-primary) !important;
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
          border: 1px solid var(--color-border-strong) !important;
          background: var(--color-surface) !important;
          color: var(--color-ink) !important;
          box-shadow: var(--shadow-sm) !important;
        }
        [data-testid="stSliderThumbValue"] [data-testid="stMarkdownContainer"],
        [data-testid="stSliderThumbValue"] p {
          color: var(--color-ink) !important;
          border-color: var(--color-border-strong) !important;
        }

        /* ── Multiselect tags ────────────────────────────────────── */
        span[data-baseweb="tag"] {
          background: linear-gradient(180deg, #2B4C77 0%, var(--color-primary) 100%) !important;
          border: 1px solid rgba(30, 58, 95, 0.3) !important;
          color: #FFFFFF !important;
          box-shadow: none !important;
        }
        span[data-baseweb="tag"] *,
        span[data-baseweb="tag"] [data-baseweb="icon"],
        span[data-baseweb="tag"] svg,
        span[data-baseweb="tag"] path,
        span[data-baseweb="tag"] span {
          color: #FFFFFF !important;
          fill: #FFFFFF !important;
        }
        div[data-baseweb="select"] svg,
        div[data-baseweb="radio"] svg,
        div[data-baseweb="checkbox"] svg {
          color: var(--color-primary) !important;
          fill: var(--color-primary) !important;
        }

        /* ── Alerts & misc ───────────────────────────────────────── */
        div[data-testid="stAlert"] {
          border-radius: var(--radius-card);
          border: 1px solid var(--color-border-strong);
        }
        div[data-testid="stExpander"] {
          border: 1px solid var(--color-border);
          border-radius: var(--radius-card);
          background: var(--color-surface-soft);
        }
        [data-testid="stMetricValue"] {
          font-variant-numeric: tabular-nums;
        }

        /* Respect reduced motion (accessibility) */
        @media (prefers-reduced-motion: reduce) {
          * {
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
          }
          .studio-card:hover {
            transform: none;
          }
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
