"""Read selected source cards and assemble a bounded writing payload."""
import argparse,json
from common import *

def assemble(c,run,selection):
    if read(run/'manifest.json').get('workflow_version')==2:
        raise ValueError('Use logic_flow.py assemble --paragraph <id> for ledger-based runs')
    assert_fresh(c);plan=read(run/'draft_plan.json');selected=read(selection)
    db=connect(c);budgets=[]
    try:
        for unit in plan['units']:
            uid=unit['unit_id'];directory=run/uid;allowed={x['style_id'] for x in rows(directory/'candidates.jsonl')}
            picks=selected['units'].get(uid,[])
            if not picks:raise ValueError(f'{uid}: choose at least one source-backed style example')
            packed=[];used=set();quotes=set();dropped=[]
            for pick in picks:
                sid=pick['style_id']
                if sid not in allowed:raise ValueError(f'{uid}: selection not in candidate set: {sid}')
                if not pick.get('reason','').strip():raise ValueError('Every selection requires a concrete adaptation reason')
                if pick.get('applies_to')!=uid:raise ValueError('applies_to must identify the current unit')
                card=read_card(db,sid)
                if sid in used or card['quote'] in quotes:dropped.append(dict(style_id=sid,reason='duplicate'));continue
                ref=dict(reference_id=f'R{len(packed)+1:02}',style_id=sid,applies_to=uid,application=pick['reason'],
                    source_quote=card['quote'],language_analysis=card['language_analysis'],expressions=card['expressions'])
                proposed=packed+[ref]
                if len(proposed)>c['budgets']['max_references'] or count(json.dumps(proposed,ensure_ascii=False,indent=2),c)>c['budgets']['style_tokens']:
                    dropped.append(dict(style_id=sid,reason='style_budget'));continue
                packed=proposed;used.add(sid);quotes.add(card['quote'])
            if not packed:raise ValueError(f'{uid}: style budget cannot fit any complete reference')
            system=(SKILL/'references/review-writing.md').read_text(encoding='utf-8')
            user=dict(task={'domains':unit['domains'],'section':unit['section'],'mode':'translate_polish_preserve_structure'},
                      draft={'unit_id':uid,'text':unit['text'],'existing_relations':unit.get('existing_relations',[])},reference_pack=packed,
                      author_requirements=plan.get('author_requirements',''))
            messages=[dict(role='system',content=system),dict(role='user',content=json.dumps(user,ensure_ascii=False,indent=2))]
            serialized=json.dumps(messages,ensure_ascii=False,indent=2);request_tokens=count(serialized,c)
            if request_tokens>c['budgets']['writer_input_tokens']:raise ValueError(f'{uid}: serialized writing payload exceeds budget; reduce selected references or draft unit size')
            save(directory/'reference_pack.json',packed);save(directory/'writer_messages.json',messages)
            # Read this file only at the writing step; filesystem paths stay out of writing content.
            (directory/'writer_input.md').write_text(system+'\n\n'+messages[1]['content'],encoding='utf-8')
            provenance=[read_card(db,p['style_id']) for p in packed];jl(directory/'reference_sources.jsonl',provenance)
            budget=dict(unit_id=uid,tokenizer=c['tokenizer'],style_tokens=count(json.dumps(packed,ensure_ascii=False,indent=2),c),
                input_tokens=request_tokens,limits=c['budgets'],dropped=dropped,
                measurement_scope='serialized task payload in configured reference encoding; host conversation overhead excluded')
            save(directory/'budget.json',budget);budgets.append(budget)
    finally:
        db.close()
    save(run/'style_selection.json',selected)
    manifest=read(run/'manifest.json');manifest.update(status='ready_to_write',selection_model=selected.get('model_id'),
        payload_hashes={u['unit_id']:sha(run/u['unit_id']/'writer_messages.json') for u in plan['units']})
    save(run/'manifest.json',manifest);return budgets

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--run',required=True);p.add_argument('--selection',required=True);a=p.parse_args()
    print(json.dumps(assemble(config(a.config),Path(a.run),Path(a.selection)),ensure_ascii=False))
