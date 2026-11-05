# 文档字数统计器

Python 3.11+ 与 Git 即可运行，无第三方 Python 依赖。所有辅助文件集中在本目录；只有 GitHub 要求的工作流位于 `.github/workflows/wordcount.yml`。

## 当前统计规则

- 范围由 `config.json` 指定：根目录 `Exile.md`、`设定/`、`剧情/`。
- 只处理匹配过滤规则、已被 Git 跟踪的文件；未跟踪文件不统计。新文件要先 `git add`，在 GitHub 上则以已推送的内容为准。
- `characters` 是主展示值：按 Unicode 码点计数，排除 Python `str.isspace()` 认定的全部空白，包括空格、换行、制表符和全角空格。
- 不剥离 Markdown：标点、标题符号、链接地址、代码块、注释等全部计入；英文按字符而非单词计数。组合字符或组合 emoji 可能占多个码点，不等同于视觉上一个符号。
- 每个匹配文件计一篇，空文件也计一篇。目录汇总其全部后代文件，不会重复计算重叠统计根中的同一文件。
- UTF-8 解码，忽略可选 BOM；辅助指标 `raw_characters` 包含空白，换行统一为 LF。编码错误、不可读文件及未暂存删除的已跟踪文件会报错，不静默漏算。
- 不跟随符号链接。尚未创建的目录可以预先配置，显示为 0 字符 / 0 篇；不存在的文件根不生成文件节点。
- 全量扫描，无缓存。每个文件记录 SHA-256，预留增量缓存依据；将来缓存还必须包含统计规则版本，不能只在旧总数上加减。

## 本地预览与测试

在仓库根目录运行（Windows 可以将 `python` 换成 `py -3`）：

```powershell
python tools/wordcount/count.py
python -m unittest discover -s tools/wordcount -p 'test_*.py' -v
```

默认输出到 `tools/wordcount/output/`，已在本目录 `.gitignore` 排除：

| 文件 | 用途 |
| --- | --- |
| `badge.svg` | 可嵌入 README 的字数徽章，不依赖第三方徽章服务 |
| `tree.md` | 每一层目录的总字符数、总篇数，以及每篇文档的字符数 |
| `stats.json` | 完整递归结构树、来源提交、规则版本、逐文件哈希 |

也可以传 `--root`、`--config`、`--output` 指定仓库、配置和输出目录。默认路径以脚本位置为准，不依赖终端当前目录。

本地统计读取已跟踪文件的**工作区内容**，不是暂存区快照。范围内有未提交变动时，报告会标记 `working_tree_modified: true`，发布器拒绝发布这种预览。GitHub 工作流使用干净检出的推送版本。

测试会创建临时本地 Git 仓库及本地 bare remote，覆盖统计、过滤、目录汇总、文件增删移动、发布与防误覆盖；不会连接真实 GitHub 远端。

## 调整范围与过滤器

编辑本目录 `config.json`。`roots` 是白名单，`include` 和 `exclude` 是针对仓库相对路径的过滤规则。

```json
{
  "roots": [
    { "path": "Exile.md", "type": "file" },
    { "path": "设定", "type": "directory" },
    { "path": "剧情", "type": "directory" }
  ],
  "include": ["**/*.md"],
  "exclude": ["/设定/草稿/", "**/*.草稿.md"]
}
```

上面的排除项只是使用示例；实际默认配置没有排除项。

规则语义：

- 只统计在 `roots` 内、至少匹配一个 `include`、且不匹配任何 `exclude` 的文件。
- 路径统一使用 `/`，区分大小写，模式匹配整个仓库相对路径；可选的开头 `/` 含义不变。
- `*` 匹配当前一层路径内的任意字符；`?` 匹配一个非 `/` 字符。
- `**` 可以跨目录；`**/` 可以匹配零层目录，因此 `**/*.md` 也匹配根目录的 `Exile.md`。
- 以 `/` 结尾的过滤模式代表其全部后代，例如 `设定/草稿/`。
- 不是完整 `.gitignore` 语法：不支持 `!` 重新包含、`[]` 字符组或行内注释；JSON 不支持注释。排除始终优先，规则顺序无影响。
- 增加 `剧情/` 内的新文档并提交后，会自动纳入统计，无需先创建占位文件。

## 推送后如何自动运行

工作流 `Document word count` 在推送 `master` 后启动，也支持网页端手动运行。任务额外检查当前分支确实是仓库默认分支。

执行过程：检出推送版本 → 准备 Python 3.12 → 跑测试 → 生成三个报告 → 写 Actions 摘要并上传报告附件 → 发布到 `wordcount-stats` 分支。

`wordcount-stats` 是专用生成分支，首次成功运行会自动创建。它与正文分支历史分离，不要合并回 `master`，也不要往里面放人工维护的文件。发布器只允许三个报告文件；如果已有同名分支含其他文件，会拒绝覆盖。

发布器使用 Git 对象命令创建提交，不切换分支、不修改本地索引、不暂存正文，不使用强制推送。仅在生成文件变化时提交；重复运行同一来源提交不会制造相同结果的提交。报告记录 `source_commit`，因此即使字数不变，新来源提交通常仍会更新统计分支的溯源信息。

工作流串行发布；发布前检查来源分支是否仍指向被统计提交，过期任务跳过，避免旧结果覆盖较新结果。若极短时间内又有推送，新任务会继续更新结果。并发外部写入统计分支导致非快进时，普通 push 会失败而不是覆盖。

### 首次启用

1. 把这些工具文件、工作流和 README 改动提交并推送到 `master`。不要把 `output/` 一起提交。
2. 打开 GitHub 仓库的 **Actions → Document word count**，检查此次运行。
3. 工作流声明 `contents: write`，通过自动提供的 `GITHUB_TOKEN` 发布，无需新建 PAT、配置秘密令牌或购买域名。
4. 仓库或组织需允许 Actions 执行与写入；如遇 403，查看 **Settings → Actions → General → Workflow permissions** 及组织策略。统计分支的规则集也不能阻止机器人创建或更新它。
5. 成功后会出现 `wordcount-stats` 分支，README 中的徽章和明细链接开始生效。首次成功发布前链接会暂时不存在。
6. 需要补跑时，在 Actions 页面点击 **Run workflow** 并选择默认分支。不要选择统计分支。

若默认分支由 `master` 改名，需要同步修改工作流的 `on.push.branches`。若仓库转移或改名，需要更新主 README 中两个固定 GitHub 地址。更换统计分支名时，同步修改发布参数和 README 链接。

### 展示地址与隐私

当前 README 引用：

- 徽章：`https://raw.githubusercontent.com/PhasetransCrystal/ArkdustSSNew/wordcount-stats/badge.svg`
- 明细：`https://github.com/PhasetransCrystal/ArkdustSSNew/blob/wordcount-stats/tree.md`

无需 GitHub Pages，不依赖 Shields.io。公开徽章适用于公开仓库；私有仓库的匿名图片访问不能保证可用，不要在 URL 中放访问令牌。报告本身只含路径、计数与哈希，不含文档正文，但这些元数据也会随统计分支的可见性公开。

GitHub 的图片代理可能缓存 SVG，字数徽章不保证即时刷新。排查时先看 Actions 日志及统计分支的 `tree.md` / `stats.json`；不要仅凭旧徽章判断统计失败。

每次工作流还会留下可下载报告（保留 14 天）及任务摘要。即使最后发布步骤因权限失败，也能检查已经生成的统计内容。

## 结构树数据接口

`stats.json` 包含：

- `schema_version`：数据结构版本，当前为 1。
- `counter_version`：统计规则版本，当前为 1。
- `source_commit`、`source_mode`、`working_tree_modified`：来源与本地预览状态。
- `counting_policy`、`scope`：统计口径及生效配置。
- `totals`：`characters`、`raw_characters`、`files` 三项合计。
- `tree`：递归节点；节点均包含 `type`、`name`、仓库相对 `path` 及三项合计。
  - `directory` 节点增加 `children`，排序为目录优先、名称 Unicode 顺序。
  - `file` 节点增加 `sha256`，其 `files` 为 1；没有 `children`。

前端以后可以直接渲染树、排序和绘制目录占比，无需重新扫描正文。历史增长曲线还需要读取统计分支历史或另存历史快照，最新 JSON 本身不包含完整历史序列。
