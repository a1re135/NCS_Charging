"""
NCS hybrid AI Agent.

GLM handles natural-language understanding and chooses
an approved NCS business tool.

The LLM never accesses the database directly.

If GLM is unavailable, disabled, or returns an error,
the existing local Agent in agent.py is used instead.
"""

import json
import os

from flask import current_app
from openai import OpenAI

from .agent import (
    chat as local_chat,
    station_recommendation,
    current_order,
    latest_order,
    wallet_info,
    fault_help,
    today_top_station,
    revenue_summary,
    device_summary,
    fault_ranking,
    operations_report,
)


TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
}


# =========================================================
# Tool definitions
# =========================================================

USER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recommend_station",
            "description": (
                "Recommend a nearby operating charging station "
                "with available chargers. Use this when the user "
                "asks about nearby charging stations, available "
                "chargers, fast chargers, or station recommendations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fast_only": {
                        "type": "boolean",
                        "description": (
                            "True if the user specifically wants "
                            "an available fast charger."
                        ),
                    },
                },
                "required": [
                    "fast_only",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "current_order",
            "description": (
                "Get the current user's active reservation "
                "or charging order."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "latest_order",
            "description": (
                "Get the current user's most recent completed "
                "charging order and payment information."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "wallet_info",
            "description": (
                "Get the current user's wallet balance "
                "and unpaid charging debt."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "charging_fault_help",
            "description": (
                "Diagnose why the current user's charger "
                "or charging session cannot start. "
                "Checks the user's active order, charger status "
                "and station operating status."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]


OPERATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "today_top_station",
            "description": (
                "Find the charging station with the most "
                "orders today."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "revenue_summary",
            "description": (
                "Get completed order count, charging energy "
                "and collected revenue for a recent period."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": (
                            "Number of recent days to analyze. "
                            "Must be between 1 and 30."
                        ),
                    },
                },
                "required": [
                    "days",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "device_summary",
            "description": (
                "Get current counts of idle, reserved, charging, "
                "fault, offline and maintenance chargers."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "fault_ranking",
            "description": (
                "Find chargers with the highest number "
                "of historical fault records."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "operations_report",
            "description": (
                "Generate data for an operations report including "
                "orders, revenue, charging energy, registered users, "
                "devices and unresolved faults."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": (
                            "Number of recent days covered "
                            "by the report. Must be between 1 and 30."
                        ),
                    },
                },
                "required": [
                    "days",
                ],
                "additionalProperties": False,
            },
        },
    },
]


# =========================================================
# Role permissions
# =========================================================

def tools_for_role(role):
    if role == "user":
        return USER_TOOLS

    if role == "technician":
        return [
            tool
            for tool in OPERATION_TOOLS
            if tool["function"]["name"]
            in {
                "device_summary",
                "fault_ranking",
            }
        ]

    if role in (
        "operator",
        "admin",
    ):
        return OPERATION_TOOLS

    return []


def allowed_tool_names(role):
    return {
        tool["function"]["name"]
        for tool in tools_for_role(role)
    }


# =========================================================
# Execute approved NCS tools
# =========================================================

def execute_tool(
    user,
    name,
    arguments,
    lat,
    lng,
):
    role = user["role"]

    if (
        name
        not in allowed_tool_names(role)
    ):
        raise PermissionError(
            "当前角色无权调用该 Agent 工具"
        )

    if name == "recommend_station":
        return station_recommendation(
            user,
            lat,
            lng,
            fast_only=bool(
                arguments.get(
                    "fast_only",
                    False,
                )
            ),
        )

    if name == "current_order":
        return current_order(
            user["id"]
        )

    if name == "latest_order":
        return latest_order(
            user["id"]
        )

    if name == "wallet_info":
        return wallet_info(
            user["id"]
        )

    if name == "charging_fault_help":
        return fault_help(
            user["id"]
        )

    if name == "today_top_station":
        return today_top_station()

    if name == "revenue_summary":
        days = int(
            arguments.get(
                "days",
                7,
            )
        )

        days = max(
            1,
            min(
                days,
                30,
            ),
        )

        return revenue_summary(
            days
        )

    if name == "device_summary":
        return device_summary()

    if name == "fault_ranking":
        return fault_ranking()

    if name == "operations_report":
        days = int(
            arguments.get(
                "days",
                7,
            )
        )

        days = max(
            1,
            min(
                days,
                30,
            ),
        )

        return operations_report(
            days
        )

    raise ValueError(
        f"Unknown Agent tool: {name}"
    )


# =========================================================
# GLM instructions
# =========================================================

def system_prompt(user):
    role = user["role"]

    role_names = {
        "user": "普通用户",
        "operator": "运营人员",
        "technician": "运维人员",
        "admin": "系统管理员",
    }

    role_name = role_names.get(
        role,
        role,
    )

    return f"""
你是 NCS 智能充电桩运营服务平台的 AI Agent。

当前登录角色：{role_name}

你不是普通聊天机器人。
你的任务是理解自然语言，并在需要真实平台数据时调用系统提供的业务工具。

规则：

1. 涉及充电站、设备、订单、余额、欠费、营收、故障或运营数据的问题，
   必须使用提供的工具查询真实系统数据。

2. 不得编造任何：
   - 充电站
   - 设备状态
   - 订单
   - 用户余额
   - 收入
   - 故障
   - 运营统计

3. 不得调用当前角色没有权限使用的功能。

4. 不得尝试生成 SQL，也不得要求直接访问数据库。

5. 不得泄露：
   - API Key
   - 数据库密码
   - 用户密码
   - 系统密钥

6. 如果用户使用中文，就用中文回答。
   如果用户使用英文，就用英文回答。

7. 回答尽量简洁、自然，适合充电平台用户阅读。

8. 如果某项信息无法从工具结果确认，要明确说明无法确认，
   不要自行猜测。

9. 如果问题与 NCS 充电平台无关，可以简单说明：
   你主要负责 NCS 充电服务相关问题。


普通用户可以咨询：

- 附近充电站
- 空闲快充
- 当前充电订单
- 最近充电记录
- 钱包余额
- 欠费
- 充电无法启动


运营人员和管理员可以咨询：

- 今日订单
- 近期营收
- 当前设备状态
- 故障情况
- 故障排名
- 运营报告


运维人员可以咨询：

- 当前设备状态
- 故障设备
- 故障历史
"""


# =========================================================
# Configuration
# =========================================================

def llm_enabled():
    value = os.getenv(
        "NCS_LLM_ENABLED",
        "0",
    )

    return (
        value.strip().lower()
        in TRUE_VALUES
    )


def local_fallback(
    user,
    message,
    lat,
    lng,
    mode="local",
):
    result = local_chat(
        user,
        message,
        lat,
        lng,
    )

    result["agent_mode"] = mode

    return result


# =========================================================
# Main hybrid Agent
# =========================================================

def hybrid_chat(
    user,
    message,
    lat=39.9593,
    lng=116.2981,
):
    """
    GLM is used in normal application mode.

    Automated tests always use the deterministic
    local Agent so unit tests never consume API credits.
    """

    # ---------------------------------------------
    # Automated tests must never call GLM.
    # ---------------------------------------------

    if current_app.config.get(
        "TESTING"
    ):
        return local_fallback(
            user,
            message,
            lat,
            lng,
            "local-test",
        )

    # ---------------------------------------------
    # Configuration
    # ---------------------------------------------

    api_key = os.getenv(
        "BIGMODEL_API_KEY",
        "",
    ).strip()

    base_url = os.getenv(
        "BIGMODEL_BASE_URL",
        "https://open.bigmodel.cn/api/paas/v4/",
    ).strip()

    model = os.getenv(
        "BIGMODEL_MODEL",
        "glm-5.2",
    ).strip()

    if (
        not llm_enabled()
        or not api_key
    ):
        return local_fallback(
            user,
            message,
            lat,
            lng,
            "local",
        )

    tools = tools_for_role(
        user["role"]
    )

    if not tools:
        return local_fallback(
            user,
            message,
            lat,
            lng,
            "local",
        )

    # ---------------------------------------------
    # Connect to BigModel
    # ---------------------------------------------

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=20.0,
            max_retries=1,
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt(
                    user
                ),
            },
            {
                "role": "user",
                "content": message,
            },
        ]

        # -----------------------------------------
        # First GLM call:
        # understand question + select a tool
        # -----------------------------------------

        response = (
            client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        )

        assistant_message = (
            response
            .choices[0]
            .message
        )

        tool_calls = (
            assistant_message
            .tool_calls
            or []
        )

        # -----------------------------------------
        # No tool required.
        # Example: "你好"
        # -----------------------------------------

        if not tool_calls:
            text = (
                assistant_message
                .content
                or ""
            ).strip()

            if text:
                return {
                    "answer": text,
                    "intent":
                        "glm_general",
                    "data": None,
                    "agent_mode":
                        "glm",
                }

            return local_fallback(
                user,
                message,
                lat,
                lng,
                "local-fallback",
            )

        # -----------------------------------------
        # Only use the first tool call.
        # -----------------------------------------

        tool_call = tool_calls[0]

        tool_name = (
            tool_call
            .function
            .name
        )

        raw_arguments = (
            tool_call
            .function
            .arguments
            or "{}"
        )

        try:
            arguments = json.loads(
                raw_arguments
            )
        except json.JSONDecodeError:
            arguments = {}

        # -----------------------------------------
        # Execute real NCS business logic
        # -----------------------------------------

        result = execute_tool(
            user,
            tool_name,
            arguments,
            lat,
            lng,
        )

        # -----------------------------------------
        # Add GLM's tool request to history
        # -----------------------------------------

        messages.append(
            {
                "role": "assistant",
                "content":
                    assistant_message
                    .content
                    or "",

                "tool_calls": [
                    {
                        "id":
                            tool_call.id,

                        "type":
                            "function",

                        "function": {
                            "name":
                                tool_name,

                            "arguments":
                                raw_arguments,
                        },
                    }
                ],
            }
        )

        # -----------------------------------------
        # Add our verified database result
        # -----------------------------------------

        messages.append(
            {
                "role": "tool",

                "tool_call_id":
                    tool_call.id,

                "content":
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
            }
        )

        # -----------------------------------------
        # Tell GLM to produce final response
        # -----------------------------------------

        messages.append(
            {
                "role": "system",
                "content": (
                    "业务工具已经返回真实系统数据。"
                    "请根据工具结果直接回答用户。"
                    "不要编造工具结果中没有的数据。"
                    "不要再调用其他工具。"
                ),
            }
        )

        final_response = (
            client.chat.completions.create(
                model=model,
                messages=messages,
            )
        )

        answer = (
            final_response
            .choices[0]
            .message
            .content
            or ""
        ).strip()

        if not answer:
            answer = result.get(
                "answer",
                "暂时无法生成回答。",
            )

        return {
            "answer": answer,

            "intent":
                tool_name,

            "data":
                result.get(
                    "data"
                ),

            "agent_mode":
                "glm",
        }

    # ---------------------------------------------
    # GLM failure → existing Agent still works
    # ---------------------------------------------

    except Exception as exc:
        current_app.logger.warning(
            "GLM Agent failed; "
            "using local fallback: %s",
            exc,
        )

        return local_fallback(
            user,
            message,
            lat,
            lng,
            "local-fallback",
        )