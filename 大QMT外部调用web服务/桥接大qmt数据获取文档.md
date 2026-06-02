# 桥接内置 Python 获取数据文档

## 文档定位

这份文档用于说明如何在**外部 Python 环境**中，通过桥接方式调用**大QMT 内置 Python**的数据能力，并把返回结果整理成类似 `akshare` 的**数据表（DataFrame）**形式。

目标不是直接看 JSON，而是：

1. 从大QMT桥接接口获取原始数据
2. 转成 `pandas.DataFrame`
3. 直接打印、保存、分析、画图

这样用户复制文档中的示例代码后，就可以快速上手获取：

- `tick` 五档行情
- `1分钟` 行情
- `5分钟` 行情
- `日线` 行情
- 分时图数据

## 使用前提

### 1. 启动大QMT桥接

先在大QMT内置 Python 中运行：

```python
big_data_qmt_app.py
```

默认桥接地址：

```text
http://127.0.0.1:1690
```

### 2. 外部环境安装 pandas

文档下面的示例统一使用 `pandas` 把桥接数据整理成表格：

```bash
pip install pandas
```

## 通用基础代码

下面这段代码是所有示例的通用基础代码。建议先复制保存成一个脚本，例如：

```text
qmt_bridge_dataframe_demo.py
```

```python
# -*- coding: utf-8 -*-
"""
大QMT 桥接数据获取通用示例

说明：
1. 本脚本运行在外部 Python 环境，不运行在大QMT内置 Python 中。
2. 通过 HTTP 调用大QMT桥接服务。
3. 所有返回结果统一转成 pandas.DataFrame，方便像 akshare 一样直接使用。
"""

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


def save_table(df, file_path):
    """
    保存 DataFrame。

    说明：
    - .csv 使用 utf-8-sig，便于 Excel 直接打开中文不乱码
    - .xlsx 使用 pandas 默认 Excel 写法
    """
    file_path = os.path.abspath(file_path)
    lower_path = file_path.lower()
    if lower_path.endswith(".xlsx"):
        df.to_excel(file_path, index=False)
    else:
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path
```

## 行情字段并不只有 OHLCV

大QMT 文档里，`ContextInfo.get_market_data_ex()` 支持的字段明显不止：

```text
time, open, high, low, close, volume
```

根据大QMT文档，常规 K 线 / 分钟线 / 日线常用字段还包括：

| 字段 | 含义 | 备注 |
| --- | --- | --- |
| `time` | 时间 | 时间戳 |
| `open` | 开盘价 | 常规K线字段 |
| `high` | 最高价 | 常规K线字段 |
| `low` | 最低价 | 常规K线字段 |
| `close` | 收盘价 | 常规K线字段 |
| `volume` | 成交量 | 常规K线字段 |
| `amount` | 成交额 | 常用扩展字段 |
| `settle` | 今结算 | 期货等场景更常见 |
| `openInterest` | 持仓量 | 期货/期权更常见 |
| `preClose` | 前收盘价 | 常用于涨跌幅计算 |
| `suspendFlag` | 停牌标记 | 1停牌，0不停牌 |

如果 `period="tick"`，可获取的字段还会更完整：

| 字段 | 含义 |
| --- | --- |
| `time` | 时间戳 |
| `stime` | 字符串时间 |
| `lastPrice` | 最新价 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `lastClose` | 前收盘价 |
| `amount` | 成交额 |
| `volume` | 成交量 |
| `pvolume` | 原始成交量 |
| `stockStatus` | 证券状态 |
| `openInterest` | 持仓量 / 股票状态 |
| `transactionNum` | 成交笔数 |
| `lastSettlementPrice` | 前结算 |
| `settlementPrice` | 今结算 |
| `askPrice` | 多档委卖价 |
| `askVol` | 多档委卖量 |
| `bidPrice` | 多档委买价 |
| `bidVol` | 多档委买量 |

### 周期也不止 1m / 5m / 1d

根据大QMT文档，`period` 常见可选值包括：

```text
tick
1m、5m、15m、30m、60m
1d、1w、1mon、1y
l2quote
l2quoteaux
l2order
l2transaction
l2transactioncount
l2orderqueue
```

说明：

- `15m / 30m / 60m` 属于分钟级扩展周期
- `1w / 1mon / 1y` 属于日线合成周期
- `l2quote` 等属于 Level2 数据

所以，文档里的示例代码不应该只局限于 OHLCV，而应该根据分析目标灵活扩展字段。

## 1. 健康检查

先确认桥接服务和大QMT运行时已经就绪。

```python
payload = ensure_success(request_json("/health"))
print(payload)
```

正常时通常可以看到类似结果：

```python
{
    "status": "success",
    "runtime_ready": True,
    "bridge_host": "127.0.0.1",
    "bridge_port": 1690
}
```

## 2. 获取 tick 五档行情表

### 单只证券 tick 表

适合获取：

- 最新价
- 今开 / 最高 / 最低 / 昨收
- 买一到买五
- 卖一到卖五

```python
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


df_tick = get_tick_df("000001")
print(df_tick)
print(df_tick.T)
```

### 保存 tick 表

```python
save_table(df_tick, "tick_000001.csv")
```

## 3. 获取分时图数据表

`/market` 接口除了返回五档行情，还会返回 `chart` 分时数据，适合直接整理成分时表。

```python
def get_intraday_df(stock_code):
    """
    获取单只证券的分时图表格。
    """
    payload = ensure_success(request_json("/market", {"stock_code": stock_code}))
    chart = payload.get("chart", []) or []
    df = pd.DataFrame(chart)
    if not df.empty and "time" in df.columns:
        df = df.rename(columns={"time": "trade_time", "price": "close"})
    return df


df_intraday = get_intraday_df("000001")
print(df_intraday.head())
print(df_intraday.tail())
```

### 保存分时表

```python
save_table(df_intraday, "intraday_000001.csv")
```

## 4. 获取历史行情表

桥接接口 `/history_data` 已经支持外部按周期直接获取大QMT内置行情。返回结果里的 `data` 是行列表，最适合直接转 `DataFrame`。

### 通用历史行情函数

```python
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
```

## 推荐字段组合

下面给出几个实际最常用的字段组合，用户可以直接复制。

### 1. 基础 K 线字段

```python
fields = "time,open,high,low,close,volume"
```

适合：

- 普通技术分析
- K 线回测
- 均线、MACD、布林带等指标计算

### 2. K 线增强字段

```python
fields = "time,open,high,low,close,volume,amount,preClose,suspendFlag"
```

适合：

- 计算成交额
- 计算涨跌幅
- 识别停牌

### 3. 期货 / 期权 / 持仓量分析字段

```python
fields = "time,open,high,low,close,volume,amount,settle,openInterest"
```

适合：

- 期货分析
- 期权分析
- 持仓量变化研究

### 4. Tick 扩展字段

```python
fields = "time,stime,lastPrice,open,high,low,lastClose,volume,amount,transactionNum"
```

适合：

- 高频监控
- 盘口强弱分析
- 盘中成交节奏分析

### 5. Tick 五档字段

```python
fields = "time,stime,lastPrice,askPrice,askVol,bidPrice,bidVol"
```

适合：

- 五档盘口研究
- 委买委卖挂单分析
- 日内手动交易辅助

## 5. 获取 1 分钟行情表

```python
df_1m = get_history_df(
    stock_code="000001",
    period="1m",
    count=60,
    fields="time,open,high,low,close,volume"
)

print(df_1m.head())
print(df_1m.tail())
```

### 保存 1 分钟行情表

```python
save_table(df_1m, "000001_1m.csv")
```

## 6. 获取 5 分钟行情表

```python
df_5m = get_history_df(
    stock_code="000001",
    period="5m",
    count=80,
    fields="time,open,high,low,close,volume"
)

print(df_5m)
```

### 保存 5 分钟行情表

```python
save_table(df_5m, "000001_5m.xlsx")
```

## 7. 获取日线行情表

```python
df_day = get_history_df(
    stock_code="000001",
    period="1d",
    count=120,
    fields="time,open,high,low,close,volume"
)

print(df_day.head())
print(df_day.tail())
```

### 保存日线行情表

```python
save_table(df_day, "000001_1d.csv")
```

## 8. 获取带更多字段的历史表

如果你需要更多字段，例如成交额、昨收、停牌标记等，可以直接扩展 `fields`：

```python
df_more = get_history_df(
    stock_code="000001",
    period="1d",
    count=30,
    fields="time,open,high,low,close,volume,amount,preClose,suspendFlag"
)

print(df_more)
```

## 8.1 获取更完整的 tick 表

如果你希望像行情终端一样拿到更完整的 tick 信息，可以直接请求扩展字段，然后转成表格：

```python
df_tick_more = get_history_df(
    stock_code="000001",
    period="tick",
    count=20,
    fields="time,stime,lastPrice,open,high,low,lastClose,volume,amount,transactionNum,stockStatus"
)

print(df_tick_more)
```

## 8.2 获取 tick 五档表

如果你想研究盘口五档，可以直接请求五档字段：

```python
df_tick_level5 = get_history_df(
    stock_code="000001",
    period="tick",
    count=5,
    fields="time,stime,lastPrice,askPrice,askVol,bidPrice,bidVol"
)

print(df_tick_level5)
```

说明：

- `askPrice / askVol / bidPrice / bidVol` 返回的是列表列
- `pandas` 会把它们保存在单元格中
- 如果后续要展开成 `ask_price_1 ~ ask_price_5`，可以再做二次拆分

## 9. 批量获取多只证券日线表

如果你要像 `akshare` 一样批量拉取数据，可以对代码列表循环调用，再合并成一个大表。

```python
def get_multi_stock_day_df(stock_codes, count=20):
    """
    批量获取多只证券的日线数据，并合并为一个总表。
    """
    frames = []
    for stock_code in stock_codes:
        df = get_history_df(
            stock_code=stock_code,
            period="1d",
            count=count,
            fields="time,open,high,low,close,volume"
        )
        if df.empty:
            continue
        df["stock_code"] = stock_code
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


df_batch = get_multi_stock_day_df(["000001", "600000", "159915"], count=10)
print(df_batch)
save_table(df_batch, "batch_day_data.csv")
```

## 10. 获取买入力表

`/tick` 接口里还会返回 `buying_power`，可整理成表格直接查看普通 / 担保 / 融资的可买数量。

```python
def get_buying_power_df(stock_code):
    """
    获取单只证券的买入力表。
    """
    payload = ensure_success(request_json("/tick", {"stock_code": stock_code}))
    buying_power = payload.get("buying_power", {}) or {}
    row = {
        "stock_code": payload.get("stock_code", ""),
        "stock_name": payload.get("stock_name", ""),
        "latest_price": buying_power.get("latest_price", 0),
        "lot_size": buying_power.get("lot_size", 0),
        "preferred_source": buying_power.get("preferred_source", ""),
        "preferred_max_volume": buying_power.get("preferred_max_volume", 0),
        "normal_available_amount": buying_power.get("normal_available_amount", 0),
        "normal_max_volume": buying_power.get("normal_max_volume", 0),
        "credit_own_amount": buying_power.get("credit_own_amount", 0),
        "credit_own_max_volume": buying_power.get("credit_own_max_volume", 0),
        "credit_margin_amount": buying_power.get("credit_margin_amount", 0),
        "credit_margin_max_volume": buying_power.get("credit_margin_max_volume", 0),
    }
    return pd.DataFrame([row])


df_bp = get_buying_power_df("118025")
print(df_bp.T)
```

## 11. 一次性测试 tick、1分钟、5分钟、日线

下面这段代码适合第一次接入时快速验证。

```python
if __name__ == "__main__":
    sample_code = "000001"

    print("桥接健康检查")
    print(ensure_success(request_json("/health")))

    print("\nTick 表")
    print(get_tick_df(sample_code).T)

    print("\n1分钟表")
    print(get_history_df(sample_code, period="1m", count=10))

    print("\n5分钟表")
    print(get_history_df(sample_code, period="5m", count=10))

    print("\n日线表")
    print(get_history_df(sample_code, period="1d", count=10))
```

## 12. 当前桥接接口说明

### `/tick`

用途：

- 获取轻量五档行情
- 获取最新价
- 获取买入力结构

适合：

- 高频刷新
- 盘中手动交易
- 直接转成单行 DataFrame

### `/market`

用途：

- 获取完整行情
- 获取分时图 `chart`

适合：

- 页面刷新
- 盘中走势分析

### `/history_data`

用途：

- 获取 `tick`、`1m`、`5m`、`15m`、`30m`、`60m`、`1d` 等历史数据
- 支持通过 `fields` 参数扩展更多字段
- 支持返回 OHLCV 之外的成交额、昨收、停牌、持仓量等数据

适合：

- 外部策略研究
- DataFrame 批量分析
- 保存成 CSV / Excel

## 13. 常见问题

### 1. 返回“桥接接口未就绪”

说明大QMT内置 Python 里的 `big_data_qmt_app.py` 还没有运行，或者桥接端口不是默认值。

### 2. DataFrame 为空

常见原因：

- 证券代码错误
- 当前周期数据不足
- 非交易时段下某些接口没有返回
- `fields` 里填写了当前周期不支持的字段

### 3. 为什么文档里不只写 OHLCV？

因为大QMT文档本身就支持更多字段，例如：

- `amount`
- `preClose`
- `suspendFlag`
- `openInterest`
- `transactionNum`
- `askPrice / bidPrice / askVol / bidVol`

实际做策略研究时，通常不应该只停留在 OHLCV。

### 4. 如何像 akshare 一样使用？

核心思路就是：

1. 调桥接接口拿原始数据
2. 转成 `pandas.DataFrame`
3. 后续分析、筛选、保存全部在外部环境完成

也就是说，桥接接口负责“把大QMT数据拿出来”，`DataFrame` 负责“像 akshare 一样使用”。

## 14. 推荐上手顺序

推荐按下面顺序复制代码测试：

1. 先跑“健康检查”
2. 再跑“tick 表”
3. 再跑“1分钟表”
4. 再跑“5分钟表”
5. 最后跑“日线表”

这样最快确认桥接是否已经能够稳定输出你需要的数据表。
