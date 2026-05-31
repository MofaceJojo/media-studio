from __future__ import annotations

import hashlib
import itertools
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field


class MaterialSearchRequest(BaseModel):
    provider: str = Field(pattern="^(pexels|pixabay)$")
    api_keys: list[str]
    query: str = "nature"
    aspect: str = "portrait"
    min_duration: int = 3


class MaterialItem(BaseModel):
    provider: str
    url: str
    duration: float
    width: int | None = None
    height: int | None = None


class MaterialSearchResult(BaseModel):
    ok: bool
    message: str
    items: list[MaterialItem] = Field(default_factory=list)


def _key(keys: list[str]) -> str:
    cleaned = [item.strip() for item in keys if item.strip()]
    if not cleaned:
        raise ValueError("At least one API key is required.")
    digest = hashlib.sha256("|".join(cleaned).encode()).hexdigest()
    index = int(digest[:8], 16) % len(cleaned)
    return list(itertools.islice(itertools.cycle(cleaned), index, index + 1))[0]


def _target(aspect: str) -> tuple[str, int, int]:
    if aspect == "landscape":
        return "landscape", 1920, 1080
    if aspect == "square":
        return "square", 1080, 1080
    return "portrait", 1080, 1920


async def search_materials(payload: MaterialSearchRequest) -> MaterialSearchResult:
    try:
        api_key = _key(payload.api_keys)
    except ValueError as exc:
        return MaterialSearchResult(ok=False, message=str(exc))

    orientation, width, height = _target(payload.aspect)
    try:
        if payload.provider == "pexels":
            result = await _search_pexels(api_key, payload.query, orientation, payload.min_duration, width, height)
        else:
            result = await _search_pixabay(api_key, payload.query, payload.min_duration, width)
    except httpx.HTTPStatusError as exc:
        return MaterialSearchResult(ok=False, message=f"HTTP {exc.response.status_code}: {exc.response.text[:180]}")
    except Exception as exc:
        return MaterialSearchResult(ok=False, message=str(exc))

    return MaterialSearchResult(
        ok=bool(result),
        message=f"Found {len(result)} usable clips." if result else "No matching clips returned.",
        items=result,
    )


async def _search_pexels(
    api_key: str,
    query: str,
    orientation: str,
    min_duration: int,
    target_width: int,
    target_height: int,
) -> list[MaterialItem]:
    params = {"query": query, "per_page": 12, "orientation": orientation}
    headers = {"Authorization": api_key}
    async with httpx.AsyncClient(timeout=20, verify=True) as client:
        response = await client.get(f"https://api.pexels.com/videos/search?{urlencode(params)}", headers=headers)
        response.raise_for_status()
        data = response.json()

    items: list[MaterialItem] = []
    for video in data.get("videos", []):
        duration = float(video.get("duration") or 0)
        if duration < min_duration:
            continue
        for candidate in video.get("video_files", []):
            if int(candidate.get("width") or 0) >= target_width or int(candidate.get("height") or 0) >= target_height:
                items.append(
                    MaterialItem(
                        provider="pexels",
                        url=candidate["link"],
                        duration=duration,
                        width=candidate.get("width"),
                        height=candidate.get("height"),
                    )
                )
                break
    return items


async def _search_pixabay(api_key: str, query: str, min_duration: int, target_width: int) -> list[MaterialItem]:
    params = {"key": api_key, "q": query, "video_type": "all", "per_page": 20}
    async with httpx.AsyncClient(timeout=20, verify=True) as client:
        response = await client.get(f"https://pixabay.com/api/videos/?{urlencode(params)}")
        response.raise_for_status()
        data = response.json()

    items: list[MaterialItem] = []
    for video in data.get("hits", []):
        duration = float(video.get("duration") or 0)
        if duration < min_duration:
            continue
        for candidate in video.get("videos", {}).values():
            if int(candidate.get("width") or 0) >= target_width:
                items.append(
                    MaterialItem(
                        provider="pixabay",
                        url=candidate["url"],
                        duration=duration,
                        width=candidate.get("width"),
                        height=candidate.get("height"),
                    )
                )
                break
    return items
