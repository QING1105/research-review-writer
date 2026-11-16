"""Behavioral checks for retrieval boundaries, budgets, provenance and coverage."""
import copy,json,shutil,tempfile,unittest
from common import *
from test_support import fixture_config
from measure_style import build
from retrieve_style import retrieve
from run_writing import prepare
from assemble_prompt import assemble
from validate_records import validate

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='writer-tests-')
        cls.root=Path(cls.temp.name).resolve()
        cls.c=fixture_config(cls.root)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def task(self,name):
        c=copy.deepcopy(self.c);c['runs']=self.root/'runs'
        p=self.root/(name+'.md');p.write_text('空间转录组学保留空间信息。形态特征需要验证。',encoding='utf-8')
        x=prepare(c,p,'D04','introduction','spatial morphology validation',run_id=name,task_kind='engineering_test')
        run=Path(x['run']);cand=list(rows(run/'P001-U01/candidates.jsonl'))
        sel={'units':{'P001-U01':[dict(style_id=x['style_id'],applies_to='P001-U01',reason='检验实际候选引用与预算') for x in cand[:3]]}}
        file=run/'selection.json';save(file,sel);return c,run,file
    def test_domain_and_candidate_budget(self):
        cards,meta=retrieve(self.c,domain_values('D03'),'abstract','microfluidic chip 灌流')
        self.assertTrue(cards)
        self.assertTrue(all(x['domain']==DOMAINS['D03'] and x['section']=='abstract' for x in cards))
        self.assertLessEqual(meta['candidate_tokens'],self.c['budgets']['candidate_tokens'])
    def test_long_multilingual_draft_coverage(self):
        c=copy.deepcopy(self.c);c['budgets']['draft_unit_tokens']=40
        draft='标题\n\n'+('空间转录组学保留空间信息。Morphology requires validation. '*30)+'\n\n结尾。'
        units=split_draft(draft,c);self.assertGreater(len(units),3)
        for u in units:self.assertEqual(draft[u['start']:u['end']],u['text']);self.assertLessEqual(count(u['text'],c),40)
    def test_unknown_selection_rejected(self):
        c,run,f=self.task('unknown');sel=read(f);sel['units']['P001-U01'][0]['style_id']='ST-MISSING';save(f,sel)
        with self.assertRaises(ValueError):assemble(c,run,f)
    def test_duplicate_and_reference_limit(self):
        c,run,f=self.task('duplicate');sel=read(f);sel['units']['P001-U01'].insert(1,sel['units']['P001-U01'][0]);save(f,sel)
        c['budgets']['max_references']=2;assemble(c,run,f)
        pack=read(run/'P001-U01/reference_pack.json')
        self.assertEqual(len(pack),2);self.assertEqual(len({x['style_id'] for x in pack}),2)
        self.assertTrue(read(run/'P001-U01/budget.json')['dropped'])
    def test_empty_style_budget_rejected(self):
        c,run,f=self.task('budget');c['budgets']['style_tokens']=1
        with self.assertRaises(ValueError):assemble(c,run,f)
    def test_exact_source_and_input_budget(self):
        c,run,f=self.task('valid');assemble(c,run,f)
        self.assertEqual(validate(c,run)['status'],'passed')
    def test_modified_writing_payload_rejected(self):
        c,run,f=self.task('tamper');assemble(c,run,f)
        p=run/'P001-U01/writer_messages.json';m=read(p);m[1]['content']+='modified';save(p,m)
        with self.assertRaises(AssertionError):validate(c,run)
    def test_index_growth_keeps_payload_bounded(self):
        c=copy.deepcopy(self.c);directory=self.root/'large-index';directory.mkdir()
        c['runtime']=directory;c['db']=directory/'style-index.sqlite3'
        shutil.copy2(self.c['db'],c['db']);shutil.copy2(self.c['runtime']/'index-manifest.json',directory/'index-manifest.json')
        db=connect(c);base=db.execute('SELECT * FROM cards WHERE domain=? LIMIT 1',(DOMAINS['D04'],)).fetchone()
        terms=db.execute('SELECT terms FROM card_fts WHERE rowid=?',(base['id'],)).fetchone()['terms']
        with db:
            for i in range(3000):
                payload=json.loads(base['payload']);payload['style_id']=f'SYNTHETIC-SCALE-{i}'
                cur=db.execute('INSERT INTO cards(style_id,domain,section,roles,family,payload) VALUES(?,?,?,?,?,?)',
                  (payload['style_id'],base['domain'],base['section'],base['roles'],base['family'],json.dumps(payload,ensure_ascii=False)))
                db.execute('INSERT INTO card_fts(rowid,terms) VALUES(?,?)',(cur.lastrowid,terms))
        db.close()
        cards,meta=retrieve(c,domain_values('D04'),'any','spatial morphology')
        self.assertTrue(cards);self.assertLessEqual(meta['candidate_tokens'],c['budgets']['candidate_tokens'])
        self.assertLessEqual(len(cards),c['budgets']['max_candidates'])

if __name__=='__main__':unittest.main(verbosity=2)
