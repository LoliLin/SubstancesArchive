# SubstancesArchive

每周从 Journal Android Multilingual 文档列出的主要数据源抓取快照，按来源分别保存；不合并、不清洗、不转换字段。快照路径固定，Git 历史保留前次版本，便于直接审查每周 diff。

## 来源与存档内容

| 路径 | 抓取内容 | 上游 |
|---|---|---|
| `archive/psychonautwiki/<substance>.json` | PsychonautWiki GraphQL 完整字段响应拆分后的单个物质记录 | [GraphQL API](https://api.psychonautwiki.org/) |
| `archive/tripsit/<substance>.json` | TripSit 完整 drugs.json 响应拆分后的单个物质记录 | [TripSit/drugs](https://github.com/TripSit/drugs) |
| `archive/wikidata/<QID>.json` | Wikidata SPARQL 完整响应按实体合并 ATC 记录后的单个物质文件 | [Wikidata Query Service](https://query.wikidata.org/) |
| `archive/euda/european-drug-report.html` | EUDA European Drug Report 报告落地页响应 | [EUDA report](https://www.euda.europa.eu/publications/european-drug-report_en) |
| `archive/freeodwiki/` | `药物/*.md`、许可与索引文件逐个按原始字节保存 | [FreeODwiki](https://github.com/SalviaSWC/FreeODwiki) |

API 会先完整读取上游 JSON 响应，再解析并拆分为单物质文件，以 UTF-8、两空格缩进格式保存。PsychonautWiki 和 TripSit 文件名来自物质名称；Wikidata 按实体 QID 分组，同一实体的 ATC 查询记录保存在该物质文件的 `bindings` 数组中。JSON 文件只在内容变化时更新；过期的 JSON 文件会在该来源成功解析后清理。FreeODwiki 文件按原始字节保存。

每次 Action 更新相同路径，**不会创建带日期的副本**；Git 提交历史就是快照历史。首次导入会显示整批新增，之后只显示源站变更。如果源内容、查询结果和顺序都没变，Action 不会产生归档 diff/提交。Wikidata 查询显式排序；源站记录的返回顺序会保留在各个物质文件中，格式化缩进会让 JSON 以便于审查的多行形式呈现。

EUDA 官方报告端点会对无会话请求返回 HTTP 403（上游文档也说明 CSV 需要浏览器会话）。遇到 403 时其他来源仍照常归档，EUDA 本周不产生快照。可在仓库 Actions secrets 配置 `EUDA_COOKIE` 提供有效会话 cookie；否则每次运行日志会明确报告 EUDA 未能获取。当前自动端点是报告落地页，不是该年度 CSV。

## 自动运行

`.github/workflows/weekly-fetch.yml` 每周一 03:17 UTC 运行，也可在 GitHub Actions 页面手动执行。Action 使用仓库 `GITHUB_TOKEN` 将有变化的快照提交回当前分支。只有归档检测到变化时，才会检查 [journal-android-multilingual](https://github.com/LoliLin/journal-android-multilingual) 是否已有标题为 `[SubstancesArchive] 上游数据快照已更新` 的未关闭 issue；已存在时不重复创建，也不重复留言，没有时创建 issue 并附本次归档提交与运行日志链接。请在 SubstancesArchive 仓库添加 `UPSTREAM_ISSUE_TOKEN` Actions secret：使用有权在目标仓库创建 issue 的 fine-grained PAT，并授予 `journal-android-multilingual` 的 Issues read/write 权限。只有 EUDA 返回 403 时，该来源跳过并给出警告，其他来源照常提交；其它来源的抓取失败会使任务失败，防止提交不完整快照。

## 本地运行

需要 Python 3.10+，无第三方依赖：

```bash
python scripts/fetch_sources.py
```

脚本对每个上游独立请求并分目录保存响应，不修改其他来源或生成合并数据。

## 来源许可

存档会保留源站的原始内容，不代表本仓库取得再分发授权。各来源许可限制不同：例如 PsychonautWiki 与 FreeODwiki 为 CC BY-SA，Wikidata 为 CC0，TripSit 仓库未声明许可证，EUDA 要求副本注明来源。使用或再分发前请查看各来源当前许可及 [上游数据来源说明](https://github.com/LoliLin/journal-android-multilingual/blob/main/docs/data-sources-and-licenses.md)。
