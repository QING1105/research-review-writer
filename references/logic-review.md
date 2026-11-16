# 分开审阅与交付

v3的L1/L2中文成稿后生成zh_reviews的fidelity、reader输入；英文后产生reviews的fidelity、reader、style输入。每位审阅者只读自己的角色包。输入以紧凑JSON实际保存并计数，input_budgets.json记录总量及分项；作者要求只装入一次，英文审阅保留认可中文的完整正文。

fidelity核对原稿、台账、作者原始要求、结构化要求、规划和正文。检查事实、条件、分母、强度、引用、对象和范围；原要求遗漏也列issue。重点核对主旨、必要关系及附带作用。解释句指向支持事实并保持结论范围。英文还须对照认可中文。

argument_first运行的完整台账属于来源档案；正文覆盖要求以规划中保留的claims为准。读取editorial_selection，分别核对保留内容和删去内容：例证与主旨的相关性、重复信息的合并、核心论点及必要限定的完整性、关键反例与结论强度的关系。引用检查以实际证据对应为准，逐项核对随论断删去、分段跟随和重复合并的记录。源文引用总数与正文总数的差异由这些记录解释。
reader只读正文，先概括首句，再读全段判断其主旨，逐句指出承接、指代和回读点；引用原文说明阅读问题。sentence_spans供定位；同时检查它是否对应真实句子，混合多句或断开句子时列出映射问题，修正后复核。
style对照实际库内段落和语言范例，检查推进关系、句式与搭配自然程度、领域适配和生硬移植，分别记录来源与输出特征。

宿主按实际子代理调用登记：
```powershell
python research-review-writer/scripts/logic_flow.py dispatch --run <run> --stage zh --role reader --context-id <actual-context> --model <actual-host-or-model>
```
具体model_id可用时加--model-id。报告使用相同真实标识，程序与dispatch比对。每个角色独立上下文。

所有报告必填：input_sha256、context_id、model、model_id（可null）、isolation:independent_context、status:completed、issues数组、paragraphs数组。paragraphs每项有paragraph_id，覆盖全文各段一次。

fidelity另填reviewed_claim_ids、author_request_coverage:complete、author_requirement_checks:[{requirement_id,status:satisfied|violated,reason,evidence:[{paragraph_id,quote}]}]。reviewed_claim_ids覆盖完整来源台账，包括经核对的取舍。argument_first另填editorial_checks:[{decision_id,status:supported|issue,reason}]，覆盖editorial_selection.decisions中的每项删去论断和引用合并；具体说明其对作者论证和证据对应的影响。发现问题时列issue并修正规划及正文后复核。每段另填main_point、author_intent_assessment。逐项核对作者原始要求是否完整提取，并核对kind分类。content要求引用正文；workflow要求引用execution_evidence，证据格式为{artifact_id,fact}，fact使用该记录中的真实文本或序列化片段；mixed两类证据都提供。记录来源、开发模式等执行要求按实际文件核对，科研论述要求按正文核对。

reader每段必填：
- first_sentence：按输入sentence_spans第一个跨度逐字引用首句；这些跨度仅标识正文位置。
- first_sentence_outline：只读首句理解的重点。
- main_point_after_reading：读完整段得到的判断。
- topic_alignment：aligned/partial/misaligned；topic_alignment_reason解释两者关系。
- sentence_links：逐句按顺序列sentence_index（从1开始）、text（逐字句子）、relation、reason。
- unclear_references、reread_points：数组，有问题时注明片段和阅读障碍。

style每段必填source_features、output_features、fit_notes，引用真实范例和输出片段。

issue字段为severity（minor/major/blocking）、paragraph_id、span（正文片段）、reason、fix。主旨、必要关系、对象或范围错误作为实质问题处理。修改关系和范围时重写整段，检查前后承接；前段变化后重新组装后段。正文修改后重新生成相关审阅包并独立复核。

当前稿保留的minor意见记录到对应审阅目录revision_decisions.json：{snapshot_sha256,items:[{role,issue_index,decision:retain,reason}]}。已解决问题留在history。程序检查实际片段、字段、覆盖和版本；模型提供有证据的语义判断。

中文审阅完成后交作者确认；confirm --evaluation只用于development_evaluation的明确模拟确认，最终状态为completed_development_evaluation。v2历史运行沿用原报告格式。

机械检查由fluency_metrics.py运行spaCy，检查句长、依存距离、名词化、指代及重复句首；这些用于定位，再结合语境编辑。引用、来源、用户认可与写作质量分别记录。

审阅报告与核对明细保存在运行目录。为作者撰写修改说明时，读取[修改说明交付规则](delivery-notes.md)，按实际改动生成简明说明。
