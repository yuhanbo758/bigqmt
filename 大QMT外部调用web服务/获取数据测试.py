
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


# 允许通过环境变量覆盖桥接地址，便于未来切换端口或远程调试。
BRIDGE_BASE_URL = os.getenv("BIG_QMT_BRIDGE_BASE_URL", "http://127.0.0.1:1690")


def request_json(path, params=None):
    """
    通用桥接请求函数。

    参数：
    - path: 接口路径，例如 '/tick'、'/history_data'
    - params: 查询参数字典

    返回：
    - Python 字典（由 JSON 反序列化而来）
    """
    params = params or {}
    query = urlencode(params)
    url = BRIDGE_BASE_URL + path + (("?" + query) if query else "")
    request = Request(url, method="GET")
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_success(payload):
    """
    校验桥接接口是否成功。

    如果接口返回失败，则直接抛出异常，方便测试时快速定位问题。
    """
    if str(payload.get("status", "")).lower() != "success":
        raise RuntimeError(payload.get("message", "桥接接口返回失败"))
    return payload

def get_tick_df(stock_code):
    """
    获取单只证券 tick 数据，并整理为一行表格。
    """
    payload = ensure_success(request_json("/tick", {"stock_code": stock_code}))
    tick = payload.get("tick", {}) or {}

    row = {
        "stock_code": payload.get("stock_code", ""),
        "stock_name": payload.get("stock_name", ""),
        "latest_price": tick.get("最新", 0),
        "open": tick.get("今开", 0),
        "high": tick.get("最高", 0),
        "low": tick.get("最低", 0),
        "pre_close": tick.get("昨收", 0),
        "up_limit": tick.get("涨停", 0),
        "down_limit": tick.get("跌停", 0),
    }

    ask_price = tick.get("askPrice", []) or []
    ask_vol = tick.get("askVol", []) or []
    bid_price = tick.get("bidPrice", []) or []
    bid_vol = tick.get("bidVol", []) or []

    for i in range(5):
        row["ask_price_{}".format(i + 1)] = ask_price[i] if i < len(ask_price) else None
        row["ask_vol_{}".format(i + 1)] = ask_vol[i] if i < len(ask_vol) else None
        row["bid_price_{}".format(i + 1)] = bid_price[i] if i < len(bid_price) else None
        row["bid_vol_{}".format(i + 1)] = bid_vol[i] if i < len(bid_vol) else None

    return pd.DataFrame([row])


def get_history_df(stock_code, period="1d", count=20,
                   fields="time,open,high,low,close,volume",
                   start_time="", end_time="", dividend_type="none"):
    """
    获取历史行情，并整理成 DataFrame。

    常用 period：
    - tick
    - 1m
    - 5m
    - 15m
    - 30m
    - 1d

    常用 fields 不止 OHLCV，还可以扩展：
    - amount
    - preClose
    - settle
    - openInterest
    - suspendFlag
    """
    payload = ensure_success(
        request_json(
            "/history_data",
            {
                "stock_code": stock_code,
                "period": period,
                "count": count,
                "fields": fields,
                "start_time": start_time,
                "end_time": end_time,
                "dividend_type": dividend_type,
            },
        )
    )

    df = pd.DataFrame(payload.get("data", []) or [])
    if not df.empty and "time" in df.columns:
        df["time"] = df["time"].astype(str)
    return df

if __name__ == "__main__":
    # 测试 tick 数据
    df_tick = get_tick_df("000001")
    print(df_tick)
    # 测试历史数据
    df_history = get_history_df("000002", period="1d", count=10)
    print(df_history)
    # 测试历史行情
    df_history = get_history_df("600000", period="1d", count=10, fields="time,open,high,low,close,volume,amount,preClose,suspendFlag")
    print(df_history)






