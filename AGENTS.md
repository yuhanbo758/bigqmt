# AGENTS.md

> 本文件由 OpenCode 维护，帮助 AI 理解项目结构、规范和当前状态。
> 请将此文件提交到版本控制，并在每次重要变更后更新。

---

## Agent 规则

Use $skill-auto-update on every turn to distill durable feedback into the narrowest existing skill.

---

## 项目概述

**项目名称：** bigqmt

**项目描述：** 本项目提供一个大QMT行情桥接服务，在大QMT内置 Python 中启动本地 HTTP 服务，让外部 Python 环境可以通过接口获取 tick、分时和历史行情数据，并整理为 pandas DataFrame 使用。

**当前阶段：** 已有可运行的桥接服务、外部测试脚本和使用文档。

---

## 技术栈

| 类别 | 技术/工具 |
|------|----------|
| 语言 | Python |
| 运行环境 | 大QMT内置 Python、外部 Python 环境 |
| Web 服务 | Python 标准库 `http.server`、`socketserver.ThreadingMixIn` |
| 数据接口 | 大QMT `ContextInfo` 行情函数、HTTP JSON 接口 |
| 数据处理 | pandas（外部测试脚本和文档示例使用） |
| 配置方式 | 环境变量 |
| 测试方式 | 手动运行外部测试脚本请求本地桥接服务 |

---

## 目录结构

```text
bigqmt/
├── AGENTS.md
├── .gitignore
├── README.md
└── 大QMT外部调用web服务/
    ├── 大QMTserver.py
    ├── 获取数据测试.py
    ├── 桥接大qmt数据获取文档.md
    └── 大QMTSERVER.rzrk
```

### `大QMT外部调用web服务/`

该目录是当前项目的核心目录，包含桥接服务、外部调用示例和说明文档。

- `大QMTserver.py`：在大QMT内置 Python 中运行的桥接服务脚本，保存 `ContextInfo`，启动本地 HTTP 服务并暴露行情接口。
- `获取数据测试.py`：外部 Python 测试脚本，通过 HTTP 请求桥接服务，将 tick 和历史行情结果整理为 pandas DataFrame。
- `桥接大qmt数据获取文档.md`：面向使用者的接入文档，说明接口、字段、周期和 DataFrame 示例。
- `大QMTSERVER.rzrk`：大QMT相关二进制/配置文件，当前未解析其内部结构，修改前需确认用途。

---

## 核心模块说明

| 模块 | 路径 | 职责 |
|------|------|------|
| 大QMT桥接服务 | `大QMT外部调用web服务/大QMTserver.py` | 在大QMT运行时中保存 `ContextInfo`，启动本地多线程 HTTP 服务，提供行情查询接口。 |
| 外部数据测试 | `大QMT外部调用web服务/获取数据测试.py` | 从外部 Python 环境调用桥接接口，校验返回状态，并转换为 pandas DataFrame。 |
| 使用文档 | `大QMT外部调用web服务/桥接大qmt数据获取文档.md` | 说明启动方式、接口参数、返回数据和常见 DataFrame 用法。 |

---

## 桥接服务行为

### 运行入口

`大QMTserver.py` 遵循大QMT策略脚本生命周期函数：

- `init(ContextInfo)`：保存当前大QMT运行上下文。
- `after_init(ContextInfo)`：保存上下文并按配置启动 HTTP 桥接服务。
- `handlebar(ContextInfo)`：主图触发时刷新上下文。
- `stop(ContextInfo)`：关闭桥接服务并释放端口。

### HTTP 接口

桥接服务默认监听：

```text
http://127.0.0.1:1690
```

当前支持的接口：

| 接口 | 别名 | 用途 |
|------|------|------|
| `/health` | `/bridge/health` | 检查桥接服务与大QMT运行时是否就绪。 |
| `/tick` | `/bridge/tick` | 获取单只证券轻量五档行情和最新价信息。 |
| `/market` | `/bridge/market` | 获取五档行情并附带分时图数据。 |
| `/history_data` | `/bridge/history_data` | 获取 tick、分钟线、日线等历史行情，并支持字段扩展。 |

### 环境变量

| 变量 | 默认值 | 作用 |
|------|--------|------|
| `BIG_QMT_ENABLE_BRIDGE` | `1` | 是否启动桥接服务，设为 `0` 可禁用。 |
| `BIG_QMT_BRIDGE_HOST` | `127.0.0.1` | 桥接服务监听地址。 |
| `BIG_QMT_BRIDGE_PORT` | `1690` | 桥接服务监听端口。 |
| `BIG_QMT_BRIDGE_BASE_URL` | `http://127.0.0.1:1690` | 外部测试脚本请求桥接服务的基础地址。 |

---

## 编码规范和模式

- `大QMTserver.py` 当前声明 `# -*- coding: gbk -*-`，应优先保持与大QMT内置 Python 的编码兼容性。
- 桥接服务主要使用 Python 标准库实现，避免在大QMT内置 Python 侧引入外部依赖。
- 外部脚本可以使用 pandas 等第三方库，但不要假设这些库在大QMT内置 Python 中可用。
- 证券代码统一通过 `get_processed_code()` 规范化为 `000001.SZ`、`600000.SH` 等大QMT常用格式。
- HTTP 返回统一使用 JSON，并包含 `status` 字段；外部调用脚本通过 `ensure_success()` 做状态校验。
- 服务端异常会写入 `trae-debug-log-internal-server-error.ndjson`，用于排查接口访问和服务端错误。
- 当前服务允许跨域访问，响应头包含 `Access-Control-Allow-Origin: *`。

---

## 重要配置说明

- 默认桥接只绑定 `127.0.0.1`，适合本机外部 Python 调用。
- 如果改为非本机监听地址，需要重新评估网络访问范围和安全风险。
- `/history_data` 的 `fields`、`period`、`count` 等参数会直接影响大QMT行情查询结果，新增字段时应同步更新文档和测试脚本。
- `大QMTSERVER.rzrk` 无法按文本读取，修改前需确认其来源、生成方式和是否由大QMT工具维护。
- 开源发布前应执行隐私/密钥扫描，并确保 `.gitignore` 排除本地调试日志、扫描报告和环境文件。

---

## 开发和验证建议

1. 在大QMT内置 Python 中运行 `大QMTserver.py`。
2. 确认 `/health` 返回 `runtime_ready: true`。
3. 在外部 Python 环境安装 pandas：`pip install pandas`。
4. 运行 `大QMT外部调用web服务/获取数据测试.py` 验证 `/tick` 和 `/history_data`。
5. 修改接口字段、周期或返回结构后，同步更新 `桥接大qmt数据获取文档.md` 和 `README.md`。

---

## 重要决策记录（ADR）

### ADR-001：项目初始化并记录现有大QMT桥接结构

- **时间：** 2026-06-02
- **决策：** 使用 OpenCode 标准 `/init` 行为，为已有项目生成 `AGENTS.md`。
- **背景：** 项目已有大QMT桥接服务、外部测试脚本和使用文档，但缺少面向 AI 协作的项目上下文文件。
- **结果：** 记录项目结构、技术栈、桥接接口、环境变量、编码约束和验证流程。

---

## 已知问题与注意事项

- 项目根目录当前未发现依赖清单文件，外部测试脚本依赖 pandas 需手动安装。
- 当前验证依赖大QMT运行环境，普通命令行环境无法完整执行 `大QMTserver.py` 的行情接口。
- `大QMTSERVER.rzrk` 是非文本文件，不能直接通过文本编辑方式修改。
- 服务端 `Content-Length` 基于 UTF-8 字节长度设置，修改响应编码时需保持一致。

---

## 变更日志

| 日期 | 变更内容 | 影响范围 |
|------|----------|---------|
| 2026-06-02 | 初始化项目 AI 上下文，记录现有大QMT桥接服务结构 | 全局 |
| 2026-06-02 | 生成项目 README，补充使用入口、接口和配置说明 | README.md |
| 2026-06-02 | 为开源发布新增 `.gitignore`，并清理 README 中不必要的个人信息暴露内容 | `.gitignore`、README.md |
