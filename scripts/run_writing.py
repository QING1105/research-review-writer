"""Prepare host-executed writing runs and finalize checked outputs."""
import argparse,json,re,tempfile
from datetime import datetime,timezone
from common import *
from measure_style import build
from retrieve_style import retrieve

def prepare(c,input_path,domain,section,query='',roles=None,run_id=None,requirements='',task_kind='user_draft',plan_path=None):
    index=build(c);source_bytes=Path(input_path).read_bytes()
    draft=source_bytes.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    units=split_draft(draft,c);domains=domain_values(domain)
    run_id=run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('run-id must contain letters, digits, underscore or hyphen')
    run=c['runs']/run_id
    if run.exists():raise ValueError('Run already exists; use a new run-id')
    run.mkdir(parents=True)
    (run/'original_input.md').write_bytes(source_bytes)
    (run/'input.md').write_bytes(draft.encode('utf-8'))
    supplied=read(plan_path) if plan_path else {};requests=supplied.get('units',{})
    for unit in units:
        uid=unit['unit_id'];directory=run/uid;directory.mkdir()
        spec=requests.get(uid,{})
        unit_domains=domain_values(','.join(spec['domains'])) if spec.get('domains') else domains
        unit_section=spec.get('section',section)
        unit_roles=spec.get('roles',roles or [])
        unit_query=spec.get('query') or query or unit['text']
        if supplied and uid not in requests:raise ValueError(f'Missing unit in supplied plan: {uid}')
        items,meta=retrieve(c,unit_domains,unit_section,unit_query,unit_roles)
        if not items:raise ValueError(f'{uid}: no annotated style sources in selected domain/section/roles')
        jl(directory/'candidates.jsonl',items)
        save(directory/'candidates_view.json',[plain_card(x) for x in items]);save(directory/'retrieval.json',meta)
        unit['domains']=unit_domains;unit['section']=unit_section;unit['roles']=unit_roles
        unit['existing_relations']=spec.get('existing_relations',[])
    if set(requests)-{u['unit_id'] for u in units}:raise ValueError('Supplied plan references unknown draft units')
    plan=dict(domains=domains,section=section,author_requirements=requirements,units=units,
        task_analysis_origin='host_authored_plan' if supplied else 'explicit_user_domain_section_and_deterministic_paragraph_split')
    save(run/'draft_plan.json',plan)
    save(run/'manifest.json',dict(run_id=run_id,status='awaiting_style_selection',task_kind=task_kind,
        input_sha256=sha(run/'input.md'),original_input_sha256=sha(run/'original_input.md'),input_normalization='UTF-8 without BOM; LF; original bytes retained',source_hashes=index['source_hashes'],config=recordable_config(c),
        backend='current_skill_host',model_id=None,model_id_status='record actual identifier when available',
        created_at=datetime.now(timezone.utc).isoformat()))
    return dict(run=str(run),units=[dict(unit_id=u['unit_id'],candidate_view=str(run/u['unit_id']/'candidates_view.json')) for u in units])

def finalize(c,run):
    if read(run/'manifest.json').get('workflow_version') in (2,3):
        from logic_flow import finish
        return finish(c,run)
    from validate_records import validate
    result=validate(c,run,require_outputs=True)
    plan=read(run/'draft_plan.json');text=[];audits=[]
    last=None
    for u in plan['units']:
        r=read(run/u['unit_id']/'result.json')
        if last==u['paragraph_id']:text[-1]+=' '+r['text'].strip()
        else:text.append(r['text'].strip())
        last=u['paragraph_id'];audits.append(dict(unit_id=u['unit_id'],audit=r['audit'],style_alignment=r['style_alignment'],queries=r.get('queries',[])))
    (run/'output.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8');save(run/'audit.json',audits)
    manifest=read(run/'manifest.json');manifest.update(status='completed_host_review',output_sha256=sha(run/'output.md'),
        validation=result,semantic_review='host self-review; user acceptance recorded separately',user_approval='pending')
    save(run/'manifest.json',manifest)
    return dict(output=str(run/'output.md'),audit=str(run/'audit.json'),validation=result)

def main():
    p=argparse.ArgumentParser();p.add_argument('--config');sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--input',required=True);a.add_argument('--domain',required=True);a.add_argument('--section',choices=['abstract','introduction','any'],default='any')
    a.add_argument('--query',default='');a.add_argument('--roles',default='');a.add_argument('--run-id');a.add_argument('--requirements',default='');a.add_argument('--task-kind',default='user_draft');a.add_argument('--plan')
    a.add_argument('--requirements-file')
    a.add_argument('--workflow',choices=['logic','legacy'],default='logic')
    a.add_argument('--level',choices=['L0','L1','L2'],default='L0')
    a.add_argument('--citation-mode',choices=['keep_original','first_appearance'],default='keep_original')
    a.add_argument('--content-policy',choices=['argument_first','preserve_all'],help='L1/L2 default to argument_first; use preserve_all for explicit no-omission tasks. L0 preserves the accepted source.')
    b=sub.add_parser('finish');b.add_argument('--run',required=True)
    b=sub.add_parser('inspect');b.add_argument('--run',required=True)
    a=p.parse_args();c=config(a.config)
    if a.command=='prepare':
        if a.requirements_file:a.requirements=Path(a.requirements_file).read_text(encoding='utf-8-sig')
        source=a.input
        if a.workflow=='logic':
            import reference_audit
            body,_,_=reference_audit.document(source)
            with tempfile.TemporaryDirectory() as temporary:
                body_path=Path(temporary)/'body.md';body_path.write_text(body,encoding='utf-8')
                result=prepare(c,body_path,a.domain,a.section,a.query,[r for r in a.roles.split(',') if r],a.run_id,a.requirements,a.task_kind,a.plan)
        else:result=prepare(c,a.input,a.domain,a.section,a.query,[r for r in a.roles.split(',') if r],a.run_id,a.requirements,a.task_kind,a.plan)
        if a.workflow=='logic':
            run=Path(result['run']);reference_audit.parse(source,run)
            manifest=read(run/'manifest.json');manifest.update(reference_audit_required=True,audit_level=a.level,audit_citation_mode=a.citation_mode,status='awaiting_reference_audit')
            if a.content_policy:manifest['requested_content_policy']=a.content_policy
            save(run/'manifest.json',manifest)
            result=dict(run=str(run),status='awaiting_reference_audit',next='verify_references.py then validate_references.py --begin')
    elif a.command=='finish':result=finalize(c,Path(a.run))
    else:result=read(Path(a.run)/'manifest.json')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
