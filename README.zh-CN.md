# MCP Witness

**把已经成功的 MCP 工具调用，变成升级前可执行的离线回归测试。**

[English](README.md) · [设计与边界](docs/design.md) · [CI 集成](docs/ci.md)

一个典型问题：Agent 今天能执行 `lookup_invoice({"invoice_id":"demo-001"})`，
明天 MCP 服务升级后要求增加 `workspace`。服务仍能启动，工具仍在列表里，健康检查
也通过，但原来的工作流已经不能运行。

MCP Witness 用旧版契约确认样本原本有效，再用新版契约验证同一条调用。如果失败，
报告会给出具体案例 ID、约束类型和字段位置，让维护者在 CI 阶段看见问题。

## 快速体验

需要 Python 3.11+。离线检查不需要模型 API、账户或正在运行的 MCP 服务。
当前为早期 alpha，安装来源是 GitHub；尚未发布到 PyPI。

```powershell
git clone https://github.com/shyangar/mcp-witness.git
cd mcp-witness
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .

# 正常版本：退出码 0
.venv\Scripts\python.exe -m mcp_witness check --baseline examples/baseline.json --candidate examples/baseline.json --cases examples/cases.json

# 故意破坏兼容性的版本：退出码 1，这是示例的预期结果
.venv\Scripts\python.exe -m mcp_witness check --baseline examples/baseline.json --candidate examples/breaking.json --cases examples/cases.json
```

第二条检查会发现：

- `lookup-existing`：新增必填参数，原调用缺少 `workspace`。
- `list-pending`：枚举不再接受 `pending`，原调用失效。
- `list-paid`：仍可通过；报告不会把所有样本都判为失败。
- 返回契约变化进入人工审查，因为输入样本不能证明返回行为是否兼容。

## 首版实现

| 功能 | 用途 |
| --- | --- |
| 调用样本回归 | 区分确有失败证据的变化和仍需人工确认的变化。 |
| 契约变更审查 | 跟踪输入/输出 Schema、描述、行为声明以及其他工具元数据。 |
| 工具覆盖率 | 明确显示没有调用样本覆盖的工具，可通过 `--require-coverage` 纳入审查。 |
| 本地目录快照 | 导入完整的 `tools/list` 结果，排序并计算 SHA-256 指纹。 |
| stdio 服务发现 | 可选 MCP SDK 适配器，支持初始化、分页和超时；不执行工具调用。 |
| CI 报告 | 文本、JSON、Markdown、JUnit XML。 |
| 样本导入 | 从 MCP JSON / JSONL 请求记录提取 `tools/call` 参数。 |

默认 `--fail-on review` 会让“已证实破坏”与“需要审查”都阻断检查。
`--fail-on breaking` 只阻断已移除工具和已知调用失效，是明确放宽的策略。
退出码 `2` 表示输入、Schema、连接或文件操作有问题，不应当被视为兼容性通过。

## 从真实服务采集

```powershell
.venv\Scripts\python.exe -m pip install -e ".[capture]"
.venv\Scripts\python.exe -m mcp_witness capture --output baseline.json -- .venv\Scripts\python.exe examples/invoice_server.py
.venv\Scripts\python.exe -m mcp_witness capture --output candidate.json -- .venv\Scripts\python.exe examples/invoice_server.py --breaking
.venv\Scripts\python.exe -m mcp_witness check --baseline baseline.json --candidate candidate.json --cases examples/cases.json
```

采集会启动你提供的服务程序，应只用于可信程序。它不是沙箱，也不会自动转发任意
环境凭据。示例服务只使用虚构发票数据，不访问外部业务系统。

## 适用边界

这里的“回放”是重新验证输入契约，不是重新执行真实业务动作。检查通过仅代表已收录
样本通过选定策略，不能证明所有调用都兼容、工具实现没有变化、Agent 决策一定正确。

Schema 使用 Draft 2020-12，支持本地 JSON Pointer `$ref`；其他草案、外部引用、
`$id`、锚点和动态引用会返回错误。`format` 按注解处理，不执行格式断言。
Streamable HTTP 和实际返回值断言尚未实现，见 [路线图](ROADMAP.md)。

导入器会原样复制参数，不会自动脱敏。提交样本前，请把私人数据替换为虚构数据。
报告省略参数值，但保留工具名、案例 ID 和字段路径。不要把这些字段本身当作秘密存储。

欢迎用“脱敏调用样本 + 新旧 Schema”报告问题。MIT 开源，当前尚无已验证的外部采用记录。
