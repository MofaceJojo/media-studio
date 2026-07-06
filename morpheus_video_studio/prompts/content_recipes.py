# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Content recipes (栏目配方) for topic-based script generation.

The base topic prompt is tuned for viewpoint-sharing content, which makes
knowledge verticals (science, TCM, rankings, medical) drift into
"life-insight" chatter. A recipe pins the script to a vertical-specific
structure with hard factual requirements and safety rules, and explicitly
overrides the base prompt's style suggestions where they conflict.
"""

from __future__ import annotations

from typing import Final


_RECIPES: Final[list[dict[str, str]]] = [
    {
        "id": "general",
        "label": "通用（观点分享）",
        "description": "默认风格：像朋友聊天一样分享观点与感悟",
        "block": "",
    },
    {
        "id": "science",
        "label": "科普知识",
        "description": "反常识开场 + 机制讲解带数字 + 误区澄清，事实优先",
        "block": """# 栏目配方：科普知识（当与上文风格要求冲突时，以本配方为准）
本视频是知识科普，不是人生感悟。目标：让观众"学到一个具体知识点"。

结构骨架（按分镜顺序执行）：
- 第 1 镜：用一个反常识的事实、数字或问题开场，直接点明本期主题
- 中间各镜：每镜讲清一个具体知识点，必须包含至少一项"硬内容"——数字、机制原理、实验结论或权威研究（不得编造来源）
- 倒数第 2 镜：澄清一个大众常见误区
- 最后 1 镜：一句话总结 + 一个可执行的行动建议

硬性禁忌：
- 禁止人生感悟、心灵鸡汤、情绪化抒情
- 禁止空泛表述（如"非常神奇""大自然的奥秘"），每句都要有信息量
- 不确定的内容宁可不写，禁止编造数据和文献""",
    },
    {
        "id": "tcm",
        "label": "中药百科",
        "description": "性味归经 + 功效（传统+现代）+ 用法搭配 + 禁忌与医嘱提示",
        "block": """# 栏目配方：中药百科（当与上文风格要求冲突时，以本配方为准）
本视频是中药知识科普。目标：讲清一味药材/方剂的来历、功效与边界。

结构骨架（按分镜顺序执行）：
- 第 1 镜：药材身份——名称、别名、来源部位，一句话点出它最出名的用途
- 第 2 镜起：性味归经与核心功效，传统记载（如《本草纲目》《神农本草经》，注明出处）与现代研究可分开讲
- 中段：常见用法、经典搭配或食疗场景，讲"什么情况适合用"
- 倒数第 2 镜：禁忌人群与注意事项（孕妇、体质、配伍禁忌等）
- 最后 1 镜：必须以类似"以上内容仅供科普参考，具体用药请遵医嘱"的提示收尾

硬性禁忌：
- 不得夸大疗效，不得使用"根治""治愈""包好"等承诺性表述
- 不得给出具体剂量或替代医嘱的用药指导
- 引用典籍必须真实，禁止编造条文""",
    },
    {
        "id": "ranking",
        "label": "排名盘点",
        "description": "悬念开场 + 倒序揭榜，每条一个硬事实，冠军留惊喜",
        "block": """# 栏目配方：排名盘点（当与上文风格要求冲突时，以本配方为准）
本视频是榜单盘点。目标：节奏紧凑地倒序揭榜，每个条目都有干货。

结构骨架（按分镜顺序执行）：
- 第 1 镜：悬念开场，点明榜单主题和评判维度（如"按……排名"），预告冠军有意外
- 中间各镜：从第 N 名倒序到第 2 名，每镜一个条目，格式为：排名 + 名称 + 一个硬事实或数字 + 一句精准点评
- 最后 1 镜：揭晓第 1 名 + 一个大多数人不知道的信息，结尾抛一个互动问题（如"你猜对了吗"）

硬性要求与禁忌：
- 条目总数要与分镜数量匹配，不得一镜塞多个条目
- 每个条目必须有具体事实/数字支撑，禁止只堆形容词
- 排名依据要一致，禁止中途更换评判标准""",
    },
    {
        "id": "medical",
        "label": "医学健康",
        "description": "症状引入 + 机制通俗讲解 + 就医边界 + 免责声明",
        "block": """# 栏目配方：医学健康（当与上文风格要求冲突时，以本配方为准）
本视频是医学健康科普。目标：把一个健康问题讲准、讲透，并划清就医边界。

结构骨架（按分镜顺序执行）：
- 第 1 镜：从常见现象或症状切入（观众有代入感的场景）
- 第 2 镜起：解释背后的机制，用通俗类比 + 准确医学术语（首次出现时用一句话解释术语）
- 中段：什么情况属于正常、什么信号需要警惕
- 倒数第 2 镜：实用建议（生活方式、观察要点、就医时机）
- 最后 1 镜：必须包含类似"本内容仅供健康科普，不能替代专业诊疗，不适请及时就医"的提示

硬性禁忌：
- 不诊断、不开处方、不推荐具体药物剂量
- 不承诺疗效，不使用绝对化表述（"一定""必然治好"）
- 不制造健康焦虑或恐慌，语气冷静专业
- 引用研究必须真实，禁止编造""",
    },
]


def list_content_recipes() -> list[dict[str, str]]:
    return [recipe.copy() for recipe in _RECIPES]


def get_content_recipe(recipe_id: str) -> dict[str, str]:
    for recipe in _RECIPES:
        if recipe["id"] == recipe_id:
            return recipe.copy()
    raise KeyError(f"Unknown content recipe: {recipe_id}")


def get_recipe_block(recipe_id: str | None) -> str:
    """Return the prompt overlay for a recipe id; unknown/empty ids mean no overlay."""
    if not recipe_id:
        return ""
    try:
        return get_content_recipe(recipe_id)["block"]
    except KeyError:
        return ""
