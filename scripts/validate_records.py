"""Validate bounded inputs and traceable host outputs. Semantics reviewed by host/user."""
import argparse,json,re
from common import *

def validate(c,run,require_outputs=False):
    assert_fresh(c);plan=read(run/'draft_plan.json');manifest=read(run/'manifest.json')
    draft=(run/'input.md').read_text(encoding='utf-8');assert text_sha(draft)==manifest['input_sha256']
    chunks={x['chunk_id']:x for x in rows(c['source']/'chunks.jsonl')};db=connect(c)
    ref_count=0;align_count=0;cursor=0
    try:
        for unit in plan['units']:
            assert not draft[cursor:unit['start']].strip();assert draft[unit['start']:unit['end']]==unit['text'];cursor=unit['end']
            directory=run/unit['unit_id'];messages=read(directory/'writer_messages.json');pack=read(directory/'reference_pack.json')
            assert sha(directory/'writer_messages.json')==manifest['payload_hashes'][unit['unit_id']]
            assert count(json.dumps(messages,ensure_ascii=False,indent=2),c)<=c['budgets']['writer_input_tokens']
            assert count(json.dumps(pack,ensure_ascii=False,indent=2),c)<=c['budgets']['style_tokens']
            payload=json.loads(messages[1]['content']);assert payload['draft']['text']==unit['text'];assert payload['reference_pack']==pack
            for ref in pack:
                source=read_card(db,ref['style_id']);ch=chunks[source['chunk_id']];span=source['span']
                assert ch['text_clean'][span['start']:span['end']]==ref['source_quote']==source['quote']
                assert ref['language_analysis']==source['language_analysis'];assert ref['expressions']==source['expressions']
                assert source['domain'] in unit['domains'];ref_count+=1
            if require_outputs:
                result=read(directory/'result.json');assert result['text'].strip()
                assert result['reviewer']=='current_skill_host'
                for key in ['facts_and_numbers','logic_and_order','terminology_and_scope','style_fit']:
                    item=result['audit'][key];assert item['status'] in ['checked','author_query'];assert item['note'].strip()
                ids={x['reference_id']:x for x in pack}
                for alignment in result['style_alignment']:
                    assert alignment['reference_id'] in ids
                    assert alignment['output_span'] and alignment['output_span'] in result['text']
                    assert alignment['reference_span'] and alignment['reference_span'] in ids[alignment['reference_id']]['source_quote']
                    assert alignment['feature'].strip();align_count+=1
                assert result['style_alignment'], 'Record concrete stylistic correspondences for the reviewed draft'
                # A factual-number mismatch is returned for review, not silently normalized.
                numbers=lambda t:Counter(re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?',t))
                if numbers(unit['text'])!=numbers(result['text']):
                    assert result.get('number_change_review'), 'Numeric forms changed; record concrete review'
        assert not draft[cursor:].strip()
    finally:
        db.close()
    return dict(status='passed',units=len(plan['units']),source_references=ref_count,style_alignments=align_count,
        source_quotes_verified=True,draft_coverage_verified=True,payload_budgets_verified=True,
        output_check='host review with exact span/ID checks' if require_outputs else 'inputs only',
        tokenizer=c['tokenizer'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--run',required=True);p.add_argument('--outputs',action='store_true');a=p.parse_args()
    print(json.dumps(validate(config(a.config),Path(a.run),a.outputs),ensure_ascii=False,indent=2))
