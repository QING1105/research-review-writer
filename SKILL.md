---
name: research-review-writer
description: Translate and polish biomedical review drafts for clear logic, fluent English and the user's paper-corpus wording style. Use for source-grounded editing, author-reviewed restructuring, or refreshing an author-configured reference corpus.
---

# Research review writer

Use the author's draft and explicit corrections as the content source. Use the existing corpus for paragraph progression and concrete grammar/wording. Preserve provenance, author intent and separate argumentation/language realization.

Use this Skill folder as the implementation root. Configure the reference corpus through `project.local.json`, which overrides `assets/project-template.yaml`. For installation and source preparation, read [README.md](README.md) and [corpus-setup.md](references/corpus-setup.md). Keep original papers, author drafts and run records in the configured data directories.

Before operations explain sources, processing, actual model roles and inputs. Current host performs semantic planning, selection and writing; independent subagents perform the role reviews. Scripts check provenance, coverage, budgets and versions. Record actual host/model and context, keeping unavailable model IDs null. Commands below run from this Skill folder with its Python dependencies installed.

Use Python 3.11 or newer. For optional spaCy diagnostics, configure `fluency_python` in the local settings; otherwise the workflow uses its built-in sentence checks. Scripts prepare and validate materials; the current host model writes and reviews the prose. Before starting, check that the host provides independent review contexts and that the configured annotated corpus exists.

## Prepare and plan

Read [logic-planning.md](references/logic-planning.md) and [style-profile.md](references/style-profile.md). Domain precedes section/task. L0 retains the supplied argument and paragraph order; L1 allows within-paragraph and adjacent-paragraph changes; L2 allows restructuring within this section. New L1/L2 runs prioritize the author's argument and reader flow (`argument_first`): select relevant claims, omit irrelevant or redundant material with reasons, and place citations with the claims they support. An explicit request to preserve every fact or citation uses `--content-policy preserve_all`. L0 preserves the accepted source. Author structure governs this run. L1/L2 require readable Chinese and actual author confirmation before English.

```powershell
python scripts/run_writing.py prepare --input outputs/draft.md --domain D02,D05 --section introduction --level L2 --requirements-file outputs/author_request.md
```

### Audit references before building the ledger (A0)

Read [reference-audit.md](references/reference-audit.md). Prepare preserves the DOCX/Markdown source, separates its bibliography and creates references_audit.json. Run:

```powershell
python scripts/verify_references.py --run <run>
python scripts/validate_references.py --run <run> --begin
```

Read author_queries_refs.md and present blocking items together. Await the author's actual decisions or item-specific waivers before building the fact ledger. Pending/offline verification, unconfirmed missing inline mapping, and undecided retraction block A0. Propose corrected metadata only from retained database responses. Preserve the original source and corrections sidecars. For missing inline markers show proposed_mapping.md; ingest the author's mapping or explicit none_by_author choice. Weak surname matches remain suggestions.

### Check cited claim support before planning (A1)

After A0 passes, read bounded planning_inputs and author fact_ledger.json using audited reference identities. Then:

```powershell
python scripts/check_support.py --run <run> --ledger <run>/fact_ledger.json
```

Run independent support-review subagents, each receiving only its claim/abstract or OA passage packet. Save actual invocation identity, exact evidence quotes and support verdicts using reference-audit.md. Contradictions need an author decision before planning; partial and undeterminable findings go into the author question list. Preserve evidence strength pending author correction. Then validate support and create the logic plan:

```powershell
python scripts/check_support.py --run <run> --validate
python scripts/logic_flow.py plan --run <run> --ledger <run>/fact_ledger.json --plan <run>/logic_plan.json
```

Keep the complete source ledger and original citation identities in the archive. Record `editorial_selection` in the existing logic plan; the writer receives the selected claims and planned citation locations. Each retained claim preserves its facts, quantities, scope and evidence strength. Omitted examples leave the prose together with their citations; shared evidence stays attached to the retained claims. Core arguments, necessary qualifications and relevant counterevidence remain priorities during selection and independent review. Attach sourced author requirements to paragraph purpose, scope and relationships. Model proposals remain separate candidates; author-approved new scientific content enters a linked source revision. Paragraph count and necessity/benefit choices come from this task.

## Compose readable Chinese for L1/L2

For each paragraph in order:
```powershell
python scripts/logic_flow.py candidates --run <run> --paragraph N001 --stage zh
python scripts/logic_flow.py assemble --run <run> --paragraph N001 --selection <selected.json> --stage zh
```
Select real corpus IDs using the two-channel schema in style-profile.md, with the source relationship and its adaptation. Read N001/zh/writer_input.md and write N001/zh/result.json following [chinese-writing.md](references/chinese-writing.md). Write connected prose; keep sentence mappings and ledger as sidecars.

```powershell
python scripts/logic_flow.py preview --run <run>
python scripts/logic_flow.py reviews --run <run> --stage zh
```
Read [logic-review.md](references/logic-review.md). Run separate fidelity/author-intent and Chinese-reader subagents; each receives only its role packet. Record actual invocation with dispatch. Revise affected paragraphs, refresh downstream inputs and final-version reviews. Show restructured_zh.md as a complete article with brief material changes; keep IDs and audit tables backstage.

After actual confirmation of this exact version:
```powershell
python scripts/logic_flow.py confirm --run <run> --author-message "<actual confirmation>"
```
For author edits use ingest-edits and reconcile changes. Relevance-based omissions and citation consolidation use the existing plan's selection records; changes to scientific meaning or newly supplied facts enter a linked source run. The approved Chinese version governs the English handoff, including its recorded omissions. A development run with --task-kind development_evaluation may use confirm --evaluation for clearly labeled simulated approval; its output remains a development artifact.

## Compose English and finish

L0 uses preserved source. L1/L2 pass the approved Chinese paragraph verbatim, facts, author requirements, outline, preceding English, next main point and corpus references. Follow [writing-principles.md](references/writing-principles.md). Keep the approved argument while choosing natural English sentence organization from the corpus.

```powershell
python scripts/logic_flow.py candidates --run <run> --paragraph N001 --stage en
python scripts/logic_flow.py assemble --run <run> --paragraph N001 --selection <selected.json> --stage en
python scripts/logic_flow.py reviews --run <run> --stage en
python scripts/run_writing.py finish --run <run>
```
Write each result.json before assembling the next paragraph. English reviews use independent fidelity/intent, reader and corpus-style contexts. Register invocations and satisfy role schemas before finish. Intent/relationship/scope errors require paragraph revision plus adjacent-context review; lexical edits may stay local. output.md contains English; source maps and audit remain in the run.

## Author-facing modification notes

When delivering 修改说明, read [delivery-notes.md](references/delivery-notes.md) and use the [notes template](assets/modification-notes-template.md). Describe the author's comment, its location and the actual edit, followed by necessary structure/language changes. A normal citation check gets one sentence. Keep fact-ledger counts, unchanged data inventories, review logs and Word verification procedures in the run files; attach technical reports when the user requests them. Apply this rule to both Chinese and English manuscript deliveries.

## Budgets and compatibility

assets/project-template.yaml: sentence/paragraph candidates 2400 tokens each; selected language 1800; selected complete paragraphs 600 and at most two; serialized writer input 6500; chapter review input 16000. Count with o200k_base. Reduce redundant examples within the limits while retaining factual/accepted-source material. Large documents use section runs with common terminology/reference identities.

v3 serializes request content as compact JSON. Query/operation logs and source coordinates remain in run files; writing receives the selected claims in full, their source text, author requirements and selected references. assembly.json records component token counts; budget_rejected.json identifies an over-budget attempt.

New logic runs use workflow v3 through the existing run_writing.py/logic_flow.py entrypoints. Existing v2 runs retain their contract; legacy v1 remains explicit via prepare --workflow legacy. Keep earlier runs, canonical corpus and negative examples. Keep the bundled workflow references aligned with implementation changes.

Report reference verification as passed only when validate_references.py passes for the current audit version. Save evidence_unverified.md and not_checked/not_checkable coverage in the run. Bring concrete unresolved citation problems to the author with their location and required decision; use the modification-notes rule above for the author-facing explanation.
