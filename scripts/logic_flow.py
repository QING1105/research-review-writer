"""Ledger, paragraph planning, bounded dual-reference writing and review artifacts.

Semantic records are authored by the executing model; this module checks and
assembles them. Existing v1 runs remain readable by run_writing.py.
"""
import argparse
import json
import re
import subprocess
import shutil
from collections import Counter
from common import *
from retrieve_style import retrieve
import author_contract as author
import content_selection

CITE = re.compile(r'\[(\d+(?:\s*[-–,，]\s*\d+)*)\]')
TOKEN = re.compile(r'\{\{cite:([^{}]+)\}\}')
XREF = re.compile(r'\{\{xref:([^{}]+)\}\}')
OPS = {
    'L0': {'KEEP'},
    'L1': {'KEEP','REORDER_WITHIN_PARA','PROMOTE_TOPIC_SENTENCE','MOVE_TO_ADJACENT_PARA','ADD_TRANSITION','SYNTHESIZE_TOPIC_SENTENCE','OMIT_IRRELEVANT_OR_REDUNDANT'},
}
OPS['L2'] = OPS['L1'] | {'SPLIT_PARAGRAPH','MERGE_PARAGRAPHS','REORDER_PARAGRAPHS'}

def require(ok, message):
    if not ok: raise ValueError(message)

def unique(items, key):
    result = {x[key]: x for x in items}
    require(len(result) == len(items), f'Duplicate {key}')
    return result

def cite_keys(value):
    nums=[]
    for part in re.split(r'[,，]', value):
        bounds=re.split(r'[-–]', part.strip())
        a=int(bounds[0]); b=int(bounds[-1])
        require(0 < a <= b and b-a < 1000, 'Invalid citation range')
        nums.extend(range(a,b+1))
    return [f'REF{n:03}' for n in dict.fromkeys(nums)]

def initialize(c, run, level='L0', citation_mode='keep_original', workflow_version=3, content_policy=None):
    audit_required=read(run/'manifest.json').get('reference_audit_required',False)
    if audit_required:
        import reference_audit
        reference_audit.require_a0(run)
    require(level in OPS, 'Unknown editing level')
    require(citation_mode in ('keep_original','first_appearance'), 'Unknown citation mode')
    content_policy = content_policy or read(run/'manifest.json').get('requested_content_policy') or ('argument_first' if workflow_version >= 3 and level != 'L0' else 'preserve_all')
    require(content_policy in ('argument_first','preserve_all'), 'Unknown content policy')
    require(level != 'L0' or content_policy == 'preserve_all', 'L0 preserves the accepted source; use L1/L2 for content selection')
    draft=(run/'input.md').read_text(encoding='utf-8')
    source=[]; occurrences=[]; signals=[]; refs={}
    # Source units preserve exact offsets; models may merge sentence segments in claims.
    for i,m in enumerate(re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)',draft),1):
        pid=f'P{i:03}'; sentences=[]; cursor=m.start()
        boundaries=[m.start()+x.end() for x in re.finditer(r'[。！？](?:[”’])?|[.!?](?=\s|$)',m.group())]+[m.end()]
        for end in sorted(set(boundaries)):
            if not draft[cursor:end].strip(): cursor=end; continue
            start=cursor
            while start<end and draft[start].isspace(): start+=1
            sid=f'{pid}-S{len(sentences)+1:03}'
            sentences.append(dict(sid=sid,start=start,end=end,text=draft[start:end]))
            for match in CITE.finditer(draft[start:end]):
                keys=cite_keys(match[1]); oid=f'CIT{len(occurrences)+1:04}'
                occurrences.append(dict(occurrence_id=oid,sid=sid,start=start+match.start(),end=start+match.end(),text=match[0],ref_keys=keys))
                for key in keys: refs[key]=dict(ref_key=key,original_number=int(key[3:]),entry_text=None,status='entry_not_supplied')
            excluded=[(x.start(),x.end()) for x in CITE.finditer(draft[start:end])]
            for match in re.finditer(r'\d+(?:\.\d+)?\s*%?|未必|并非|无法|没有|不|未|\b(?:not|no|never)\b',draft[start:end]):
                if any(a<=match.start()<b for a,b in excluded):continue
                signals.append(dict(signal_id=f'SIG{len(signals)+1:04}',sid=sid,start=start+match.start(),end=start+match.end(),text=match[0]))
            cursor=end
        source.append(dict(para_id=pid,start=m.start(),end=m.end(),sentences=sentences))
    skeleton=dict(schema_version=workflow_version,source_units=source,claims=[],uncovered=[],citation_occurrences=occurrences,
        references=list(refs.values()),anchors=[],terms=[],signals=signals,signal_reviews=[])
    if audit_required:
        skeleton=reference_audit.seed_refs(run,skeleton);occurrences=skeleton['citation_occurrences']
    save(run/'ledger_seed.json',skeleton)
    # One bounded extraction request per source paragraph; global records stay on disk.
    instruction=(SKILL/'references/logic-planning.md').read_text(encoding='utf-8')
    for p in source:
        sids={s['sid'] for s in p['sentences']}
        payload=dict(source_unit=p,citation_occurrences=[x for x in occurrences if x['sid'] in sids],signals=[x for x in signals if x['sid'] in sids])
        body=instruction+'\n\n'+json.dumps(payload,ensure_ascii=False,indent=2)
        require(count(body,c)<=c['budgets']['writer_input_tokens'], f'{p["para_id"]}: extraction request exceeds budget; divide the source paragraph with author agreement or adjust budget')
        path=run/'planning_inputs'/f'{p["para_id"]}.md';path.parent.mkdir(exist_ok=True);path.write_text(body,encoding='utf-8')
    manifest=read(run/'manifest.json');manifest.update(workflow_version=workflow_version,level=level,citation_mode=citation_mode,content_policy=content_policy,status='awaiting_fact_ledger',ledger_seed_sha256=sha(run/'ledger_seed.json'))
    if audit_required:manifest['references_checkpoint']=sha(run/'references_audit.json')
    if workflow_version>=3:
        (run/'author_request.md').write_text(read(run/'draft_plan.json').get('author_requirements',''),encoding='utf-8')
        manifest['author_request_sha256']=sha(run/'author_request.md')
    save(run/'manifest.json',manifest)
    return dict(run=str(run),status=manifest['status'],planning_inputs=str(run/'planning_inputs'))

def validate_ledger(run, ledger):
    manifest=read(run/'manifest.json');seed=read(run/'ledger_seed.json')
    if manifest.get('reference_audit_required'):
        import reference_audit
        reference_audit.validate_ledger_references(run,ledger)
    require(sha(run/'ledger_seed.json')==manifest['ledger_seed_sha256'],'Source seed changed')
    input_matches=sha(run/'input.md')==manifest['input_sha256']
    if manifest.get('workflow_version',2)<3:
        input_matches=input_matches or text_sha((run/'input.md').read_text(encoding='utf-8'))==manifest['input_sha256']
    require(input_matches,'Original draft changed')
    for key in ('source_units','citation_occurrences','signals'):
        require(ledger[key]==seed[key],f'Immutable source records changed: {key}')
    sents={s['sid']:s for p in seed['source_units'] for s in p['sentences']}
    claims=unique(ledger['claims'],'claim_id'); refs=unique(ledger['references'],'ref_key')
    anchors=unique(ledger['anchors'],'anchor_id'); occurrences=unique(seed['citation_occurrences'],'occurrence_id')
    for ref in seed['references']:
        require(ref['ref_key'] in refs and refs[ref['ref_key']]['original_number']==ref['original_number'],'Original reference identity changed')
    covered=set(); used_occ=set()
    for cid,cl in claims.items():
        require(cl.get('text_zh','').strip() and cl['sids'] and set(cl['sids'])<=sents.keys(),f'{cid}: source/text missing')
        require(len({sid.split('-')[0] for sid in cl['sids']})==1, f'{cid}: split cross-paragraph claims before planning')
        require(cl['type'] in {'background','finding','interpretation','limitation','proposal','scope','definition','example'},f'{cid}: type')
        require(cl['strength'] in {'established','reported','associated','suggested','possible','proposed','expected'},f'{cid}: strength')
        require(cl['polarity'] in {'positive','negative','mixed'},f'{cid}: polarity')
        for key in ('conditions','quantities','xrefs','citation_occurrences','relations'):require(isinstance(cl[key],list),f'{cid}: {key}')
        require(set(cl['xrefs'])<=anchors.keys(),f'{cid}: unknown anchor')
        require(set(cl['citation_occurrences'])<=occurrences.keys(),f'{cid}: unknown citation occurrence')
        expected=set()
        for oid in cl['citation_occurrences']:
            oc=occurrences[oid]; require(oc['sid'] in cl['sids'],f'{cid}: citation from another source sentence')
            expected.update(oc['ref_keys']);used_occ.add(oid)
        require(set(cl['citations'])==expected and expected<=refs.keys(),f'{cid}: reference attachment differs from source occurrence')
        for rel in cl['relations']:
            require(rel['to'] in claims and rel['type'] in {'cause','consequence','contrast','concession','addition','example_of','condition','comparison','specification'},f'{cid}: invalid relation')
        covered.update(cl['sids'])
    require(used_occ==occurrences.keys(),'Attach every original citation occurrence to a claim')
    for item in ledger['uncovered']:
        require(item['sid'] in sents and item['sid'] not in covered and item.get('reason','').strip(),'Explain uncovered source units')
        require(item.get('kind') in ('heading','transition'),'Substantive source sentences require claims')
        covered.add(item['sid'])
    require(covered==sents.keys(),'Source sentence coverage incomplete')
    reviews=unique(ledger['signal_reviews'],'signal_id')
    require(reviews.keys()=={x['signal_id'] for x in seed['signals']},'Review every number/negation signal')
    for signal in seed['signals']:
        r=reviews[signal['signal_id']]; require(r.get('note','').strip(),'Signal review needs contextual explanation')
        require(r.get('claims') and set(r['claims'])<=claims.keys(),'Signal review needs claims')
        require(all(signal['sid'] in claims[x]['sids'] for x in r['claims']),'Signal mapped to another sentence')
    if author.enabled(run):author.validate(run,ledger)
    return claims

def validate_plan(run, ledger, plan):
    claims=validate_ledger(run,ledger);manifest=read(run/'manifest.json');level=manifest['level']
    require(plan['level']==level,'Plan level differs from selected level')
    selected,selection=content_selection.project(ledger,plan,manifest.get('content_policy','preserve_all'))
    active={c['claim_id']:c for c in selected['claims']}
    paragraphs=plan['paragraphs']; unique(paragraphs,'new_para_id')
    source_ids=[p['para_id'] for p in ledger['source_units']]
    all_ids=[cid for p in paragraphs for cid in p['claim_order']]
    require(Counter(all_ids)==Counter(active.keys()),'Every retained claim needs one primary position')
    destinations={cid:p['new_para_id'] for p in paragraphs for cid in p['claim_order']}
    for occurrence in selected['citation_occurrences']:
        owners=[cid for cid,cl in active.items() if occurrence['occurrence_id'] in cl['citation_occurrences']]
        require(len({destinations[cid] for cid in owners})==1,'A planned citation must accompany its supporting claims')
    origins={cid:cl['sids'][0].split('-')[0] for cid,cl in claims.items()}
    if level in ('L0','L1'):
        require(len(paragraphs)==len(source_ids),'L0/L1 preserve paragraph count')
        require([p['target_source_para'] for p in paragraphs]==source_ids,'L0/L1 preserve paragraph slots')
    for p in paragraphs:
        require(re.fullmatch(r'[A-Za-z0-9_-]+',p['new_para_id']), 'Invalid paragraph identifier')
        require(p['main_point'].strip() and p['claim_order'],'Paragraph main point/claims required')
        require(p.get('ops'),'Document paragraph editing operations')
        require(set(p['main_point_claims'])<=set(p['claim_order']),'Main point must use this paragraph claims')
        require(set(p['source_paras'])=={origins[cid] for cid in p['claim_order']},'Source paragraph list mismatch')
        for op in p['ops']:
            require(op['op'] in OPS[level] and op.get('reason','').strip(),'Operation exceeds level or lacks reason')
        if level=='L0':
            expected=[cid for cid in claims if origins[cid]==p['target_source_para']]
            require(p['claim_order']==expected,'L0 preserves source claim order and ownership')
            require(not p.get('additions'),'L0 keeps the original structure')
        if level=='L1':
            dest=source_ids.index(p['target_source_para'])
            require(all(abs(source_ids.index(origins[x])-dest)<=1 for x in p['claim_order']),'L1 moves only between adjacent paragraphs')
            operations={x['op'] for x in p['ops']}
            if any(origins[x]!=p['target_source_para'] for x in p['claim_order']):
                require('MOVE_TO_ADJACENT_PARA' in operations,'Document the adjacent-paragraph move')
            same_origin=[x for x in p['claim_order'] if origins[x]==p['target_source_para']]
            original=[x for x in claims if x in same_origin]
            if same_origin!=original:require(bool(operations&{'REORDER_WITHIN_PARA','PROMOTE_TOPIC_SENTENCE'}),'Document the within-paragraph reorder')
        for add in p.get('additions',[]):
            require(add['op'] in OPS[level] and add['op'] in {'ADD_TRANSITION','SYNTHESIZE_TOPIC_SENTENCE'},'Invalid generated addition')
            require(add.get('text_zh','').strip() and add.get('claims') and set(add['claims'])<=set(p['claim_order']),'Addition needs existing claims and Chinese text')
            if add['op']=='ADD_TRANSITION':
                require(add.get('relation') in [r for cid in p['claim_order'] for r in claims[cid]['relations']],'Transition needs a ledger relation')
        require(p.get('domains') and all(x in DOMAINS.values() for x in p['domains']),'Paragraph domain required')
        require(p['section'] in ('abstract','introduction','any'),'Invalid section')
    # Source claim list itself must be ordered by source position.
    starts={s['sid']:s['start'] for p in ledger['source_units'] for s in p['sentences']}
    positions=[min(starts[s] for s in cl['sids']) for cl in claims.values()]
    require(positions==sorted(positions),'Ledger claims must follow source order')
    if author.enabled(run):author.validate(run,ledger,plan)
    return claims

def preview(run, ledger, plan):
    claims={x['claim_id']:x for x in ledger['claims']};refs={x['ref_key']:x for x in ledger['references']}
    sentences={s['sid']:s for p in ledger['source_units'] for s in p['sentences']}
    lines=[];changes=[]
    for p in plan['paragraphs']:
        lines.append('## '+p['new_para_id']+' · '+p['main_point'])
        for add in p.get('additions',[]):lines.append('【新增；待确认】'+add['text_zh']+'〔'+','.join(add['claims'])+'〕')
        order=p['claim_order'];i=0
        while i<len(order):
            cid=order[i];cl=claims[cid];sid=cl['sids'][0]
            group=[x for x in order if claims[x]['sids']==[sid]]
            complete=[x for x in claims if claims[x]['sids']==[sid]]
            if cl['sids']==[sid] and group==complete and order[i:i+len(group)]==group:
                text=sentences[sid]['text'];tags=group;i+=len(group)
            else:
                text=cl['text_zh'];tags=[cid];i+=1
                if cl['citations']:text+=' ['+','.join(str(refs[x]['original_number']) for x in cl['citations'])+']'
            lines.append(text+'〔'+','.join(tags)+'〕')
        lines.append('')
        changes.append(dict(paragraph=p['new_para_id'],source_paras=p['source_paras'],ops=p['ops'],additions=p.get('additions',[])))
    (run/'restructured_zh.md').write_text('\n\n'.join(lines),encoding='utf-8')
    save(run/'restructured_zh_changes.json',dict(changes=changes,diagnosis=plan.get('diagnosis',[]),author_queries=plan.get('author_queries',[])))

def accept_plan(c,run,ledger_path,plan_path):
    ledger=read(ledger_path);plan=read(plan_path);validate_plan(run,ledger,plan)
    if read(run/'manifest.json').get('reference_audit_required'):
        import reference_audit
        ledger=reference_audit.apply_support(run,ledger)
    prior=read(run/'manifest.json')
    if prior.get('author_edit_pending'):
        require(plan.get('author_edit_resolution',{}).get('edited_directory')==prior['author_edit_pending'] and plan['author_edit_resolution'].get('note','').strip(),'Reconcile the pending author edits in the plan')
    save(run/'fact_ledger.json',ledger);save(run/'logic_plan.json',plan)
    if prior.get('content_policy')=='argument_first':
        _,selection=content_selection.project(ledger,plan,'argument_first')
        save(run/'editorial_selection.json',selection)
    if author.enabled(run):
        m=read(run/'manifest.json');m.update(status='plan_ready',plan_hashes={name:sha(run/name) for name in ('fact_ledger.json','logic_plan.json')})
        if m.get('reference_audit_required'):m['support_checkpoint']=reference_audit.support_checkpoint(run)
        for key in ('structure_confirmation','chinese_hashes','author_edit_pending'):m.pop(key,None)
        save(run/'manifest.json',m)
        if m['level']=='L0':author.initial_source(run,ledger,plan)
        return dict(status=read(run/'manifest.json')['status'],next='candidates and assemble --stage zh' if m['level']!='L0' else 'candidates and assemble --stage en')
    preview(run,ledger,plan)
    m=read(run/'manifest.json');m.update(status='structure_confirmed' if m['level']=='L0' else 'awaiting_structure_confirmation',
        plan_hashes={name:sha(run/name) for name in ('fact_ledger.json','logic_plan.json','restructured_zh.md')})
    m.pop('structure_confirmation',None)
    if m.get('author_edit_pending'):
        m.pop('author_edit_pending',None)
    save(run/'manifest.json',m)
    return dict(status=m['status'],preview=str(run/'restructured_zh.md'))

def check_plan(run,confirmed=True):
    m=read(run/'manifest.json')
    if m.get('reference_audit_required'):
        import reference_audit
        require(m.get('support_checkpoint')==reference_audit.support_checkpoint(run),'Support review changed; revalidate and import the plan')
        reference_audit.support_validate(run,read(run/'fact_ledger.json'))
    require(not m.get('author_edit_pending'),'Reconcile author edits and regenerate the Chinese preview first')
    require(m.get('plan_hashes'),'Import and validate the ledger and plan first')
    for name,digest in m['plan_hashes'].items():require(sha(run/name)==digest,f'{name} changed; reimport the plan and renew confirmation')
    ledger=read(run/'fact_ledger.json');plan=read(run/'logic_plan.json');validate_plan(run,ledger,plan)
    if confirmed and m['level']!='L0':
        record=m.get('structure_confirmation',{})
        require(record.get('plan_hashes')==m['plan_hashes'] and record.get('author_message'),'Author confirmation of this Chinese version is required')
        if author.enabled(run):
            author.verify_chinese(run)
            require(record.get('chinese_hashes')==m.get('chinese_hashes'),'Confirmation belongs to an earlier Chinese draft')
            for role,digest in record.get('review_hashes',{}).items():require(sha(run/'zh_reviews'/f'{role}_review.json')==digest,'Chinese review changed after confirmation')
    if confirmed and author.enabled(run):author.verify_chinese(run)
    return ledger,plan

def confirm(run,author_message,evaluation=False):
    if author.enabled(run):return author.confirm(run,author_message,evaluation)
    check_plan(run,False);require(author_message.strip(),'Record the actual author confirmation message')
    m=read(run/'manifest.json');m['structure_confirmation']=dict(author_message=author_message,plan_hashes=m['plan_hashes'])
    m['status']='structure_confirmed';save(run/'manifest.json',m);return dict(status=m['status'])

def ingest_edits(run,path):
    ledger,plan=check_plan(run,False);edited=Path(path).read_text(encoding='utf-8')
    digest=text_sha(edited);directory=run/'author_edits'/digest[:16];directory.mkdir(parents=True,exist_ok=True)
    (directory/'edited_zh.md').write_text(edited,encoding='utf-8')
    known={x['claim_id'] for x in ledger['claims']};found=[];lines=[]
    for line in edited.splitlines():
        if not line.strip() or line.startswith('#'):continue
        tags=re.findall(r'〔([^〕]+)〕',line);ids=[x.strip() for tag in tags for x in tag.split(',')]
        require(set(ids)<=known,'Edited preview has an unknown claim tag; use untagged text for author additions')
        found.extend(ids);lines.append(dict(text=line,claims=ids,review='compare wording, conditions, strength, numbers and citations' if ids else 'author_added_candidate'))
    report=dict(edited_sha256=digest,base_plan_hashes=read(run/'manifest.json')['plan_hashes'],lines=lines,
        missing_claim_tags=sorted(known-set(found)),repeated_claim_tags={k:v for k,v in Counter(found).items() if v>1},
        next_step='Host reviews tagged edits; preserve changed facts as a new source draft and linked run, or update structure-only plan. Present renewed Chinese preview for confirmation.')
    save(directory/'change_candidates.json',report)
    m=read(run/'manifest.json');m['status']='awaiting_author_edit_reconciliation';m.pop('structure_confirmation',None)
    m['author_edit_pending']=str(directory);save(run/'manifest.json',m)
    return dict(review=str(directory/'change_candidates.json'),status=m['status'])

def paragraph_index(c):
    chunks={x['chunk_id']:x for x in rows(c['source']/'chunks.jsonl')};cards=[]
    for line,p in enumerate(rows(c['source']/'paragraph_patterns.jsonl'),1):
        ch=chunks[p['chunk_id']];moves=p['rhetorical_moves'];roles=[r for m in moves for r in m['roles']]
        # A coarse retrieval label, retaining the original authored progression.
        if 'SCOPE' in roles:label='scope_and_context'
        elif 'COMPARE' in roles:label='comparison'
        elif 'FIND' in roles:label='evidence_and_interpretation'
        elif 'GAP' in roles and 'CAUSE' in roles:label='gap_and_cause'
        elif 'DEF' in roles and 'GAP' in roles:label='definition_capability_limit'
        elif 'GAP' in roles:label='limitation_and_direction'
        elif 'DEF' in roles:label='definition_and_value'
        elif 'METHOD' in roles:label='method_and_application'
        else:label='background_and_value'
        cards.append(dict(chunk_id=p['chunk_id'],paper_id=p['paper_id'],domain=p['domain'],section=p['section_role'],
            paragraph_type=label,type_status='rule_proposed',roles=roles,source_quote=ch['text_clean'],
            rhetorical_moves=moves,abstract_pattern=p['abstract_pattern'],source_location=p['source_location'],
            source_path=str(c['source']/'paragraph_patterns.jsonl'),source_line=line))
    path=c['root']/'style/paragraph-types-v1';path.mkdir(parents=True,exist_ok=True)
    jl(path/'assignments.jsonl',cards)
    save(path/'manifest.json',dict(count=len(cards),types=dict(Counter(x['paragraph_type'] for x in cards)),
        classification='rule_proposed; task model selects using complete source paragraphs and authored moves',
        source_sha256=sha(c['source']/'paragraph_patterns.jsonl')))
    return cards

def paragraph_view(card):
    return {k:card[k] for k in ('chunk_id','paper_id','paragraph_type','source_quote','abstract_pattern')}

def candidates(c,run,pid,stage='en'):
    ledger,plan=check_plan(run,stage=='en');p=next(x for x in plan['paragraphs'] if x['new_para_id']==pid)
    directory=run/pid;directory.mkdir(exist_ok=True)
    query=p.get('query') or p['main_point'];sentences,meta=retrieve(c,p['domains'],p['section'],query,p.get('roles'))
    jl(directory/'candidates.jsonl',sentences);save(directory/'candidates_view.json',[plain_card(x) for x in sentences]);save(directory/'retrieval.json',meta)
    terms=set(tokenize(query));cards=[x for x in paragraph_index(c) if x['domain'] in p['domains'] and (p['section']=='any' or x['section']==p['section'])]
    cards.sort(key=lambda x:(x['paragraph_type']==p.get('paragraph_type'),len(terms&set(tokenize(x['source_quote'])))),reverse=True)
    chosen=[];papers=set();cap=c['budgets'].get('paragraph_candidate_tokens',2400)
    for card in cards:
        if card['paper_id'] in papers:continue
        view=paragraph_view(card)
        if count(json.dumps(chosen+[view],ensure_ascii=False),c)>cap:continue
        chosen.append(view);papers.add(card['paper_id'])
        if len(chosen)>=4:break
    require(chosen,'No complete paragraph fits paragraph candidate budget in this domain/section')
    jl(directory/'paragraph_candidates.jsonl',[x for x in cards if x['chunk_id'] in {v['chunk_id'] for v in chosen}])
    save(directory/'paragraph_candidates_view.json',chosen)
    return dict(paragraph=pid,sentence_candidates=len(sentences),paragraph_candidates=len(chosen),directory=str(directory))

def result_directory(run,pid,stage='en'):
    return run/pid/'zh' if stage=='zh' else run/pid

def assemble(c,run,pid,selection_path,stage='en'):
    require(stage in ('zh','en'),'Unknown writing stage')
    require(stage=='en' or author.enabled(run),'Chinese prose stage requires workflow v3')
    ledger,plan=check_plan(run,stage=='en');paras=plan['paragraphs'];i=next(i for i,p in enumerate(paras) if p['new_para_id']==pid);p=paras[i]
    candidate_directory=run/pid;directory=result_directory(run,pid,stage);directory.mkdir(parents=True,exist_ok=True)
    selection=read(selection_path);refs=[];paragraphs=[];sources=[]
    previous='';previous_hash=None
    if i:
        prior=result_directory(run,paras[i-1]['new_para_id'],stage)/'result.json';validate_result(c,run,paras[i-1]['new_para_id'],stage)
        previous=read(prior)['text'];previous_hash=sha(prior)
    allowed={x['style_id'] for x in rows(candidate_directory/'candidates.jsonl')}
    db=connect(c);cardmap={sid:read_card(db,sid) for sid in allowed};db.close()
    for pick in selection['language']:
        require(pick['id'] in cardmap and pick.get('reason','').strip(),'Select a language candidate with an adaptation reason')
        card=cardmap[pick['id']];sources.append(card)
        refs.append(dict(reference_id=pick['id'],source_quote=card['quote'],language_analysis=card['language_analysis'],expressions=card['expressions'],application=pick['reason']))
    allowed_paras={x['chunk_id'] for x in rows(candidate_directory/'paragraph_candidates.jsonl')}
    paramap={x['chunk_id']:x for x in paragraph_index(c) if x['chunk_id'] in allowed_paras}
    for pick in selection['paragraphs']:
        require(pick['id'] in paramap and pick.get('reason','').strip(),'Select a complete paragraph candidate with a reason')
        card=paramap[pick['id']];sources.append(card)
        if author.enabled(run):author.relation_selection(pick,p)
        ref=dict(reference_id=pick['id'],source_quote=card['source_quote'],progression=card['abstract_pattern'],application=pick['reason'])
        if author.enabled(run):ref['relationship_match']={k:pick[k] for k in ('relation_fit','source_relation','target_relation','adaptation','applies_to_claims')}
        paragraphs.append(ref)
    require(refs and paragraphs,'Both corpus language and paragraph examples are required')
    require(all(x['domain'] in p['domains'] and (p['section']=='any' or x['section']==p['section']) for x in sources),'Selected reference outside paragraph domain/section')
    unique(refs,'reference_id');unique(paragraphs,'reference_id')
    require(len(refs)<=c['budgets']['max_references'] and len(paragraphs)<=2,'Too many references')
    require(count(json.dumps(refs,ensure_ascii=False),c)<=c['budgets']['style_tokens'],'Language reference budget exceeded')
    require(count(json.dumps(paragraphs,ensure_ascii=False),c)<=c['budgets'].get('paragraph_tokens',600),'Complete paragraph reference budget exceeded')
    policy=read(run/'manifest.json').get('content_policy','preserve_all')
    clmap={x['claim_id']:x for x in ledger['claims']};claims=[clmap[x] for x in p['claim_order']]
    output_occurrences=[x for x in ledger['citation_occurrences'] if x['occurrence_id'] in {o for cl in claims for o in cl['citation_occurrences']}]
    excluded=[]
    if policy=='argument_first':
        claims,output_occurrences,excluded=content_selection.writer_projection(ledger,plan,pid,policy)
    sids={s for cl in claims for s in cl['sids']}
    anchors={x for cl in claims for x in cl['xrefs']}
    payload=dict(paragraph_plan=p,claims=claims,source_sentences=[s for x in ledger['source_units'] for s in x['sentences'] if s['sid'] in sids],
        citation_occurrences=output_occurrences,
        anchors=[x for x in ledger['anchors'] if x['anchor_id'] in anchors],glossary=ledger['terms'],
        previous_paragraph_en=previous,next_paragraph_main_point=paras[i+1]['main_point'] if i+1<len(paras) else '',
        reference_paragraphs=paragraphs,reference_language=refs,author_requirements=read(run/'draft_plan.json').get('author_requirements',''))
    if policy=='argument_first':
        payload['content_selection']=dict(policy=policy,source_context_exclusions=excluded,instruction='Write the selected claims in their planned order. Source sentences provide evidence context; excluded context stays outside the prose. Use the planned citation occurrences, which may combine repeated citations or accompany claims moved to separate paragraphs.')
    if author.enabled(run):author.add_writer_context(run,plan,p,payload,stage)
    if author.enabled(run):
        payload['paragraph_plan']={k:p[k] for k in ('new_para_id','main_point','main_point_claims','claim_order','subject_scope','required_relations','section')}
        payload['source_sentences']=[dict(sid=s['sid'],text=s['text']) for s in payload['source_sentences']]
    if stage=='zh':payload['previous_paragraph_zh']=payload.pop('previous_paragraph_en')
    system=(SKILL/'references'/('chinese-writing.md' if stage=='zh' else 'writing-principles.md')).read_text(encoding='utf-8')
    serialize=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':')) if author.enabled(run) else json.dumps(value,ensure_ascii=False,indent=2)
    messages=[dict(role='system',content=system),dict(role='user',content=serialize(payload))]
    tokens=count(serialize(messages),c)
    components={key:count(serialize(value),c) for key,value in payload.items()}
    if tokens>c['budgets']['writer_input_tokens']:
        save(directory/'budget_rejected.json',dict(stage=stage,actual_tokens=tokens,limit=c['budgets']['writer_input_tokens'],system_tokens=count(system,c),component_tokens=components))
    require(tokens<=c['budgets']['writer_input_tokens'],f'Writing payload {tokens} exceeds {c["budgets"]["writer_input_tokens"]} tokens; inspect budget_rejected.json and reduce redundant references/metadata')
    save(directory/'writer_messages.json',messages);save(directory/'selection.json',selection);jl(directory/'reference_sources.jsonl',sources)
    (directory/'writer_input.md').write_text(system+'\n\n'+messages[1]['content'],encoding='utf-8')
    save(directory/'assembly.json',dict(payload_sha256=sha(directory/'writer_messages.json'),plan_hashes=read(run/'manifest.json')['plan_hashes'],
        previous_result_sha256=previous_hash,tokens=tokens,component_tokens=components,source_hashes=source_hashes(c),paragraph_source_sha256=sha(c['source']/'paragraph_patterns.jsonl'),stage=stage,chinese_hashes=author.checkpoint(run) if author.enabled(run) and stage=='en' else {}))
    return dict(input=str(directory/'writer_input.md'),tokens=tokens)

def validate_result(c,run,pid,stage='en'):
    ledger,plan=check_plan(run,stage=='en');directory=result_directory(run,pid,stage);a=read(directory/'assembly.json');messages=read(directory/'writer_messages.json');payload=json.loads(messages[1]['content'])
    require(sha(directory/'writer_messages.json')==a['payload_sha256'],'Writing payload changed')
    require(a['plan_hashes']==read(run/'manifest.json')['plan_hashes'],'Writing payload uses an earlier plan')
    if author.enabled(run) and stage=='en':
        require(a.get('chinese_hashes')==author.checkpoint(run),'Writing input uses an earlier accepted Chinese/source draft')
        draft=read(run/'chinese_draft.json');expected=next(x['text'] for x in draft['paragraphs'] if x['paragraph_id']==pid)
        key='approved_chinese_paragraph' if draft['mode']=='model_composed' else 'accepted_source_paragraph'
        require(payload.get(key)==expected,'Writer input must contain the accepted paragraph verbatim')
    require(a['source_hashes']==source_hashes(c) and a['paragraph_source_sha256']==sha(c['source']/'paragraph_patterns.jsonl'),'Corpus changed; refresh the writing payload')
    paras=plan['paragraphs'];idx=next(i for i,p in enumerate(paras) if p['new_para_id']==pid)
    if idx:require(sha(result_directory(run,paras[idx-1]['new_para_id'],stage)/'result.json')==a['previous_result_sha256'],'Previous paragraph changed; refresh downstream writing inputs')
    result=read(directory/'result.json');text=result['text'];require(text.strip(),'Empty output')
    if author.enabled(run):require(not re.search(r'\n\s*\n',text),'One planned paragraph must produce one prose paragraph')
    claims={x['claim_id']:x for x in payload['claims']};seen=set();cursor=0
    if read(run/'manifest.json').get('content_policy')=='argument_first':
        expected_claims,expected_occurrences,_=content_selection.writer_projection(ledger,plan,pid,'argument_first')
        require(payload['claims']==expected_claims and payload['citation_occurrences']==expected_occurrences,'Writing input differs from the selected claims or planned evidence links')
    require(result.get('input_sha256')==a['payload_sha256'],'Output must identify its writing input hash')
    occurrences={x['occurrence_id']:x for x in payload['citation_occurrences']};used=[];bound_spans=[]
    for sentence in result['sentence_claims']:
        start,end=sentence['start'],sentence['end'];ids=set(sentence['claims'])
        require(cursor<=start<end<=len(text) and not text[cursor:start].strip(),'Sentence spans must cover output in order')
        require(ids and ids<=claims.keys(),'Each output sentence needs existing claim IDs')
        require(sentence.get('role','content') in ('content','summary','transition'),'Unknown sentence role')
        if sentence.get('role','content')=='content':seen.update(ids)
        fragment=text[start:end]
        for binding in sentence.get('citations',[]):
            oid=binding['occurrence_id'];require(oid in occurrences,'Unknown citation occurrence')
            bs,be=binding['start'],binding['end'];require(start<=bs<be<=end,'Citation must fall inside mapped sentence')
            match=TOKEN.fullmatch(text[bs:be]);require(match and match[1].split(',')==occurrences[oid]['ref_keys'],'Citation keys changed')
            if 'required_claim_ids' in occurrences[oid]:
                owners=set(occurrences[oid]['required_claim_ids'])
                require(owners & ids and owners <= seen | ids and set(binding['claims'])==owners,
                        'Planned citation must cover its supported claims in this sentence or preceding sentences of the same paragraph')
            else:
                owners={cid for cid in ids if oid in claims[cid]['citation_occurrences']}
                require(owners and set(binding['claims'])==owners,'Citation attachment requires corresponding claims')
            bound_spans.append((bs,be));used.append(oid)
        expected_xrefs={x for cid in ids for x in claims[cid]['xrefs']}
        actual_xrefs=set(XREF.findall(fragment));require(actual_xrefs<=expected_xrefs,'Cross reference attached to another claim')
        cursor=end
    require(not text[cursor:].strip() and seen==claims.keys(),'Claim or output coverage incomplete')
    require(Counter(used)==Counter({k:1 for k in occurrences}),'Every planned output citation must appear once')
    require(sorted(bound_spans)==[m.span() for m in TOKEN.finditer(text)],'Citation placeholder lacks an occurrence binding')
    require(set(XREF.findall(text))=={x for cl in claims.values() for x in cl['xrefs']},'Cross reference coverage changed')
    require(not CITE.search(text),'Use stable citation placeholders in writer output')
    references={x['reference_id']:x for x in payload['reference_language']+payload['reference_paragraphs']}
    require(result.get('style_alignment'),'Record actual corpus wording correspondences')
    for item in result['style_alignment']:
        require(item['reference_id'] in references and item.get('feature','').strip(),'Unknown style correspondence')
        require(item.get('output_span') and item['output_span'] in text,'Output style span mismatch')
        require(item.get('reference_span') and item['reference_span'] in references[item['reference_id']]['source_quote'],'Source style span mismatch')
    return result

def review_inputs(c,run,stage='en'):
    if author.enabled(run):return author.review_inputs(c,run,stage)
    ledger,plan=check_plan(run);outputs=[]
    for p in plan['paragraphs']:
        r=validate_result(c,run,p['new_para_id']);outputs.append(dict(paragraph_id=p['new_para_id'],text=r['text'],sentence_claims=r['sentence_claims']))
    text='\n\n'.join(x['text'] for x in outputs)
    (run/'draft_en.md').write_text(text+'\n',encoding='utf-8')
    directory=run/'reviews';directory.mkdir(exist_ok=True)
    if (directory/'snapshot.json').exists():
        archive=directory/'history'/sha(directory/'snapshot.json')[:16];archive.mkdir(parents=True,exist_ok=True)
        for previous in directory.glob('*.json'):shutil.copy2(previous,archive/previous.name)
    # Reader gets English only. Fidelity sees claims/plan/output, never style examples.
    requests={
      'fidelity':dict(instruction='逐条核对论断、条件、数字、极性、强度、引用分句归属，查找新增事实。返回 reviewed_claim_ids、issues（severity,claim_id,span,reason,fix）。',ledger=ledger,plan=plan,outputs=outputs),
      'reader':dict(instruction='只根据以下英文，返回每段的首句提纲、读完全段后的主旨、逐句承接、指代和卡顿点；issues 含 severity,paragraph_id,span,reason,fix。',english=text),
    }
    style=[]
    for p in plan['paragraphs']:
        payload=json.loads(read(run/p['new_para_id']/'writer_messages.json')[1]['content'])
        style.append(dict(paragraph_id=p['new_para_id'],text=read(run/p['new_para_id']/'result.json')['text'],references=payload['reference_language']))
    requests['style']=dict(instruction='独立比较英文与库内语言范例，逐段返回实际采用的句法、搭配、语态及其自然程度。检查生硬套句、原文片语照搬和领域错配。返回 paragraphs、issues（severity,paragraph_id,span,reason,fix）。',paragraphs=style)
    for name,payload in requests.items():save(directory/f'{name}_input.json',payload)
    for name,payload in requests.items():
        require(count(json.dumps(payload,ensure_ascii=False,indent=2),c)<=c['budgets'].get('review_input_tokens',16000),f'{name}: review exceeds chapter budget; prepare smaller section runs with shared reference identities')
    words=re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",TOKEN.sub('',text));sentences=re.split(r'(?<=[.!?])\s+',TOKEN.sub('',text))
    lengths=[len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",s)) for s in sentences if s.strip()]
    save(directory/'mechanical.json',dict(method='regex surface diagnostics',words=len(words),sentence_lengths=lengths,
        over_40_word_sentences=[i+1 for i,n in enumerate(lengths) if n>40],interpretation='Long sentences are review candidates; decide edits from meaning and corpus examples.'))
    executable=Path(c.get('fluency_python',''))
    if executable.is_file():
        command=[str(executable),'-X','utf8',str(SKILL/'scripts/fluency_metrics.py'),'--input',str(run/'draft_en.md'),'--output',str(directory/'mechanical.json')]
        baseline=c['root']/'style/fluency-baseline-v1/metrics.json'
        if baseline.exists():command+=['--baseline',str(baseline)]
        subprocess.run(command,check=True,capture_output=True,text=True,encoding='utf-8',timeout=120)
    snapshot={p['new_para_id']:sha(run/p['new_para_id']/'result.json') for p in plan['paragraphs']}
    save(directory/'snapshot.json',dict(results=snapshot,input_hashes={name:sha(directory/f'{name}_input.json') for name in requests}))
    return dict(review_directory=str(directory),draft=str(run/'draft_en.md'))

def write_mechanical(c,run,directory,text):
    """Retain the existing diagnostics for both native workflow versions."""
    words=re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",TOKEN.sub('',text))
    fragments=re.split(r'(?<=[.!?])\s+',TOKEN.sub('',text))
    lengths=[len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",s)) for s in fragments if s.strip()]
    save(directory/'mechanical.json',dict(method='regex surface diagnostics',words=len(words),sentence_lengths=lengths,over_40_word_sentences=[i+1 for i,n in enumerate(lengths) if n>40],interpretation='Locate sentences for contextual review.'))
    executable=Path(c.get('fluency_python',''))
    if executable.is_file():
        command=[str(executable),'-X','utf8',str(SKILL/'scripts/fluency_metrics.py'),'--input',str(run/'draft_en.md'),'--output',str(directory/'mechanical.json')]
        baseline=c['root']/'style/fluency-baseline-v1/metrics.json'
        if baseline.exists():command+=['--baseline',str(baseline)]
        subprocess.run(command,check=True,capture_output=True,text=True,encoding='utf-8',timeout=120)

def render_citations(text,ledger,mode):
    refs={x['ref_key']:x for x in ledger['references']};anchors={x['anchor_id']:x for x in ledger['anchors']};mapping={}
    def cite(match):
        nums=[]
        for key in match[1].split(','):
            require(key in refs,'Unknown reference key')
            if key not in mapping:mapping[key]=refs[key]['original_number'] if mode=='keep_original' else len(mapping)+1
            nums.append(mapping[key])
        return '['+','.join(map(str,nums))+']'
    output=TOKEN.sub(cite,text)
    def xref(match):
        require(match[1] in anchors and anchors[match[1]].get('render_label_en'),'Supply the approved English label for this anchor')
        return anchors[match[1]]['render_label_en']
    output=XREF.sub(xref,output)
    require('{{' not in output and '}}' not in output,'Unresolved placeholder')
    return output,dict(mode=mode,mapping=mapping,references=[dict(refs[k],final_number=v) for k,v in mapping.items()],unused_references=[k for k in refs if k not in mapping])

def finish(c,run):
    if read(run/'manifest.json').get('reference_audit_required'):
        import reference_audit
        reference_audit.delivery(run,read(run/'fact_ledger.json'))
    ledger,plan=check_plan(run);directory=run/'reviews';snapshot=read(directory/'snapshot.json');results=[]
    for p in plan['paragraphs']:
        pid=p['new_para_id'];results.append(validate_result(c,run,pid))
        require(all(isinstance(q,dict) and (q.get('status')=='resolved' or q.get('severity')=='advisory') for q in results[-1].get('queries',[])),'Resolve author queries before final delivery')
        require(sha(run/pid/'result.json')==snapshot['results'][pid],'Draft changed after review; regenerate review inputs')
    reports=author.verify_reports(run,'en') if author.enabled(run) else {}
    for role in (() if author.enabled(run) else ('fidelity','reader','style')):
        report=read(directory/f'{role}_review.json')
        require(report['input_sha256']==sha(directory/f'{role}_input.json')==snapshot['input_hashes'][role],'Review input hash mismatch')
        require(report.get('context_id') and report.get('model') and report.get('isolation')=='independent_context','Record actual independent reviewer context and model')
        require(report['status']=='completed' and not any(x['severity'] in ('major','blocking') for x in report['issues']),'Resolve substantive review issues and rerun affected reviews')
        if role=='fidelity':require(set(report['reviewed_claim_ids'])=={x['claim_id'] for x in ledger['claims']},'Fidelity review must cover every claim')
        else:require({x['paragraph_id'] for x in report['paragraphs']}=={x['new_para_id'] for x in plan['paragraphs']},'Reader review must cover every paragraph')
        reports[role]=report
    require(len({r['context_id'] for r in reports.values()})==len(reports),'Review roles require separate contexts')
    text='\n\n'.join(x['text'] for x in results);mode=read(run/'manifest.json')['citation_mode']
    output,mapping=render_citations(text,ledger,mode)
    (run/'output.md').write_text(output+'\n',encoding='utf-8');save(run/'citation_map.json',mapping)
    locations=[]
    for p,result in zip(plan['paragraphs'],results):
        for sentence_index,sentence in enumerate(result['sentence_claims'],1):
            for binding in sentence.get('citations',[]):locations.append(dict(paragraph_id=p['new_para_id'],sentence=sentence_index,**binding))
    mapping['occurrences']=locations;save(run/'citation_map.json',mapping)
    if read(run/'manifest.json').get('content_policy')=='argument_first':
        _,selection=content_selection.project(ledger,plan,'argument_first')
        mapping['source_disposition']=selection
        save(run/'editorial_selection.json',selection);save(run/'citation_map.json',mapping)
    save(run/'xref_map.json',dict(anchors=ledger['anchors'],occurrences=[dict(paragraph_id=p['new_para_id'],anchor_id=m[1],start=m.start(),end=m.end()) for p,r in zip(plan['paragraphs'],results) for m in XREF.finditer(r['text'])]))
    if mapping['references'] and all(x.get('entry_text') for x in mapping['references']):
        (run/'references_renumbered.md').write_text('\n\n'.join(f"[{x['final_number']}] {x['entry_text']}" for x in sorted(mapping['references'],key=lambda x:x['final_number']))+'\n',encoding='utf-8')
    save(run/'audit.json',dict(reviews=reports,mechanical=read(directory/'mechanical.json') if (directory/'mechanical.json').exists() else {'status':'not_run'},style_alignment=[x['style_alignment'] for x in results],
        revision_decisions=read(run/'revision_decisions.json') if (run/'revision_decisions.json').exists() else [],user_acceptance='pending'))
    if author.enabled(run):
        audit=read(run/'audit.json');m=read(run/'manifest.json')
        audit.update(workflow_version=3,author_requirements=plan['author_requirements'],accepted_source_hashes=author.checkpoint(run),structure_confirmation=m.get('structure_confirmation',{'mode':'source_preserved'}),review_dispatch=read(directory/'dispatch.json'),revision_decisions=read(directory/'revision_decisions.json') if (directory/'revision_decisions.json').exists() else [])
        if m['level']!='L0':
            audit['chinese_reviews']={role:read(run/'zh_reviews'/f'{role}_review.json') for role in ('fidelity','reader')}
            audit['chinese_review_dispatch']=read(run/'zh_reviews/dispatch.json')
            audit['chinese_revision_decisions']=read(run/'zh_reviews/revision_decisions.json') if (run/'zh_reviews/revision_decisions.json').exists() else []
        save(run/'audit.json',audit)
    m=read(run/'manifest.json');m.update(status='completed_development_evaluation' if m.get('task_kind')=='development_evaluation' else 'completed_independent_reviews',output_sha256=sha(run/'output.md'));save(run/'manifest.json',m)
    return dict(output=str(run/'output.md'),citation_map=str(run/'citation_map.json'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config');subs=parser.add_subparsers(dest='command',required=True)
    for command in ('plan','confirm','ingest-edits','candidates','assemble','preview','reviews','dispatch','finish'):
        p=subs.add_parser(command);p.add_argument('--run',required=True)
        if command=='plan':p.add_argument('--ledger',required=True);p.add_argument('--plan',required=True)
        if command=='confirm':
            p.add_argument('--author-message',required=True);p.add_argument('--evaluation',action='store_true')
        if command=='ingest-edits':p.add_argument('--input',required=True)
        if command in ('candidates','assemble'):p.add_argument('--paragraph',required=True)
        if command=='assemble':p.add_argument('--selection',required=True)
        if command in ('candidates','assemble','reviews','dispatch'):p.add_argument('--stage',choices=['zh','en'],default='en')
        if command=='dispatch':
            p.add_argument('--role',choices=['reader','fidelity','style'],required=True);p.add_argument('--context-id',required=True);p.add_argument('--model',required=True);p.add_argument('--model-id')
    args=parser.parse_args();c=config(args.config);run=Path(args.run)
    if args.command=='plan':result=accept_plan(c,run,args.ledger,args.plan)
    elif args.command=='confirm':result=confirm(run,args.author_message,args.evaluation)
    elif args.command=='ingest-edits':result=ingest_edits(run,args.input)
    elif args.command=='candidates':result=candidates(c,run,args.paragraph,args.stage)
    elif args.command=='assemble':result=assemble(c,run,args.paragraph,args.selection,args.stage)
    elif args.command=='preview':result=author.preview(c,run)
    elif args.command=='reviews':result=review_inputs(c,run,args.stage)
    elif args.command=='dispatch':result=author.dispatch(run,args.role,args.context_id,args.model,args.stage,args.model_id)
    else:result=finish(c,run)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
