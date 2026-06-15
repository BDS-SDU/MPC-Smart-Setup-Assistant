from __future__ import annotations

from copy import deepcopy
from typing import Any


OPTION_GROUPS: list[dict[str, Any]] = [
    {
        "id": "party_count_mode",
        "label": "参与方规模",
        "help": "先选 2 方 / 3 方 / n 方；如果需要精确人数，可以继续填写“参与方数量”。",
        "options": [
            {
                "value": "auto",
                "label": "自动推断",
                "description": "继续根据自然语言需求或默认规则推断。",
            },
            {
                "value": "two_party",
                "label": "2 方",
                "description": "典型 2PC 场景，例如 Yao、2PC 比较类任务。",
            },
            {
                "value": "three_party",
                "label": "3 方",
                "description": "三方部署或 3PC 风格场景。",
            },
            {
                "value": "n_party",
                "label": "n 方",
                "description": "多方场景，通常表示 n>=4。",
            },
        ],
    },
    {
        "id": "circuit_domain",
        "label": "电路形式",
        "help": "算术电路更适合求和、均值、线性代数；布尔电路更适合比较、排序、位运算。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "根据任务类型和文本描述推断。"},
            {"value": "boolean", "label": "布尔", "description": "强调比较、条件判断、位级操作。"},
            {"value": "arithmetic", "label": "算术", "description": "强调加法、乘法、聚合、统计和 ML 线性部分。"},
            {"value": "mixed", "label": "混合", "description": "同时存在算术和布尔子电路。"},
        ],
    },
    {
        "id": "math_structure",
        "label": "底层数学结构",
        "help": "主要影响算术型协议；布尔协议通常不会显式暴露这个选择。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "交给协议筛选逻辑决定。"},
            {"value": "ring", "label": "环", "description": "常见于 2^k 环上的高效算术共享。"},
            {"value": "finite_field", "label": "有限域", "description": "常见于 Shamir/BGW、SPDZ/MASCOT 等域上协议。"},
        ],
    },
    {
        "id": "secret_sharing",
        "label": "Secret Sharing",
        "help": "不是所有协议都会直接暴露 secret sharing 形式；如果不确定，推荐保留自动。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "让系统根据协议能力决定。"},
            {"value": "additive", "label": "Additive", "description": "加法共享，常见于高效算术协议。"},
            {"value": "replicated", "label": "Replicated", "description": "复制共享，常用于部分三方/诚实多数方案。"},
            {"value": "shamir", "label": "Shamir", "description": "Shamir secret sharing，常见于 BGW/Shamir 路线。"},
        ],
    },
    {
        "id": "preprocessing_preference",
        "label": "预处理阶段",
        "help": "区分是否希望显式利用 offline / online 两阶段结构。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "由协议能力和性能偏好共同决定。"},
            {"value": "required", "label": "需要预处理", "description": "更接受离线准备，换取在线阶段更轻。"},
            {"value": "disallowed", "label": "不使用预处理", "description": "倾向单阶段或不依赖明显 offline 阶段。"},
        ],
    },
    {
        "id": "security_model",
        "label": "敌手行为模型",
        "help": "这里描述 adversary 的行为强度；“自适应”单独拆到“腐化方式”。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "若文本未说明，则沿用默认安全假设。"},
            {"value": "semi_honest", "label": "半诚实", "description": "参与方遵循协议，但会试图窥探额外信息。"},
            {"value": "covert", "label": "Covert", "description": "允许作弊，但希望作弊可检测。"},
            {"value": "malicious", "label": "恶意", "description": "允许主动偏离协议，需要更强安全性。"},
        ],
    },
    {
        "id": "corruption_timing",
        "label": "腐化方式",
        "help": "将“自适应”从敌手行为里拆出来，避免和半诚实/恶意混在一起。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "默认不额外声明 static / adaptive。"},
            {"value": "static", "label": "静态", "description": "协议开始前就确定被腐化的参与方。"},
            {"value": "adaptive", "label": "自适应", "description": "执行过程中允许动态腐化，要求更高。"},
        ],
    },
    {
        "id": "network_model",
        "label": "网络模型",
        "help": "很多工程实现默认同步网络；异步要求通常更强，也更少见。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "若未明确要求，则不增加网络约束。"},
            {"value": "synchronous", "label": "同步", "description": "假设消息延迟可控或按轮次推进。"},
            {"value": "asynchronous", "label": "异步", "description": "不依赖同步轮次，需要更专门的协议设计。"},
        ],
    },
    {
        "id": "corruption_threshold",
        "label": "敌手门限",
        "help": "将 honest-majority / dishonest-majority 进一步细化为常见阈值写法。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "继续由文本或默认规则推断。"},
            {"value": "t_lt_n_over_3", "label": "t < n/3", "description": "常见于更强鲁棒性/异步相关讨论。"},
            {"value": "t_lt_n_over_2", "label": "t < n/2", "description": "典型诚实多数约束。"},
            {"value": "t_lt_n", "label": "t < n", "description": "非诚实多数 / dishonest majority 风格约束。"},
        ],
    },
    {
        "id": "security_goal",
        "label": "安全目标",
        "help": "区分 security with abort 与 guaranteed output delivery 等更细目标。",
        "options": [
            {"value": "auto", "label": "自动推断", "description": "若未说明，则交给默认协议目标。"},
            {"value": "security_with_abort", "label": "Abort", "description": "允许在检测异常时中止。"},
            {
                "value": "guaranteed_output_delivery",
                "label": "GOD",
                "description": "希望即使存在恶意参与方也尽量保证输出交付。",
            },
        ],
    },
]

OPTION_VALUES: dict[str, set[str]] = {
    group["id"]: {option["value"] for option in group["options"]}
    for group in OPTION_GROUPS
}


def list_requirement_options() -> list[dict[str, Any]]:
    return deepcopy(OPTION_GROUPS)
