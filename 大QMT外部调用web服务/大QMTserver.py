# -*- coding: gbk -*-
import inspect
import json
import os
import socketserver
import sys
import threading
import traceback
from datetime import datetime, time as datetime_time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# 大QMT行情桥接服务


def resolve_base_dir():
    """尽量稳定地推断脚本所在目录，便于输出调试日志文件。"""
    candidates = []

    def append_candidate(value):
        if not value:
            return
        normalized = os.path.abspath(value)
        if os.path.isfile(normalized):
            normalized = os.path.dirname(normalized)
        candidates.append(normalized)

    script_file = globals().get("__file__")
    append_candidate(script_file)

    code_object = getattr(resolve_base_dir, "__code__", None)
    append_candidate(code_object.co_filename if code_object else "")

    frame = inspect.currentframe()
    try:
        append_candidate(frame.f_code.co_filename if frame else "")
    finally:
        del frame

    argv0 = sys.argv[0] if getattr(sys, "argv", None) else ""
    if argv0 not in ("", "-c"):
        append_candidate(argv0)

    append_candidate(os.getcwd())

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.isfile(os.path.join(candidate, "big_data_qmt_app.py")):
            return candidate

    if candidates:
        return os.path.abspath(candidates[0])
    return os.path.abspath(os.getcwd())


BASE_DIR = resolve_base_dir()
DEBUG_LOG_PATH = os.path.join(BASE_DIR, "trae-debug-log-internal-server-error.ndjson")
QMT_CONTEXT = None
QMT_CONTEXT_LOCK = threading.Lock()
QMT_BRIDGE_SERVER_STARTED = False
QMT_BRIDGE_SERVER = None
ENABLE_QMT_BRIDGE_SERVER = os.getenv("BIG_QMT_ENABLE_BRIDGE", "1") != "0"
QMT_BRIDGE_HOST = os.getenv("BIG_QMT_BRIDGE_HOST", "127.0.0.1")

try:
    QMT_BRIDGE_PORT = int(os.getenv("BIG_QMT_BRIDGE_PORT", "1690"))
except ValueError:
    QMT_BRIDGE_PORT = 1690


def log_info(message):
    print(str(message))


def log_error(message):
    print(str(message))


def log_exception(prefix, exc):
    log_error("{}: {}".format(prefix, exc))
    traceback.print_exc()


def append_debug_log(event_name, payload):
    """将桥接访问和异常记录到本地 ndjson 文件，便于排查服务端错误。"""
    try:
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event_name,
            "payload": payload,
        }
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def normalize_stock_code(stock_code):
    return str(stock_code or "").strip().upper()


def normalize_runtime_text(value):
    """兼容大QMT运行时里 bytes、正常字符串和伪乱码字符串。"""
    if value is None:
        return ""

    if isinstance(value, bytes):
        for encoding in ("gbk", "utf-8", "latin1"):
            try:
                text = value.decode(encoding).strip()
                if text:
                    return text
            except Exception:
                pass
        return ""

    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""

    if any(ord(char) > 127 for char in text):
        for source_encoding in ("latin1", "utf-8"):
            try:
                recovered = text.encode(source_encoding).decode("gbk").strip()
                if recovered:
                    return recovered
            except Exception:
                pass

    return text


def get_base_stock_code(stock_code):
    normalized = normalize_stock_code(stock_code)
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized


def get_processed_code(stock_code):
    """把 000001 或 000001.SZ 统一规范成大QMT常用代码格式。"""
    normalized = normalize_stock_code(stock_code)
    if "." in normalized:
        base_code, market = normalized.split(".", 1)
        if base_code.isdigit() and len(base_code) == 6 and market in ("SH", "SZ"):
            return "{}.{}".format(base_code, market)
        normalized = base_code

    base_code = normalized
    if not base_code.isdigit() or len(base_code) != 6:
        return ""

    if base_code.startswith("6"):
        return "{}.SH".format(base_code)
    if base_code.startswith(("0", "3")):
        return "{}.SZ".format(base_code)
    if base_code.startswith(("11", "113")):
        return "{}.SH".format(base_code)
    if base_code.startswith("12"):
        return "{}.SZ".format(base_code)
    if base_code.startswith(("50", "51", "58")):
        return "{}.SH".format(base_code)
    if base_code.startswith(("15", "16", "18")):
        return "{}.SZ".format(base_code)
    return ""


def call_context_function(function_names, *args, **kwargs):
    """兼容大QMT不同版本中少量函数命名差异。"""
    context = ensure_big_qmt_context()
    for function_name in function_names:
        func = getattr(context, function_name, None)
        if callable(func):
            return func(*args, **kwargs)
    return None


def extract_name_from_instrument_detail(detail):
    if not isinstance(detail, dict):
        return ""
    for key in (
        "InstrumentName",
        "StockName",
        "SecuName",
        "Name",
        "instrumentName",
        "stockName",
    ):
        name_value = normalize_runtime_text(detail.get(key))
        if name_value:
            return name_value
    return ""


def set_big_qmt_context(context):
    global QMT_CONTEXT
    with QMT_CONTEXT_LOCK:
        QMT_CONTEXT = context


def get_big_qmt_runtime_error():
    return "大QMT运行环境未就绪，请在大QMT内置Python中运行，并等待 init/after_init 完成。"


def ensure_big_qmt_context():
    if QMT_CONTEXT is None:
        raise RuntimeError(get_big_qmt_runtime_error())
    return QMT_CONTEXT


def get_security_name(stock_code):
    """名称查询只使用行情/合约信息接口，不读取任何账户或交易对象。"""
    processed_code = get_processed_code(stock_code)
    if not processed_code:
        return ""

    for code_value in (processed_code, get_base_stock_code(processed_code)):
        try:
            stock_name = call_context_function(["get_stock_name"], code_value)
            stock_name = normalize_runtime_text(stock_name)
            if stock_name:
                return stock_name
        except Exception:
            pass

    for code_value in (processed_code, get_base_stock_code(processed_code)):
        try:
            detail = call_context_function(
                ["get_instrument_detail", "get_instrumentdetail"],
                code_value,
            )
            stock_name = extract_name_from_instrument_detail(detail)
            if stock_name:
                return stock_name
        except Exception:
            pass

    return processed_code


def normalize_level5(values):
    values = list(values or [])[:5]
    return [to_float(value) for value in values] + [0.0] * (5 - len(values))


def format_chart_time(index_value):
    raw_value = str(index_value)
    if len(raw_value) >= 12 and raw_value[:8].isdigit():
        return "{}:{}".format(raw_value[8:10], raw_value[10:12])
    return raw_value


def is_trading_minute_point(time_text):
    if not time_text or ":" not in time_text:
        return False

    try:
        hour, minute = time_text.split(":", 1)
        point_time = datetime_time(int(hour), int(minute))
    except (TypeError, ValueError):
        return False

    morning_start = datetime_time(9, 30)
    morning_end = datetime_time(11, 30)
    afternoon_start = datetime_time(13, 0)
    afternoon_end = datetime_time(15, 0)
    return (morning_start <= point_time <= morning_end) or (
        afternoon_start <= point_time <= afternoon_end
    )


def get_tick_snapshot(processed_code):
    """返回轻量五档行情结构，只依赖 get_full_tick 与合约详情。"""
    context = ensure_big_qmt_context()
    tick_map = context.get_full_tick([processed_code]) or {}
    stock_tick = tick_map.get(processed_code)
    if not stock_tick:
        return None

    last_close = to_float(stock_tick.get("lastClose"))
    up_limit = 0.0
    down_limit = 0.0

    try:
        instrument_detail = call_context_function(
            ["get_instrument_detail", "get_instrumentdetail"],
            processed_code,
        )
        if isinstance(instrument_detail, dict):
            up_limit = to_float(instrument_detail.get("UpStopPrice"))
            down_limit = to_float(instrument_detail.get("DownStopPrice"))
    except Exception:
        pass

    if not up_limit and last_close > 0:
        up_limit = round(last_close * 1.1, 3)
    if not down_limit and last_close > 0:
        down_limit = round(last_close * 0.9, 3)

    return {
        "askPrice": normalize_level5(stock_tick.get("askPrice")),
        "bidPrice": normalize_level5(stock_tick.get("bidPrice")),
        "askVol": normalize_level5(stock_tick.get("askVol")),
        "bidVol": normalize_level5(stock_tick.get("bidVol")),
        "最新": to_float(stock_tick.get("lastPrice")),
        "今开": to_float(stock_tick.get("open")),
        "最高": to_float(stock_tick.get("high")),
        "最低": to_float(stock_tick.get("low")),
        "昨收": last_close,
        "涨停": up_limit,
        "跌停": down_limit,
    }


def resolve_intraday_price(close_price, open_price, fallback_price, prefer_open=False):
    close_price = to_float(close_price)
    open_price = to_float(open_price)
    fallback_price = to_float(fallback_price)

    if prefer_open and open_price > 0:
        return open_price
    if close_price > 0:
        return close_price
    if open_price > 0:
        return open_price
    if fallback_price > 0:
        return fallback_price
    return 0.0


def get_intraday_chart(processed_code, tick_snapshot=None):
    """把 1 分钟数据整理成桥接文档需要的分时图结构。"""
    context = ensure_big_qmt_context()
    start_date = datetime.now().strftime("%Y%m%d")
    market_data = context.get_market_data_ex(
        fields=["time", "open", "close", "volume"],
        stock_code=[processed_code],
        period="1m",
        start_time=start_date,
        count=241,
        subscribe=True,
    )

    stock_data = market_data.get(processed_code)
    if stock_data is None or stock_data.empty:
        return []

    chart = []
    session_open_price = to_float((tick_snapshot or {}).get("今开"))
    previous_price = session_open_price
    if previous_price <= 0:
        previous_price = to_float((tick_snapshot or {}).get("昨收"))

    first_chart_point = True
    for index_value, row in stock_data.iterrows():
        chart_time = format_chart_time(index_value)
        if not is_trading_minute_point(chart_time):
            continue

        price = resolve_intraday_price(
            row.get("close"),
            row.get("open"),
            session_open_price if first_chart_point and session_open_price > 0 else previous_price,
            prefer_open=first_chart_point,
        )
        if price > 0:
            previous_price = price

        chart.append(
            {
                "time": chart_time,
                "price": price,
                "volume": to_float(row.get("volume")),
            }
        )
        first_chart_point = False

    return chart


def build_bridge_health_payload():
    runtime_ready = QMT_CONTEXT is not None
    return {
        "status": "success",
        "runtime_ready": runtime_ready,
        "message": "" if runtime_ready else get_big_qmt_runtime_error(),
        "bridge_host": QMT_BRIDGE_HOST,
        "bridge_port": QMT_BRIDGE_PORT,
    }


def build_quote_payload(raw_code, include_chart):
    stock_code = get_processed_code(raw_code)
    if not stock_code:
        return {"status": "error", "message": "证券代码无效"}

    tick = get_tick_snapshot(stock_code)
    if tick is None:
        return {
            "status": "error",
            "message": "大QMT暂未返回 {} 的五档行情，请确认当前图表和行情环境可用".format(stock_code),
        }

    payload = {
        "status": "success",
        "stock_code": stock_code,
        "stock_name": get_security_name(stock_code),
        "tick": tick,
        "quote_refresh_interval_ms": 1000,
    }
    if include_chart:
        payload["chart"] = get_intraday_chart(stock_code, tick)
    return payload


def build_market_data_payload(raw_code):
    return build_quote_payload(raw_code, True)


def build_tick_data_payload(raw_code):
    return build_quote_payload(raw_code, False)


def parse_fields_text(fields_text):
    values = []
    for item in str(fields_text or "").split(","):
        field_name = str(item or "").strip()
        if field_name:
            values.append(field_name)
    return values


def build_history_market_payload(payload):
    """桥接历史行情接口，对应桥接文档中的 /history_data。"""
    context = ensure_big_qmt_context()
    stock_code = get_processed_code(payload.get("stock_code", ""))
    if not stock_code:
        return {"status": "error", "message": "证券代码无效"}

    period = str(payload.get("period", "1d") or "1d").strip()
    start_time = str(payload.get("start_time", "") or "").strip()
    end_time = str(payload.get("end_time", "") or "").strip()
    count = to_int(payload.get("count", 60))
    if count <= 0:
        count = 60

    dividend_type = str(payload.get("dividend_type", "none") or "none").strip()
    fields = parse_fields_text(payload.get("fields", "time,open,high,low,close,volume"))
    if not fields:
        fields = ["time", "open", "high", "low", "close", "volume"]

    market_data = context.get_market_data_ex(
        fields=fields,
        stock_code=[stock_code],
        period=period,
        start_time=start_time,
        end_time=end_time,
        count=count,
        dividend_type=dividend_type,
        fill_data=True,
        subscribe=False,
    )

    stock_data = market_data.get(stock_code)
    if stock_data is None or stock_data.empty:
        return {
            "status": "success",
            "stock_code": stock_code,
            "stock_name": get_security_name(stock_code),
            "period": period,
            "fields": fields,
            "data": [],
        }

    rows = []
    for index_value, row in stock_data.iterrows():
        item = {"time": str(index_value)}
        for field_name in fields:
            if field_name == "time":
                continue
            value = row.get(field_name)
            if isinstance(value, (int, float)):
                item[field_name] = float(value)
            else:
                item[field_name] = value
        rows.append(item)

    return {
        "status": "success",
        "stock_code": stock_code,
        "stock_name": get_security_name(stock_code),
        "period": period,
        "fields": fields,
        "data": rows,
    }


class ThreadedBridgeHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def normalize_bridge_params(params):
    normalized = {}
    for key, value in params.items():
        if isinstance(value, list):
            normalized[key] = value[0] if value else ""
        else:
            normalized[key] = value
    return normalized


def create_bridge_handler():
    class QmtBridgeHandler(BaseHTTPRequestHandler):
        def log_message(self, format_text, *args):
            append_debug_log(
                "qmt_bridge_access",
                {
                    "client": self.client_address[0],
                    "message": format_text % args,
                },
            )

        def _write_json(self, status_code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def _read_params(self):
            url_info = urlparse(self.path)
            params = normalize_bridge_params(parse_qs(url_info.query, keep_blank_values=True))

            if self.command == "POST":
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                raw_body = self.rfile.read(content_length) if content_length > 0 else b""
                content_type = self.headers.get("Content-Type", "")
                if raw_body:
                    if "application/json" in content_type:
                        try:
                            params.update(json.loads(raw_body.decode("utf-8")))
                        except Exception:
                            pass
                    else:
                        params.update(
                            normalize_bridge_params(
                                parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
                            )
                        )
            return url_info.path, params

        def do_OPTIONS(self):
            self._write_json(200, {"status": "success"})

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def _dispatch(self):
            try:
                path, params = self._read_params()

                if path in ("/health", "/bridge/health"):
                    self._write_json(200, build_bridge_health_payload())
                    return

                if path in ("/market", "/bridge/market"):
                    self._write_json(200, build_market_data_payload(params.get("stock_code", "")))
                    return

                if path in ("/tick", "/bridge/tick"):
                    self._write_json(200, build_tick_data_payload(params.get("stock_code", "")))
                    return

                if path in ("/history_data", "/bridge/history_data"):
                    self._write_json(200, build_history_market_payload(params))
                    return

                self._write_json(404, {"status": "error", "message": "桥接接口不存在"})
            except Exception as exc:
                append_debug_log(
                    "qmt_bridge_exception",
                    {
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                )
                self._write_json(500, {"status": "error", "message": str(exc)})

    return QmtBridgeHandler


def run_qmt_bridge_server():
    global QMT_BRIDGE_SERVER
    server = ThreadedBridgeHTTPServer(
        (QMT_BRIDGE_HOST, QMT_BRIDGE_PORT),
        create_bridge_handler(),
    )
    QMT_BRIDGE_SERVER = server
    log_info(
        "big_qmt_app bridge 服务已启动: http://{}:{}".format(
            QMT_BRIDGE_HOST,
            QMT_BRIDGE_PORT,
        )
    )
    server.serve_forever()


def start_qmt_bridge_server_once():
    global QMT_BRIDGE_SERVER_STARTED
    if QMT_BRIDGE_SERVER_STARTED:
        return
    QMT_BRIDGE_SERVER_STARTED = True
    server_thread = threading.Thread(
        target=run_qmt_bridge_server,
        name="big_qmt_bridge_server",
        daemon=True,
    )
    server_thread.start()


def init(ContextInfo):
    """初始化时保存 ContextInfo，后续 HTTP 请求直接复用当前行情环境。"""
    set_big_qmt_context(ContextInfo)


def after_init(ContextInfo):
    """启动桥接服务，只暴露纯行情接口。"""
    set_big_qmt_context(ContextInfo)
    if ENABLE_QMT_BRIDGE_SERVER:
        start_qmt_bridge_server_once()


def handlebar(ContextInfo):
    """主图每次触发时刷新最新 ContextInfo。"""
    set_big_qmt_context(ContextInfo)


def stop(ContextInfo):
    global QMT_BRIDGE_SERVER
    global QMT_BRIDGE_SERVER_STARTED

    set_big_qmt_context(ContextInfo)
    if QMT_BRIDGE_SERVER is not None:
        try:
            QMT_BRIDGE_SERVER.shutdown()
            QMT_BRIDGE_SERVER.server_close()
        except Exception:
            pass
        QMT_BRIDGE_SERVER = None
    QMT_BRIDGE_SERVER_STARTED = False
    log_info("big_qmt_app stop")
