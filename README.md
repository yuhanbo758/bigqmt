# bigqmt

大QMT行情桥接项目。它在大QMT内置 Python 中启动本地 HTTP 服务，将大QMT `ContextInfo` 行情能力暴露给外部 Python 环境，方便外部脚本获取 tick、分时和历史行情数据，并整理为 pandas DataFrame 使用。

## 功能特性

- 在大QMT内置 Python 中启动本地多线程 HTTP 桥接服务。
- 支持健康检查、tick 五档行情、分时数据和历史行情查询。
- 支持常见证券代码自动补全市场后缀，例如 `000001` 转为 `000001.SZ`。
- 外部 Python 示例可将接口结果转换为 pandas DataFrame。
- 支持通过环境变量调整桥接地址、端口和外部请求地址。
- 服务端访问和异常会写入本地 ndjson 调试日志。

## 项目结构

```text
bigqmt/
├── AGENTS.md
├── README.md
└── 大QMT外部调用web服务/
    ├── 大QMTserver.py
    ├── 获取数据测试.py
    ├── 桥接大qmt数据获取文档.md
    └── 大QMTSERVER.rzrk
```

## 核心文件

| 文件 | 说明 |
|------|------|
| `大QMT外部调用web服务/大QMTserver.py` | 大QMT内置 Python 侧运行的桥接服务脚本。 |
| `大QMT外部调用web服务/获取数据测试.py` | 外部 Python 调用示例，将返回结果整理为 DataFrame。 |
| `大QMT外部调用web服务/桥接大qmt数据获取文档.md` | 详细使用文档，包含字段、周期和示例代码。 |
| `大QMT外部调用web服务/大QMTSERVER.rzrk` | 大QMT相关二进制/配置文件，修改前需确认来源和用途。 |

## 环境要求

- 大QMT客户端及其内置 Python 环境。
- 外部 Python 环境，用于运行测试脚本和数据分析。
- pandas，用于外部脚本转换 DataFrame。

安装外部测试依赖：

```bash
pip install pandas
```

## 快速开始

1. 在大QMT内置 Python 中运行桥接服务脚本：`大QMT外部调用web服务/大QMTserver.py`。
2. 确认默认桥接地址可访问：`http://127.0.0.1:1690/health`。
3. 在外部 Python 环境运行测试脚本：`python 大QMT外部调用web服务/获取数据测试.py`。
4. 根据需要阅读 `大QMT外部调用web服务/桥接大qmt数据获取文档.md`，扩展字段、周期或批量获取逻辑。

## HTTP 接口

默认服务地址：

```text
http://127.0.0.1:1690
```

| 接口 | 别名 | 用途 |
|------|------|------|
| `/health` | `/bridge/health` | 检查桥接服务和大QMT运行时是否就绪。 |
| `/tick` | `/bridge/tick` | 获取单只证券 tick 五档行情。 |
| `/market` | `/bridge/market` | 获取 tick 行情和分时图数据。 |
| `/history_data` | `/bridge/history_data` | 获取历史行情，支持周期、字段和数量参数。 |

示例：

```text
http://127.0.0.1:1690/tick?stock_code=000001
http://127.0.0.1:1690/history_data?stock_code=600000&period=1d&count=10
```

## 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BIG_QMT_ENABLE_BRIDGE` | `1` | 是否启用桥接服务，设为 `0` 可禁用。 |
| `BIG_QMT_BRIDGE_HOST` | `127.0.0.1` | 服务监听地址。 |
| `BIG_QMT_BRIDGE_PORT` | `1690` | 服务监听端口。 |
| `BIG_QMT_BRIDGE_BASE_URL` | `http://127.0.0.1:1690` | 外部测试脚本请求地址。 |

## 注意事项

- `大QMTserver.py` 声明为 GBK 编码，修改时需保持大QMT内置 Python 的兼容性。
- 桥接服务端尽量只使用 Python 标准库，避免在大QMT内置 Python 中引入额外依赖。
- 外部脚本依赖 pandas，但这不代表大QMT内置 Python 侧也需要安装 pandas。
- 如果将监听地址从 `127.0.0.1` 改为局域网或公网地址，需要额外评估访问控制和安全风险。

## 相关文档

- [桥接大qmt数据获取文档](大QMT外部调用web服务/桥接大qmt数据获取文档.md)
- [AI 协作上下文](AGENTS.md)

## 👨‍💻 作者信息

**余汉波** - 编程爱好者-量化交易和效率工具开发

- **GitHub**: [@yuhanbo758](https://github.com/yuhanbo758)

- **Email**: yuhanbo@sanrenjz.com

- **Website**: [三人聚智](https://www.sanrenjz.com)

## 🌐 相关链接

- 🏠 [项目主页](https://www.sanrenjz.com)

- 📚 [在线文档](https://docs.sanrenjz.com)（财经、代码和库文档等）

- 🛒 [插件商店](https://shop.sanrenjz.com)（个人开发的所有程序，包括开源和不开源）


## 联系我们

[联系我们 - 三人聚智-余汉波](https://www.sanrenjz.com/contact_us/)

python 程序管理工具下载：[sanrenjz - 三人聚智-余汉波](https://www.sanrenjz.com/sanrenjz/)

效率工具程序管理下载：[sanrenjz-tools - 三人聚智-余汉波](https://www.sanrenjz.com/sanrenjz-tools/)

智能codebot下载：[sanrenjz-codebot - 三人聚智-余汉波](https://www.sanrenjz.com/sanrenjz-codebot/)

![三码合一](https://gdsx.sanrenjz.com/image/sanrenjz_yuhanbolh_yuhanbo758.png?imageSlim&t=1ab9b82c-e220-8022-beff-e265a194292a)

![余汉波打赏码](https://gdsx.sanrenjz.com/image/%E6%89%93%E8%B5%8F%E7%A0%81%E5%90%88%E4%B8%80.png?imageSlim)

## 🙏 致谢

感谢所有为本项目贡献代码和想法的开发者们！

---
**⭐ 如果这个项目对您有帮助，请给它一个 Star！**
