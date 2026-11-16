# 事实台账与中文规划

执行模型：当前 Skill 宿主。逐段读取此任务输入，按原稿明确表达的信息拆分论断。保存 JSON，供脚本核验。保留事实忠实、逻辑与阅读顺畅、库内措辞风格三个目标；本阶段处理前两项，写作阶段同时读取库内语言范例。

## 台账

prepare生成ledger_seed.json和draft_plan.json；fact_ledger.json及logic_plan.json由宿主读取来源后创建。v3新增字段和中文成稿步骤见本文件末节。

以 `ledger_seed.json` 为底稿，将逐段抽取结果合并到 `fact_ledger.json`。保留 source_units、citation_occurrences、signals 原样。新增：

```json
{
  "claims": [{"claim_id":"C001","sids":["P001-S001"],"text_zh":"空间转录组学保留基因表达的空间背景。","type":"background","strength":"established","polarity":"positive","quantities":[],"conditions":[],"citations":[],"citation_occurrences":[],"xrefs":[],"relations":[]}],
  "uncovered": [],
  "signal_reviews": [],
  "anchors": [],
  "terms": []
}
```

按原稿顺序编号 claim。一句话包含两个独立判断时拆为两条，二者都指向原 sid。type：background/finding/interpretation/limitation/proposal/scope/definition/example；strength：established/reported/associated/suggested/possible/proposed/expected。条件、数值单位、否定范围分别记录。relations 的 to 指向其他 claim，type 使用 cause/consequence/contrast/concession/addition/example_of/condition/comparison/specification。

数字和否定词 signals 是查漏提示。逐项填 `{"signal_id":"SIG0001","claims":["C001"],"note":"70% 的分母为该研究中的活检标本；已保存在 quantities 与 conditions"}`。先理解上下文，再决定数值、名称中的数字、否定范围怎样保存。

来源台账按原位置记录引用：claim.citation_occurrences 填 CIT 编号，citations 填该位置展开的 REF 编号。一处引用支持多个 claim 时记录共享关系；两个位置引用同一篇文献时记录两个来源 CIT。原位置用于追溯，正文采用位置由下述论述取舍决定。引用归属含糊时登记 author_queries 并让作者确认。数字方括号由脚本识别；作者年份、上标、文献管理器字段需要在源文导入时转换为带原位置的 citation_occurrences，并升级解析器后使用。

标题或纯过渡可填 uncovered，注明 sid、kind（heading/transition）、reason。当前段落写作路径要求每段有 substantive claim；标题作为章节元数据单独管理。

交叉引用 anchors 格式：`{"anchor_id":"fig:1","kind":"figure","original_label":"图1","render_label_en":"Fig. 1"}`；编号来自作者提供的图表/章节清单。terms 格式：`{"zh":"空间转录组学","en":"spatial transcriptomics","abbr":"ST","defined_in":"C001"}`。

## 逻辑规划

逐段判断主旨、已有关系、读者在哪里需要背景或解释。把主旨后置、例子先行、长句、指代和术语变化作为待检查线索；根据表达目的与真实原文范例决定是否修改。

```json
{
  "level":"L0",
  "paragraphs":[{
    "new_para_id":"N001","target_source_para":"P001","source_paras":["P001"],
    "domains":["04_spatiotemporal_molecular_pathology"],"section":"introduction",
    "paragraph_type":"background_and_value","query":"spatial transcriptomics morphology validation",
    "main_point":"空间信息及其结合形态学的价值","main_point_claims":["C001"],
    "claim_order":["C001"],"link_from_previous":"开篇",
    "ops":[{"op":"KEEP","reason":"作者已确定论证顺序"}],"additions":[]
  }],
  "diagnosis":[],"author_queries":[]
}
```

L0 保留段落和 claim 顺序，可在写作时拆合句子。L1 允许段内重排、相邻段落移动、主旨句和基于已有关系的过渡；保持段落槽位与数量。L2 可拆合段、在同一章节内重排。不同章节分别建立运行；跨章节移动由作者明确指定。

操作枚举见 `logic_flow.py:OPS`。每项操作写出理由。新增主旨/过渡记录在 additions：op、text_zh、claims；ADD_TRANSITION 同时提供与台账完全相同的 relation 对象。新增中文用于明确展示概括与衔接，英文只表达其已有信息。

每条保留的 claim 在 claim_order 中有一个主要表达位置；main_point_claims 和 additions.claims 用作概括关联。完整来源台账中的其余 claim 通过 editorial_selection 记录取舍。L1/L2 执行 plan 后交付 restructured_zh.md 与具体改动，取得作者对此版本的实际确认后调用 confirm。L0 默认保留已接受的源文结构。

### 论述优先的内容与引用取舍

新建L1/L2运行默认使用`content_policy: argument_first`。先确定段落要回答的问题及其推进关系，再选择支持这一主旨的论点、解释和证据。重复信息或与当前主旨无关的例证可以删去，引用随论断处理。保留内容继续维持原有事实、数值、条件、比较对象和证据强度；核心论点、必要限定及会影响结论的反例应优先保留。独立审阅结合作者原话判断取舍是否改变了其论证。

原稿和完整`fact_ledger.json`继续归档。规划在现有`logic_plan.json`增加：

```json
{
  "editorial_selection": {
    "omitted_claims": [
      {"claim_id":"C001","reason":"该研究比较句与本段的模型身份及代表性主旨缺少关系。","effect_on_argument":"删去例证后，模型核实要求、偏差原因和临床条件仍完整衔接。"}
    ],
    "citation_merges": [
      {"occurrence_ids":["CIT0002","CIT0003"],"paragraph_id":"N001","reason":"两处引用指向同一组文献，支持的论断在同段连续展开，集中标注在后一句。"}
    ]
  }
}
```

两个数组分别按实际需要填写。`editorial_selection`仅包含`omitted_claims`和`citation_merges`；保留清单及引用去向由脚本生成到独立审计文件。`omitted_claims`中的ID从所有段落的`claim_order`移出；来源台账保留原条目。引用的全部支持论断都被移除时，脚本记录`omitted_with_claims`；仍有保留论断时，引用继续跟随这些论断。保留论断分到不同段落时，脚本按段落派生引用位置，并保存它们与原始CIT的关系。这样，共享引用的原位置可支持重新组织后的段落。

`citation_merges`用于合并同一组文献的重复标注，ID从本次派生的引用记录读取。引用可放在一句或同段连续展开的多句之后；binding.claims记录它实际支持的全部保留论断，脚本检查这些论断已在本段出现，独立审阅判断读者能否清楚识别其证据范围。分段后的引用分别跟随相应论断。不同文献的证据分别维护，来源身份保持稳定。原始编号继续由`citation_mode`控制；`keep_original`表示沿用编号，允许按取舍记录出现编号间隔。

`editorial_selection.json`和最终`citation_map.json.source_disposition`记录保留、随论断删除、拆分跟随及重复合并的去向。写作请求只装入本段选中的内容；原句同时含有删去内容时，用`source_context_exclusions`标记。fidelity读取完整台账与取舍记录，检查删去内容是否影响主旨、必要条件或关键反例；reader继续只根据正文判断逻辑和流畅度。

作者明确要求“事实或引用逐项保留”时，prepare使用`--content-policy preserve_all`。纯翻译以及从已确认中文生成英文采用L0或已确认规划。英文以该中文版本及其取舍为准。旧运行缺少content_policy时沿用其原有完整保留契约。

作者改稿：保存作者文件，使用 ingest-edits 命令生成带标签变动记录。宿主逐条判断措辞、结构、内容取舍和科学含义变化。移除偏题或重复内容时更新现有plan的editorial_selection，保留来源台账，重新生成中文并绑定作者确认；新增事实或改变科学含义时，将作者认可的新源文保存为关联run并重建台账。原run与claim记录持续保留。英文继续使用最终确认中文和该版本的取舍。

## 大文稿

抽取输入逐段保存；语义规划先看 claim ID、主旨与关系的紧凑清单，再读取受影响段落。按章节运行并保留共享术语表和 REF 身份。每次模型调用先核验实际材料预算；完整语料保留在磁盘，写作只读取当前段落的两个范例包。

## v3 作者要求和中文成稿

新运行schema/workflow为3。有效claim增加origin:source，作者明确补入输入的内容可用author_source；两者都必须指向source sid。模型新提案另存model_candidates:[{candidate_id,text,supports:[claim_id],reason,status:proposed|rejected|deferred}]。作者采纳新内容后更新关联原稿，再生成有效claim。

logic_plan增加author_requirements:[{requirement_id,text,source:request|draft,source_quote}]。source_quote逐字来自author_request.md或input.md，保留每项要求出处。作者规定段数时可加author_structure:{paragraph_count,requirement_id}；段数属于当前任务。

每项要求增加kind:content/workflow/mixed（默认content）。content用正文核对，workflow如来源记录、开发状态等用实际执行记录核对，mixed同时包含两类依据。要求分类仍按作者原话判断；workflow内容保留在后台执行，正文表达作者的科研内容。

每段增加subject_scope（对象、阶段和范围）、requirement_ids，以及required_relations:[{type,description,claims,requirement_ids}]。type为cause/necessity/consequence/condition/contrast/concession/sequence/example/comparison/addition；description说明具体关系。requirements从用户要求提取，claims指向本段事实。

v3的plan只保存规划。L1/L2继续candidates/assemble --stage zh，宿主按chinese-writing.md写N001/zh/result.json，preview合并成完整正文restructured_zh.md，句级对应另存chinese_draft.json。独立事实/作者要求核对和中文冷读完成后，交作者确认。英文输入直接包含认可中文。L0保留原文。上文的标签式预览为v2历史行为。
