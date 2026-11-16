"""Behavioral invariants for author intent, prose handoff and complete reviews."""
import copy
import tempfile
import unittest
from common import *
from test_support import fixture_config
from run_writing import prepare,finalize
import logic_flow as flow
import author_contract as author
import test_logic_flow as fixtures

class AuthorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='author-contract-')
        cls.root=Path(cls.temp.name).resolve();cls.serial=0
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def task(self,level='L2',workflow_requirement=False):
        c,run,ledger,plan=fixtures.LogicTests.task(self,level)
        request='保持一段；空间信息有价值，形态分析仍需要验证。'
        if workflow_requirement:request+='本次为开发验证，保存执行记录。'
        (run/'author_request.md').write_text(request,encoding='utf-8')
        m=read(run/'manifest.json');m.update(workflow_version=3,author_request_sha256=sha(run/'author_request.md'),task_kind='development_evaluation');save(run/'manifest.json',m)
        for cl in ledger['claims']:cl['origin']='source'
        plan['author_requirements']=[dict(requirement_id='A001',text=request,source='request',source_quote=request)]
        if workflow_requirement:plan['author_requirements'].append(dict(requirement_id='MODE',kind='workflow',text='保存开发模式',source='request',source_quote='本次为开发验证，保存执行记录。'))
        plan['author_structure']=dict(paragraph_count=1,requirement_id='A001')
        for p in plan['paragraphs']:p.update(subject_scope='空间转录组及形态分析',requirement_ids=['A001'],required_relations=[dict(type='contrast',description='保留空间信息有价值，形态分析仍需验证',claims=p['claim_order'],requirement_ids=['A001'])])
        if workflow_requirement:plan['paragraphs'][0]['requirement_ids'].append('MODE')
        self.activate(c,run,ledger,plan)
        return c,run,ledger,plan

    def activate(self,c,run,l,p):return fixtures.LogicTests.activate(self,c,run,l,p)

    def write(self,c,run,l,p,stage):
        flow.candidates(c,run,'N001',stage);directory=run/'N001'
        sentences=list(rows(directory/'candidates.jsonl'));cards=list(rows(directory/'paragraph_candidates.jsonl'))
        picks=[]
        for card in cards:
            pick=dict(id=card['chunk_id'],reason='engineering fixture',relation_fit='partial',source_relation='source progression',target_relation='value then validation',adaptation='use scoped relationship',applies_to_claims=['C001','C002'])
            reference=dict(reference_id=card['chunk_id'],source_quote=card['source_quote'],progression=card['abstract_pattern'],application=pick['reason'],relationship_match={k:pick[k] for k in ('relation_fit','source_relation','target_relation','adaptation','applies_to_claims')})
            if count(json.dumps([reference],ensure_ascii=False),c)<=600:picks=[pick];break
        self.assertTrue(picks)
        selection=dict(language=[dict(id=sentences[0]['style_id'],reason='engineering fixture')],paragraphs=picks)
        save(directory/'selected.json',selection);flow.assemble(c,run,'N001',directory/'selected.json',stage)
        directory=flow.result_directory(run,'N001',stage);payload=json.loads(read(directory/'writer_messages.json')[1]['content'])
        fragments=['空间转录组学保留基因表达的空间背景。','形态特征的提取仍需要仔细验证。'] if stage=='zh' else ['Spatial transcriptomics preserves the spatial context of gene expression.','Extracting morphological features still requires careful validation.']
        text=' '.join(fragments);cursor=0;mapping=[]
        for i,fragment in enumerate(fragments):
            mapping.append(dict(start=cursor,end=cursor+len(fragment),claims=[f'C{i+1:03}'],role='content',citations=[]));cursor+=len(fragment)+1
        ref=payload['reference_paragraphs'][0]
        save(directory/'result.json',dict(input_sha256=read(directory/'assembly.json')['payload_sha256'],text=text,sentence_claims=mapping,queries=[],style_alignment=[dict(reference_id=ref['reference_id'],output_span=fragments[0],reference_span=ref['source_quote'],feature='engineering fixture; quality tested separately')]))
        flow.validate_result(c,run,'N001',stage)

    def reviews(self,c,run,l,p,stage):
        flow.review_inputs(c,run,stage);directory=run/('zh_reviews' if stage=='zh' else 'reviews');r=read(flow.result_directory(run,'N001',stage)/'result.json')
        roles=('fidelity','reader') if stage=='zh' else ('fidelity','reader','style')
        fidelity=read(directory/'fidelity_input.json')
        self.assertNotIn('author_requirements',fidelity['plan'])
        self.assertEqual(fidelity['author_requirements'],p['author_requirements'])
        if stage=='en':
            self.assertEqual([x['text'] for x in fidelity['accepted_source']['paragraphs']],[x['text'] for x in read(run/'chinese_draft.json')['paragraphs']])
            self.assertNotIn('sentence_claims',fidelity['accepted_source']['paragraphs'][0])
        for role,budget in read(directory/'input_budgets.json').items():
            self.assertEqual(budget['tokens'],count((directory/f'{role}_input.json').read_text(encoding='utf-8'),c))
            self.assertLessEqual(budget['tokens'],16000)
        for role in roles:
            context=f'engineering-fixture-{stage}-{role}';author.dispatch(run,role,context,'engineering_fixture',stage)
            paragraph=dict(paragraph_id='N001',main_point='fixture purpose',author_intent_assessment='fixture supported')
            if role=='reader':
                ss=r['sentence_claims'];paragraph.update(first_sentence=r['text'][ss[0]['start']:ss[0]['end']],first_sentence_outline='fixture first purpose',main_point_after_reading='fixture whole purpose',topic_alignment='aligned',topic_alignment_reason='fixture rationale',sentence_links=[dict(sentence_index=i+1,text=r['text'][s['start']:s['end']],relation='linked',reason='fixture explanation') for i,s in enumerate(ss)],unclear_references=[],reread_points=[])
            if role=='style':paragraph.update(source_features=['fixture source'],output_features=['fixture output'],fit_notes='fixture fit')
            report=dict(input_sha256=sha(directory/f'{role}_input.json'),context_id=context,model='engineering_fixture',isolation='independent_context',status='completed',issues=[],paragraphs=[paragraph])
            if role=='fidelity':
                checks=[]
                for req in p['author_requirements']:
                    proof=[dict(artifact_id='execution:run',fact='development_evaluation')] if req.get('kind')=='workflow' else [dict(paragraph_id='N001',quote=r['text'])]
                    checks.append(dict(requirement_id=req['requirement_id'],status='satisfied',reason='engineering fixture evidence',evidence=proof))
                report.update(reviewed_claim_ids=['C001','C002'],author_request_coverage='complete',author_requirement_checks=checks)
            save(directory/f'{role}_review.json',report)

    def ready(self,**kwargs):
        c,run,l,p=self.task(**kwargs);self.write(c,run,l,p,'zh');author.preview(c,run);self.reviews(c,run,l,p,'zh');flow.confirm(run,'Development simulation',evaluation=True)
        return c,run,l,p

    def test_end_to_end_prose_handoff(self):
        c,run,l,p=self.ready();self.write(c,run,l,p,'en');self.reviews(c,run,l,p,'en');finalize(c,run)
        self.assertEqual(read(run/'manifest.json')['status'],'completed_development_evaluation')
        actual=(run/'restructured_zh.md').read_text(encoding='utf-8').strip()
        payload=json.loads(read(run/'N001/writer_messages.json')[1]['content'])
        self.assertEqual(payload['approved_chinese_paragraph'],actual)
        assembly=read(run/'N001/assembly.json');self.assertLessEqual(assembly['tokens'],6500)
        self.assertEqual(set(payload['paragraph_plan']['claim_order']),{'C001','C002'})
        self.assertEqual(len(payload['source_sentences']),2)
        self.assertNotIn('〔C001〕',actual);self.assertNotIn('## N001',actual)
        confirmation=read(run/'reviews/fidelity_input.json')['execution_evidence'][0]['facts']['structure_confirmation']
        self.assertEqual(confirmation['approval_kind'],'evaluation_simulation')
        self.assertEqual(confirmation['author_message'],'Development simulation')
        self.assertEqual(confirmation['chinese_draft_sha256'],sha(run/'chinese_draft.json'))
    def test_english_waits_for_actual_chinese(self):
        c,run,l,p=self.task()
        with self.assertRaises(ValueError):flow.candidates(c,run,'N001')
    def test_one_result_cannot_hide_extra_paragraphs(self):
        c,run,l,p=self.task();self.write(c,run,l,p,'zh')
        f=run/'N001/zh/result.json';r=read(f);r['text']=r['text'].replace('。 ','。\n\n');save(f,r)
        with self.assertRaisesRegex(ValueError,'one prose paragraph'):flow.validate_result(c,run,'N001','zh')
    def test_candidate_inference_cannot_be_mandatory(self):
        c,run,l,p=self.task();l['claims'][0]['origin']='model_inference'
        with self.assertRaises(ValueError):flow.validate_ledger(run,l)
    def test_model_candidate_preserved_outside_required_claims(self):
        c,run,l,p=self.task();l['model_candidates']=[dict(candidate_id='X1',text='more experiments',supports=['C001'],reason='separate branch',status='deferred')];flow.validate_plan(run,l,p)
    def test_author_paragraph_count_enforced(self):
        c,run,l,p=self.task();p['author_structure']['paragraph_count']=3
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_fabricated_author_quote_rejected(self):
        c,run,l,p=self.task();p['author_requirements'][0]['source_quote']='unsupported'
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_conflicting_example_rejected(self):
        c,run,l,p=self.task()
        with self.assertRaises(ValueError):author.relation_selection(dict(relation_fit='conflict'),p['paragraphs'][0])
    def test_omitted_first_sentence_review_blocks_confirmation(self):
        c,run,l,p=self.task();self.write(c,run,l,p,'zh');author.preview(c,run);self.reviews(c,run,l,p,'zh')
        f=run/'zh_reviews/reader_review.json';r=read(f);r['paragraphs'][0].pop('first_sentence_outline');save(f,r)
        with self.assertRaises(ValueError):flow.confirm(run,'fixture',evaluation=True)
    def test_author_relation_violation_blocks_confirmation(self):
        c,run,l,p=self.task();self.write(c,run,l,p,'zh');author.preview(c,run);self.reviews(c,run,l,p,'zh')
        f=run/'zh_reviews/fidelity_review.json';r=read(f);r['author_requirement_checks'][0]['status']='violated';save(f,r)
        with self.assertRaises(ValueError):flow.confirm(run,'fixture',evaluation=True)
    def test_wrong_review_quote_rejected(self):
        c,run,l,p=self.ready();f=run/'zh_reviews/reader_review.json';r=read(f);r['paragraphs'][0]['sentence_links'][0]['text']='a different version';save(f,r)
        with self.assertRaises(ValueError):author.verify_reports(run,'zh')
    def test_changed_chinese_revokes_english(self):
        c,run,l,p=self.ready();(run/'restructured_zh.md').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):flow.check_plan(run)
    def test_review_without_invocation_rejected(self):
        c,run,l,p=self.ready();f=run/'zh_reviews/dispatch.json';r=read(f);r['reader']['context_id']='wrong';save(f,r)
        with self.assertRaises(ValueError):author.verify_reports(run,'zh')
    def test_simulated_confirmation_disallowed_for_user_run(self):
        c,run,l,p=self.ready();m=read(run/'manifest.json');m['task_kind']='user_draft';save(run/'manifest.json',m)
        with self.assertRaises(ValueError):flow.confirm(run,'simulation',evaluation=True)
    def test_l0_preserves_exact_source_input(self):
        c,run,l,p=self.task('L0');self.write(c,run,l,p,'en')
        payload=json.loads(read(run/'N001/writer_messages.json')[1]['content'])
        self.assertEqual(payload['accepted_source_paragraph'],(run/'input.md').read_text(encoding='utf-8'))
    def test_default_initialize_selects_v3(self):
        type(self).serial+=1;c=fixture_config(self.root);c['runs']=self.root/'runs'
        source=self.root/f'default-{self.serial}.md';source.write_text('空间信息需要验证。',encoding='utf-8')
        run=Path(prepare(c,source,'D04','introduction',query='spatial validation',run_id=f'default-{self.serial}',requirements='保留原意')['run'])
        flow.initialize(c,run)
        self.assertEqual(read(run/'manifest.json')['workflow_version'],3)
        self.assertEqual((run/'author_request.md').read_text(encoding='utf-8'),'保留原意')
    def test_workflow_requirement_uses_actual_execution_record(self):
        c,run,l,p=self.ready(workflow_requirement=True);author.verify_reports(run,'zh')
        payload=json.loads(read(run/'N001/zh/writer_messages.json')[1]['content'])
        self.assertNotIn('MODE',[x['requirement_id'] for x in payload['author_requirements']])
    def test_scientific_requirement_needs_body_evidence(self):
        c,run,l,p=self.ready();f=run/'zh_reviews/fidelity_review.json';r=read(f)
        r['author_requirement_checks'][0]['evidence']=[dict(artifact_id='execution:run',fact='development_evaluation')];save(f,r)
        with self.assertRaisesRegex(ValueError,'evidence type'):author.verify_reports(run,'zh')
    def test_workflow_evidence_cannot_invent_execution(self):
        c,run,l,p=self.ready(workflow_requirement=True);f=run/'zh_reviews/fidelity_review.json';r=read(f)
        r['author_requirement_checks'][-1]['evidence']=[dict(artifact_id='execution:missing',fact='development_evaluation')];save(f,r)
        with self.assertRaisesRegex(ValueError,'actual execution'):author.verify_reports(run,'zh')
    def test_multiline_crlf_bom_preserved_and_normalized(self):
        type(self).serial+=1;c=fixture_config(self.root);c['runs']=self.root/'runs'
        source=self.root/f'crlf-{self.serial}.md';raw=b'\xef\xbb\xbf'+'空间信息有价值。\r\n\r\n形态分析需要验证。\r\n'.encode('utf-8');source.write_bytes(raw)
        run=Path(prepare(c,source,'D04','introduction',query='spatial validation',run_id=f'crlf-{self.serial}')['run']);flow.initialize(c,run)
        self.assertEqual((run/'original_input.md').read_bytes(),raw)
        self.assertNotIn(b'\r',(run/'input.md').read_bytes())
        self.assertEqual(read(run/'manifest.json')['input_sha256'],sha(run/'input.md'))
        self.assertEqual(len(read(run/'ledger_seed.json')['source_units']),2)
    def test_legacy_v2_normalized_input_hash_remains_readable(self):
        c,run,l,p=fixtures.LogicTests.task(self,'L0','空间信息有价值。\n\n形态分析需要验证。')
        original=(run/'input.md').read_text(encoding='utf-8');(run/'input.md').write_bytes(original.replace('\n','\r\n').encode('utf-8'))
        m=read(run/'manifest.json');m['input_sha256']=text_sha(original);save(run/'manifest.json',m)
        flow.validate_plan(run,l,p)

if __name__=='__main__':unittest.main(verbosity=2)
