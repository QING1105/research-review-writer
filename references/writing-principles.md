# 生物医学综述逐段写作

将本次规划选中的内容写成英文，同时实现逻辑清楚、阅读顺畅，以及参考语料中的语法、措辞和句式。论述主旨和推进以认可中文及paragraph_plan为准；保留事实、条件、数量、证据强度和引文对应以claims为准。source_sentences提供来源语境，content_selection.source_context_exclusions指出同句中已决定删去的内容。按本次选定的论述范围组织正文。

reference_paragraphs 提供完整的库内段落。观察其主旨怎样展开、已知信息怎样接到新信息、解释和例证怎样安排，把适合本段已有关系的推进方式用于本段。reference_language 提供真实句子、语言标注与选用理由；据此实现主从句安排、动词补语、限定语位置、时态语态、词汇搭配及句间衔接。参考中的研究事实属于参考材料。

L0 按 claim_order 保留论断顺序与主次。L1/L2 按作者确认的中文规划写作。依据 previous_paragraph_en 接续对象和术语，利用 next_paragraph_main_point 判断段末怎样收束。首句、例证位置、句长和指代都是阅读检查点；具体句法选择以本段目的和库内范例为依据。

强度按完整语义判断：相关关系保持关联表述，可能性保留 may/could 等限定，作者建议仍表述为建议；reported 结合原句判断 reported/found/showed 的适用性。关联与因果、体外效应与临床获益分别保留。动词本身结合主语、限定语、研究设计共同决定强度。

数字、否定作用范围、比较对象、适用人群逐项核对。术语按 glossary 与前文保持一致。连接词表达台账中已经存在的关系。需要作者补充的含义记入 queries。

引用写成 {{cite:REF035}} 或 {{cite:REF016,REF017}}，放在实际支持的分句或同段连续论述之后。每个本次规划的输出citation_occurrence使用一次；它可能来自原始位置、随论断移动后的派生位置或重复标注的合并。含required_claim_ids时，binding.claims记录该引用支持的全部保留论断，可以覆盖本句及本段前面已表达的相关句子；安排位置时让读者清楚识别其证据范围。已删去的论断和其引用按后台取舍记录归档。交叉引用写成 {{xref:fig:1}} 等稳定锚点。

输出 result.json：
- input_sha256：assembly.json 的 payload_sha256。
- text：本段英文，保留占位符。
- sentence_claims：每个输出句子在 text 中的 start/end（Python Unicode 字符偏移），claims；role 为 content/summary/transition。正文句映射覆盖本段全部 claim，概括句以 summary 单独标识。
- 每句 citations 数组：occurrence_id、claims、start/end（整段偏移，精确覆盖占位符）。
- style_alignment：reference_id、output_span、reference_span、feature。两段片段均为实际文本，说明具体采用了什么句法或搭配；用于来源追溯。
- transitions_added：新增衔接与其关系依据；queries：含义待确认项。

完成后分别进入事实审阅、英文冷读和机械检查。审阅材料由脚本单独生成。

## v3 认可中文与作者主旨

approved_chinese_paragraph是作者认可的完整论述。保持其中论点、主次、因果、条件、解释和范围；L0使用accepted_source_paragraph。section_outline和author_requirements确定当前任务意图。使用库内真实句式与搭配，以自然英文拆合句子、安排主从句与指代。

L1/L2按已确认的段落主旨组织首句，背景和例证随后展开；L0保持源段的论证顺序。一个自然句可承载多项事实。required_relations中的必要安排、附带作用和进一步条件分别落实。主旨或对象变化时重写受影响段落并检查前后承接。支持性解释须指向已有事实并保持强度；模型候选提案留在后台处理。
