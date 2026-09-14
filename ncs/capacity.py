"""Course capacity target configuration.

The project explicitly uses four capacity levels. This version selects L1
as the declared target so the implementation and performance test can use
one consistent baseline.
"""

import os

CAPACITY_LEVEL = os.getenv("NCS_CAPACITY_LEVEL", "L1").upper()
if CAPACITY_LEVEL not in {"L1", "L2", "L3", "L4"}:
    raise ValueError("NCS_CAPACITY_LEVEL 必须是 L1/L2/L3/L4")

CAPACITY_TARGETS = {
    "L1": {
        "name": "基础业务级",
        "position": "校园 / 小型园区 / 单个商业中心 / 小型企业停车场",
        "registered_users": 10_000,
        "daily_active_users": 1_000,
        "stations": 10,
        "chargers": 100,
        "concurrent_users": 100,
        "qps": {
            "login": 20,
            "station_query": 50,
            "device_view": 30,
            "start_charging": 10,
            "end_charging": 10,
            "agent": 5,
        },
    },
    "L2": {
        "name": "标准应用级",
        "position": "城市级中小规模运营平台",
        "registered_users": 100_000,
        "daily_active_users": 10_000,
        "stations": 100,
        "chargers": 1_000,
        "concurrent_users": 1_000,
        "qps": {"login": 100, "station_query": 500, "device_view": 300, "start_charging": 50, "end_charging": 50, "agent": 30},
    },
    "L3": {
        "name": "高并发应用级",
        "position": "较大规模的城市级充电运营平台",
        "registered_users": 1_000_000,
        "daily_active_users": 100_000,
        "stations": 1_000,
        "chargers": 10_000,
        "concurrent_users": 10_000,
        "qps": {"login": 500, "station_query": 2_000, "device_view": 1_000, "start_charging": 300, "end_charging": 300, "agent": 200},
    },
    "L4": {
        "name": "高容量平台级",
        "position": "全国性充电桩运营平台",
        "registered_users": 10_000_000,
        "daily_active_users": 1_000_000,
        "stations": 10_000,
        "chargers": 100_000,
        "concurrent_users": 100_000,
        "qps": {"login": 2_000, "station_query": 10_000, "device_view": 5_000, "start_charging": 1_000, "end_charging": 1_000, "agent": 1_000},
    },
}


def get_capacity(level: str = CAPACITY_LEVEL):
    return CAPACITY_TARGETS[level]
