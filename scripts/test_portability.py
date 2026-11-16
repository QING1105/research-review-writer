"""Public configuration and credential handling checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import common
from run_writing import prepare
from test_support import fixture_config

class PortabilityTests(unittest.TestCase):
    def test_local_override_merges_and_explicit_config_stays_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            template=common.read(common.SKILL/'assets/project-template.yaml')
            common.save(root/'assets/project-template.yaml',template)
            common.save(root/'project.local.json',{'corpus_root':'./private-data','budgets':{'max_candidates':3}})
            common.save(root/'explicit.json',dict(template,corpus_root='./explicit-data'))
            with patch.object(common,'SKILL',root):
                local=common.config();explicit=common.config(root/'explicit.json')
            self.assertEqual(local['root'],root/'private-data')
            self.assertEqual(local['budgets']['max_candidates'],3)
            self.assertEqual(local['budgets']['style_tokens'],template['budgets']['style_tokens'])
            self.assertEqual(explicit['root'],root/'explicit-data')
            self.assertEqual(explicit['budgets']['max_candidates'],template['budgets']['max_candidates'])

    def test_run_manifest_omits_configured_contact_and_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);c=fixture_config(root)
            c['reference_audit'].update(ncbi_api_key='synthetic-test-credential',contact_email='sample@example.invalid')
            source=root/'draft.md';source.write_text('空间信息需要验证。',encoding='utf-8')
            run=Path(prepare(c,source,'D04','introduction',run_id='privacy-test')['run'])
            text=(run/'manifest.json').read_text(encoding='utf-8')
            self.assertNotIn('synthetic-test-credential',text)
            self.assertNotIn('sample@example.invalid',text)
            self.assertEqual(c['reference_audit']['ncbi_api_key'],'synthetic-test-credential')
            self.assertEqual(json.loads(text)['config']['reference_audit']['ncbi_api_key'],'[redacted]')

if __name__=='__main__':unittest.main()
