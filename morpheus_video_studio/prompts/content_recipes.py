"""Broad content recipes for topic-based video script generation."""

from __future__ import annotations

import re
from typing import Final

VISUAL_NO_HUMAN = """## 画面硬性规则（优先级最高）
- 严禁出现人物、人体、人脸、手部、人影。本地模型画人容易变形，一律回避。
- 优先使用与主题直接相关的器物、建筑、地图、书页、档案、自然景观、实验材料、图表、产品或静物。
- 构图清晰，主体单一，避免画面文字、水印和无关装饰。
- 不要写人物动作；把动作转换成物体状态、环境变化或信息图表达。"""


_RECIPES: Final[list[dict[str, str]]] = [
    {
        "id": "general",
        "label": "自由创作",
        "description": "不套固定结构，按主题自然生成",
        "block": "",
    },
    {
        "id": "science",
        "label": "知识科普",
        "description": "反常识开场，讲清原理、事实和常见误区",
        "block": """# 栏目配方：知识科普
目标：让观众真正学会一个具体知识点，而不是听泛泛感悟。

结构骨架：
- 第 1 镜：用反常识事实、数字或问题直接切入主题
- 中间各镜：逐层解释原理，每镜至少包含一个事实、机制或可靠数据
- 倒数第 2 镜：澄清一个常见误区
- 最后 1 镜：一句话总结，并给出可执行的理解或观察方法

禁止编造数据、论文和来源；不确定的内容宁可不写。""",
        "visual": VISUAL_NO_HUMAN,
    },
    {
        "id": "story",
        "label": "故事讲述",
        "description": "人物目标、冲突推进、转折和有余味的结尾",
        "block": """# 栏目配方：故事讲述
目标：用清楚的因果和冲突讲完一个有起伏的故事。

结构骨架：
- 第 1 镜：交代主角、目标和即将发生的问题
- 前半段：冲突出现并升级，每镜都推动事件
- 中段：出现关键信息或选择，让故事发生转折
- 后半段：展示选择带来的结果
- 最后 1 镜：完成结局，并留下情绪、启示或悬念

禁止只有氛围没有事件；禁止重复同一信息拖长篇幅。""",
    },
    {
        "id": "history",
        "label": "历史人文",
        "description": "时代背景、关键事件、因果关系和今天的意义",
        "block": """# 栏目配方：历史人文
目标：把一段历史、一个人物或一种文化现象讲清楚。

结构骨架：
- 第 1 镜：用一个具体细节或疑问引出主题
- 前段：交代时间、地点和必要背景
- 中段：按因果关系讲关键事件，不做流水账
- 后段：说明事件的影响、争议或后续变化
- 最后 1 镜：回到今天，说明它为何仍值得了解

史实、年代和引用必须可靠；有争议的说法要明确标注。""",
        "visual": VISUAL_NO_HUMAN,
    },
    {
        "id": "tutorial",
        "label": "实用教程",
        "description": "先给结果，再按步骤操作并提醒常见坑",
        "block": """# 栏目配方：实用教程
目标：让观众看完可以立刻完成一件具体事情。

结构骨架：
- 第 1 镜：明确最终能得到什么结果
- 第 2 镜：列出开始前需要准备的条件或材料
- 中间各镜：按顺序讲步骤，一镜只完成一个动作
- 倒数第 2 镜：提醒最常见的错误和排查方法
- 最后 1 镜：快速复盘步骤和成功判断标准

避免空泛建议；每一步必须具体、可执行、顺序明确。""",
    },
    {
        "id": "commentary",
        "label": "观点评论",
        "description": "鲜明观点、事实依据、回应反方并形成结论",
        "block": """# 栏目配方：观点评论
目标：提出一个清楚、有依据、经得起反问的观点。

结构骨架：
- 第 1 镜：直接亮出核心观点，不绕弯
- 前半段：给出事实、案例或逻辑依据
- 中段：承认一个合理的反方观点或限制条件
- 后半段：解释为什么核心判断仍然成立
- 最后 1 镜：收束结论，并提出值得讨论的问题

区分事实和意见；禁止用情绪、标签或人身攻击代替论证。""",
    },
    {
        "id": "ranking",
        "label": "盘点推荐",
        "description": "统一标准、逐项盘点，每一项都有具体理由",
        "block": """# 栏目配方：盘点推荐
目标：按统一标准快速比较多个对象，让观众知道为什么值得选。

结构骨架：
- 用户要求几个对象，就输出几个分镜；每个分镜直接介绍一个条目
- 不要占用单独分镜做开场或总结，也不要写泛泛的主题感悟
- 每个分镜必须包含：明确名称、具体内容或关键情节、入选理由
- 影视或动漫盘点必须交代具体人物、人物行动、剧情冲突、关键场面和入选理由
- 不能用抽象情绪或人生感悟代替剧情介绍；要说明谁为了什么做了什么、发生了什么冲突
- 所有旁白严格使用“第1项：具体名称｜具体介绍与入选理由”的格式，序号依次递增

评判标准必须前后一致；禁止只堆形容词、重复同一观点或伪造排名数据。""",
    },
    {
        "id": "health",
        "label": "健康生活",
        "description": "解释健康现象、实用建议、风险信号与就医边界",
        "block": """# 栏目配方：健康生活
目标：准确解释健康、饮食、运动或传统养生主题，并划清医疗边界。

结构骨架：
- 第 1 镜：从常见现象、困扰或误区切入
- 前半段：用通俗语言解释可能的机制和可靠证据
- 中段：给出低风险、可执行的生活方式建议
- 倒数第 2 镜：说明禁忌、风险信号和需要及时就医的情况
- 最后 1 镜：明确“本内容仅供健康科普，不能替代专业诊疗”

不得夸大疗效，不诊断、不开处方、不提供具体药物剂量；传统记载与现代研究必须分开表述。""",
        "visual": VISUAL_NO_HUMAN,
    },
]


_RANKING_INTENT = re.compile(
    r"(?:盘点|排行榜|top\s*\d+|(?:最|推荐|必看|值得).{0,16}(?:\d+|[一二三四五六七八九十]+)\s*(?:集|部|个|款|名|本|首|期|次|大))",
    re.IGNORECASE,
)


def list_content_recipes() -> list[dict[str, str]]:
    return [recipe.copy() for recipe in _RECIPES]


def get_content_recipe(recipe_id: str) -> dict[str, str]:
    for recipe in _RECIPES:
        if recipe["id"] == recipe_id:
            return recipe.copy()
    raise KeyError(f"Unknown content recipe: {recipe_id}")


def get_recipe_visual_rules(recipe_id: str | None) -> str:
    if not recipe_id:
        return ""
    try:
        return get_content_recipe(recipe_id).get("visual", "")
    except KeyError:
        return ""


def get_recipe_block(recipe_id: str | None) -> str:
    if not recipe_id:
        return ""
    try:
        return get_content_recipe(recipe_id)["block"]
    except KeyError:
        return ""


def resolve_content_recipe(topic: str, selected_recipe: str | None) -> str:
    """Infer an obvious structured recipe while respecting explicit choices."""
    selected = selected_recipe or "general"
    if selected != "general":
        return selected
    if _RANKING_INTENT.search(topic or ""):
        return "ranking"
    return selected
