"""Indexed candidate retrieval; return only a bounded candidate view to the host."""
import argparse,json
from common import *

def retrieve(c,domains,section,query,roles=None):
    assert_fresh(c);db=connect(c)
    where='c.domain IN ('+','.join('?' for _ in domains)+')';params=list(domains)
    if section!='any':where+=' AND c.section=?';params.append(section)
    if roles:
        where+=' AND ('+' OR '.join("instr('|'||c.roles||'|',?)>0" for _ in roles)+')'
        params.extend('|'+r+'|' for r in roles)
    terms=list(dict.fromkeys(tokenize(query)))[:96]
    expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
    found=[]
    if expression:
        found=db.execute('SELECT c.payload,bm25(card_fts) AS score FROM card_fts JOIN cards c ON c.id=card_fts.rowid WHERE card_fts MATCH ? AND '+where+' ORDER BY score,c.style_id LIMIT ?', [expression]+params+[c['retrieval']['candidate_scan_limit']]).fetchall()
    mode='fts5_bm25'
    if not found:
        mode='metadata_only_no_lexical_hit'
        found=db.execute('SELECT c.payload,0 AS score FROM cards c WHERE '+where+' ORDER BY c.style_id LIMIT ?',params+[c['retrieval']['candidate_scan_limit']]).fetchall()
    db.close()
    candidates=[];seen=set();papers=Counter();families=Counter()
    # Two passes: cross-paper/family diversity first, then relevant remaining items.
    ordered=[(json.loads(r['payload']),r['score']) for r in found]
    for strict in [True,False]:
        for card,score in ordered:
            if card['style_id'] in seen:continue
            if strict and (papers[card['paper_id']]>=2 or families[card['family_id']]>=1):continue
            candidates.append(dict(card,retrieval_score=score));seen.add(card['style_id'])
            papers[card['paper_id']]+=1;families[card['family_id']]+=1
    view=bounded_candidates(candidates,c);ids={x['style_id'] for x in view}
    return [x for x in candidates if x['style_id'] in ids],dict(mode=mode,domains=domains,section=section,roles=roles or [],
        query=query,candidate_tokens=count(json.dumps(view,ensure_ascii=False,indent=2),c),candidate_limit=c['budgets']['candidate_tokens'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--domain',required=True);p.add_argument('--section',default='any');p.add_argument('--query',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    c=config(a.config);items,meta=retrieve(c,domain_values(a.domain),a.section,a.query)
    save(a.output,dict(candidates=items,retrieval=meta));print(json.dumps(meta,ensure_ascii=False))
