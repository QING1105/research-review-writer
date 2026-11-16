"""Integration tests for source coverage, edit boundaries, references and review gates."""
import copy
import tempfile
import unittest
from common import *
from test_support import fixture_config
from run_writing import prepare
import logic_flow as flow

class LogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='logic-tests-')
        cls.root=Path(cls.temp.name).resolve()
        cls.serial=0
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def task(self,level='L0',text='空间转录组学保留基因表达的空间背景。形态特征的提取仍需要仔细验证。'):
        type(self).serial+=1;c=fixture_config(self.root);c['runs']=self.root/'runs';name=f'test-{self.serial}'
        source=self.root/(name+'.md');source.write_text(text,encoding='utf-8')
        run=Path(prepare(c,source,'D04','introduction',query='spatial morphology validation',run_id=name)['run'])
        flow.initialize(c,run,level,workflow_version=2);ledger=read(run/'ledger_seed.json');paras=[]
        for p in ledger['source_units']:
            ids=[]
            for s in p['sentences']:
                cid=f'C{len(ledger["claims"])+1:03}';ids.append(cid)
                occ=[x for x in ledger['citation_occurrences'] if x['sid']==s['sid']]
                ledger['claims'].append(dict(claim_id=cid,sids=[s['sid']],text_zh=s['text'],type='background',strength='established',polarity='positive',quantities=[],conditions=[],citations=list(dict.fromkeys(k for x in occ for k in x['ref_keys'])),citation_occurrences=[x['occurrence_id'] for x in occ],xrefs=[],relations=[]))
            paras.append(dict(new_para_id=f'N{len(paras)+1:03}',target_source_para=p['para_id'],source_paras=[p['para_id']],domains=domain_values('D04'),section='introduction',paragraph_type='background_and_value',query='spatial morphology validation',main_point='空间信息的价值与验证',main_point_claims=[ids[0]],claim_order=ids,ops=[dict(op='KEEP',reason='保持原顺序')],additions=[]))
        for sig in ledger['signals']:
            ledger['signal_reviews'].append(dict(signal_id=sig['signal_id'],claims=[x['claim_id'] for x in ledger['claims'] if sig['sid'] in x['sids']],note='Engineering fixture signal mapping'))
        plan=dict(level=level,paragraphs=paras,diagnosis=[],author_queries=[])
        save(run/'ledger-proposal.json',ledger);save(run/'plan-proposal.json',plan)
        return c,run,ledger,plan

    def activate(self,c,run,ledger,plan):
        save(run/'ledger-proposal.json',ledger);save(run/'plan-proposal.json',plan)
        return flow.accept_plan(c,run,run/'ledger-proposal.json',run/'plan-proposal.json')

    def assembled(self,source_text=None):
        c,run,ledger,plan=self.task(**({'text':source_text} if source_text else {}));self.activate(c,run,ledger,plan)
        flow.candidates(c,run,'N001');directory=run/'N001'
        sentences=list(rows(directory/'candidates.jsonl'));paras=list(rows(directory/'paragraph_candidates.jsonl'))
        chosen=None
        for card in paras:
            ref=dict(reference_id=card['chunk_id'],source_quote=card['source_quote'],progression=card['abstract_pattern'],application='学习主旨与限定关系的推进')
            if count(json.dumps([ref],ensure_ascii=False),c)<=600:chosen=card;break
        self.assertIsNotNone(chosen)
        selection=dict(language=[dict(id=sentences[0]['style_id'],reason='学习信息对象与谓语搭配')],paragraphs=[dict(id=chosen['chunk_id'],reason='学习主旨与限定关系的推进')])
        save(directory/'selected.json',selection);flow.assemble(c,run,'N001',directory/'selected.json')
        payload=json.loads(read(directory/'writer_messages.json')[1]['content']);ref=payload['reference_language'][0]
        texts=['Spatial transcriptomics preserves the spatial context of gene expression.','Extracting morphological features still requires careful validation.']
        for i,cl in enumerate(ledger['claims']):
            if cl['citations']:texts[i]=texts[i][:-1]+' {{cite:'+','.join(cl['citations'])+'}}.'
        text=' '.join(texts);boundary=len(texts[0]);mapping=[];cursor=0
        for i,(fragment,cl) in enumerate(zip(texts,ledger['claims'])):
            bindings=[]
            for oid in cl['citation_occurrences']:
                match=flow.TOKEN.search(fragment);bindings.append(dict(occurrence_id=oid,claims=[cl['claim_id']],start=cursor+match.start(),end=cursor+match.end()))
            mapping.append(dict(start=cursor,end=cursor+len(fragment),claims=[cl['claim_id']],citations=bindings));cursor+=len(fragment)+1
        result=dict(input_sha256=read(directory/'assembly.json')['payload_sha256'],text=text,
            sentence_claims=mapping,
            style_alignment=[dict(reference_id=ref['reference_id'],output_span='Spatial transcriptomics',reference_span=ref['source_quote'],feature='Engineering fixture correspondence record; quality is assessed separately')])
        save(directory/'result.json',result)
        return c,run,ledger,plan

    def test_ledger_dropped_sentence_rejected(self):
        c,run,l,p=self.task();l['claims'].pop()
        with self.assertRaises(ValueError):flow.validate_ledger(run,l)
    def test_l0_reorder_rejected(self):
        c,run,l,p=self.task();p['paragraphs'][0]['claim_order'].reverse()
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_l1_reorder_waits_for_confirmation(self):
        c,run,l,p=self.task('L1');p['paragraphs'][0]['claim_order'].reverse();p['paragraphs'][0]['ops']=[dict(op='REORDER_WITHIN_PARA',reason='Engineering fixture reorder')];self.activate(c,run,l,p)
        with self.assertRaises(ValueError):flow.check_plan(run)
        flow.confirm(run,'Engineering fixture author confirmation');flow.check_plan(run)
    def test_changed_preview_revokes_confirmation(self):
        c,run,l,p=self.task('L1');self.activate(c,run,l,p);flow.confirm(run,'Engineering fixture confirmation')
        (run/'restructured_zh.md').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):flow.check_plan(run)
    def test_l1_nonadjacent_move_rejected(self):
        c,run,l,p=self.task('L1','空间信息有价值。\n\n形态信息有价值。\n\n分析需要验证。')
        p['paragraphs'][0]['claim_order'],p['paragraphs'][2]['claim_order']=p['paragraphs'][2]['claim_order'],p['paragraphs'][0]['claim_order']
        p['paragraphs'][0]['source_paras']=['P003'];p['paragraphs'][2]['source_paras']=['P001']
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_duplicate_claim_rejected(self):
        c,run,l,p=self.task();p['paragraphs'][0]['claim_order'].append('C001')
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_l2_split_requires_author_confirmation(self):
        c,run,l,p=self.task('L2');first=copy.deepcopy(p['paragraphs'][0]);second=copy.deepcopy(first)
        first['claim_order']=['C001'];first['main_point_claims']=['C001']
        second['new_para_id']='N002';second['claim_order']=['C002'];second['main_point_claims']=['C002']
        for paragraph in (first,second):paragraph['ops']=[dict(op='SPLIT_PARAGRAPH',reason='Engineering fixture split')]
        p['paragraphs']=[first,second];self.activate(c,run,l,p)
        with self.assertRaises(ValueError):flow.check_plan(run)
        flow.confirm(run,'Engineering fixture split confirmation');flow.check_plan(run)
    def test_l1_split_rejected(self):
        c,run,l,p=self.task('L1');p['paragraphs'].append(copy.deepcopy(p['paragraphs'][0]));p['paragraphs'][1]['new_para_id']='N002'
        with self.assertRaises(ValueError):flow.validate_plan(run,l,p)
    def test_quote_mutation_in_seed_rejected(self):
        c,run,l,p=self.task();l['source_units'][0]['sentences'][0]['text']='替换原稿'
        with self.assertRaises(ValueError):flow.validate_ledger(run,l)
    def test_repeated_citations_keep_occurrence_identity(self):
        c,run,l,p=self.task(text='研究报道了空间信息[5–7]。另一研究报告验证[5]。')
        flow.validate_ledger(run,l)
        self.assertEqual(len(l['references']),3);self.assertEqual(len(l['citation_occurrences']),2)
        l['claims'][1]['citation_occurrences']=[];l['claims'][1]['citations']=[]
        with self.assertRaises(ValueError):flow.validate_ledger(run,l)
    def test_number_negation_signal_requires_review(self):
        c,run,l,p=self.task(text='该研究中70%的标本未形成培养物。');l['signal_reviews']=[]
        with self.assertRaises(ValueError):flow.validate_ledger(run,l)
    def test_two_reference_channels_and_budget(self):
        c,run,l,p=self.assembled();a=read(run/'N001/assembly.json');self.assertLessEqual(a['tokens'],6500)
        payload=json.loads(read(run/'N001/writer_messages.json')[1]['content'])
        self.assertTrue(payload['reference_language']);self.assertTrue(payload['reference_paragraphs']);flow.validate_result(c,run,'N001')
    def test_output_claim_omission_rejected(self):
        c,run,l,p=self.assembled();f=run/'N001/result.json';r=read(f);r['sentence_claims'][1]['claims']=['C001'];save(f,r)
        with self.assertRaises(ValueError):flow.validate_result(c,run,'N001')
    def test_citation_binding_tracks_claim_and_occurrence(self):
        c,run,l,p=self.assembled('空间转录组学保留基因表达的空间背景[5–7]。形态特征的提取仍需要仔细验证[5]。')
        flow.validate_result(c,run,'N001');file=run/'N001/result.json';original=read(file)
        wrong=copy.deepcopy(original);wrong['sentence_claims'][0]['citations'][0]['claims']=['C002'];save(file,wrong)
        with self.assertRaises(ValueError):flow.validate_result(c,run,'N001')
        missing=copy.deepcopy(original);missing['sentence_claims'][0]['citations']=[];save(file,missing)
        with self.assertRaises(ValueError):flow.validate_result(c,run,'N001')
    def test_citation_numbering_and_xref(self):
        l=dict(references=[dict(ref_key='REF035',original_number=35),dict(ref_key='REF016',original_number=16)],anchors=[dict(anchor_id='fig:1',render_label_en='Fig. 1')])
        text='A {{cite:REF035}}; B {{cite:REF016,REF035}}; {{xref:fig:1}}.'
        output,m=flow.render_citations(text,l,'first_appearance');self.assertEqual(output,'A [1]; B [2,1]; Fig. 1.')
        output,m=flow.render_citations(text,l,'keep_original');self.assertEqual(output,'A [35]; B [16,35]; Fig. 1.')
    def test_review_separation_and_gate(self):
        c,run,l,p=self.assembled();flow.review_inputs(c,run)
        reader=read(run/'reviews/reader_input.json');self.assertEqual(set(reader),{'instruction','english'})
        fidelity=read(run/'reviews/fidelity_input.json');self.assertNotIn('reference_language',json.dumps(fidelity))
        for role in ('reader','fidelity','style'):
            report=dict(input_sha256=sha(run/f'reviews/{role}_input.json'),context_id='same-context',model='test_fixture',isolation='independent_context',status='completed',issues=[],reviewed_claim_ids=['C001','C002'],paragraphs=[dict(paragraph_id='N001')])
            save(run/f'reviews/{role}_review.json',report)
        with self.assertRaises(ValueError):flow.finish(c,run)
        f=run/'reviews/reader_review.json';r=read(f);r['context_id']='second-test-context';save(f,r)
        f=run/'reviews/style_review.json';r=read(f);r['context_id']='third-test-context';save(f,r)
        flow.finish(c,run);self.assertTrue((run/'output.md').exists())
        f=run/'N001/result.json';r=read(f);r['queries']=['changed after reviews'];save(f,r)
        with self.assertRaises(ValueError):flow.finish(c,run)
    def test_author_edits_saved_and_confirmation_revoked(self):
        c,run,l,p=self.task('L1');self.activate(c,run,l,p);flow.confirm(run,'fixture confirmation')
        file=run/'author-copy.md';file.write_text('修改后的中文〔C001〕\n作者新增内容',encoding='utf-8')
        out=flow.ingest_edits(run,file);record=read(out['review']);self.assertEqual(record['missing_claim_tags'],['C002'])
        with self.assertRaises(ValueError):flow.check_plan(run)

if __name__=='__main__':unittest.main(verbosity=2)
