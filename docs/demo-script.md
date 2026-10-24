# SupportPilot 演示视频分镜脚本（2–3 分钟）

> 用途：按此分镜用 Loom/OBS 录制英文讲解或英文字幕。数据全部为 mock。

## 0:00 — 问题与方案（约 15s）

- 画面：落地页 `/`，品牌 SupportPilot 清晰可见。
- 旁白：*“Small stores need an AI support agent that can look up orders, answer from a knowledge base, book call-backs, and hand off to a human — with full traces. SupportPilot is a self-built portfolio demo I built with AI-assisted coding.”*

## 0:15 — FAQ + 引用（约 25s）

- 画面：打开 `/chat`，点击示例「What is your return policy?」。
- 展示：流式回答 + 引用来源折叠面板（Return Policy）。
- 旁白：强调 RAG，回答带来源，不编造。

## 0:40 — 查订单 + 错误邮箱（约 25s）

- 输入：`Where is order A1001? email jane@example.com` → 订单卡片。
- 再输入错误邮箱 → Agent 拒绝泄露。
- 旁白：双因素校验（订单号 + 邮箱）。

## 1:05 — 退货 RMA / 超期（约 25s）

- 合格订单（如 A1003）发起退货 → 显示 RMA。
- 超期订单（A1005）→ 解释超出退货窗口。

## 1:30 — 预约回电（约 20s）

- 查询空档 → 确认预约 → 确认信息卡片。

## 1:50 — Mock 故障率 + 重试转人工（约 25s）

- `/admin/settings`：调高 Mock failure rate。
- 再触发物流查询 → Trace 中可见重试 → 失败后转人工工单。

## 2:15 — Trace 与工单（约 20s）

- `/admin/conversations`：时间线展示节点、工具入参/出参、耗时、错误高亮。
- `/admin/tickets`：工单状态更新。

## 2:35 — 架构收尾（约 15s）

- 展示架构图 / LangGraph mermaid、技术栈一行。
- 明确声明：*Self-built demo, mock data, AI-assisted development — not a production customer project.*

## 录制检查清单

- [ ] 未暴露真实 API Key
- [ ] 全程使用种子 mock 数据
- [ ] 字幕或旁白为英文
- [ ] 片尾含 GitHub 链接位置
