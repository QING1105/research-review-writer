import unittest,tempfile,copy,json
from pathlib import Path
from common import save,read,sha,config,text_sha
import reference_audit as audit

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name);self.source=self.run/'source.md'
    def tearDown(self):self.tmp.cleanup()
    def parse(self,text):
        self.source.write_text(text,encoding='utf-8');return audit.parse(self.source,self.run)
    def test_synthetic_docx_reference_regression(self):
        import zipfile
        from xml.sax.saxutils import escape
        # Original fixture text, deliberately malformed to exercise the parser.
        paragraphs=['Exampleton et al. compared measurements. Missingname et al. discussed validation. Secondname et al. tested a method.',
                    'References',
                    '1. Exampleton A, Secondname B. Synthetic title [J]. Example Journal, 2020, 1(1): 742-262.',
                    '2. Anonymous. Another synthetic title [J]. Example Journal, 2020, 2(1): 1-4.']
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        xml+=''.join('<w:p><w:r><w:t>'+escape(p)+'</w:t></w:r></w:p>' for p in paragraphs)
        xml+='</w:body></w:document>'
        source=self.run/'synthetic.docx'
        with zipfile.ZipFile(source,'w') as archive:archive.writestr('word/document.xml',xml)
        a=audit.parse(source,self.run)
        self.assertEqual(a['doc']['n_entries'],2)
        self.assertEqual(a['doc']['inline_markers'],'absent')
        self.assertIn('pages_invalid',a['entries'][0]['offline_flags'])
        self.assertIn('author_invalid',a['entries'][1]['offline_flags'])
        mentions={x['surname']:x['status'] for x in a['mentions']}
        self.assertEqual(mentions['Exampleton'],'matched')
        self.assertEqual(mentions['Missingname'],'orphan_mention')
        self.assertEqual(mentions['Secondname'],'weak_match')
    def test_pages_abbreviation_and_malformed(self):
        self.assertEqual(audit.expanded_pages('742-62'),('742-762',False));self.assertTrue(audit.expanded_pages('742-262')[1]);self.assertTrue(audit.expanded_pages('19422-194227')[1])
    def test_apa_vancouver_gbt(self):
        for text in ['Xing M. A title [J]. Endocr Rev, 2007, 28(7): 742-762.','Xing M. A title. Endocr Rev. 2007;28(7):742-762.','Xing, M. (2007). A title. Endocr Rev, 28(7), 742-762.']:
            p=audit.parse_entry(text,1)['parsed'];self.assertEqual(p['title'],'A title');self.assertEqual(p['year'],2007)
    def test_pending_and_offline_block(self):
        a=self.parse('Evidence[1].\n\nReferences\n\nXing M. A title [J]. Endocr Rev, 2007, 28(7): 742-762.')
        self.assertEqual(audit.gate(self.run)['status'],'blocked')
        a['entries'][0].update(status='unverified_offline',queries=[dict(source='offline',query='test',retrieved_at='test',response=None)]);save(self.run/'references_audit.json',a)
        self.assertIn('REF001: unverified_offline',audit.gate(self.run)['errors'])
    def test_missing_inline_mapping_blocks_after_lookup(self):
        a=self.parse('Xing et al. studied this.\n\nReferences\n\nXing M. A title [J]. Endocr Rev, 2007, 28(7): 742-762.')
        a['entries'][0].update(status='not_found',queries=[dict(source='crossref',query='test',retrieved_at='test',response='{}',status_code=200)]);save(self.run/'references_audit.json',a)
        self.assertIn('inline_markers_absent_unconfirmed',audit.gate(self.run)['errors'])
        save(self.run/'decision.json',dict(origin='none_by_author',pairs=[],author_message='fixture author chooses no citations'))
        self.assertEqual(audit.decisions(self.run,self.run/'decision.json',True)['status'],'passed')
    def test_fabricated_correction_rejected(self):
        a=self.parse('Evidence[1].\n\nReferences\n\nXing M. A title [J]. Endocr Rev, 2007, 28(7): 742-762.')
        a['entries'][0].update(status='metadata_mismatch',queries=[dict(source='crossref',query='test',retrieved_at='test',status_code=200,response='{"message":{"items":[]}}')],matched=dict(year=2099),corrections=dict(year=2099));save(self.run/'references_audit.json',a)
        self.assertTrue(any('correction_not_in_database' in e for e in audit.gate(self.run)['errors']))
    def test_retracted_decision_required(self):
        a=self.parse('Evidence[1].\n\nReferences\n\nXing M. A title [J]. Endocr Rev, 2007, 28(7): 742-762.')
        a['entries'][0].update(status='not_found',retracted=True,queries=[dict(source='crossref',query='test',retrieved_at='test',response='{}')]);save(self.run/'references_audit.json',a)
        self.assertIn('REF001: retracted_undecided',audit.gate(self.run)['errors'])
    def test_no_references_passes_without_network(self):
        self.parse('A sentence without references.');self.assertEqual(audit.gate(self.run)['status'],'passed')
    def test_repeated_citation_occurrences(self):
        a=self.parse('A[1–3]. B[1].');self.assertEqual(len(a['markers']),2);self.assertEqual(a['markers'][0]['ref_keys'],['REF001','REF002','REF003'])
    def test_a0_prevents_ledger_creation(self):
        self.parse('A[1].');(self.run/'input.md').write_text('A[1].',encoding='utf-8');save(self.run/'manifest.json',dict(reference_audit_required=True))
        from logic_flow import initialize
        with self.assertRaisesRegex(ValueError,'A0 blocked'):initialize(config(),self.run)
        self.assertFalse((self.run/'ledger_seed.json').exists())
    def support_fixture(self,verdict='supports'):
        self.parse('A source sentence.');(self.run/'input.md').write_text('A source sentence.',encoding='utf-8');save(self.run/'manifest.json',{})
        ledger={'claims':[{'claim_id':'C001','text_zh':'A source sentence.'}]}
        directory=self.run/'support';directory.mkdir()
        packet={'evidence':'An exact abstract sentence.'};save(directory/'input.json',packet)
        save(directory/'manifest.json',{'ledger_content_hash':text_sha(json.dumps(ledger,sort_keys=True)),'audit_sha256':sha(self.run/'references_audit.json'),'tasks':[{'claim_id':'C001','ref_key':'REF001','status':'pending','input':'input.json','input_sha256':sha(directory/'input.json'),'result':'result.json'}]})
        result={'input_sha256':sha(directory/'input.json'),'claim_id':'C001','ref_key':'REF001','isolation':'independent_context','context_id':'fixture-review-context','model':'fixture-model','support':verdict,'scope_diff':[],'evidence':packet['evidence'],'note':'Fixture support decision'}
        save(directory/'result.json',result);return ledger,result
    def test_support_exact_evidence_and_hash(self):
        ledger,result=self.support_fixture();audit.support_validate(self.run,ledger)
        result['evidence']='Invented evidence.';save(self.run/'support/result.json',result)
        with self.assertRaisesRegex(ValueError,'exact supplied'):audit.support_validate(self.run,ledger)
    def test_contradiction_requires_actual_author_decision(self):
        ledger,result=self.support_fixture('contradicts')
        with self.assertRaisesRegex(ValueError,'Contradiction'):audit.support_validate(self.run,ledger)
        result['author_decision']={'action':'keep_as_is','author_message':'Fixture author keeps the statement'};save(self.run/'support/result.json',result);audit.support_validate(self.run,ledger)
    def test_changed_claim_invalidates_support(self):
        ledger,result=self.support_fixture();ledger['claims'][0]['text_zh']='Changed statement'
        with self.assertRaisesRegex(ValueError,'Ledger differs'):audit.support_validate(self.run,ledger)
    def test_support_same_context_rejected(self):
        ledger,result=self.support_fixture();result['isolation']='writer_self_review';save(self.run/'support/result.json',result)
        with self.assertRaisesRegex(ValueError,'Independent'):audit.support_validate(self.run,ledger)

if __name__=='__main__':unittest.main(verbosity=2)
