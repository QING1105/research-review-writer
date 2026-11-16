"""Create/update the local source-backed style index from existing annotations."""
from collections import Counter,defaultdict
import argparse,json,re,sqlite3
from common import *

PATTERNS=[('by_ing',r'^By\s+\w+ing\b'),('relative_which',r',\s*which\b'),
 ('concession',r'^(Although|While|Despite)\b'),('emerged_as',r'\b(?:have|has) emerged as\b'),
 ('thereby_ing',r'\bthereby\s+\w+ing\b'),('purpose_to',r'^To\s+\w+'),
 ('comparison',r'^(Compared|Unlike)\b'),('gerund_subject',r'^(Preserving|Understanding|Integrating)\b'),
 ('used_to',r'\b(?:have|has) been used to\b'),('review_scope',r'\bIn this review\b')]

def build(c):
    hashes=source_hashes(c);c['runtime'].mkdir(parents=True,exist_ok=True)
    old=read(c['runtime']/'index-manifest.json') if (c['runtime']/'index-manifest.json').exists() else None
    if old and old['source_hashes']==hashes and c['db'].exists():return dict(status='unchanged',**old)
    chunks={x['chunk_id']:x for x in rows(c['source']/'chunks.jsonl')}
    args={x['sentence_id']:x for x in rows(c['source']/'argumentation.jsonl')}
    source_lines={x['chunk_id']:i for i,x in enumerate(rows(c['source']/'chunks.jsonl'),1)}
    cards=[];excluded=Counter();groups=defaultdict(list)
    for line,l in enumerate(rows(c['source']/'language_realization.jsonl'),1):
        if l['selection']['status']!='selected_expression_candidate':excluded[l['selection']['status']]+=1;continue
        if l.get('editorial_flags'):excluded['editorial_flags_present']+=1;continue
        ch=chunks[l['chunk_id']];s=l['source_span'];quote=s['quote']
        assert ch['text_clean'][s['start']:s['end']]==quote
        roles=args[l['sentence_id']]['labels']['sentence_roles']
        hints=[name for name,pat in PATTERNS if re.search(pat,quote,re.I)]
        hint=hints[0] if hints else 'other'
        group='|'.join([ch['domain'],ch['section_role'],','.join(sorted(roles)),hint])
        family='F-'+text_sha(group)[:16]
        card=dict(style_id='ST-'+l['sentence_id'],family_id=family,family_hint=hint,
            grouping_method='domain_section_existing_roles_surface_hint; authored explanation is authoritative',
            chunk_id=l['chunk_id'],sentence_id=l['sentence_id'],paper_id=ch['paper_id'],
            domain=ch['domain'],section=ch['section_role'],roles=roles,quote=quote,
            language_analysis=l['labels']['analysis'],
            expressions=[x['quote'] for x in l['labels'].get('authored_focus_spans',[])],
            span=s,title=ch['title'],doi=ch['doi'],source_location=ch['source_location'],
            source_storage={'chunk_file':str(c['source']/'chunks.jsonl'),'chunk_line':source_lines[ch['chunk_id']],
                            'language_file':str(c['source']/'language_realization.jsonl'),'language_line':line},
            review_status=l['review'],selection_status=l['selection']['status'])
        cards.append(card);groups[family].append(card)
    # Transactional replacement of derived index contents only.
    db=connect(c)
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY,style_id TEXT UNIQUE,domain TEXT,section TEXT,roles TEXT,family TEXT,payload TEXT)')
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS card_fts USING fts5(terms)')
        db.execute('DELETE FROM card_fts');db.execute('DELETE FROM cards')
        for n,card in enumerate(cards,1):
            db.execute('INSERT INTO cards VALUES (?,?,?,?,?,?,?)',(n,card['style_id'],card['domain'],card['section'],'|'.join(card['roles']),card['family_id'],json.dumps(card,ensure_ascii=False)))
            db.execute('INSERT INTO card_fts(rowid,terms) VALUES (?,?)',(n,' '.join(tokenize(card['quote']+' '+card['language_analysis']))))
        db.execute('CREATE INDEX IF NOT EXISTS cards_domain_section ON cards(domain,section)')
    db.close()
    jl(c['runtime']/'cards.jsonl',cards)
    jl(c['runtime']/'families.jsonl',[dict(family_id=k,domain=v[0]['domain'],section=v[0]['section'],roles=v[0]['roles'],
        surface_hint=v[0]['family_hint'],papers=len({x['paper_id'] for x in v}),sentences=len(v),style_ids=[x['style_id'] for x in v]) for k,v in groups.items()])
    manifest=dict(index_version='source-language-v1',source_hashes=hashes,papers=len({x['paper_id'] for x in cards}),
        corpus_papers=len({x['paper_id'] for x in chunks.values()}),corpus_chunks=len(chunks),cards=len(cards),
        families=len(groups),excluded=dict(excluded),update_mode='hash-triggered transactional rebuild',
        semantic_grouping_status='existing authored labels; surface families are retrieval grouping, not new model judgments')
    save(c['runtime']/'index-manifest.json',manifest);return dict(status='built',**manifest)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config');a=p.parse_args();print(json.dumps(build(config(a.config)),ensure_ascii=False))
