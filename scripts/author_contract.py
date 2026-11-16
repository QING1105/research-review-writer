"""Version 3 author intent, readable Chinese drafts and semantic review contracts.

Models supply prose and evidence-backed judgments. These helpers verify their
provenance, coverage and version; they do not infer semantic correctness.
"""
from common import *
import shutil

def require(ok, message):
    if not ok: raise ValueError(message)

def enabled(run):
    return read(run/'manifest.json').get('workflow_version', 1) >= 3

def validate(run, ledger, plan=None):
    m=read(run/'manifest.json')
    require(sha(run/'author_request.md')==m['author_request_sha256'],'Author request changed; create a linked run')
    for claim in ledger['claims']:
        require(claim.get('origin') in ('source','author_source'),'Active claims require source or author_source origin; keep model candidates separately')
    ids={x['claim_id'] for x in ledger['claims']}
    for item in ledger.get('model_candidates',[]):
        require(item.get('text') and item.get('reason') and item.get('status') in ('proposed','rejected','deferred'),'Record candidate text, relevance and disposition')
        require(item.get('supports') and set(item['supports'])<=ids,'Candidate must point to source claims')
        require(item.get('candidate_id') not in ids,'A model candidate cannot be a mandatory claim')
    if plan is None:return
    requirements=plan.get('author_requirements')
    require(isinstance(requirements,list),'Supply author_requirements as sourced records')
    reqmap={x['requirement_id']:x for x in requirements}
    require(len(reqmap)==len(requirements),'Duplicate author requirement')
    source={'request':(run/'author_request.md').read_text(encoding='utf-8'),'draft':(run/'input.md').read_text(encoding='utf-8')}
    for r in requirements:
        require(r.get('text') and r.get('source') in source and r.get('source_quote') and r['source_quote'] in source[r['source']],'Each author requirement needs an exact source quote')
        require(r.get('kind','content') in ('content','workflow','mixed'),'Requirement kind must distinguish prose from execution')
    if source['request'].strip():require(requirements,'Map the supplied author request before writing')
    used=set()
    for p in plan['paragraphs']:
        require(p.get('subject_scope') and isinstance(p.get('required_relations'),list),'Record paragraph subject scope and required relations')
        require(isinstance(p.get('requirement_ids'),list) and set(p['requirement_ids'])<=reqmap.keys(),'Map paragraph author requirements')
        used.update(p['requirement_ids'])
        for relation in p['required_relations']:
            require(relation.get('description') and relation.get('type') in ('cause','necessity','consequence','condition','contrast','concession','sequence','example','comparison','addition'),'Describe the specific argumentative relationship')
            require(relation.get('claims') and set(relation['claims'])<=set(p['claim_order']),'Relation needs this paragraph source claims')
            require(set(relation.get('requirement_ids',[]))<=set(p['requirement_ids']),'Relation author requirement mismatch')
    require(used==reqmap.keys(),'Map every author requirement to at least one paragraph')
    shape=plan.get('author_structure',{})
    if shape:
        require(shape.get('requirement_id') in reqmap,'Author structure needs a sourced requirement')
        if shape.get('paragraph_count') is not None:
            require(len(plan['paragraphs'])==shape['paragraph_count'],'Paragraph count differs from the author structure')

def checkpoint(run):
    return read(run/'manifest.json').get('chinese_hashes',{})

def verify_chinese(run):
    m=read(run/'manifest.json');hashes=m.get('chinese_hashes',{})
    require(hashes,'Complete the readable Chinese/source draft first')
    for name,digest in hashes.items():require(sha(run/name)==digest,'Chinese draft changed; regenerate its review and confirmation')

def initial_source(run,ledger,plan):
    """L0 preserves the supplied draft verbatim; L1/L2 require generated prose."""
    source=(run/'input.md').read_text(encoding='utf-8');paragraphs=[]
    source_map={p['para_id']:p for p in ledger['source_units']}
    for p in plan['paragraphs']:
        old=source_map[p['target_source_para']]
        paragraphs.append(dict(paragraph_id=p['new_para_id'],text=source[old['start']:old['end']],claims=p['claim_order']))
    save(run/'chinese_draft.json',dict(mode='source_preserved',paragraphs=paragraphs))
    (run/'restructured_zh.md').write_text(source,encoding='utf-8')
    m=read(run/'manifest.json');m['chinese_hashes']={n:sha(run/n) for n in ('chinese_draft.json','restructured_zh.md')};m['status']='source_structure_preserved';save(run/'manifest.json',m)

def preview(c,run):
    import logic_flow as flow
    ledger,plan=flow.check_plan(run,False);outputs=[];hashes={}
    require(read(run/'manifest.json')['level']!='L0','L0 already preserves the supplied source')
    for p in plan['paragraphs']:
        pid=p['new_para_id'];result=flow.validate_result(c,run,pid,stage='zh')
        clean,_=flow.render_citations(result['text'],ledger,'keep_original')
        outputs.append(dict(paragraph_id=pid,text=clean,working_text=result['text'],sentence_claims=result['sentence_claims']))
        hashes[f'{pid}/zh/result.json']=sha(run/pid/'zh/result.json')
    # Retain previous readable versions before replacing the working preview.
    if (run/'chinese_draft.json').exists():
        archive=run/'chinese_history'/sha(run/'chinese_draft.json')[:16];archive.mkdir(parents=True,exist_ok=True)
        for name in ('chinese_draft.json','restructured_zh.md'):shutil.copy2(run/name,archive/name)
    save(run/'chinese_draft.json',dict(mode='model_composed',paragraphs=outputs))
    (run/'restructured_zh.md').write_text('\n\n'.join(x['text'] for x in outputs)+'\n',encoding='utf-8')
    hashes.update({n:sha(run/n) for n in ('chinese_draft.json','restructured_zh.md')})
    m=read(run/'manifest.json');m.update(chinese_hashes=hashes,status='awaiting_chinese_reviews');m.pop('structure_confirmation',None);save(run/'manifest.json',m)
    return dict(preview=str(run/'restructured_zh.md'),next='reviews --stage zh')

def author_view(plan,p):
    return [x for x in plan['author_requirements'] if x['requirement_id'] in p['requirement_ids'] and x.get('kind','content')!='workflow']

def add_writer_context(run,plan,p,payload,stage):
    payload['author_requirements']=author_view(plan,p)
    payload['section_outline']=[dict(paragraph_id=x['new_para_id'],main_point=x['main_point']) for x in plan['paragraphs']]
    if stage=='en':
        verify_chinese(run);draft=read(run/'chinese_draft.json')
        para=next(x for x in draft['paragraphs'] if x['paragraph_id']==p['new_para_id'])
        key='approved_chinese_paragraph' if draft['mode']=='model_composed' else 'accepted_source_paragraph'
        payload[key]=para['text'];payload['source_mode']=draft['mode']

def relation_selection(pick,p):
    require(pick.get('relation_fit') in ('matched','partial'),'Select a compatible progression; conflicting examples belong outside the paragraph channel')
    require(pick.get('source_relation') and pick.get('target_relation') and pick.get('adaptation'),'Explain source relationship, target relationship and adaptation')
    require(pick.get('applies_to_claims') and set(pick['applies_to_claims'])<=set(p['claim_order']),'Match paragraph example to actual source claims')

def archive_reviews(directory):
    if (directory/'snapshot.json').exists():
        archive=directory/'history'/sha(directory/'snapshot.json')[:16];archive.mkdir(parents=True,exist_ok=True)
        for path in directory.glob('*.json'):shutil.copy2(path,archive/path.name)

def review_inputs(c,run,stage):
    import logic_flow as flow
    ledger,plan=flow.check_plan(run,stage=='en');verify_chinese(run)
    outputs=[]
    for p in plan['paragraphs']:
        r=flow.validate_result(c,run,p['new_para_id'],stage=stage)
        outputs.append(dict(paragraph_id=p['new_para_id'],text=r['text'],sentence_claims=r['sentence_claims']))
    directory=run/('zh_reviews' if stage=='zh' else 'reviews');directory.mkdir(exist_ok=True);archive_reviews(directory)
    instruction=(SKILL/'references/logic-review.md').read_text(encoding='utf-8')
    m=read(run/'manifest.json')
    save(directory/'source_manifest_snapshot.json',m)
    execution=[dict(artifact_id='execution:run',source_file=str((directory/'source_manifest_snapshot.json').relative_to(run)),sha256=sha(directory/'source_manifest_snapshot.json'),facts=dict(workflow_version=m['workflow_version'],task_kind=m['task_kind'],review_stage=stage))]
    if stage=='en' and m['level']!='L0':
        confirmation=m['structure_confirmation']
        execution[0]['facts']['structure_confirmation']=dict(approval_kind=confirmation['approval_kind'],author_message=confirmation['author_message'],chinese_draft_sha256=confirmation['chinese_hashes']['chinese_draft.json'])
    for p in plan['paragraphs']:
        pid=p['new_para_id'];d=flow.result_directory(run,pid,stage)
        actual=json.loads(read(d/'writer_messages.json')[1]['content'])
        execution.append(dict(artifact_id=f'execution:{pid}',source_file=str((d/'writer_messages.json').relative_to(run)),sha256=sha(d/'writer_messages.json'),facts=dict(argumentation_references=[x['reference_id'] for x in actual['reference_paragraphs']],language_references=[x['reference_id'] for x in actual['reference_language']],separate_channels=['reference_paragraphs','reference_language'],result_sha256=sha(d/'result.json'))))
    requests={
        'fidelity':dict(role='fidelity',stage=stage,instruction=instruction,ledger=ledger,plan={k:v for k,v in plan.items() if k!='author_requirements'},author_request=(run/'author_request.md').read_text(encoding='utf-8'),author_requirements=plan['author_requirements'],outputs=outputs),
        'reader':dict(role='reader',stage=stage,instruction=instruction,paragraphs=[dict(paragraph_id=x['paragraph_id'],text=x['text'],sentence_spans=[dict(sentence_index=i+1,start=s['start'],end=s['end']) for i,s in enumerate(x['sentence_claims'])]) for x in outputs])}
    requests['fidelity']['execution_evidence']=execution
    if m.get('content_policy')=='argument_first':
        import content_selection
        _,selection=content_selection.project(ledger,plan,'argument_first')
        requests['fidelity']['editorial_selection']=selection
    if stage=='en':
        accepted=read(run/'chinese_draft.json')
        requests['fidelity']['accepted_source']=dict(mode=accepted['mode'],paragraphs=[dict(paragraph_id=p['paragraph_id'],text=p['text']) for p in accepted['paragraphs']])
        style=[]
        for p,r in zip(plan['paragraphs'],outputs):
            payload=json.loads(read(run/p['new_para_id']/'writer_messages.json')[1]['content'])
            style.append(dict(paragraph_id=r['paragraph_id'],text=r['text'],reference_language=payload['reference_language'],reference_paragraphs=payload['reference_paragraphs']))
        requests['style']=dict(role='style',stage=stage,instruction=instruction,paragraphs=style)
        (run/'draft_en.md').write_text('\n\n'.join(x['text'] for x in outputs)+'\n',encoding='utf-8')
        flow.write_mechanical(c,run,directory,'\n\n'.join(x['text'] for x in outputs))
    budgets={};serialized={};limit=c['budgets'].get('review_input_tokens',16000)
    for role,payload in requests.items():
        serialized[role]=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
        budgets[role]=dict(tokens=count(serialized[role],c),limit=limit,component_tokens={k:count(json.dumps(v,ensure_ascii=False,separators=(',',':')),c) for k,v in payload.items()})
    save(directory/'input_budgets.json',budgets)
    for role,record in budgets.items():require(record['tokens']<=limit,f'{role}: chapter review input {record["tokens"]} exceeds {limit}; inspect input_budgets.json')
    for role,text in serialized.items():
        (directory/f'{role}_input.json').write_bytes(text.encode('utf-8'))
    snapshot=dict(stage=stage,plan_hashes=read(run/'manifest.json')['plan_hashes'],chinese_hashes=checkpoint(run),results={p['new_para_id']:sha(flow.result_directory(run,p['new_para_id'],stage)/'result.json') for p in plan['paragraphs']},input_hashes={role:sha(directory/f'{role}_input.json') for role in requests})
    save(directory/'snapshot.json',snapshot)
    return dict(review_directory=str(directory),roles=list(requests),stage=stage)

def dispatch(run,role,context_id,model,stage='en',model_id=None):
    """Host records the actual child invocation before ingesting its report."""
    directory=run/('zh_reviews' if stage=='zh' else 'reviews');snapshot=read(directory/'snapshot.json')
    require(role in snapshot['input_hashes'],'Unknown review role')
    require(context_id.strip() and model.strip(),'Record actual reviewer context and host/model')
    path=directory/'dispatch.json';record=read(path) if path.exists() else {}
    record[role]=dict(context_id=context_id,model=model,model_id=model_id,input_sha256=sha(directory/f'{role}_input.json'))
    save(path,record);return record[role]

def verify_reports(run,stage):
    import logic_flow as flow
    ledger,plan=flow.check_plan(run,False);verify_chinese(run)
    directory=run/('zh_reviews' if stage=='zh' else 'reviews');snapshot=read(directory/'snapshot.json');dispatches=read(directory/'dispatch.json')
    require(snapshot['plan_hashes']==read(run/'manifest.json')['plan_hashes'] and snapshot['chinese_hashes']==checkpoint(run),'Review source version is stale')
    outputs={p['new_para_id']:read(flow.result_directory(run,p['new_para_id'],stage)/'result.json') for p in plan['paragraphs']}
    for pid in outputs:require(sha(flow.result_directory(run,pid,stage)/'result.json')==snapshot['results'][pid],'Draft changed after review')
    reports={};roles=('fidelity','reader') if stage=='zh' else ('fidelity','reader','style')
    for role in roles:
        report=read(directory/f'{role}_review.json');call=dispatches[role]
        require(report.get('input_sha256')==call['input_sha256']==sha(directory/f'{role}_input.json')==snapshot['input_hashes'][role],'Review input or invocation is stale')
        require(report.get('context_id')==call['context_id'] and report.get('model')==call['model'] and report.get('isolation')=='independent_context','Review must match the recorded independent invocation')
        require(report.get('model_id')==call.get('model_id'),'Review model ID differs from the invocation record')
        require(report.get('status')=='completed' and isinstance(report.get('issues'),list),'Review is incomplete')
        for issue in report['issues']:
            require(issue.get('severity') in ('minor','major','blocking') and issue.get('paragraph_id') in outputs and issue.get('reason') and issue.get('fix'),'Issue needs location, severity, reason and repair')
            require(issue.get('span') and issue['span'] in outputs[issue['paragraph_id']]['text'],'Issue quote must occur in this draft')
            require(issue['severity']=='minor','Resolve substantive review issues before delivery')
        paragraphs={x['paragraph_id']:x for x in report.get('paragraphs',[])}
        require(len(paragraphs)==len(report.get('paragraphs',[])) and paragraphs.keys()==outputs.keys(),'Review every paragraph exactly once')
        for pid,p in paragraphs.items():
            text=outputs[pid]['text'];sentences=outputs[pid]['sentence_claims']
            if role=='reader':
                for key in ('first_sentence_outline','main_point_after_reading','topic_alignment','topic_alignment_reason'):require(isinstance(p.get(key),str) and p[key].strip(),f'Reader missing {key}')
                first=text[sentences[0]['start']:sentences[0]['end']]
                require(p.get('first_sentence')==first,'Reader must quote the actual first sentence')
                require(p['topic_alignment'] in ('aligned','partial','misaligned'),'Reader topic_alignment value')
                if p['topic_alignment']!='aligned':
                    require(any(x['paragraph_id']==pid for x in report['issues']),'Record the topic alignment problem as an issue')
                links=p.get('sentence_links',[])
                require([x.get('sentence_index') for x in links]==list(range(1,len(sentences)+1)),'Reader must cover each sentence in order')
                for link,s in zip(links,sentences):
                    require(link.get('text')==text[s['start']:s['end']] and link.get('relation') and link.get('reason'),'Reader sentence quote and explanation required')
                for key in ('unclear_references','reread_points'):require(isinstance(p.get(key),list),f'Reader missing {key}')
            elif role=='style':
                for key in ('source_features','output_features','fit_notes'):require(p.get(key),f'Style review missing {key}')
            else:require(p.get('main_point') and p.get('author_intent_assessment'),'Fidelity must assess the paragraph purpose and author intent')
        if role=='fidelity':
            require(set(report.get('reviewed_claim_ids',[]))=={x['claim_id'] for x in ledger['claims']},'Review source claims as retained content or documented omissions')
            if read(run/'manifest.json').get('content_policy')=='argument_first':
                import content_selection
                _,selection=content_selection.project(ledger,plan,'argument_first')
                decisions={x['decision_id'] for x in selection['decisions']}
                checks=report.get('editorial_checks',[])
                require(len(checks)==len(decisions) and {x.get('decision_id') for x in checks}==decisions,'Review every omission and citation merge')
                require(all(x.get('status')=='supported' and x.get('reason','').strip() for x in checks),'Resolve content-selection or citation-merge issues')
            checks=report.get('author_requirement_checks',[]);reqs={x['requirement_id']:x for x in plan['author_requirements']}
            require(len(checks)==len(reqs) and {x['requirement_id'] for x in checks}==reqs.keys(),'Review every author requirement')
            execution={x['artifact_id']:x for x in read(directory/'fidelity_input.json')['execution_evidence']}
            require(execution['execution:run']['facts']['task_kind']==read(run/'manifest.json')['task_kind'],'Execution mode changed after review')
            for check in checks:
                require(check.get('status')=='satisfied' and check.get('reason') and check.get('evidence'),'Resolve author requirement mismatch')
                kinds=set()
                for e in check['evidence']:
                    if 'artifact_id' in e:
                        require(e['artifact_id'] in execution and e.get('fact') and e['fact'] in json.dumps(execution[e['artifact_id']],ensure_ascii=False),'Workflow requirement needs actual execution evidence')
                        kinds.add('workflow')
                    else:
                        require(e.get('paragraph_id') in outputs and e.get('quote') and e['quote'] in outputs[e['paragraph_id']]['text'],'Author requirement needs actual draft evidence')
                        kinds.add('content')
                kind=reqs[check['requirement_id']].get('kind','content');needed={'content','workflow'} if kind=='mixed' else {kind}
                require(needed<=kinds,'Requirement evidence type does not match its content/workflow scope')
            require(report.get('author_request_coverage')=='complete','Check the source request against extracted requirements')
        reports[role]=report
    require(len({x['context_id'] for x in reports.values()})==len(roles),'Use separate review contexts')
    if any(r['issues'] for r in reports.values()):
        path=directory/'revision_decisions.json';decisions=read(path)
        require(decisions.get('snapshot_sha256')==sha(directory/'snapshot.json'),'Revision decisions must identify the reviewed version')
        for role,r in reports.items():
            for index,issue in enumerate(r['issues']):
                found=[d for d in decisions.get('items',[]) if d.get('role')==role and d.get('issue_index')==index]
                require(len(found)==1 and found[0].get('decision')=='retain' and found[0].get('reason'),'Record the disposition of each remaining minor issue')
    return reports

def confirm(run,message,evaluation=False):
    import logic_flow as flow
    flow.check_plan(run,False);verify_chinese(run);m=read(run/'manifest.json')
    require(m['level']!='L0','L0 uses the preserved source without restructuring confirmation')
    verify_reports(run,'zh');require(message.strip(),'Record actual confirmation or explicit evaluation simulation')
    if evaluation:require(m.get('task_kind')=='development_evaluation','Evaluation simulation belongs to development runs')
    m['structure_confirmation']=dict(author_message=message,approval_kind='evaluation_simulation' if evaluation else 'author_message',plan_hashes=m['plan_hashes'],chinese_hashes=m['chinese_hashes'],review_hashes={role:sha(run/'zh_reviews'/f'{role}_review.json') for role in ('fidelity','reader')})
    m['status']='evaluation_structure_ready' if evaluation else 'structure_confirmed';save(run/'manifest.json',m)
    return dict(status=m['status'])
