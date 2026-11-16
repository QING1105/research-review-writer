"""Behavioral checks for argument-driven selection and source citation provenance."""
import copy
import tempfile
import unittest
from common import *
from test_support import fixture_config
import content_selection as selection
import logic_flow as flow
import test_logic_flow as fixtures


class ContentSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='content-selection-')
        cls.root=Path(cls.temp.name).resolve();cls.serial=0
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def task(self,text='背景比较研究[37]。本段讨论模型身份核实[16]。',level='L2',policy='argument_first'):
        c,run,l,p=fixtures.LogicTests.task(self,level,text)
        m=read(run/'manifest.json');m['content_policy']=policy;save(run/'manifest.json',m)
        return c,run,l,p

    def omit(self,p,cid='C001'):
        p['editorial_selection']=dict(omitted_claims=[dict(claim_id=cid,reason='Comparison example does not develop this paragraph topic.',effect_on_argument='Model identity remains the topic and its supporting evidence is retained.')])
        for para in p['paragraphs']:
            para['claim_order']=[x for x in para['claim_order'] if x!=cid]
            para['main_point_claims']=para['claim_order'][:1]
            para['ops']=[dict(op='OMIT_IRRELEVANT_OR_REDUNDANT',reason='Keep the model-identity argument focused.')]
        p['paragraphs']=[para for para in p['paragraphs'] if para['claim_order']]

    def test_chapter3_comparison_can_be_removed_with_its_citation(self):
        text='Studies in colorectal cancer have compared PDO drug responses with patient treatment outcomes [37].\n\nSampling bias may alter the model response.'
        c,r,l,p=self.task(text);before=copy.deepcopy(l);self.omit(p)
        flow.validate_plan(r,l,p);out,audit=selection.project(l,p,'argument_first')
        self.assertEqual(l,before)
        self.assertEqual(audit['omitted_claim_ids'],['C001'])
        self.assertEqual(audit['citation_actions'][0]['action'],'omitted_with_claims')
        self.assertEqual(out['citation_occurrences'],[])
        self.assertEqual([x['claim_id'] for x in out['claims']],['C002'])

    def test_unrecorded_claim_loss_rejected(self):
        c,r,l,p=self.task();p['paragraphs'][0]['claim_order']=['C002']
        with self.assertRaisesRegex(ValueError,'omitted claim'):flow.validate_plan(r,l,p)

    def test_omission_needs_relevance_and_argument_effect(self):
        c,r,l,p=self.task();self.omit(p);del p['editorial_selection']['omitted_claims'][0]['effect_on_argument']
        with self.assertRaisesRegex(ValueError,'effect'):flow.validate_plan(r,l,p)

    def test_explicit_preserve_all_blocks_omission(self):
        c,r,l,p=self.task(policy='preserve_all');self.omit(p)
        with self.assertRaisesRegex(ValueError,'argument_first'):flow.validate_plan(r,l,p)

    def test_l0_keeps_author_approved_content(self):
        c,r,l,p=self.task(level='L0');self.omit(p)
        with self.assertRaisesRegex(ValueError,'L0'):flow.validate_plan(r,l,p)

    def test_new_v3_defaults_and_explicit_preservation(self):
        c,r,l,p=self.task()
        flow.initialize(c,r,'L2',workflow_version=3)
        self.assertEqual(read(r/'manifest.json')['content_policy'],'argument_first')
        m=read(r/'manifest.json');m['requested_content_policy']='preserve_all';save(r/'manifest.json',m)
        flow.initialize(c,r,'L2',workflow_version=3)
        self.assertEqual(read(r/'manifest.json')['content_policy'],'preserve_all')
        flow.initialize(c,r,'L0',workflow_version=3)
        self.assertEqual(read(r/'manifest.json')['content_policy'],'preserve_all')

    def test_shared_citation_survives_when_one_claim_is_removed(self):
        c,r,l,p=self.task('模型形成球状结构且仍需核实身份[16]。')
        second=copy.deepcopy(l['claims'][0]);second['claim_id']='C002';second['text_zh']='仍需核实身份';l['claims'].append(second)
        l['claims'][0]['text_zh']='形成球状结构';p['paragraphs'][0]['claim_order'].append('C002');self.omit(p)
        flow.validate_plan(r,l,p);out,audit=selection.project(l,p,'argument_first')
        self.assertEqual(out['citation_occurrences'][0]['required_claim_ids'],['C002'])
        self.assertEqual(audit['citation_actions'][0]['action'],'retained')

    def test_shared_citation_can_follow_claims_into_separate_paragraphs(self):
        c,r,l,p=self.task('模型形成球状结构且仍需核实身份[16]。')
        second=copy.deepcopy(l['claims'][0]);second.update(claim_id='C002',text_zh='仍需核实身份');l['claims'].append(second)
        new=copy.deepcopy(p['paragraphs'][0]);new.update(new_para_id='N002',claim_order=['C002'],main_point_claims=['C002'])
        p['paragraphs'].append(new)
        flow.validate_plan(r,l,p);out,audit=selection.project(l,p,'argument_first')
        self.assertEqual(len(out['citation_occurrences']),2)
        self.assertTrue(all(x['source_occurrence_ids']==['CIT0001'] for x in out['citation_occurrences']))
        self.assertEqual(audit['citation_actions'][0]['action'],'split_with_claims')

    def test_duplicate_reference_locations_can_be_consolidated(self):
        c,r,l,p=self.task('模型身份需要核实[16]。培养物状态需要核实[16]。')
        p['editorial_selection']=dict(citation_merges=[dict(occurrence_ids=['CIT0001','CIT0002'],paragraph_id='N001',reason='Both checks are expressed in one sentence with the same evidence.')])
        flow.validate_plan(r,l,p);out,audit=selection.project(l,p,'argument_first')
        self.assertEqual(out['citation_occurrences'][0]['required_claim_ids'],['C001','C002'])
        self.assertEqual(out['citation_occurrences'][0]['source_occurrence_ids'],['CIT0001','CIT0002'])
        self.assertEqual(len(out['citation_occurrences']),1)

    def test_distinct_references_keep_separate_evidence_links(self):
        c,r,l,p=self.task();p['editorial_selection']=dict(citation_merges=[dict(occurrence_ids=['CIT0001','CIT0002'],paragraph_id='N001',reason='Combine')])
        with self.assertRaisesRegex(ValueError,'identical reference'):flow.validate_plan(r,l,p)

    def test_same_sentence_excluded_context_is_explicit(self):
        c,r,l,p=self.task('模型形成球状结构且仍需核实身份[16]。')
        second=copy.deepcopy(l['claims'][0]);second.update(claim_id='C002',text_zh='仍需核实身份');l['claims'].append(second)
        p['paragraphs'][0]['claim_order'].append('C002');self.omit(p)
        claims,cites,excluded=selection.writer_projection(l,p,'N001','argument_first')
        self.assertEqual([x['claim_id'] for x in claims],['C002']);self.assertEqual(excluded[0]['claim_id'],'C001')

    def test_writer_payload_and_result_use_selected_citations(self):
        c,r,l,p=self.task();self.omit(p)
        fixtures.LogicTests.activate(self,c,r,l,p);flow.confirm(r,'Engineering fixture confirmation')
        flow.candidates(c,r,'N001');d=r/'N001'
        candidate=next(x for x in rows(d/'paragraph_candidates.jsonl') if count(json.dumps([dict(reference_id=x['chunk_id'],source_quote=x['source_quote'],progression=x['abstract_pattern'],application='fixture')],ensure_ascii=False),c)<=600)
        sentence=next(rows(d/'candidates.jsonl'))
        save(d/'selection.json',dict(language=[dict(id=sentence['style_id'],reason='fixture')],paragraphs=[dict(id=candidate['chunk_id'],reason='fixture')]))
        flow.assemble(c,r,'N001',d/'selection.json')
        payload=json.loads(read(d/'writer_messages.json')[1]['content'])
        self.assertEqual([x['claim_id'] for x in payload['claims']],['C002'])
        self.assertEqual([x['occurrence_id'] for x in payload['citation_occurrences']],['CIT0002'])
        text='Model identity requires verification {{cite:REF016}}.';m=flow.TOKEN.search(text)
        result=dict(input_sha256=read(d/'assembly.json')['payload_sha256'],text=text,sentence_claims=[dict(start=0,end=len(text),claims=['C002'],role='content',citations=[dict(occurrence_id='CIT0002',claims=['C002'],start=m.start(),end=m.end())])],style_alignment=[dict(reference_id=payload['reference_language'][0]['reference_id'],output_span='Model',reference_span=payload['reference_language'][0]['source_quote'],feature='engineering fixture')])
        save(d/'result.json',result);flow.validate_result(c,r,'N001')
        result['sentence_claims'][0]['citations']=[];save(d/'result.json',result)
        with self.assertRaisesRegex(ValueError,'planned output citation'):flow.validate_result(c,r,'N001')

    def test_one_citation_can_support_two_sentences_without_forcing_a_long_sentence(self):
        c,r,l,p=self.task('模型身份需要核实[16]。培养物状态需要核实[16]。')
        p['editorial_selection']=dict(citation_merges=[dict(occurrence_ids=['CIT0001','CIT0002'],paragraph_id='N001',reason='The same evidence supports two consecutive statements.')])
        fixtures.LogicTests.activate(self,c,r,l,p);flow.confirm(r,'Engineering fixture confirmation')
        flow.candidates(c,r,'N001');d=r/'N001'
        card=next(x for x in rows(d/'paragraph_candidates.jsonl') if count(json.dumps([dict(reference_id=x['chunk_id'],source_quote=x['source_quote'],progression=x['abstract_pattern'],application='fixture')],ensure_ascii=False),c)<=600)
        lang=next(rows(d/'candidates.jsonl'))
        save(d/'selection.json',dict(language=[dict(id=lang['style_id'],reason='fixture')],paragraphs=[dict(id=card['chunk_id'],reason='fixture')]))
        flow.assemble(c,r,'N001',d/'selection.json');payload=json.loads(read(d/'writer_messages.json')[1]['content'])
        first='Model identity requires verification.';second='Culture state also requires verification {{cite:REF016}}.';text=first+' '+second;marker=flow.TOKEN.search(text)
        result=dict(input_sha256=read(d/'assembly.json')['payload_sha256'],text=text,sentence_claims=[dict(start=0,end=len(first),claims=['C001'],role='content',citations=[]),dict(start=len(first)+1,end=len(text),claims=['C002'],role='content',citations=[dict(occurrence_id='MERGED_CIT0001',claims=['C001','C002'],start=marker.start(),end=marker.end())])],style_alignment=[dict(reference_id=lang['style_id'],output_span='Model',reference_span=payload['reference_language'][0]['source_quote'],feature='engineering fixture')])
        save(d/'result.json',result);flow.validate_result(c,r,'N001')
        result['sentence_claims'][0]['claims']=['C002'];result['sentence_claims'][1]['claims']=['C002'];save(d/'result.json',result)
        with self.assertRaisesRegex(ValueError,'supported claims'):flow.validate_result(c,r,'N001')


if __name__=='__main__':unittest.main(verbosity=2)
