# 参考库准备与运行设置

## 先准备哪些材料

选取与你的研究方向、目标章节和期刊写法相近的论文。以完整段落保存原文，并保留句子在原段中的位置。“论述怎样推进”和“英文怎样表达”分别标注，写作时分别挑选。

对于 PDF，先提取正文，核对双栏顺序、跨页段落和断词；将章节、图注、表格及参考文献分开保存。逐段检查后，再生成下面的文件。当前项目从这些整理好的文件建立索引。

建议先完成少量有代表性的段落，检查原文位置和标注是否准确，再扩大参考库。选择材料时先确定研究领域，再选择章节和段落用途。

## 四个数据文件

文件采用 UTF-8 编码和 JSONL 格式：每行是一条完整 JSON 记录。目录结构如下：

```text
你的参考库/
└── annotations/
    └── abstract-introduction-v2/
        ├── chunks.jsonl
        ├── argumentation.jsonl
        ├── language_realization.jsonl
        └── paragraph_patterns.jsonl
```

`abstract-introduction-v2` 是可配置的数据版本名。参考库也可以包含正文段落；写作时可选择不限章节，再按段落用途筛选。

| 文件 | 保存什么 | 写作时的用途 |
| --- | --- | --- |
| `chunks.jsonl` | 完整原段、论文题名与标识、领域、章节、原文位置 | 读取原文并追溯出处。 |
| `argumentation.jsonl` | 每个句子在论述中承担什么作用 | 找到解释概念、比较方法、指出问题等相近表达任务。 |
| `language_realization.jsonl` | 原句位置、语法和措辞特点、可借鉴片段 | 选择具体英文表达范例。 |
| `paragraph_patterns.jsonl` | 整段怎样展开、可以抽象出怎样的组织方式 | 参考段落推进和句间关系。 |

下面是一组**为说明格式专门编写的示例**，论文标识和位置均为示例。仓库的 [examples/corpus](../examples/corpus) 提供可直接读取的完整示例文件，用于测试配置和程序。

### 完整原段：chunks.jsonl

```json
{"chunk_id":"DEMO-C001","paper_id":"DEMO-P001","domain":"04_spatiotemporal_molecular_pathology","section_role":"introduction","text_clean":"Spatial assays preserve sample coordinates. Morphology measurements require validation.","title":"Synthetic writing example 1","doi":null,"source_location":{"kind":"synthetic_example","paragraph":1}}
```

真实数据中的 `source_location` 应保存页码、章节、段落序号及可用的原文件定位信息。`chunk_id`、`paper_id` 需要稳定且唯一，后续记录用它们连接原文。

### 句子作用：argumentation.jsonl

```json
{"sentence_id":"DEMO-C001-S01","chunk_id":"DEMO-C001","labels":{"sentence_roles":["BACKGROUND","VALUE"]}}
```

标注应具体说明句子承担的任务。常见角色包括 `DEF`（解释概念）、`VALUE`（说明用途）、`GAP`（指出缺口）、`CAUSE`（解释原因）、`COMPARE`（比较）、`FIND`（报告发现）和 `SCOPE`（交代综述范围）。同一库内统一角色含义。

### 语言表达：language_realization.jsonl

```json
{"sentence_id":"DEMO-C001-S01","chunk_id":"DEMO-C001","source_span":{"start":0,"end":43,"quote":"Spatial assays preserve sample coordinates."},"labels":{"analysis":"以技术为主语，直接说明它保留的信息；谓语 preserve 连接具体对象。","authored_focus_spans":[{"quote":"preserve sample coordinates"}]},"review":{"status":"example_only"},"selection":{"status":"selected_expression_candidate"}}
```

`start` 从 0 开始，`end` 为结束位置且自身不计入。程序按 Python 字符位置检查 `text_clean[start:end]` 与 `quote` 是否逐字相同。人工复核后，将可用句子的 `selection.status` 设为 `selected_expression_candidate`；带有 `editorial_flags` 的记录会从语言候选中排除。

### 段落推进：paragraph_patterns.jsonl

```json
{"chunk_id":"DEMO-C001","paper_id":"DEMO-P001","domain":"04_spatiotemporal_molecular_pathology","section_role":"introduction","rhetorical_moves":[{"roles":["VALUE"],"explanation":"先说方法保留的信息"},{"roles":["GAP"],"explanation":"再交代测量需要验证"}],"abstract_pattern":"方法能保留什么信息 → 使用这些信息前需要完成什么检查","source_location":{"kind":"synthetic_example","paragraph":1}}
```

真实标注应结合原段给出具体推进关系，再写出可借鉴的组织方式。原文内容与抽象说明同时保留。

## 设置参考库位置

在 Skill 根目录新建 `project.local.json`：

```json
{
  "corpus_root": "./data/corpus",
  "annotation_version": "abstract-introduction-v2"
}
```

将 `corpus_root` 改成自己的参考库路径。相对路径以 **Skill 根目录** 为起点；绝对路径直接使用。Windows 路径可以使用正斜杠，例如 `D:/my-references`。

本机设置覆盖 [默认模板](../assets/project-template.yaml) 中对应的字段。其他设置沿用模板。`project.local.json` 已列入 Git 忽略规则。

在 Skill 根目录运行：

```bash
python scripts/measure_style.py
```

程序读取标注并建立本地检索索引。以后增改原文或句子标注，再运行同一命令即可更新；段落标注在生成段落候选时读取。

需要单独验证安装时，可复制 `examples/corpus` 为 `data/corpus`，再运行索引命令。这里的文字是测试示例，实际写作请换成经过核对的论文参考段落。

## 领域和章节怎样选

| 参数 | 研究方向 |
| --- | --- |
| `D01` | 活组织诊断 |
| `D02` | 患者来源类器官 |
| `D03` | 类器官芯片 |
| `D04` | 时空分子病理 |
| `D05` | 病理质量控制 |
| `D06` | 时空溯源 |
| `D07` | 功能精准肿瘤学 |

记录中的 `domain` 使用 [common.py](../scripts/common.py) 中对应的完整名称。涉及多个方向时，以逗号分隔，例如 `D02,D05`。新增其他领域需要同步扩展该文件的 `DOMAINS`，并提供匹配的参考记录。

章节参数为 `abstract`、`introduction` 或 `any`。摘要与引言精确匹配对应的 `section_role`；`any` 允许从所选领域的各章节中查找，再结合具体写作任务选材。

## 命令示例

以下命令供需要手动运行脚本的使用者参考。日常使用可直接把任务交给助手，按 [SKILL.md](../SKILL.md) 执行。

```bash
python scripts/run_writing.py prepare --input data/draft.md --domain D02,D05 --section introduction --level L2 --requirements-file data/author_request.md
```

`prepare` 读取原稿、建立候选和文献核对记录。后续由助手完成事实整理、范例选择、中文写作、作者确认、英文写作与独立审阅。运行步骤及所需文件见 [SKILL.md](../SKILL.md)。

| 参数 | 含义 |
| --- | --- |
| `--level L0` | 保留原有论证和段落顺序，翻译或润色。 |
| `--level L1` | 允许段内和相邻段落调整，先确认中文。 |
| `--level L2` | 允许在指定章节内重组，先确认中文。 |
| `--content-policy argument_first` | 以论述需要决定材料取舍，保留删改依据。L1/L2 默认采用。 |
| `--content-policy preserve_all` | 逐项保留原有内容和引用。L0 默认采用。 |

输入支持 UTF-8 Markdown 和 DOCX 正文。DOCX 导入读取文字、上标和参考文献相关字段；表格版式、图件与最终 Word 修订交由文档工具处理。

默认输出保存在参考库下的 `runs/writing/<本次编号>/`。主要文件包括：

- `restructured_zh.md`：结构调整后的完整中文稿。
- `output.md`：完成检查的英文稿。
- `fact_ledger.json`、`logic_plan.json` 和各段来源记录：后台核对材料。

各文件随对应阶段完成后生成。涉及结构调整时，需要作者确认当前中文稿才能完成英文交付。

需要独立配置文件时，复制完整默认模板，再传入 `--config`。该参数写在子命令前；同一次任务的后续脚本继续使用同一配置文件：

```bash
python scripts/run_writing.py --config project.local-full.json prepare --input data/draft.md --domain D04 --section introduction --level L0
```

显式 `--config` 读取完整配置；根目录 `project.local.json` 是部分字段覆盖，两者用途不同。

## 可选的英文句子检查

默认提供句长等基础检查。需要进一步检查主语与谓语距离、指代和词形时，可以在所用 Python 环境安装 spaCy 及英文模型：

```bash
python -m pip install spacy
python -m spacy download en_core_web_sm
```

然后在 `project.local.json` 增加 `fluency_python`，填写这个 Python 解释器的完整路径。脚本用它运行 [fluency_metrics.py](../scripts/fluency_metrics.py)。这些结果用于定位待审阅的句子，实际改法结合上下文决定。

## 材料与运行记录

写作与审阅使用当前 AI 助手选择的模型；脚本本身没有接入额外的写作模型服务。原稿、作者要求和选定的参考范例会作为该助手的输入。

文献核对会调用 Crossref、PubMed 和 OpenAlex，发送题名、作者、DOI 或其他检索字段。查找具名研究的缺失题录时，Crossref 请求包含作者姓氏及所在上下文的前 600 个字符。PubMed/PMC 查询还可能使用文献编号。使用者应根据自己的材料要求选择文献核对方式。

`reference_audit.contact_email` 和 `reference_audit.ncbi_api_key` 可以在本机设置中填写；前者随数据库请求发送联系信息，后者用于 NCBI 请求。它们在新生成的运行清单中会显示为 `[redacted]`。

原稿、参考原文、模型输入、作者意见、结果和数据库响应保存在本地工作目录中。建议将这些目录与源码仓库分开管理；随 Skill 提供的 Git 忽略规则已覆盖默认数据目录、运行目录、缓存和本机配置。
