"""Original synthetic data for tests; no papers or author manuscripts are read."""
from common import *
from measure_style import build

def fixture_config(directory):
    root=Path(directory)/'synthetic-corpus'
    cfg=read(SKILL/'assets/project-template.yaml')
    cfg.update(corpus_root=str(root),fluency_python='')
    path=Path(directory)/'fixture-config.json';save(path,cfg)
    c=config(path)
    if (c['source']/'chunks.jsonl').exists():return c
    c['source'].mkdir(parents=True,exist_ok=True)
    chunks=[];language=[];argument=[];patterns=[]
    examples=[
        ('D04','introduction','Spatial assays preserve sample coordinates. Morphology measurements require validation.'),
        ('D04','introduction','By recording coordinates, a spatial assay links each measurement to a location. Validation checks the resulting map.'),
        ('D04','introduction','Although spatial measurements retain coordinates, morphology analysis requires validation. This review examines the measurement workflow.'),
        ('D04','introduction','Spatial maps describe the locations of measured signals. Comparing maps requires a consistent validation procedure.'),
        ('D03','abstract','A microfluidic chip controls fluid delivery. This example describes chip validation.')]
    for n,(domain,section,text) in enumerate(examples,1):
        cid=f'DEMO-C{n:03}';sid=f'{cid}-S01';pid=f'DEMO-P{n:03}'
        location={'kind':'synthetic_example','paragraph':n}
        chunks.append(dict(chunk_id=cid,paper_id=pid,domain=DOMAINS[domain],section_role=section,
                           text_clean=text,title=f'Synthetic writing example {n}',doi=None,source_location=location))
        language.append(dict(sentence_id=sid,chunk_id=cid,source_span=dict(start=0,end=len(text),quote=text),
                             labels=dict(analysis='先交代测量对象，再说明验证要求；具体主语连接动作。',authored_focus_spans=[]),
                             review={'status':'synthetic_fixture'},selection={'status':'selected_expression_candidate'}))
        argument.append(dict(sentence_id=sid,chunk_id=cid,labels={'sentence_roles':['BACKGROUND','VALUE']}))
        patterns.append(dict(chunk_id=cid,paper_id=pid,domain=DOMAINS[domain],section_role=section,
                             source_location=location,rhetorical_moves=[dict(roles=['BACKGROUND','VALUE'])],
                             abstract_pattern='先说明测量保留什么，再交代检查要求。'))
    for name,items in [('chunks',chunks),('language_realization',language),('argumentation',argument),('paragraph_patterns',patterns)]:
        jl(c['source']/(name+'.jsonl'),items)
    build(c)
    return c
