<div align="center">
  <img src="assets/logo.svg" alt="Kedu" width="440">
</div>

# Kedu · 刻牍

[English](README.md) | **中文**

**本地优先、无损的 AI 编程 agent 会话记录层。**

*Kedu（刻牍，读作 “Kay-Doo”）意为“刻写记录”——把发生过的事刻下来，让它长久留存。*

Kedu 把你的开发会话历史以你自己拥有的纯文本文件形式保存在项目里。任何 agent——Claude
Code、Codex、Kiro、Cursor，或将来出现的任何工具——都能从上一个 agent 停下的地方继续，而不必
依赖锁死在某个工具内部的记忆。

**Kedu 不是记忆，而是一个记录层。** 它记录*发生了什么、谁做的、证据在哪里、下一步该做什么*，
让 agent 的工作可审计、可交接，而不是被困在不透明、被厂商掌控的记忆里。普通的“记忆”回答的是
*模型记得什么*；Kedu 回答的是*我们为什么知道这件事、证据在哪里、是谁产生的、是否经过验证、由谁
接着做下去。*

> Kedu 是 agent 世界里的书记员。它不保存世界本身——它记录 agent 做过什么、证据在哪里、结果
> 是否可信、下一步交给谁。

<p>
  <a href="https://github.com/jasonshrepo/kedu/actions/workflows/ci.yml"><img src="https://github.com/jasonshrepo/kedu/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-17313C.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-216C83.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-475A60.svg" alt="Platform: macOS | Linux">
  <img src="https://img.shields.io/badge/status-developer%20preview-C8553D.svg" alt="Status: developer preview">
</p>

---

## 目录

- [五分钟上手](#五分钟上手)
- [为什么选择 Kedu](#为什么选择-kedu)
- [核心理念](#核心理念)
- [Kedu 做什么](#kedu-做什么)
- [Kedu 不是什么](#kedu-不是什么)
- [当前状态](#当前状态)
- [已知限制](#已知限制)
- [从源码安装](#从源码安装)
- [使用 Kedu](#使用-kedu)
- [设计原则](#设计原则)
- [方案架构](#方案架构)
- [许可证](#许可证)

## 五分钟上手

完整流程——安装、接入 agent、保存一条记录，再让*下一个* agent 读回来：

```bash
# 1. 从源码安装（把 `kedu` 装到 ~/.local/bin，引擎装到 ~/.kedu/kedu）
git clone https://github.com/jasonshrepo/kedu.git
cd kedu && bash install.sh

# 2. 接入一个真实项目（选择你的 host：claude | codex | kiro | cursor）
cd /path/to/your/project
kedu init --host claude
```

然后，**在 agent 里**记一笔并交接：

```text
/kedu-log    我们决定了什么、接下来该做什么
```

之后在同一项目里打开*另一个* agent，让它从你离开的地方接着做：

```text
/kedu-search    上一个决定
```

就这样——记录是 `.kedu/` 和 `~/.kedu` 里的纯文本文件，任何 agent 都能读取。项目里的 `.kedu/`
是开发者自有、跨 agent 的会话记忆——它跟着仓库走，而不是跟着某个厂商走。每个 host 的具体调用
方式见 [使用 Kedu](#使用-kedu)，安装细节见 [从源码安装](#从源码安装)。

## 为什么选择 Kedu

要让一个 AI 编程 agent 在真实项目上真正好用，是要花功夫的。你给它讲清楚架构、各种决策、踩过的
坑、哪些还没做完。然后会话一结束——这些理解全蒸发了。下次又得从头来。

今天，这些来之不易的上下文被困住了：

- **随线程消亡。** 关掉对话或撞上上下文上限，共享的理解就没了。
- **无法在工具间流动。** 从 Claude Code 换到 Cursor——或交接给队友——新 agent 对你的项目
  一无所知。
- **被厂商锁定。** 平台“记忆”存在别人的服务器上。你读不到、改不了、也带不走。
- **被摘要抹掉。** 长会话被压缩成有损的概述，而你真正需要的细节往往最先被丢弃。

Kedu 的解决办法，是把项目历史放回它该在的地方：**在你的项目里，作为你拥有的纯文本文件。**
下一个 agent 读到的是同一份“发生了什么”的书面记录——不是猜测，也不是厂商的黑箱。

## 核心理念

把你的 agent 当作书记员。在一次会话结束时——或任何重要的时刻——你让它写下你做了什么、想记住
什么。这条笔记成为项目里的一条记录。下次打开项目时，agent 先读这些记录，于是它已经了解历史，
能从你离开的地方接着做。Kedu 像一个称职的书记员，只记录重要的时刻——做了什么决定、证据在哪里、
下一步是什么——而不是数据本身。

Kedu 最初只是一个一行的 `/log` skill：它把会话摘要追加到一个 `history.md` 文件里（一份在项目
内、一份全局），每次会话开始时读回。这个办法有效——直到历史大到每次都重读不现实。Kedu 是同一个
想法，但做了结构化以便扩展：用许多小记录代替一个不断膨胀的文件，开头读一份简短概览，再用确定性
检索只取出相关的部分。

## Kedu 做什么

你来指挥，agent 来记录：

1. **捕获（Capture）**——你让 agent 写下你做了什么、什么值得记住。可以记录整个会话，也可以只
   指向你想保留的具体内容。
2. **保存（Preserve）**——agent 写下笔记；Kedu 原样保存，绝不像上下文窗口那样重新摘要或淘汰它。
3. **检索（Retrieve）**——需要时取回相关的历史记录。
4. **交接（Hand off）**——下一个 agent 或下一次会话先读这些记录。
5. **推理（Reason）**——模型基于你能看到、能信任的真实笔记工作，而不是它自己臆造的记忆。

后台不会悄悄记录任何东西——**由你决定记什么。** 这些记录就是你仓库和主目录里的文件：可以打开、
阅读、用 git diff 对比、编辑或脱敏其中任何内容。

## Kedu 不是什么

| Kedu 不是 | 通俗解释 |
|---|---|
| 记忆（Memory） | 它不让模型“记住更多”。它记录做过什么、证据在哪里，让下一个 agent 能够验证并继续。 |
| 数据库 | 它不保存你的大批量数据——帖子、评论、表、文件。它记录这些数据*在哪里*（路径、数量、哈希），而不是数据本身。 |
| 向量记忆 / RAG | 没有 embedding，没有模糊相似度猜测。它靠精确过滤和关键词查找记录。 |
| 搜索引擎 | 它给出可能相关的候选记录；由模型决定真正重要的是什么。没有排序打分。 |
| 爬虫 / 连接器 | 它不抓取网页或平台 API。它记录*发生过*一次抓取，并指向其产物。 |
| Dashboard | 它不做渲染或可视化。它是其他工具可以读取的底层记录。 |
| 聊天记录 | 不是对话流水的堆砌。是关于决策、证据和下一步的有意、结构化的记录。 |
| Agent 框架 | 它不运行或调度 agent。它记录会话，并把上下文交接给你使用的任何 agent。 |
| 平台记忆 | 你的记录是你拥有的本地文件——不是存在厂商服务器上的记忆。 |

## 当前状态

Kedu 是一个**源码优先的开发者预览版**。你从本仓库安装；目前还没有公开的包管理器发行版。

今天已经可用、并由测试套件（`uv run pytest`）覆盖的能力：

- 捕获会话记录（`kedu log`）。
- 查找历史记录（`kedu search`、`kedu show`），以及列出已知项目（`kedu projects`）。
- 旧记录的整理与长期归档（`kedu maintain`）。
- 对既有存储做一次性的项目名规范化（`kedu migrate`）。
- 从记录中移除密钥，包括事后移除（`kedu redact`）。
- 把 Kedu 接入你选择的 agent（`kedu init --host …`），以及干净地移除它（`kedu uninstall`）
  ——且永不删除你的记录。

## 已知限制

Kedu 刻意做得很小，而且这是早期预览。请注意：

- **仅支持源码安装。** 你用 `bash install.sh` 从本仓库安装。目前没有 `pip install kedu`、
  `brew install kedu` 或 `npm install -g kedu`。
- **确定性检索，而非语义搜索。** 搜索匹配精确关键词、标签和正则——没有 embedding、向量相似度
  或相关性排序。相关性由模型在 Kedu 返回候选之后判断。
- **仅有意捕获。** 后台不会悄悄记录。由你（或 agent，在你的指示下）决定记什么；Kedu 不会自动
  摄取对话、提示词或工具调用。
- **仅支持 macOS 和 Linux。** 不支持也未测试 Windows。
- **开发者预览。** 记录格式、CLI 接口和 host 接入方式在版本间仍可能变化；预期会有粗糙之处，
  欢迎提 issue。

## 从源码安装

> 目前仅支持源码安装。没有 `npm install -g kedu`、`brew install kedu` 或 `pip install kedu`。

```bash
git clone https://github.com/jasonshrepo/kedu.git
cd kedu

# 安装 `kedu` 命令（到 ~/.local/bin）和一份引擎副本（到 ~/.kedu/kedu）
bash install.sh

# 可选：macOS 定时维护
bash install.sh --install-launchd
```

确认 `~/.local/bin` 在你的 `PATH` 中，然后检查是否可用：

```bash
kedu --help
```

记录默认存放在 `~/.kedu` 下。用 `export KEDU_HOME=/path/to/store` 覆盖。

**为 Kedu 本身做开发：**

```bash
uv sync          # 安装依赖（Python >=3.11）
uv run pytest    # 运行测试套件
```

## 使用 Kedu

### 1. 把项目接入你的 agent（一次性设置）

在终端里自己运行，每个项目一次：

```bash
cd /path/to/project
kedu init --host claude        # 或：codex | kiro | cursor
kedu init --host claude --global   # 可选的用户级默认设置
```

这会把 `kedu` 命令接入你的 agent。从此你通过 agent 工作——不必手动敲原始 CLI。

### 2. 日常中，你与 agent 对话

Kedu 给你两个明确的 skill：

```text
/kedu-log                       保存本次会话的一条记录
/kedu-log <要记录的内容>          记录你想保留的某个具体内容
/kedu-search <查询>              查找历史记录
/kedu-search 还有哪些待办         把未完成的下一步汇总成清单
```

具体怎么触发取决于 host：

| Host | 如何调用 Kedu |
|---|---|
| **Claude Code**（CLI 和桌面端） | `/kedu-log`、`/kedu-search`——或直接用自然语言提问；skill 描述会触发自动发现 |
| **Kiro**（CLI 和 IDE） | `/kedu-log`、`/kedu-search` 斜杠命令，由对应的 skill 支撑。在 **IDE** 里你也可以直接用自然语言——“在 Kedu 里搜……”、“保存一条 Kedu 记录”——skill 会接住。 |
| **Cursor**（CLI；IDE 未验证） | 用自然语言提问，由 `.cursor/rules/kedu.mdc` 规则引导 |
| **Codex**（CLI 和桌面端） | `$kedu-log`、`$kedu-search`——或自然语言 |

你是编辑，agent 是记录员。当你让它记录时，agent 把会话（或你指向的内容）整理成一条结构化记录
并保存——内容由你决定。下次会话开始时，agent 读回项目概览和相关记录，于是它已经了解历史。你始终
只和 agent 对话；由 agent 去调用 `kedu` CLI。

### 直接使用 CLI（用于脚本，或查看 agent 实际运行了什么）

agent 最终调用的是 `kedu` CLI，你也可以——用于自动化或直接查看存储：

```bash
# 保存一条记录（agent 会构造 JSON；你也可以自己写或通过 stdin 传入）
kedu log --source manual --agent claude --project my-project --body record.json

# 查找记录
kedu search --scope current_project --query "auth cookie"
kedu search --scope all --tags security --since 2026-01-01
kedu show '<session-id>:1'
kedu projects                                     # 列出已知项目 slug

# 维护、脱敏与移除（uninstall 永不删除记录）
kedu maintain --dry-run
kedu redact --value "secret-value" --reason "leaked in session"
kedu migrate --dry-run                            # 预览项目名规范化（一次性升级步骤）

# 移除接入——记录始终被保留
kedu uninstall --dry-run                          # 预览所有将被移除的内容
kedu uninstall --hosts kiro                        # 只移除某一个 host（claude|kiro|codex|cursor）
kedu uninstall --hosts kiro,cursor --project-only  # 一个或多个 host，仅项目内文件
kedu uninstall --no-scan-projects                  # 只清理当前项目
kedu uninstall --user-only                         # 只清理用户级安装 + 全局 host 接入
```

默认情况下，`uninstall` 会清理常见项目根目录下所有发现的、启用了 Kedu 的项目（用
`--no-scan-projects` 限制为仅当前项目）。它按 **host**（`--hosts all` 或逗号列表）和**位置**
（`--project-only`、`--user-only`，或两者都不给时同时清理）来划定范围，并会移除运行时锁文件
`~/.kedu/.kedu.lock`。你的 `long` 和 `short` 记录永不被删除——只移除接入文件。

即使 agent 从子目录运行 `kedu log`，记录也会锚定到你的项目根——其解析方式见
[方案架构](#方案架构)。

## 设计原则

- **记录层，而非记忆**——Kedu 捕获发生了什么、谁做的、证据和交接，让工作可审计、可验证、可恢复
  ——而不只是“被记住”。
- **本地优先**——记录存在你的仓库和 `~/.kedu` 里，而非厂商服务。
- **由你决定记什么**——agent 是你的书记员；捕获是有意的，绝非后台静默记忆。
- **捕获之后无损**——agent 一旦写下记录，Kedu 就原样保留；绝不重新摘要、压缩或淘汰。
- **可见、可信的记录**——你和 agent 写下、可编辑的明确笔记，而非看不见的厂商记忆。
- **先确定性检索，再模型推理**——用精确过滤找出候选；由模型判断相关性。
- **可检视的文件，而非黑箱回忆**——纯 JSON 和 Markdown，你可以读、可以 diff、可以脱敏。
- **开发者自有的历史，而非平台掌控的记忆**——你的文件、你的存储、你的掌控。

---

## 方案架构

这一节是技术深入。上面的内容已经足够使用 Kedu；如果你想了解它如何工作或想扩展它，再往下读。

### 存储分层

每次 `log` 都会把记录写入一个热层和一个持久层，再由 `kedu maintain` 老化进归档层。读取时合并
三层并按 `id` 去重。

| 层 | 位置 | 保留 |
|---|---|---|
| **short（热层）** | `<project>/.kedu/short.jsonl` | 14 天滚动窗口，项目内 |
| **long（持久层）** | `~/.kedu/long/<project>.jsonl` | 全部记录，共享存储 |
| **archive（归档）** | `~/.kedu/archive/project=<name>/month=<YYYY-MM>/entries.parquet` | 老化记录，DuckDB Parquet |

一次项目内 init 会创建：

```text
<project>/.kedu/
├── short.jsonl     # 热层：14 天滚动窗口
└── config.json     # init 标记 + 规范项目 slug

~/.kedu/
├── long/<project>.jsonl                                   # 持久层：全部记录
├── archive/project=<name>/month=<YYYY-MM>/entries.parquet # 老化记录（DuckDB Parquet）
└── redaction_log.jsonl
```

`kedu maintain` 滚动 14 天热窗口，并把超过约 92 天的持久记录（若 long 文件超过 50 MB，则在
31 天时强制）通过 DuckDB 归档进 Parquet。

### 记录 schema

每条记录是一个 JSON 对象（schema 版本 2）：

```json
{
  "schema_version": 2,
  "id": "<session-uuid>:<seq>",
  "ts": "2026-06-03T00:28:54+10:00",
  "project": "my-project",
  "agent": "claude",
  "source": "manual",
  "title": "Fixed project-root resolution for non-git repos",
  "tags": ["bugfix", "paths"],
  "search_terms": ["project_root", "KEDU_PROJECT_ROOT"],
  "next_steps": ["sync to release", "run smoke matrix"],
  "redactions": [],
  "body_md": "Full human-readable narrative of what happened..."
}
```

合法的 `source` 值为 `manual` 和 `agent`。`id` 形如 `{session-uuid}:{seq}`，其中 session
UUID 取自第一个被设置的 `KEDU_SESSION_ID` / `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` /
`KIRO_SESSION_ID`，`seq` 在每个 session 内递增。

### 确定性检索

`kedu search` 加载所请求范围的所有分层，应用结构化过滤（source、agent、tags、时间范围），再在
`title + body_md + tags + search_terms + next_steps` 上做精确关键词或正则扫描。关键词匹配按
词项 OR。结果按时间戳排序，最新在前。没有 embedding 模型，也没有相关性打分——搜索找出候选，由
模型决定什么重要。

### 项目根解析

`kedu log` 按以下优先级解析项目根：

1. `KEDU_PROJECT_ROOT` 环境变量。
2. 最近的、包含 `.kedu/config.json` init 标记的祖先目录（该标记只由 `kedu init` 写入，因此
   子目录里散落的 `.kedu/` 数据目录无法劫持解析）。
3. git 仓库根（`git rev-parse --show-toplevel`）。
4. 当前工作目录，作为最后兜底。

项目 slug 从 init 标记中读取，因此即使 agent 从子目录运行 `kedu log`，记录也始终锚定到正确的
项目，并且 slug 在目录改名后保持稳定。项目名在所有入口（log、search、存储文件名）都被规范化为
唯一的**小写** slug，因此 `MyProject` 和 `myproject` 是同一个项目，大小写笔误不会再分叉出一份
检索不到的历史。如果以上都无法确定根目录，且没有给出 `--project`，`kedu log` 会中止，而不是
创建一个散落的身份。

### 脱敏

脱敏在写入时、记录持久化之前运行：先是来自可配置规则集的正则规则，再是 Shannon 熵检测以捕获
高熵 token（如密钥），并有一个白名单来放过已知安全的值。`kedu redact --value …` 执行事后脱敏，
重写每个 JSONL 和 Parquet 分层以替换某个字面值，并向 `~/.kedu/redaction_log.jsonl` 追加一条
审计事件。

> **脱敏是尽力而为的。** 正则规则和熵检测能捕获常见的凭据、密钥，以及可被正则识别的 PII（邮箱、
> 电话、API key、SSN 等），但它们**不是**保证。它们会漏掉自由格式或含糊的个人数据——尤其是姓名、
> 住址和依赖上下文的标识符。第一道防线是一开始就不要把密钥或 PII 写进记录。
>
> 如果你需要严格的 PII 检测，可以在记录之前作为预处理步骤选用外部方案：
>
> - **Microsoft Presidio**——在本地运行；文本留在你的机器上，保持 Kedu 的本地优先保证。
> - **云端 DLP/PII API**（AWS、Google、Azure）——能力更强，但它们会把你的记录文本**发送到本机
>   之外**的第三方服务。这与 Kedu 的本地优先承诺直接冲突；只有在你的威胁模型能接受这一权衡时才
>   使用。
>
> Kedu 不捆绑 Presidio 或任何云 SDK——以上只是文档建议，不是依赖。

### Host 接入

`kedu init --host <host>` 把 Kedu 接入一个项目（或用户全局位置），各 host 如下：Claude、Codex
和 Kiro 各自获得两个 skill——`kedu-log` 和 `kedu-search`——位于各自的 skills 目录
（`.claude/skills/`、`.agents/skills/`、`.kiro/skills/`）；Kiro 还会在 `.kiro/` 下获得一个
CLI agent 配置。Cursor 获得 `.cursor/rules/` 下的单个规则（Cursor CLI 已验证；Cursor IDE
未验证）。这些 skill 只告诉 agent 如何调用 `kedu` CLI——记录始终由 CLI 写入上面的分层，绝不由
skill 或规则本身写入。

## 许可证

基于 [Apache License 2.0](LICENSE) 授权。Copyright 2026 Jason Shen。
