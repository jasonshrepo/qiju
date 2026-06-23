<div align="center">
  <img src="assets/logo.svg" alt="QiJu" width="440">
</div>

# QiJu · 起居

[English](README.md) | **中文**

**本地优先、无损的 AI 编程 agent 会话记录层。**

*QiJu(起居)，读作 “CHEE-joo”，得名于中国古代的起居郎——专门记录皇帝言行政事的史官，把真实发生过的事如实记下，留给后人。*

QiJu 把你的开发会话历史以你自己拥有的纯文本文件形式保存在项目里。任何 agent——Claude
Code、Codex、Kiro、Cursor，或将来出现的任何工具——都能从上一个 agent 停下的地方继续，而不必
依赖锁死在某个工具内部的记忆。

**QiJu 不是记忆，而是一个记录层。** 它记录*发生了什么、谁做的、证据在哪里、下一步该做什么*，
让 agent 的工作可审计、可交接，而不是被困在不透明、被厂商掌控的记忆里。普通的“记忆”回答的是
*模型记得什么*；QiJu 回答的是*我们为什么知道这件事、证据在哪里、是谁产生的、是否经过验证、由谁
接着做下去。*

> QiJu 是 agent 世界里的书记员。它不保存世界本身——它记录 agent 做过什么、证据在哪里、结果
> 是否可信、下一步交给谁。

<p>
  <a href="https://github.com/jasonshrepo/qiju/actions/workflows/ci.yml"><img src="https://github.com/jasonshrepo/qiju/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-17313C.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-216C83.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-475A60.svg" alt="Platform: macOS | Linux">
  <img src="https://img.shields.io/badge/status-developer%20preview-C8553D.svg" alt="Status: developer preview">
</p>

---

## 目录

- [五分钟上手](#五分钟上手)
- [名字的由来：QiJu(起居)](#名字的由来qiju起居)
- [为什么选择 QiJu](#为什么选择-qiju)
- [核心理念](#核心理念)
- [QiJu 做什么](#qiju-做什么)
- [QiJu 不是什么](#qiju-不是什么)
- [QiJu 与会话分享工具的区别](#qiju-与会话分享工具的区别)
- [当前状态](#当前状态)
- [已知限制](#已知限制)
- [安装](#安装)
- [使用 QiJu](#使用-qiju)
- [设计原则](#设计原则)
- [方案架构](#方案架构)
- [许可证](#许可证)

## 名字的由来：QiJu(起居)

QiJu(起居)，读作 *CHEE-joo*，得名于中国古代的**起居郎**——专门负责记录皇帝言行、政务与
日常起居的史官。他们日复一日地编写《起居注》，这份第一手记录，正是后来史官修撰实录与国史时所
依凭的原始材料。起居郎不替皇帝治国，也不替皇帝决断；他们只做一件事——如实、可信地记录，好让后
来的人知道究竟发生了什么、又为什么如此。

这正是本项目要做的事。把“皇帝”换成“agent”，职责完全对应：

| 起居郎 | QiJu(起居) |
| --- | --- |
| 记录皇帝的言行举止 | 记录 agent 会话中的决定与步骤 |
| 不替皇帝决策 | 不替 agent 执行 |
| 为史册保存证据 | 保存可验证的会话记录 |
| 为后人修史提供材料 | 为下一个 agent 接力上下文 |
| 形成正式档案 | 用你自己拥有的 JSONL / Markdown / Parquet 保存 |
| 有意识地选择该记什么 | 有意捕获——绝不在后台静默记忆 |

> The agent does the work. QiJu keeps the record.（agent 负责做事，QiJu 负责留下记录。）

## 五分钟上手

完整流程——安装、接入 agent、保存一条记录，再让*下一个* agent 读回来：

```bash
# 1. 安装
uv tool install qiju         # 推荐方式
# pipx install qiju          # 备选方式
# pip install qiju           # 备选方式（在已激活的 venv 中使用）

# 2. 接入一个真实项目（选择你的 host：claude | codex | kiro | cursor）
cd /path/to/your/project
qiju init --host claude
```

然后，**在 agent 里**记一笔并交接：

```text
/qiju-log    我们决定了什么、接下来该做什么
```

之后在同一项目里打开*另一个* agent，让它从你离开的地方接着做：

```text
/qiju-search    上一个决定
```

就这样——记录是 `.qiju/` 和 `~/.qiju` 里的纯文本文件，任何 agent 都能读取。项目里的 `.qiju/`
是开发者自有、跨 agent 的会话记忆——它跟着仓库走，而不是跟着某个厂商走。每个 host 的具体调用
方式见 [使用 QiJu](#使用-qiju)，安装细节见 [安装](#安装)。

## 为什么选择 QiJu

要让一个 AI 编程 agent 在真实项目上真正好用，是要花功夫的。你给它讲清楚架构、各种决策、踩过的
坑、哪些还没做完。然后会话一结束——这些理解全蒸发了。下次又得从头来。

今天，这些来之不易的上下文被困住了：

- **随线程消亡。** 关掉对话或撞上上下文上限，共享的理解就没了。
- **无法在工具间流动。** 从 Claude Code 换到 Cursor——或交接给队友——新 agent 对你的项目
  一无所知。
- **被厂商锁定。** 平台“记忆”存在别人的服务器上。你读不到、改不了、也带不走。
- **被摘要抹掉。** 长会话被压缩成有损的概述，而你真正需要的细节往往最先被丢弃。

QiJu 的解决办法，是把项目历史放回它该在的地方：**在你的项目里，作为你拥有的纯文本文件。**
下一个 agent 读到的是同一份“发生了什么”的书面记录——不是猜测，也不是厂商的黑箱。

## 核心理念

把你的 agent 当作书记员。在一次会话结束时——或任何重要的时刻——你让它写下你做了什么、想记住
什么。这条笔记成为项目里的一条记录。下次打开项目时，agent 先读这些记录，于是它已经了解历史，
能从你离开的地方接着做。QiJu 像一个称职的书记员，只记录重要的时刻——做了什么决定、证据在哪里、
下一步是什么——而不是数据本身。

QiJu 最初只是一个一行的 `/log` skill：它把会话摘要追加到一个 `history.md` 文件里（一份在项目
内、一份全局），每次会话开始时读回。这个办法有效——直到历史大到每次都重读不现实。QiJu 是同一个
想法，但做了结构化以便扩展：用许多小记录代替一个不断膨胀的文件，开头读一份简短概览，再用确定性
检索只取出相关的部分。

## QiJu 做什么

你来指挥，agent 来记录：

1. **捕获（Capture）**——你让 agent 写下你做了什么、什么值得记住。可以记录整个会话，也可以只
   指向你想保留的具体内容。
2. **保存（Preserve）**——agent 写下笔记；QiJu 原样保存，绝不像上下文窗口那样重新摘要或淘汰它。
3. **检索（Retrieve）**——需要时取回相关的历史记录。
4. **交接（Hand off）**——下一个 agent 或下一次会话先读这些记录。
5. **推理（Reason）**——模型基于你能看到、能信任的真实笔记工作，而不是它自己臆造的记忆。

后台不会悄悄记录任何东西——**由你决定记什么。** 这些记录就是你仓库和主目录里的文件：可以打开、
阅读、用 git diff 对比、编辑或脱敏其中任何内容。

## QiJu 不是什么

| QiJu 不是 | 通俗解释 |
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
| 分享 / 展示界面（如 [Claude Code Artifacts](https://code.claude.com/docs/en/artifacts)） | 它不发布一个供人查看的网页。它写下机器可读的记录，让*下一个 agent* 能继续。见 [QiJu 与会话分享工具的区别](#qiju-与会话分享工具的区别)。 |

## QiJu 与会话分享工具的区别

像 **[Claude Code Artifacts](https://code.claude.com/docs/en/artifacts)** 这类工具也“捕获
会话里发生了什么”，所以值得把区别讲清楚。它们解决的是问题的两个相反的半边：

- **Artifacts 是给人看的*展示*层。** 它把会话产出变成一个位于私有 URL 的、可交互的实时网页，
  让*队友*能看到——带批注的 diff、dashboard、并排的多个方案。
- **QiJu 是给 agent 用的*记录*层。** 它写下持久、机器可读的记录，让*下一个 agent*——在任何工具里
  ——能够验证证据并继续工作。

| | **QiJu(起居)** | **Claude Code Artifacts** |
|---|---|---|
| **目的** | 无损会话记录 → agent 交接与延续 | 把会话产出变成可分享的网页 |
| **主要消费者** | 下一个 AI agent（以及做审计的你） | 人类审阅者 / 队友 |
| **产出** | 纯 JSONL / Markdown / Parquet 记录 | 一个自包含的 HTML/Markdown 页面 |
| **存放位置** | 本地——`.qiju/` + `~/.qiju`，你拥有的文件 | Anthropic 基础设施（claude.ai），私有 URL |
| **持久性** | 永久、分层；绝不自动淘汰 | 带版本的页面，受组织保留策略约束 |
| **分享** | 随仓库（git）走；跨工具、跨厂商 | 仅限组织内；需登录 |
| **锁定** | 无——Claude Code、Codex、Kiro、Cursor | 仅 Anthropic；需 Team/Enterprise 套餐 + claude.ai 登录 |
| **检索** | 确定性的关键词/标签/正则搜索 | 无——页面是用来看的，不是用来查询的 |
| **成本** | 免费、开源（Apache-2.0） | 付费套餐，beta |

两者是**互补，而非竞争**：发布一个 Artifact 让人*现在*就能审阅工作，再运行 `/qiju-log` 让下一个
agent *之后*能接着做。Artifact 是会议幻灯片；QiJu 是起居注。一个看过即弃，一个被保存、被读回。

## 当前状态

QiJu 处于**开发者预览**阶段，现已在 PyPI 上发布。

今天已经可用、并由测试套件（`uv run pytest`）覆盖的能力：

- 捕获会话记录（`qiju temp-entry` 分配暂存文件，`qiju log` 写入记录）。
- 查找历史记录（`qiju search`、`qiju show`），以及列出已知项目（`qiju projects`）。
- 旧记录的整理与长期归档（`qiju maintain`）。
- 对既有存储做一次性的项目名规范化（`qiju migrate`）。
- 从记录中移除密钥，包括事后移除（`qiju redact`）。
- 把 QiJu 接入你选择的 agent（`qiju init --host …`），以及干净地移除它（`qiju uninstall`）
  ——且永不删除你的记录。
- 升级后刷新所有已注册项目中的 skill 文件（`qiju update`）。

## 已知限制

QiJu 刻意做得很小，而且这是早期预览。请注意：

- **确定性检索，而非语义搜索。** 搜索匹配精确关键词、标签和正则——没有 embedding、向量相似度
  或相关性排序。相关性由模型在 QiJu 返回候选之后判断。
- **仅有意捕获。** 后台不会悄悄记录。由你（或 agent，在你的指示下）决定记什么；QiJu 不会自动
  摄取对话、提示词或工具调用。
- **仅支持 macOS 和 Linux。** 不支持也未测试 Windows。
- **开发者预览。** 记录格式、CLI 接口和 host 接入方式在版本间仍可能变化；预期会有粗糙之处，
  欢迎提 issue。

## 安装

### 包管理器（推荐）

```bash
uv tool install qiju
```

备选方式：

```bash
pipx install qiju          # 如果你使用 pipx
pip install qiju           # 普通 pip，在已激活的 venv 中
uvx qiju --help            # 一次性运行，无需持久安装
```

确认可以使用：

```bash
qiju --version
qiju --help
```

记录默认存放在 `~/.qiju` 下。用 `export QIJU_HOME=/path/to/store` 覆盖。

### 源码安装（macOS launchd 或参与贡献）

包管理器安装能满足 QiJu 作为工具的所有使用场景。源码安装只在两种特定情况下需要：
运行 macOS 定时维护的 launchd 代理，或参与 QiJu 本身的开发。

```bash
git clone https://github.com/jasonshrepo/qiju.git
cd qiju

# 安装 `qiju` 命令（到 ~/.local/bin）和一份引擎副本（到 ~/.qiju/qiju）
bash install.sh

# 可选：通过 launchd 设置 macOS 定时维护
bash install.sh --install-launchd
```

确认 `~/.local/bin` 在你的 `PATH` 中。

**为 QiJu 本身做开发：**

```bash
uv sync          # 安装依赖（Python >=3.11）
uv run pytest    # 运行测试套件
```

## 使用 QiJu

### 1. 把项目接入你的 agent（一次性设置）

在终端里自己运行，每个项目一次：

```bash
cd /path/to/project
qiju init --host claude        # 或：codex | kiro | cursor
qiju init --host claude --global   # 可选的用户级默认设置
```

这会把 `qiju` 命令接入你的 agent。从此你通过 agent 工作——不必手动敲原始 CLI。

### 2. 日常中，你与 agent 对话

QiJu 给你三个明确的 skill：

```text
/qiju-log                       保存本次会话的一条记录
/qiju-log <要记录的内容>          记录你想保留的某个具体内容
/qiju-search <查询>              查找历史记录
/qiju-search 还有哪些待办         把未完成的下一步汇总成清单
/qiju-review                    复盘近期记录，提炼经验和 prompt 改进
```

具体怎么触发取决于 host：

| Host | 如何调用 QiJu |
|---|---|
| **Claude Code**（CLI 和桌面端） | `/qiju-log`、`/qiju-search`、`/qiju-review`——或直接用自然语言提问；skill 描述会触发自动发现 |
| **Kiro**（CLI 和 IDE） | `/qiju-log`、`/qiju-search`、`/qiju-review` 斜杠命令，由对应的 skill 支撑。在 **IDE** 里你也可以直接用自然语言——“在 QiJu 里搜……”、“保存一条 QiJu 记录”——skill 会接住。 |
| **Cursor**（CLI 和 IDE） | 从 `.cursor/skills/` 调用 `/qiju-log`、`/qiju-search`、`/qiju-review`，或直接用自然语言提问 |
| **Codex**（CLI 和桌面端） | `$qiju-log`、`$qiju-search`、`$qiju-review`——或自然语言 |

你是编辑，agent 是记录员。当你让它记录时，agent 把会话（或你指向的内容）整理成一条结构化记录
并保存——内容由你决定。下次会话开始时，agent 读回项目概览和相关记录，于是它已经了解历史。你始终
只和 agent 对话；由 agent 去调用 `qiju` CLI。

### 直接使用 CLI（用于脚本，或查看 agent 实际运行了什么）

agent 最终调用的是 `qiju` CLI，你也可以——用于自动化或直接查看存储：

```bash
# 保存一条记录——分配暂存文件，写入 JSON，再写入存储
qiju temp-entry --agent claude                                # 返回 .qiju/tmp/ 下的路径
qiju log --source manual --agent claude --project my-project --body <path> --cleanup

# 查找记录——两阶段：search 列出候选的 <uuid>:N id，show 再水合其中一条
qiju search --scope current_project --query "auth cookie"
qiju search --scope all --tags security --since 2026-01-01
qiju show '<session-id>:1'                         # id 必须与 search 打印的完全一致（':N' 后缀必填）
qiju projects                                     # 列出已知项目 slug

# 维护、脱敏与移除（uninstall 永不删除记录）
qiju maintain --dry-run
qiju redact --value "secret-value" --reason "leaked in session"
qiju migrate --dry-run                            # 预览项目名规范化（一次性升级步骤）

# 升级后刷新 skill 文件
uv tool upgrade qiju              # 更新 CLI
qiju update                       # 刷新所有已注册项目中的 SKILL.md
qiju update --dry-run             # 预览将要变更的内容
qiju update --host claude         # 只刷新 claude 的 skill
qiju update --scan-projects       # 首次迁移：扫描并填充注册表

# 移除接入——记录始终被保留
qiju uninstall --dry-run                          # 预览所有将被移除的内容
qiju uninstall --hosts kiro                        # 只移除某一个 host（claude|kiro|codex|cursor）
qiju uninstall --hosts kiro,cursor --project-only  # 一个或多个 host，仅项目内文件
qiju uninstall --no-scan-projects                  # 只清理当前项目
qiju uninstall --user-only                         # 只清理用户级安装 + 全局 host 接入
```

`qiju update` 刷新每个在 `qiju init` 时注册的项目中的 `SKILL.md` 文件（注册表为
`~/.qiju/registry.d/` 目录下每个项目一个文件）。若已有安装但尚无注册表，运行一次
`qiju update --scan-projects` 扫描并填充——之后直接运行 `qiju update` 即可快速完成更新。早期的
单文件 `~/.qiju/project-register.json` 会在首次使用时自动迁移到 `registry.d/`（旧文件重命名为 `.migrated`）。

默认情况下，`uninstall` 会清理常见项目根目录下所有发现的、启用了 QiJu 的项目（用
`--no-scan-projects` 限制为仅当前项目）。它按 **host**（`--hosts all` 或逗号列表）和**位置**
（`--project-only`、`--user-only`，或两者都不给时同时清理）来划定范围，并会移除运行时锁文件
`~/.qiju/.qiju.lock`。你的 `long` 和 `short` 记录永不被删除——只移除接入文件。

即使 agent 从子目录运行 `qiju log`，记录也会锚定到你的项目根——其解析方式见
[方案架构](#方案架构)。

## 设计原则

- **记录层，而非记忆**——QiJu 捕获发生了什么、谁做的、证据和交接，让工作可审计、可验证、可恢复
  ——而不只是“被记住”。
- **本地优先**——记录存在你的仓库和 `~/.qiju` 里，而非厂商服务。
- **由你决定记什么**——agent 是你的书记员；捕获是有意的，绝非后台静默记忆。
- **捕获之后无损**——agent 一旦写下记录，QiJu 就原样保留；绝不重新摘要、压缩或淘汰。
- **可见、可信的记录**——你和 agent 写下、可编辑的明确笔记，而非看不见的厂商记忆。
- **先确定性检索，再模型推理**——用精确过滤找出候选；由模型判断相关性。
- **可检视的文件，而非黑箱回忆**——纯 JSON 和 Markdown，你可以读、可以 diff、可以脱敏。
- **开发者自有的历史，而非平台掌控的记忆**——你的文件、你的存储、你的掌控。

---

## 方案架构

这一节是技术深入。上面的内容已经足够使用 QiJu；如果你想了解它如何工作或想扩展它，再往下读。

### 存储分层

每次 `log` 都会把记录写入一个热层和一个持久层，再由 `qiju maintain` 老化进归档层。读取时合并
三层并按 `id` 去重。

| 层 | 位置 | 保留 |
|---|---|---|
| **short（热层）** | `<project>/.qiju/short.jsonl` | 14 天滚动窗口，项目内 |
| **long（持久层）** | `~/.qiju/long/<project>.jsonl` | 全部记录，共享存储 |
| **archive（归档）** | `~/.qiju/archive/project=<name>/month=<YYYY-MM>/entries.parquet` | 老化记录，DuckDB Parquet |

一次项目内 init 会创建：

```text
<project>/.qiju/
├── short.jsonl     # 热层：14 天滚动窗口
└── config.json     # init 标记 + 规范项目 slug

~/.qiju/
├── long/<project>.jsonl                                   # 持久层：全部记录
├── archive/project=<name>/month=<YYYY-MM>/entries.parquet # 老化记录（DuckDB Parquet）
└── redaction_log.jsonl
```

`qiju maintain` 滚动 14 天热窗口，并把超过约 92 天的持久记录（若 long 文件超过 50 MB，则在
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
  "search_terms": ["project_root", "QIJU_PROJECT_ROOT"],
  "next_steps": ["sync to release", "run smoke matrix"],
  "redactions": [],
  "body_md": "Full human-readable narrative of what happened..."
}
```

合法的 `source` 值为 `manual` 和 `agent`。`id` 形如 `{session-uuid}:{seq}`，其中 session
UUID 取自第一个被设置的 `QIJU_SESSION_ID` / `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` /
`KIRO_SESSION_ID`，`seq` 在每个 session 内递增。

### 确定性检索

检索分两阶段。**第一阶段——`qiju search`** 负责找出候选：加载所请求范围的所有分层，应用结构化
过滤（source、agent、tags、时间范围），再在 `title + body_md + tags + search_terms +
next_steps` 上做精确关键词或正则扫描。关键词匹配按词项 OR。结果按时间戳排序，最新在前，并以
`{session-uuid}:{seq}` 形式的 id 打印。没有 embedding 模型，也没有相关性打分——搜索找出候选，
由模型决定什么重要。

**第二阶段——`qiju show '<uuid>:N'`** 按精确 id 水合出某条记录的完整正文。传入的 id 必须与
`qiju search` 打印的完全一致，包含 `:N` 后缀；只传裸 UUID 会返回 `record not found`，并提示补上
后缀（裸 UUID 表示的是整个 session，而非单条记录）。

### 项目根解析

`qiju log` 按以下优先级解析项目根：

1. `QIJU_PROJECT_ROOT` 环境变量。
2. 最近的、包含 `.qiju/config.json` init 标记的祖先目录（该标记只由 `qiju init` 写入，因此
   子目录里散落的 `.qiju/` 数据目录无法劫持解析）。
3. git 仓库根（`git rev-parse --show-toplevel`）。
4. 当前工作目录，作为最后兜底。

项目 slug 从 init 标记中读取，因此即使 agent 从子目录运行 `qiju log`，记录也始终锚定到正确的
项目，并且 slug 在目录改名后保持稳定。项目名在所有入口（log、search、存储文件名）都被规范化为
唯一的**小写** slug，因此 `MyProject` 和 `myproject` 是同一个项目，大小写笔误不会再分叉出一份
检索不到的历史。如果以上都无法确定根目录，且没有给出 `--project`，`qiju log` 会中止，而不是
创建一个散落的身份。

### 脱敏

脱敏在写入时、记录持久化之前运行：先是来自可配置规则集的正则规则，再是 Shannon 熵检测以捕获
高熵 token（如密钥），并有一个白名单来放过已知安全的值。`qiju redact --value …` 执行事后脱敏，
重写每个 JSONL 和 Parquet 分层以替换某个字面值，并向 `~/.qiju/redaction_log.jsonl` 追加一条
审计事件。

> **脱敏是尽力而为的。** 正则规则和熵检测能捕获常见的凭据、密钥，以及可被正则识别的 PII（邮箱、
> 电话、API key、SSN 等），但它们**不是**保证。它们会漏掉自由格式或含糊的个人数据——尤其是姓名、
> 住址和依赖上下文的标识符。第一道防线是一开始就不要把密钥或 PII 写进记录。
>
> 如果你需要严格的 PII 检测，可以在记录之前作为预处理步骤选用外部方案：
>
> - **Microsoft Presidio**——在本地运行；文本留在你的机器上，保持 QiJu 的本地优先保证。
> - **云端 DLP/PII API**（AWS、Google、Azure）——能力更强，但它们会把你的记录文本**发送到本机
>   之外**的第三方服务。这与 QiJu 的本地优先承诺直接冲突；只有在你的威胁模型能接受这一权衡时才
>   使用。
>
> QiJu 不捆绑 Presidio 或任何云 SDK——以上只是文档建议，不是依赖。

### Host 接入

`qiju init --host <host>` 把 QiJu 接入一个项目（或用户全局位置），各 host 如下：Claude、Codex、
Kiro 和 Cursor 都会获得三个 skill——`qiju-log`、`qiju-search` 和 `qiju-review`——位于各自的
skills 目录（`.claude/skills/`、`.agents/skills/`、`.kiro/skills/`、`.cursor/skills/`）。
这些 skill 只告诉 agent 如何调用 `qiju` CLI——记录始终由 CLI 写入上面的分层，绝不由 skill
本身写入。

QiJu 只发布可跨 provider 使用的 Agent Skills 形态：`skills/<skill-name>/SKILL.md`，以及将来
确有需要时才会使用的可移植可选目录，例如 `scripts/`、`references/`、`assets/`。QiJu 不发布
provider 专属 metadata 文件。如果你想使用 provider 专属能力，可以在 `qiju init` 后手动修改
自己的本地副本：例如 Codex 用户可添加 `agents/openai.yaml` 来配置 Codex app 的 UI metadata
或调用策略；Cursor 用户可添加 `paths` 或 `disable-model-invocation` 等 Cursor 专属 frontmatter；
Kiro 用户如需要命名的 Kiro CLI agent，可自行创建 `.kiro/agents/qiju.json`；Claude 用户也可按
文档添加其支持的可选字段。
详情见各 provider 文档：[Codex](https://developers.openai.com/codex/skills)、
[Kiro](https://kiro.dev/docs/skills/)、
[Claude](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)、
[Cursor](https://cursor.com/docs/skills)。

## 许可证

基于 [Apache License 2.0](LICENSE) 授权。Copyright 2026 Jason Shen。
