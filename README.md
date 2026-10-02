# SubstancesArchive

每周从 Journal Android Multilingual 文档列出的主要数据源抓取快照，按来源分别保存；不合并、不清洗、不转换字段。快照路径固定，Git 历史保留前次版本，便于直接审查每周 diff。

## 来源与存档内容

| 路径 | 抓取内容 | 上游 |
|---|---|---|
| `archive/psychonautwiki/response.json` | PsychonautWiki GraphQL substance 完整字段响应 | [GraphQL API](https://api.psychonautwiki.org/) |
| `archive/tripsit/drugs.json` | 上游原始 JSON 文件 | [TripSit/drugs](https://github.com/TripSit/drugs) |
| `archive/wikidata/atc-medicines.json` | 含 ATC 码的 Wikidata 记录 SPARQL JSON 响应，按实体 URI/ATC 码排序 | [Wikidata Query Service](https://query.wikidata.org/) |
| `archive/euda/european-drug-report.html` | EUDA European Drug Report 报告落地页响应 | [EUDA report](https://www.euda.europa.eu/publications/european-drug-report_en) |
| `archive/freeodwiki/` | `药物/*.md`、许可与索引文件逐个按原始字节保存 | [FreeODwiki](https://github.com/SalviaSWC/FreeODwiki) |

API 响应按固定文件名原始字节保存，JSON 不重新序列化。PsychonautWiki 与 Wikidata 是按查询条件返回的数据，不是整站数据库导出。FreeODwiki 只存与物质目录相关的 Markdown 和许可/索引文件，不含整个仓库的图片等无关资源；新增、修改、删除的上游文件会对应显示为 Git 文件差异。

每次 Action 更新相同路径，**不会创建带日期的副本**；Git 提交历史就是快照历史。首次导入会显示整批新增，之后只显示源站变更。如果源内容、查询结果和顺序都没变，Action 不会产生归档 diff/提交。Wikidata 查询显式排序；其余源保留源站返回顺序与原始内容，不做排序或格式化，因此上游自身的顺序变化也可能出现在 diff 中。

EUDA 官方报告端点会对无会话请求返回 HTTP 403（上游文档也说明 CSV 需要浏览器会话）。遇到 403 时其他来源仍照常归档，EUDA 本周不产生快照。可在仓库 Actions secrets 配置 `EUDA_COOKIE` 提供有效会话 cookie；否则每次运行日志会明确报告 EUDA 未能获取。当前自动端点是报告落地页，不是该年度 CSV。

## 自动运行

`.github/workflows/weekly-fetch.yml` 每周一 03:17 UTC 运行，也可在 GitHub Actions 页面手动执行。Action 使用仓库 `GITHUB_TOKEN` 将有变化的快照提交回当前分支；无需额外密钥。只有 EUDA 返回 403 时，该来源跳过并给出警告，其他来源照常提交；其它来源的抓取失败会使任务失败，防止提交不完整快照。

## 本地运行

需要 Python 3.10+，无第三方依赖：

```bash
python scripts/fetch_sources.py
```

脚本对每个上游独立请求并分目录保存响应，不修改其他来源或生成合并数据。

## 来源许可

存档会保留源站的原始内容，不代表本仓库取得再分发授权。各来源许可限制不同：例如 PsychonautWiki 与 FreeODwiki 为 CC BY-SA，Wikidata 为 CC0，TripSit 仓库未声明许可证，EUDA 要求副本注明来源。使用或再分发前请查看各来源当前许可及 [上游数据来源说明](https://github.com/LoliLin/journal-android-multilingual/blob/main/docs/data-sources-and-licenses.md)。
