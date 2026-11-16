"""Shared project, source and bounded-payload utilities; no model API calls."""
from pathlib import Path
from collections import Counter
import hashlib, json, os, re, sqlite3, sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / '.runtime/packages'))
os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(SKILL / '.runtime/tokenizer-cache'))
DOMAINS = {
 'D01':'01_living_tissue_diagnosis', 'D02':'02_patient_derived_organoids',
 'D03':'03_organoid_on_chip','D04':'04_spatiotemporal_molecular_pathology',
 'D05':'05_pathological_quality_control','D06':'06_spatiotemporal_traceability',
 'D07':'07_functional_precision_oncology'}

def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rows(path):
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def jl(path, items):
    Path(path).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items),encoding='utf-8')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def text_sha(text):return hashlib.sha256(text.encode()).hexdigest()
def config(path=None):
    # An explicit config is self-contained; otherwise merge the private local
    # override into the public template. Relative data paths use the Skill root.
    c=read(path or SKILL/'assets/project-template.yaml')
    if path is None and (SKILL/'project.local.json').is_file():
        def merge(base, extra):
            for key, value in extra.items():
                if isinstance(value,dict) and isinstance(base.get(key),dict):merge(base[key],value)
                else:base[key]=value
        merge(c,read(SKILL/'project.local.json'))
    root=Path(c['corpus_root'])
    if not root.is_absolute():root=(SKILL/root).resolve()
    c['root']=root;c['source']=root/'annotations'/c['annotation_version']
    c['runtime']=root/c['runtime_directory'];c['runs']=root/c['runs_directory']
    c['db']=c['runtime']/'style-index.sqlite3'
    return c

def recordable_config(c):
    """Keep operational settings in run records without copying credentials."""
    private={'api_key','ncbi_api_key','contact_email','email','mailto','password',
             'secret','token','access_token','authorization','client_secret'}
    def scrub(value):
        if isinstance(value,dict):
            return {key:('[redacted]' if str(key).lower() in private and val else scrub(val))
                    for key,val in value.items() if not isinstance(val,Path)}
        if isinstance(value,list):return [scrub(val) for val in value]
        return value
    return scrub(c)
def encoding(c):
    import tiktoken
    return tiktoken.get_encoding(c['tokenizer']['encoding'])
def count(text,c):return len(encoding(c).encode(text,disallowed_special=()))
def source_hashes(c):return {n:sha(c['source']/n) for n in ['chunks.jsonl','language_realization.jsonl','argumentation.jsonl']}
def domain_values(value):
    items=[DOMAINS.get(x.strip().upper(),x.strip()) for x in value.split(',')]
    if not items or any(x not in DOMAINS.values() for x in items):raise ValueError('domain must be D01..D07 or their full names; separate multiple domains with commas')
    return list(dict.fromkeys(items))
def tokenize(text):
    out=re.findall(r'[a-z]+(?:-[a-z]+)*',text.lower())
    for s in re.findall(r'[\u4e00-\u9fff]+',text):out.extend(s[i:i+2] for i in range(len(s)-1))
    return out
def connect(c):
    db=sqlite3.connect(c['db']);db.row_factory=sqlite3.Row;return db
def read_card(db,style_id):
    row=db.execute('SELECT payload FROM cards WHERE style_id=?',(style_id,)).fetchone()
    if row is None:raise ValueError(f'Unknown style_id: {style_id}')
    return json.loads(row['payload'])
def assert_fresh(c):
    manifest=read(c['runtime']/'index-manifest.json')
    if manifest['source_hashes']!=source_hashes(c):raise ValueError('Source changed; run measure_style.py to update the index')
    return manifest
def plain_card(card):
    return {k:card[k] for k in ['style_id','paper_id','roles','quote','language_analysis','expressions']}
def bounded_candidates(cards,c):
    chosen=[]
    for card in cards:
        proposed=chosen+[plain_card(card)]
        if count(json.dumps(proposed,ensure_ascii=False,indent=2),c)>c['budgets']['candidate_tokens']:continue
        chosen=proposed
        if len(chosen)>=c['budgets']['max_candidates']:break
    return chosen
def split_draft(text,c):
    units=[];limit=c['budgets']['draft_unit_tokens']
    # Paragraphs separated by blank lines; retain exact offsets and all non-space characters.
    for number,m in enumerate(re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)',text),1):
        start,end=m.span();fragment=text[start:end]
        if count(fragment,c)<=limit:spans=[(start,end)]
        else:
            ends=[start+x.end() for x in re.finditer(r'[。！？](?:[”’])?|[.!?](?=\s|$)',fragment)]
            ends=sorted(set(ends+[end]));spans=[];cursor=start;last=start
            for stop in ends:
                if count(text[cursor:stop],c)>limit:
                    if last==cursor:raise ValueError(f'Paragraph {number} has a sentence exceeding draft_unit_tokens; raise the configured unit budget')
                    spans.append((cursor,last));cursor=last
                    if count(text[cursor:stop],c)>limit:raise ValueError(f'Paragraph {number} has an over-budget sentence')
                last=stop
            if cursor<end:spans.append((cursor,end))
        for sub,(a,b) in enumerate(spans,1):units.append(dict(unit_id=f'P{number:03}-U{sub:02}',paragraph_id=f'P{number:03}',start=a,end=b,text=text[a:b]))
    cursor=0
    for u in units:
        assert not text[cursor:u['start']].strip();assert text[u['start']:u['end']]==u['text'];cursor=u['end']
    assert not text[cursor:].strip()
    if not units:raise ValueError('Input draft is empty')
    return units
