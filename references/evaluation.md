# 输出审阅与保存

本文件描述 v1 / `--workflow legacy` 的记录格式。当前默认台账流程使用 [logic-review.md](logic-review.md) 和 [writing-principles.md](writing-principles.md)。

逐段检查原稿和英文稿：事实数字、否定与限定、逻辑和顺序、术语、参考风格是否自然。可明确修正的语言错误直接修订；需作者判断的问题放入queries。生成语法顺畅且忠实的最终稿后，保存到当前单元的result.json。

```json
{
  "text": "完整英文正文",
  "reviewer": "current_skill_host",
  "model_id": null,
  "audit": {
    "facts_and_numbers": {"status": "checked", "note": "具体核对对象和结果"},
    "logic_and_order": {"status": "checked", "note": "具体原有关系及其保持方式"},
    "terminology_and_scope": {"status": "checked", "note": "术语、否定及范围核对"},
    "style_fit": {"status": "checked", "note": "本次采用的实际知识库表达"}
  },
  "style_alignment": [
    {
      "output_span": "逐字来自最终英文稿",
      "reference_id": "R01",
      "reference_span": "逐字来自本次R01原句",
      "feature": "实际借鉴的句法或搭配"
    }
  ],
  "queries": []
}
```

数字形式发生变化时，增加number_change_review并具体解释。例如原稿数字拼写、引用标号和单位换算各自核对。审阅状态checked表示当前执行模型完成审阅；作者认可另记。不得将脚本通过写作质量验证表述为用户已认可。

运行finish会核验ID、逐字跨度、原稿覆盖、来源文本和输入预算，合并英文稿与审阅记录。交付output.md；用户要求时附audit.json和本次参考来源。后续用户改稿保存为独立接受记录，保留本次原稿和参考包。

作者用修改说明沿用[修改说明交付规则](delivery-notes.md)；上述audit与number_change_review保存在后台，说明正文聚焦实际修改和一句引用检查结论。
