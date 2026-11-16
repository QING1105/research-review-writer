# A0 引用身份与 A1 论断支持度

核对原稿中的参考文献、正文引用及其与论断的对应关系，并保存作者确认的处理决定。此流程在现有 v3 中文/英文写作之前运行，保留作者意图、确认、两通道范例和独立审阅。

## A0：保存原稿后，先核查文献

`run_writing.py prepare` 现在接收 Markdown 或 DOCX，保留 reference_source 原件，分离正文与参考文献表。DOCX 的上标与文献管理器字段保留在导入记录；紧邻元素符号的核素上标按科学记号处理。GB/T、Vancouver、APA 解析采用明确模式；未解析字段保留原文并标记。

```powershell
python research-review-writer/scripts/verify_references.py --run <run>
python research-review-writer/scripts/validate_references.py --run <run> --begin
```

独立审计已有文件也可使用 `parse_references.py --input <docx-or-md> --run <audit-directory>`。离线测试使用 verify_references.py --offline。

查询顺序为 DOI/Crossref、PMID/PubMed、期刊坐标 ecitmatch、题名检索，再用 OpenAlex 提供补充候选。PubMed 提供摘要、期刊标准缩写和撤稿状态；失败原因逐请求保存。Crossref 返回的期刊全名与原文缩写在缺少 NLM 别名时保持为待核对差异。缓存按请求 URL 哈希保存至 `.runtime/ref-cache/`，保留请求时间、原响应及 HTTP 状态。默认联系邮箱与 API key 为空。

先读 `author_queries_refs.md`。pending、unverified_offline、无编号且对应未确认、撤稿未决定会阻止生成 ledger_seed/planning_inputs。个别条目的作者豁免需记录原话和理由；报告仍展示其核查状态。metadata_mismatch/ambiguous/not_found/needs_manual 与点名问题集中列出。只有 validate_references.py 通过，才将本次 A0 状态记为通过。

### 作者决定

`ingest_ref_decisions.py --run <run> --input <decisions.json>`：

```json
{"author_message":"作者的实际决定","decisions":[{"ref_key":"REF007","decision":"accept_correction","corrections":{"pages":"742-762"}}],"waivers":[]}
```

decision 支持 accept_correction、keep_as_is、remove。新增/替换文献或改写科学论断时保存作者认可的新原稿，建立关联的新 run；原稿持续保留。更正记录在 reference_decisions 中，原条目与数据库更正字段同时展示。校验从原始响应重建候选，再核对 matched 和 corrections，确保更正值来自返回记录。

正文无编号时输出 proposed_mapping.md/json，按题名词项与段落交集给最多三段候选。作者确定后回读：

```json
{"origin":"author_confirmed","author_message":"作者的实际确认","pairs":[{"ref_key":"REF007","start":0,"end":12,"quote":"该位置逐字原文"}]}
```

用 `ingest_mapping.py --run <run> --input <mapping.json>` 导入。字符范围是 reference_body.md 的 Python Unicode 偏移，落在一个源句内。作者选择保持无文内引用时填写 origin=none_by_author、pairs=[]；下游记录此选择，claim 引用为空。weak_match 保留为候选，作者确认后才成为附着关系。

对未解析的文献管理器专用字段，保留原字段并人工解析稳定身份；Zotero CSL 字段中的 DOI/PMID 可按完全匹配题名优先导入。Word 字段回写沿用后续文档导出适配。

## A1：先有原子论断，再核对支持度

A0 通过后，按既有模板生成 fact_ledger.json；references 来自已核验 seed，保留 audit_status、retracted、source_ids。然后：

```powershell
python research-review-writer/scripts/check_support.py --run <run> --ledger <run>/fact_ledger.json
```

选择带引用的定量 finding/background，再选 established/reported 与作者指定条目；上限默认 80 条 claim。超额项记 not_checked，身份不清或无摘要项记 not_checkable。摘要来自保留的数据库返回；有 PMCID 时先查 PMC OA 记录，通过后按关键词取最多三段完整正文，保存 OA 与全文响应。

对每份 support/*_input.json 启动独立支持度审阅子代理，只给该输入包。记录实际 context_id、model、input_sha256。返回对应 *_result.json：

```json
{"claim_id":"C001","ref_key":"REF007","input_sha256":"实际输入哈希","context_id":"实际独立调用ID","model":"实际模型或可见宿主","isolation":"independent_context","support":"partial","scope_diff":["endpoint"],"evidence":"输入材料中的逐字原句","note":"具体不符之处"}
```

support 使用 supports/partial/contradicts/undeterminable。scope_diff 使用 species_or_model/population/endpoint/direction/entity/magnitude/design。摘要缺乏依据时填 undeterminable；该情况 evidence 可为空，其余结论提供逐字证据。

contradicts 项先给作者：保留原论断时在结果中加入 `author_decision: {action: keep_as_is, author_message: 实际答复}`；改写或删除时以认可的新源文重新建立台账与核查。partial/undeterminable 写入 author_queries_support.md。继续运行 `check_support.py --run <run> --validate`，再调用原来的 logic_flow.py plan。

规划入口回读支持度记录并写入 claims.support/evidence_unverified；后续写作再次核对审计和台账版本。原文论断的强度以作者内容为准，支持度问题单列供作者决定。最终 evidence_unverified.md 在运行目录保存全部引用仍待核实的论断、抽查未覆盖项，以及作者选择正文无引用的情况。作者用修改说明按[交付规则](delivery-notes.md)只给引用结论；实际待解决的问题注明位置、文献编号和所需处理。用户索要详细依据时再提供核查记录。

## 验证与来源

第19章离线基准：33条参考文献、25个不同点名、26次出现；16个不同 orphan、Liu 为 weak_match、Riesco-Eizaguirre 为 ambiguous；第7/24条页码异常、第11条作者异常、24条未引用。联网结果按本次实际返回记录保存，预期值只作为回归比较。

官方接口说明：[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)、[NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/)、[OpenAlex authentication](https://help.openalex.org/api/authentication/)。
