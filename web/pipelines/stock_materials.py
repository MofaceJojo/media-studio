from __future__ import annotations

from typing import Any

import streamlit as st

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.moneyprinter_tools import download_material, material_to_dicts, search_stock_materials
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.utils.async_helpers import run_async


class StockMaterialsPipelineUI(PipelineUI):
    name = "stock_materials"
    display_name = "素材库"
    icon = "🎞️"
    description = "MoneyPrinterTurbo 风格的 Pexels / Pixabay 免费视频素材检索与下载。"

    def render(self, morpheus_video_studio: Any):
        stock_config = config_manager.get_stock_materials_config()
        provider_options = ["all", "pexels", "pixabay"]
        provider_labels = {
            "all": "全部（Pexels + Pixabay）",
            "pexels": "Pexels",
            "pixabay": "Pixabay",
        }
        default_provider = stock_config.get("default_provider", "all")
        provider_index = provider_options.index(default_provider) if default_provider in provider_options else 0

        left, right = st.columns([0.92, 1.08])
        with left:
            with st.container(border=True):
                st.markdown("**素材搜索**")
                provider = st.selectbox(
                    "资源库",
                    provider_options,
                    format_func=lambda value: provider_labels.get(value, value),
                    index=provider_index,
                    key="stock_provider",
                )
                enabled_providers = [
                    item for item in ["pexels", "pixabay"]
                    if stock_config.get(f"{item}_api_key", "").strip()
                ]
                if provider == "all":
                    if enabled_providers:
                        st.success(f"已启用：{', '.join(enabled_providers)}")
                    else:
                        st.warning("请先在系统配置的“素材源配置”里填写 Pexels 或 Pixabay API Key。")
                else:
                    if stock_config.get(f"{provider}_api_key", "").strip():
                        st.success(f"{provider} 已在系统配置中启用。")
                    else:
                        st.warning(f"请先在系统配置的“素材源配置”里填写 {provider} API Key。")
                query = st.text_input("搜索关键词", value="city night", key="stock_query")
                orientation = st.selectbox("画幅", ["portrait", "landscape", "square"], key="stock_orientation")
                per_page = st.slider("返回数量", min_value=4, max_value=24, value=8, step=4, key="stock_per_page")
                search_clicked = st.button("搜索素材", type="primary", use_container_width=True)

            if search_clicked:
                providers_to_search = enabled_providers if provider == "all" else [provider]
                providers_to_search = [
                    item for item in providers_to_search
                    if stock_config.get(f"{item}_api_key", "").strip()
                ]
                if not providers_to_search:
                    st.error("请先到系统配置里填写至少一个素材源 API Key。")
                else:
                    all_items = []
                    with st.spinner("正在搜索素材..."):
                        for item_provider in providers_to_search:
                            api_key = stock_config.get(f"{item_provider}_api_key", "")
                            items = run_async(search_stock_materials(item_provider, api_key, query, orientation, per_page))
                            all_items.extend(items)
                    st.session_state["stock_material_results"] = material_to_dicts(all_items)

        with right:
            with st.container(border=True):
                st.markdown("**搜索结果**")
                results = st.session_state.get("stock_material_results", [])
                if not results:
                    st.info("搜索结果会显示在这里。下载后的素材保存在 data/stock_materials。")
                for index, item in enumerate(results):
                    cols = st.columns([1, 3, 1])
                    with cols[0]:
                        st.caption(item["provider"])
                        st.write(f"{item['width']}x{item['height']}")
                    with cols[1]:
                        st.write(item["title"])
                        st.caption(f"{item['duration']}s")
                    with cols[2]:
                        if st.button("下载", key=f"download_stock_{index}"):
                            with st.spinner("正在下载..."):
                                path = run_async(download_material(item["url"], item["provider"]))
                            st.success(f"已保存：{path}")


register_pipeline_ui(StockMaterialsPipelineUI)
