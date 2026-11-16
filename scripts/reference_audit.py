"""Reference identity audit and independent claim-support contracts.
All scientific metadata proposals originate in retained database responses.
"""
import argparse, difflib, json, re, time, unicodedata, zipfile, shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from common import *

def need(ok,msg):
    if not ok:raise ValueError(msg)
def now():return datetime.now(timezone.utc).isoformat()
def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower())
def surname(s):
    s=re.sub(r'\bet al\.?','',s).strip(' .,')
    return re.sub(r'\s+[A-Z][A-Z. -]*$','',s).split(',')[0].strip()
def expanded_pages(s):
    m=re.fullmatch(r'([A-Za-z]*)(\d+)[-–]([A-Za-z]*)(\d+)',s)
    if not m:return s,False
    prefix,a,_,b=m.groups()
    if len(b)>len(a):return s,True
    if len(b)<len(a):b=a[:len(a)-len(b)]+b
    return prefix+a+'-'+prefix+b,int(b)<int(a)
def document(path):
    path=Path(path);fields=[]
    if path.suffix.lower()=='.docx':
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        root=ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'));paras=[]
        for p in root.findall('.//w:body//w:p',ns):
            parts=[]
            for r in p.findall('.//w:r',ns):
                value=''.join(x.text or '' for x in r.findall('.//w:t',ns))
                sup=r.find('w:rPr/w:vertAlign',ns)
                if sup is not None and sup.get('{'+ns['w']+'}val')=='superscript' and re.fullmatch(r'\d+(?:[-–,]\d+)*',value):value='<sup>'+value+'</sup>'
                parts.append(value)
            if ''.join(parts).strip():paras.append(''.join(parts))
        fields=[x.text or '' for x in root.findall('.//w:instrText',ns)]
        text='\n\n'.join(paras)
    else:text=path.read_text(encoding='utf-8-sig').replace('\r\n','\n')
    match=re.search(r'(?im)^\s*#{0,6}\s*(?:References|Bibliography|参考文献)\s*[:：]?\s*$',text)
    return (text[:match.start()].rstrip() if match else text, text[match.end():].strip() if match else '',fields)

def parse_entry(text,i):
    raw=text.strip();num=re.match(r'^\s*\[?(\d+)\]?[.)]?\s+',raw)
    if num:i=int(num[1]);raw=raw[num.end():]
    doi=re.search(r'10\.\d{4,9}/[^\s<>]+',raw);pmid=re.search(r'PMID\s*:?\s*(\d+)',raw,re.I)
    p={'first_author':'','authors':[],'title':'','journal':'','year':None,'volume':'','issue':'','pages':'','doi':doi[0].rstrip('.,;') if doi else None,'pmid':pmid[1] if pmid else None}
    # GB/T and Vancouver use an author block terminated by et al. or a period.
    m=re.match(r'((?:[A-Za-z]\.\s*){2}|.+?et al\.|.+?\.)(?:\s+)(.+)',raw)
    if m:
        auth,tail=m.groups();p['authors']=[surname(x) for x in auth.split(',') if x.strip() and 'et al' not in x]
        p['first_author']=p['authors'][0] if p['authors'] else ''
        b=re.search(r'^(.*?)\s*\[J\]\.\s*(.*?),\s*(\d{4}),\s*(\d+)(?:\(([^)]+)\))?\s*:\s*([^\.]+)',tail)
        if not b:b=re.search(r'^(.*?)\.\s*(.*?)\s*[.,]?\s*(\d{4})\s*;\s*(\d+)(?:\(([^)]+)\))?\s*:\s*([^\.]+)',tail)
        if b:p.update(zip(('title','journal','year','volume','issue','pages'),b.groups()));p['year']=int(p['year'])
    apa=re.match(r'^(.*?)\((\d{4})\)\.\s*(.*?)\.\s*(.*?),\s*(\d+)(?:\(([^)]+)\))?\s*,\s*([^\.]+)',raw)
    if apa:
        auth,year,title,journal,vol,issue,pages=apa.groups();p.update(first_author=auth.split(',')[0].strip(),authors=[auth.split(',')[0].strip()],year=int(year),title=title,journal=journal,volume=vol,issue=issue,pages=pages)
    flags=[];p['issue']=p['issue'] or ''
    if expanded_pages(p['pages'])[1]:flags.append('pages_invalid')
    if len(norm(p['first_author']))<2 or norm(p['first_author'])=='anonymous' or re.fullmatch(r'(?:[A-Za-z]\.\s*)+[A-Za-z]?\.?',p['first_author']):flags.append('author_invalid')
    if p['year'] and not 1900<=p['year']<=datetime.now().year:flags.append('year_invalid')
    return dict(ref_key=f'REF{i:03}',original_number=i,entry_text=text,parsed=p,parse_status='parsed' if p['title'] else 'unparsed',offline_flags=flags,status='pending',retracted=None,retraction_status='pending',queries=[],decision=None)

def parse(path,run):
    run=Path(run);run.mkdir(parents=True,exist_ok=True);body,bibliography,fields=document(path)
    original=run/('reference_source'+Path(path).suffix.lower())
    if Path(path).resolve()!=original.resolve():
        if original.exists():need(sha(original)==sha(path),'Use a new audit run for a changed source')
        else:shutil.copyfile(path,original)
    (run/'reference_body.md').write_text(body,encoding='utf-8')
    entries=[parse_entry(x,i) for i,x in enumerate(re.split(r'\n\s*\n|\n(?=\[?\d+[\].)])',bibliography),1) if x.strip()]
    if len(entries)==1 and '\n' in bibliography:entries=[parse_entry(x,i) for i,x in enumerate(bibliography.splitlines(),1) if x.strip()]
    for field in fields:
        start=field.find('{')
        if 'ZOTERO_ITEM' in field and start>=0:
            try:
                item=json.loads(field[start:])
                for citation in item.get('citationItems',[]):
                    data=citation.get('itemData',{})
                    for e in entries:
                        if norm(data.get('title','')) and norm(data['title'])==norm(e['parsed']['title']):
                            for k in ('DOI','PMID'):
                                if data.get(k):e['parsed'][k.lower()]=str(data[k]);e.setdefault('identifier_origin',{})[k.lower()]='zotero_field'
            except ValueError:pass
    keys={e['ref_key'] for e in entries};markers=[]
    for m in re.finditer(r'\[(\d+(?:\s*[-–,，]\s*\d+)*)\]|<sup>(\d+(?:[-–,]\d+)*)</sup>',body):
        if m[2] and re.match(r'\s*(?:I\b|iodine\b|[A-Z][a-z]?\b)',body[m.end():]):continue
        from logic_flow import cite_keys
        refs=cite_keys(m[1] or m[2]);markers.append(dict(start=m.start(),end=m.end(),text=m[0],ref_keys=refs))
        for ref in refs:
            if ref not in keys:
                e=parse_entry('',int(ref[3:]));e['offline_flags']=['missing_bibliography_entry'];entries.append(e);keys.add(ref)
    mentions=[]
    for m in re.finditer(r"([A-ZÀ-Ž][\wÀ-ž’'\-]+)(?:\s+et\s+al\.?|(?=,\s*(?:19|20)\d{2}\)))",body):
        name=m[1];first=[e['ref_key'] for e in entries if norm(e['parsed']['first_author'])==norm(name)]
        weak=[e['ref_key'] for e in entries if norm(name) in [norm(a) for a in e['parsed']['authors'][1:]]]
        a=max(body.rfind('\n\n',0,m.start())+2,0);b=body.find('\n\n',m.end());sentence=body[a:b if b>=0 else len(body)]
        years=re.findall(r'\b(?:19|20)\d{2}\b',body[m.end():m.end()+16])
        mentions.append(dict(mention_id=f'M{len(mentions)+1:03}',surname=name,start=m.start(),end=m.end(),sentence=sentence,years=years,status='matched' if len(first)==1 else 'ambiguous_mention' if first else 'weak_match' if weak else 'orphan_mention',candidates=first or weak,queries=[]))
    used={k for m in markers for k in m['ref_keys']}|{k for m in mentions if m['status'] in ('matched','ambiguous_mention') for k in m['candidates']}
    duplicates={}
    for e in entries:
        if e['ref_key'] not in used:e['offline_flags'].append('unused')
        p=e['parsed'];key=p['doi'] or p['pmid'] or (norm(p['first_author']),p['year'],p['pages'].split('-')[0])
        if key in duplicates:e['offline_flags'].append('duplicate');e['duplicate_of']=duplicates[key]
        else:duplicates[key]=e['ref_key']
    for m in mentions:
        if m['status']=='matched' and m['years']:
            e=next(e for e in entries if e['ref_key']==m['candidates'][0])
            if str(e['parsed']['year']) not in m['years']:m['flags']=['year_mismatch']
    audit=dict(version=1,source_sha256=sha(original),body_sha256=sha(run/'reference_body.md'),doc=dict(inline_markers='present' if markers else 'absent' if entries else 'not_applicable',n_entries=len(entries),n_mentions=len({norm(m['surname']) for m in mentions}),n_mention_occurrences=len(mentions),manager_fields=fields),entries=entries,markers=markers,mentions=mentions,mapping=dict(origin=None,pairs=[]),waivers=[])
    save(run/'references_audit.json',audit);queries(run,audit)
    proposals=[];paras=body.split('\n\n')
    for e in entries:
        terms=set(tokenize(e['parsed']['title']));ranked=sorted(enumerate(paras,1),key=lambda x:len(terms&set(tokenize(x[1]))),reverse=True)[:3]
        proposals.append(dict(ref_key=e['ref_key'],mentions=[m for m in mentions if e['ref_key'] in m['candidates']],paragraph_candidates=[dict(paragraph=i,text=t,overlap=len(terms&set(tokenize(t)))) for i,t in ranked if terms&set(tokenize(t))]))
    save(run/'proposed_mapping.json',proposals)
    (run/'proposed_mapping.md').write_text('# 引用对应候选：供作者确认\n\n'+ '\n\n'.join(f"## {p['ref_key']}\n"+'\n'.join(f"- P{x['paragraph']:03}：{x['text']}" for x in p['paragraph_candidates']) for p in proposals),encoding='utf-8')
    return audit

class Client:
    def __init__(self,c):self.c=c.get('reference_audit',{});self.cache=SKILL/self.c.get('cache_dir','.runtime/ref-cache');self.cache.mkdir(parents=True,exist_ok=True);self.last={};self.intervals={}
    def get(self,url,params=None):
        import requests
        params=dict(params or {});source='pubmed' if 'ncbi.nlm.nih.gov' in url else 'crossref' if 'crossref.org' in url else 'openalex'
        public=url+('?' + urlencode(params) if params else '');file=self.cache/(text_sha(public)+'.json')
        if file.exists():
            rec=read(file)
            if time.time()-rec['epoch']<86400*self.c.get('cache_days_retraction',30):return rec
        if self.c.get('contact_email'):params['email' if source=='pubmed' else 'mailto']=self.c['contact_email']
        if source=='pubmed':
            params['tool']='research-review-writer'
            if self.c.get('ncbi_api_key'):params['api_key']=self.c['ncbi_api_key']
        interval=(.11 if self.c.get('ncbi_api_key') else .36) if source=='pubmed' else self.intervals.get(source,1.0)
        time.sleep(max(0,interval-(time.monotonic()-self.last.get(source,0))))
        rec=dict(source=source,query=public,retrieved_at=now(),epoch=time.time(),response=None,status_code=None)
        try:
            for attempt in range(3):
                response=requests.get(url,params=params,timeout=25,headers={'User-Agent':'research-review-writer/1.0'});self.last[source]=time.monotonic()
                if source=='crossref':
                    limit=response.headers.get('X-Rate-Limit-Limit');window=response.headers.get('X-Rate-Limit-Interval','1s')
                    if limit and str(limit).isdigit():self.intervals[source]=max(1.0,float(window.rstrip('s'))/max(1,int(limit)))
                if response.status_code not in (429,503):break
                time.sleep(min(20,float(response.headers.get('Retry-After',2**attempt))))
            rec.update(status_code=response.status_code,response=response.text)
        except requests.RequestException as exc:rec['error']=type(exc).__name__
        if rec['status_code']==200:save(file,rec)
        return rec

def crossref_record(x):
    date=x.get('published',x.get('issued',{})).get('date-parts',[[None]])[0]
    return dict(first_author=(x.get('author') or [{}])[0].get('family',''),title=(x.get('title') or [''])[0],journal=(x.get('container-title') or [''])[0],journal_aliases=x.get('short-container-title',[]),year=date[0],volume=x.get('volume',''),issue=x.get('issue',''),pages=x.get('page',x.get('article-number','')),doi=x.get('DOI'),pmid=None,abstract=re.sub('<[^>]+>',' ',x.get('abstract','')),retracted=any('retract' in str(y.get('type','')).lower() for y in x.get('update-to',[])),raw=x)
def pubmed_records(xml):
    out=[]
    for x in ET.fromstring(xml).findall('.//PubmedArticle'):
        def val(path):return ''.join(x.find(path).itertext()) if x.find(path) is not None else ''
        year=val('.//JournalIssue/PubDate/Year') or val('.//JournalIssue/PubDate/MedlineDate')[:4]
        out.append(dict(first_author=val('.//Author/LastName'),title=val('.//ArticleTitle'),journal=val('.//Journal/Title'),journal_aliases=[val('.//Journal/ISOAbbreviation'),val('.//MedlineJournalInfo/MedlineTA')],year=int(year) if year.isdigit() else None,volume=val('.//JournalIssue/Volume'),issue=val('.//JournalIssue/Issue'),pages=val('.//Pagination/MedlinePgn'),doi=val('.//ArticleId[@IdType="doi"]'),pmid=val('.//PMID'),pmcid=val('.//ArticleId[@IdType="pmc"]'),abstract=' '.join(''.join(t.itertext()) for t in x.findall('.//AbstractText')),retracted=any('Retracted Publication' in (t.text or '') for t in x.findall('.//PublicationType')),raw=ET.tostring(x,encoding='unicode')))
    return out
def compare(p,r):
    similarity=difflib.SequenceMatcher(None,norm(p['title']),norm(r['title'])).ratio()
    diffs=[]
    for field in ('first_author','title','journal','year','volume','issue','pages'):
        a=p.get(field);b=r.get(field)
        if not a:continue
        equal=norm(a)==norm(b)
        if field=='title':equal=similarity>=.90
        if field=='journal':equal=norm(a) in [norm(b)]+[norm(x) for x in r.get('journal_aliases',[])]
        if field=='pages':equal=norm(expanded_pages(a)[0])==norm(expanded_pages(str(b))[0])
        if not equal:diffs.append(dict(field=field,entry=a,database=b))
    return similarity,diffs

def verify(run,c):
    audit=read(run/'references_audit.json');client=Client(c)
    for e in audit['entries']:
        p=e['parsed'];records=[];logs=[]
        def request(url,params=None):
            r=client.get(url,params);logs.append(r);return r
        try:
            if p.get('doi'):
                r=request('https://api.crossref.org/works/'+quote(p['doi'],safe=''))
                if r['status_code']==200:records=[crossref_record(json.loads(r['response'])['message'])]
            if not records and p.get('pmid'):
                r=request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',dict(db='pubmed',id=p['pmid'],retmode='xml'))
                if r['status_code']==200:records=pubmed_records(r['response'])
            if not records and all(p.get(k) for k in ('journal','year','volume','pages','first_author')):
                b='|'.join(str(p[k]) for k in ('journal','year','volume'))+'|'+p['pages'].split('-')[0]+'|'+p['first_author']+'|'+e['ref_key']+'|'
                r=request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ecitmatch.cgi',dict(db='pubmed',retmode='xml',bdata=b))
                tail=(r['response'] or '').strip().split('|')[-1]
                if r['status_code']==200 and tail.isdigit():
                    r=request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',dict(db='pubmed',id=tail,retmode='xml'))
                    if r['status_code']==200:records=pubmed_records(r['response'])
            if not records and p['title']:
                r=request('https://api.crossref.org/works',{'query.bibliographic':p['title']+' '+p['first_author']+' '+str(p['year']),'rows':5})
                if r['status_code']==200:records=[crossref_record(x) for x in json.loads(r['response'])['message']['items']]
            # PubMed also supplies abstract and independent retraction metadata.
            if p['title']:
                r=request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',dict(db='pubmed',term=p['title']+'[Title]',retmode='json',retmax=5))
                ids=json.loads(r['response']).get('esearchresult',{}).get('idlist',[]) if r['status_code']==200 else []
                if ids:
                    r=request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',dict(db='pubmed',id=','.join(ids),retmode='xml'))
                    if r['status_code']==200:records=pubmed_records(r['response'])+records
            candidates=[]
            for r in records:
                score,diffs=compare(p,r)
                if score>=c.get('reference_audit',{}).get('title_similarity_min',.90):r.update(title_similarity=score,diffs=diffs);candidates.append(r)
            if not candidates and p['title']:
                r=request('https://api.openalex.org/works',dict(search=p['title'],per_page=5))
                if r['status_code']==200:
                    for x in json.loads(r['response']).get('results',[]):
                        score=difflib.SequenceMatcher(None,norm(p['title']),norm(x.get('title',''))).ratio()
                        if score>=.90:e.setdefault('openalex_candidates',[]).append(x)
            e.update(queries=logs,candidates=candidates)
            if candidates:
                candidates.sort(key=lambda r:(bool(r.get('pmid')),norm(r['first_author'])==norm(p['first_author']),bool(r['first_author']),r['title_similarity']),reverse=True)
                identities={norm(r.get('doi') or r['title']) for r in candidates};best=candidates[0]
                e['matched']=best;e['diffs']=best['diffs'];e['retracted']=any(r['retracted'] for r in candidates);e['retraction_status']='checked_records'
                structural={d['field'] for d in best['diffs']}&{'journal','year','volume','pages'}
                e['status']='ambiguous' if len(identities)>1 or len(structural)>=3 or norm(best['first_author'])!=norm(p['first_author']) else 'metadata_mismatch' if best['diffs'] else 'verified'
                if not any(r.get('pmid') for r in candidates) and any(r['source']=='pubmed' and r['status_code']!=200 for r in logs):
                    e['metadata_status']=e['status'];e['status']='unverified_offline';e['retraction_status']='pubmed_retry_required';e['retracted']=True if e['retracted'] else None
            elif any(r['status_code'] is None or r['status_code']>=400 and r['status_code']!=404 for r in logs):e['status']='unverified_offline'
            elif e.get('openalex_candidates'):e['status']='needs_manual'
            else:e['status']='not_found' if p['title'] else 'needs_manual'
            if not logs:e['queries']=[dict(source='parser',query=e['entry_text'],retrieved_at=now(),response={'parse_status':e['parse_status']})]
        except (ValueError,ET.ParseError,KeyError,TypeError) as exc:e.update(status='unverified_offline',queries=logs,error=type(exc).__name__)
        save(run/'references_audit.json',audit);queries(run,audit)
    for mention in audit['mentions']:
        if mention['status']=='orphan_mention':
            rec=client.get('https://api.crossref.org/works',{'query.bibliographic':mention['surname']+' '+mention['sentence'][:600],'rows':3})
            mention['queries']=[rec]
            if rec['status_code']==200:mention['search_candidates']=[crossref_record(x) for x in json.loads(rec['response'])['message']['items']]
            for candidate in mention.get('search_candidates',[]):
                candidate['overlaps_entries']=[e['ref_key'] for e in audit['entries'] if norm(candidate['title'])==norm(e['parsed']['title'])]
    save(run/'references_audit.json',audit);queries(run,audit);return audit

def queries(run,audit):
    lines=['# 引用问题：请作者集中处理','']
    if audit['doc']['inline_markers']=='absent' and not audit['mapping']['origin']:lines.append('- 阻断：正文缺少编号；请确认 proposed_mapping，或明确选择正文保持无引用。')
    for e in sorted(audit['entries'],key=lambda x:x['status'] not in ('pending','unverified_offline')):
        if e['status']!='verified' or e['offline_flags'] or e['retracted']:
            lines.append(f"- {e['ref_key']}：{e['status']}；{', '.join(e['offline_flags'])}；撤稿={e['retracted']}。原条目：{e['entry_text']}。差异：{json.dumps(e.get('diffs',[]),ensure_ascii=False)}；决定：{e['decision']}")
    for m in audit['mentions']:
        if m['status']!='matched' or m.get('flags'):lines.append(f"- {m['mention_id']} {m['surname']}：{m['status']}；位置 {m['start']}；候选 {m['candidates']}。")
    (run/'author_queries_refs.md').write_text('\n\n'.join(lines),encoding='utf-8')

def gate(run,write=True):
    a=read(run/'references_audit.json');errors=[]
    need(sha(run/'reference_body.md')==a['body_sha256'],'Audit body changed')
    originals=list(run.glob('reference_source.*'));need(len(originals)==1 and sha(originals[0])==a['source_sha256'],'Reference source changed')
    for e in a['entries']:
        if e['status'] not in ('pending','verified','metadata_mismatch','ambiguous','not_found','needs_manual','unverified_offline'):errors.append(e['ref_key']+': invalid_status')
        for q in e.get('queries',[]):
            if any(k not in q for k in ('source','query','retrieved_at','response')):errors.append(e['ref_key']+': incomplete_query_record')
        provenance=[]
        for record in e.get('queries',[]):
            if record.get('status_code')!=200:continue
            try:
                if record['source']=='crossref':
                    message=json.loads(record['response'])['message'];provenance.extend(crossref_record(x) for x in message.get('items',[message]))
                elif record['source']=='pubmed' and '<PubmedArticle' in record['response']:provenance.extend(pubmed_records(record['response']))
            except (ValueError,KeyError,ET.ParseError,TypeError):continue
        for candidate in [e['matched']] if e.get('matched') else []:
            if not any(all(candidate.get(k)==r.get(k) for k in ('title','first_author','year','pages','doi','pmid','abstract','retracted')) for r in provenance):errors.append(e['ref_key']+': matched_record_not_in_response')
        waived=any(w.get('ref_key')==e['ref_key'] and w.get('author_message') and w.get('reason') for w in a['waivers'])
        if e['status'] in ('pending','unverified_offline') and not waived:errors.append(e['ref_key']+': '+e['status'])
        if e['retracted'] and not e.get('decision') and not waived:errors.append(e['ref_key']+': retracted_undecided')
        if e['status']!='pending' and not e.get('queries'):errors.append(e['ref_key']+': missing_query_records')
        for field,value in e.get('corrections',{}).items():
            if not any(r.get(field)==value for r in provenance):errors.append(e['ref_key']+': correction_not_in_database '+field)
    if a['doc']['inline_markers']=='absent' and a['mapping']['origin'] not in ('author_confirmed','none_by_author'):errors.append('inline_markers_absent_unconfirmed')
    result=dict(status='blocked' if errors else 'passed',errors=errors,audit_sha256=sha(run/'references_audit.json'),checked_at=now())
    if write:save(run/'references_gate.json',result)
    return result

def decisions(run,path,mapping=False):
    a=read(run/'references_audit.json');d=read(path);need(d.get('author_message'),'Record actual author reply')
    if mapping:
        need(d['origin'] in ('author_confirmed','none_by_author'),'Unknown mapping decision')
        body=(run/'reference_body.md').read_text(encoding='utf-8');keys={e['ref_key'] for e in a['entries']}
        for pair in d.get('pairs',[]):need(pair['ref_key'] in keys and body[pair['start']:pair['end']]==pair['quote'],'Mapping source or reference mismatch')
        a['mapping']=d
    else:
        entries={e['ref_key']:e for e in a['entries']}
        for item in d.get('decisions',[]):
            e=entries[item['ref_key']];need(item['decision'] in ('accept_correction','keep_as_is','remove'),'Use a linked source revision for replacement/addition')
            if item['decision']=='accept_correction':
                for k,v in item['corrections'].items():need(any(r.get(k)==v for r in [e.get('matched',{})]+e.get('candidates',[])),'Correction must occur in retained database record')
                e['corrections']=item['corrections']
            e['decision']=dict(item,author_message=d['author_message'])
        a['waivers']+= [dict(w,author_message=d['author_message']) for w in d.get('waivers',[])]
    archive=run/'reference_decisions';archive.mkdir(exist_ok=True);save(archive/(text_sha(json.dumps(d,sort_keys=True))[:16]+'.json'),d)
    save(run/'references_audit.json',a);queries(run,a);return gate(run)

def require_a0(run):
    result=gate(run);need(result['status']=='passed','A0 blocked: '+', '.join(result['errors']))
    m=read(run/'manifest.json')
    need(sha(run/'input.md')==read(run/'references_audit.json')['body_sha256'],'Writing body differs from audited source')
    if m.get('references_checkpoint'):need(m['references_checkpoint']==result['audit_sha256'],'References changed; rebuild the ledger and support check')
    return read(run/'references_audit.json')

def seed_refs(run,seed):
    audit=require_a0(run);refs=[]
    for e in audit['entries']:
        action=(e.get('decision') or {}).get('decision') if isinstance(e.get('decision'),dict) else e.get('decision')
        status='removed' if action=='remove' else 'corrected' if action=='accept_correction' else 'verified' if e['status']=='verified' else 'kept_unverified'
        refs.append(dict(ref_key=e['ref_key'],original_number=e['original_number'],entry_text=e['entry_text'],audit_status=status,retracted=e['retracted'],source_ids={k:e.get('matched',e['parsed']).get(k) for k in ('doi','pmid')}))
    seed['references']=refs
    for marker in audit['markers']:
        if any(x['start']==marker['start'] and x['end']==marker['end'] for x in seed['citation_occurrences']):continue
        sent=next((s for p in seed['source_units'] for s in p['sentences'] if s['start']<=marker['start'] and marker['end']<=s['end']),None)
        need(sent,'Citation marker crosses source sentence boundaries')
        seed['citation_occurrences'].append(dict(occurrence_id=f'CIT{len(seed["citation_occurrences"])+1:04}',sid=sent['sid'],**marker))
    if audit['mapping']['origin']=='none_by_author':seed['citation_occurrences']=[]
    elif audit['mapping']['origin']=='author_confirmed':
        for pair in audit['mapping']['pairs']:
            sent=next((s for p in seed['source_units'] for s in p['sentences'] if s['start']<=pair['start'] and pair['end']<=s['end']),None)
            need(sent,'Map to an exact source sentence/span')
            seed['citation_occurrences'].append(dict(occurrence_id=f'CIT{len(seed["citation_occurrences"])+1:04}',sid=sent['sid'],start=pair['start'],end=pair['end'],text=pair['quote'],ref_keys=[pair['ref_key']],origin='author_confirmed'))
    return seed

def validate_ledger_references(run,ledger):
    audit=require_a0(run);entries={x['ref_key']:x for x in audit['entries']};refs={x['ref_key']:x for x in ledger['references']}
    for key,ref in refs.items():
        need(key in entries,'Ledger reference absent from A0')
        original=next(x for x in read(run/'ledger_seed.json')['references'] if x['ref_key']==key)
        need(ref==original,'Ledger reference metadata differs from audited seed')
    for cl in ledger['claims']:
        need(all(refs[k]['audit_status']!='removed' for k in cl['citations']),'Removed reference attached to claim')

def apply_support(run,ledger):
    outcomes=support_validate(run,ledger);refs={x['ref_key']:x for x in ledger['references']}
    for cl in ledger['claims']:
        cl['support']=outcomes.get(cl['claim_id'],[])
        cl['evidence_unverified']=bool(cl['citations']) and all(refs[k]['audit_status']=='kept_unverified' or any(x['ref_key']==k and (x.get('status')=='not_checkable' or x.get('support')=='undeterminable') for x in cl['support']) for k in cl['citations'])
    return ledger

def delivery(run,ledger):
    audit=require_a0(run);lines=['# 引用与支持度交付说明','']
    if audit['mapping']['origin']=='none_by_author':lines.append('作者选择正文保持无文内引用；本稿未添加引用占位符。')
    for cl in ledger['claims']:
        if cl.get('evidence_unverified'):lines.append(f"- {cl['claim_id']}：全部所引证据仍待核实。{cl['text_zh']}")
        for item in cl.get('support',[]):
            state=item.get('support',item.get('status'))
            if state!='supports':lines.append(f"- {cl['claim_id']} / {item['ref_key']}：{state}；{item.get('note','见 support 记录')}")
    (run/'evidence_unverified.md').write_text('\n\n'.join(lines),encoding='utf-8')
    save(run/'reference_corrections.json',[dict(ref_key=e['ref_key'],original=e['entry_text'],corrections=e.get('corrections',{}),decision=e.get('decision')) for e in audit['entries'] if e.get('decision')])

def support_prepare(run,c,ledger_path):
    audit=require_a0(run);ledger=read(ledger_path)
    from logic_flow import validate_ledger
    validate_ledger(run,ledger)
    directory=run/'support';directory.mkdir(exist_ok=True);entries={e['ref_key']:e for e in audit['entries']};tasks=[];limit=c.get('support_check',{}).get('max_claims',80)
    client=Client(c)
    selected=[x for x in ledger['claims'] if x['citations'] and (x.get('support_requested') or x['strength'] in ('established','reported') or x.get('quantities') and x['type'] in ('finding','background'))]
    selected.sort(key=lambda x:0 if x.get('quantities') and x['type'] in ('finding','background') else 1 if x['strength'] in ('established','reported') else 2)
    for i,cl in enumerate(selected):
        for ref in cl['citations']:
            e=entries[ref];abstract=e.get('matched',{}).get('abstract','');status='not_checked' if i>=limit else 'not_checkable' if not abstract or e['status'] in ('ambiguous','not_found','unverified_offline') else 'pending'
            task=dict(claim_id=cl['claim_id'],ref_key=ref,status=status)
            if status=='pending':
                passages=[];retrieval=[];pmcid=e.get('matched',{}).get('pmcid')
                if pmcid and c.get('support_check',{}).get('fulltext')=='pmc_open_access_only':
                    oa=client.get('https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi',dict(id=pmcid));retrieval.append(oa)
                    if oa['status_code']==200 and ET.fromstring(oa['response']).find('.//record') is not None:
                        full=client.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',dict(db='pmc',id=pmcid.removeprefix('PMC'),retmode='xml'));retrieval.append(full)
                        if full['status_code']==200:
                            terms=set(tokenize(cl['text_zh']));pieces=[''.join(p.itertext()) for p in ET.fromstring(full['response']).findall('.//body//p')]
                            ranked=sorted(pieces,key=lambda t:len(terms&set(tokenize(t))),reverse=True)
                            passages=[t for t in ranked if len(t)<=2000 and terms&set(tokenize(t))][:3]
                evidence=abstract+'\n\n'+'\n\n'.join(passages) if passages else abstract
                name=f'{cl["claim_id"]}-{ref}';need(re.fullmatch(r'[A-Za-z0-9_-]+',name),'Unsafe claim ID')
                packet=dict(claim={k:cl[k] for k in ('claim_id','text_zh','conditions','quantities','strength','polarity')},ref_key=ref,evidence=evidence,source_ids={k:e['matched'].get(k) for k in ('doi','pmid')},instruction='独立核对支持度；返回 supports/partial/contradicts/undeterminable、scope_diff、逐字 evidence、note。摘要没有依据时为 undeterminable。')
                if retrieval:save(directory/(name+'_retrieval.json'),retrieval)
                need(count(json.dumps(packet,ensure_ascii=False),c)<=c['budgets']['writer_input_tokens'],'Support packet exceeds token budget')
                save(directory/(name+'_input.json'),packet);task.update(input=name+'_input.json',input_sha256=sha(directory/(name+'_input.json')),result=name+'_result.json')
            tasks.append(task)
    clean=json.loads(json.dumps(ledger))
    for claim in clean['claims']:claim.pop('support',None);claim.pop('evidence_unverified',None)
    manifest=dict(ledger_sha256=sha(ledger_path),ledger_content_hash=text_sha(json.dumps(clean,sort_keys=True)),audit_sha256=sha(run/'references_audit.json'),tasks=tasks);save(directory/'manifest.json',manifest);return manifest

def support_validate(run,ledger):
    require_a0(run);manifest=read(run/'support/manifest.json')
    clean=json.loads(json.dumps(ledger))
    for claim in clean['claims']:
        claim.pop('support',None);claim.pop('evidence_unverified',None)
    need(text_sha(json.dumps(clean,sort_keys=True))==manifest['ledger_content_hash'],'Ledger differs from support source')
    need(manifest['audit_sha256']==sha(run/'references_audit.json'),'A1 audit version changed')
    outcomes={};queries_out=[]
    for task in manifest['tasks']:
        key=task['claim_id'];out=dict(task)
        if task['status']=='pending':
            packet=read(run/'support'/task['input']);result=read(run/'support'/task['result'])
            need(sha(run/'support'/task['input'])==task['input_sha256']==result['input_sha256'],'Support input hash mismatch')
            need(result.get('isolation')=='independent_context' and result.get('context_id') and result.get('model'),'Independent reviewer identity required')
            need(result['claim_id']==key and result['ref_key']==task['ref_key'],'Support claim/reference mismatch')
            need(result['support'] in ('supports','partial','contradicts','undeterminable'),'Invalid support verdict')
            need(result.get('note') and set(result['scope_diff'])<={'species_or_model','population','endpoint','direction','entity','magnitude','design'},'Support dimensions/note missing')
            need((result['support']=='undeterminable' and not result['evidence']) or result['evidence'] and result['evidence'] in packet['evidence'],'Support evidence must be an exact supplied passage')
            out.update(result)
            if result['support']=='contradicts':
                decision=result.get('author_decision',{});need(decision.get('author_message') and decision.get('action')=='keep_as_is','Contradiction needs author keep decision, or a linked revised source/ledger')
            if result['support'] in ('partial','contradicts','undeterminable'):queries_out.append(out)
        outcomes.setdefault(key,[]).append(out)
    save(run/'support/results.json',outcomes)
    (run/'author_queries_support.md').write_text('# D-SUPPORT\n\n'+json.dumps(queries_out,ensure_ascii=False,indent=2),encoding='utf-8')
    return outcomes

def support_checkpoint(run):
    manifest=read(run/'support/manifest.json')
    return {'manifest':sha(run/'support/manifest.json'),**{x['result']:sha(run/'support'/x['result']) for x in manifest['tasks'] if x['status']=='pending'}}

def main(command=None):
    p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--run',required=True);p.add_argument('--input');p.add_argument('--ledger');p.add_argument('--offline',action='store_true');p.add_argument('--validate',action='store_true');p.add_argument('--begin',action='store_true');p.add_argument('--command',default=command)
    a=p.parse_args();run=Path(a.run);c=config(a.config);cmd=a.command
    if cmd=='parse':result=parse(a.input,run)
    elif cmd=='verify':
        if a.offline:
            result=read(run/'references_audit.json')
            for e in result['entries']:e.update(status='unverified_offline',queries=[dict(source='offline',query=e['entry_text'],retrieved_at=now(),response=None)])
            save(run/'references_audit.json',result);queries(run,result)
        else:result=verify(run,c)
    elif cmd=='decisions':result=decisions(run,a.input)
    elif cmd=='mapping':result=decisions(run,a.input,True)
    elif cmd=='support':
        if a.validate:result=support_validate(run,read(a.ledger or run/'fact_ledger.json'))
        else:
            lp=Path(a.ledger) if a.ledger else run/'fact_ledger.json';result=support_prepare(run,c,lp)
    else:
        result=gate(run)
        if a.begin and result['status']=='passed':
            from logic_flow import initialize
            m=read(run/'manifest.json');result=initialize(c,run,m.get('audit_level','L0'),m.get('audit_citation_mode','keep_original'))
    print(json.dumps({k:result[k] for k in ('status','errors','doc','run') if k in result},ensure_ascii=False,indent=2))
    if cmd=='validate' and result.get('status')=='blocked':raise SystemExit(2)

if __name__=='__main__':main()
