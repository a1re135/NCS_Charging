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
import threading

from flask import current_app
from openai import OpenAI

from .i18n import current_language

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
    localize_result,
)


TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
}

_glm_client = None
_glm_client_key = None
_glm_client_lock = threading.Lock()


def get_glm_client(
    api_key,
    base_url,
):
    """
    Reuse one OpenAI-compatible client so concurrent
    Agent requests can reuse HTTP connections instead
    of creating a new client/TLS connection every time.
    """

    global _glm_client
    global _glm_client_key

    key = (
        api_key,
        base_url,
    )

    if (
        _glm_client is not None
        and _glm_client_key == key
    ):
        return _glm_client

    with _glm_client_lock:
        if (
            _glm_client is not None
            and _glm_client_key == key
        ):
            return _glm_client

        if _glm_client is not None:
            try:
                _glm_client.close()
            except Exception:
                pass

        _glm_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=20.0,
            max_retries=1,
        )

        _glm_client_key = key

        return _glm_client

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
        "user": ("普通用户", "User"),
        "operator": ("运营人员", "Operator"),
        "technician": ("运维人员", "Technician"),
        "admin": ("系统管理员", "System administrator"),
    }

    english = current_language() == "en"
    role_pair = role_names.get(role, (role, role))
    role_name = role_pair[1] if english else role_pair[0]

    if english:
        return f"""
You are the AI Agent for the NCS Smart Charging Platform.
Current user role: {role_name}.

Task: understand the user's natural-language request and select the appropriate
approved business tool when business data is required.

Rules:
1. For charging stations, chargers, orders, wallets, faults, revenue or operations data, use an approved tool.
2. Only use the tools provided to you. Never access the database directly or generate SQL.
3. Never invent business data.
4. Never reveal passwords, API keys or system secrets.
5. The interface language is English, so always answer in English, even if the user asks in Chinese.
6. Keep ordinary answers concise.
""".strip()

    return f"""
你是 NCS 智能充电平台的 AI Agent。
当前用户角色：{role_name}。

任务：理解用户自然语言，并选择合适的已提供业务工具。

规则：
1. 涉及充电站、充电桩、订单、钱包、故障、营收或运营数据时，必须调用工具。
2. 只能使用当前提供的工具，不得自行访问数据库或生成 SQL。
3. 不得编造业务数据。
4. 不得泄露密码、API Key 或系统密钥。
5. 当前界面语言是中文，因此始终使用中文回答。
6. 如果不需要工具，可以直接简短回答。
""".strip()

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
        "glm-4-flashx-250414",
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
        client = get_glm_client(
            api_key,
            base_url,
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
                temperature=0,
                max_tokens=128,
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

        # Rebuild the verified tool answer in the selected UI language.
        result = localize_result(
            tool_name,
            result,
        )

        # -----------------------------------------
        # One-call Agent path
        #
        # GLM has already understood the user's
        # natural-language request and selected the
        # approved business tool.
        #
        # The local tool returns verified system data
        # together with a ready-to-display answer, so
        # a second GLM API call is unnecessary.
        # -----------------------------------------

        answer = (
            result.get("answer")
            or (
                "Unable to generate a response right now."
                if current_language() == "en"
                else "暂时无法生成回答。"
            )
        )

        return {
            "answer": answer,
            "intent": tool_name,
            "data": result.get("data"),
            "agent_mode": "glm",
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