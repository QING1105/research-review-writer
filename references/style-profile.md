# 当前库与范例选择

当前默认运行使用 `logic_flow.py` 的 language/paragraphs 双通道选择格式，见 SKILL.md。下文 units/selection 格式用于保留的 v1 运行。两条路径共用本节的语料位置、领域顺序和语言匹配原则。

配置模板：`assets/project-template.yaml`；本机设置：`project.local.json`。语料位置由 `corpus_root` 和 `annotation_version` 确定，接入步骤见 [corpus-setup.md](corpus-setup.md)。`chunks.jsonl`保存完整原段，`argumentation.jsonl`保存表达任务，`language_realization.jsonl`保存具体语言解释及关注片段。源记录、页码、全文和所有候选保存在磁盘；每步按需读取对应运行文件。

领域：D01活组织诊断；D02患者来源类器官；D03类器官芯片；D04时空分子病理；D05病理质量控制；D06时空溯源；D07功能精准肿瘤学。先依据用户主题选领域，再选章节和表达任务。一个段落可跨领域，使用逗号分隔领域ID。

原稿分析可在`prepare --plan`中给出。单个短段落也可直接通过domain、section、query和roles传入。query同时包含中文对象、表达任务与准确的英文术语。roles来自已有标注：运行索引后可从候选roles读取；常用DEF、VALUE、LIMIT、COMPARE、FIND、SCOPE等应以库内实际值为准。长稿的plan按P001-U01等单元ID分别提供domains、section、query、roles和existing_relations；单元ID由按空行分段后编号产生。

读取当前单元的`candidates_view.json`，对照原稿选择适合的原句。选择重点：研究对象、表达任务、原稿已有关系、具体语法和搭配。识别哪些范例共享同一种结构，优先提供互补表达。为每条选择写明“原稿哪项表达可以借鉴原句哪种结构”，而不是泛称语言流畅。

保存selection.json格式：

```json
{
  "model_id": null,
  "units": {
    "P001-U01": [
      {"style_id": "从候选中复制真实ID", "applies_to": "P001-U01", "reason": "原稿中的具体表达任务与原句的具体句法对应关系"}
    ]
  }
}
```

实际模型ID可获得时填写；否则保留null并在运行记录中使用current_skill_host。脚本检查候选成员、原句真实性、去重和长度。词面检索未命中时，检索记录标为metadata_only_no_lexical_hit；此时认真对照候选，或用更准确的query重新准备任务。领域覆盖不足时向用户说明需要的范围选择。

索引中的family是领域、章节、原有句子角色和词面结构提示的分组，用于去重与检索。具体语言解释来自已有逐句标注。每条材料继续保留原审核状态。

## v3 双通道选择

先领域、对象和章节，再匹配作者的关系要求。语言初选沿用BM25，段落初选沿用粗类与词项交集；宿主阅读有界原文候选后进行语义选择。候选关系不合适时调整query重新检索并记录理由，输入预算保持固定。

selection.json格式：
```json
{"language":[{"id":"真实style_id","reason":"原稿含义与具体句法或搭配的对应"}],"paragraphs":[{"id":"真实chunk_id","reason":"推进对应点","relation_fit":"matched","source_relation":"范例具体推进","target_relation":"当前段已有关系","adaptation":"实际借鉴的部分","applies_to_claims":["C001"]}]}
```

relation_fit为matched或partial，partial在adaptation写明边界。目标关系与required_relations及主旨一致。仅搭配适合的原句进入language通道。完整来源和候选留磁盘，写作读取选中原文、标注和适配理由；程序核对来源、领域、预算，语义适配由选择模型和独立风格审阅判断。
