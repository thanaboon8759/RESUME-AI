import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate_models
import manage_policy
from auto_policy import PolicyError, load_policy


class EvidenceTests(unittest.TestCase):
    def frozen(self):
        return {'protocol_sha256':'p','extraction_gates':copy.deepcopy(manage_policy.EXTRACTION_GATES),
                'ocr_gates':{'success_rate':1,'cer_max':.05,'per_language_cer_max':.08}}

    def test_changed_gates_and_protocol_cannot_promote(self):
        frozen=self.frozen()
        with patch.dict(manage_policy.EXTRACTION_GATES,{'date_exact':.1}):
            with self.assertRaisesRegex(ValueError,'gates changed'):
                manage_policy.enforce_frozen_gates(frozen,'p')
        with self.assertRaises(ValueError):manage_policy.enforce_frozen_gates(frozen,'different')

    def test_stale_summary_is_rejected_against_actual_text(self):
        rows=[{'model':'ocr','sample_id':'one','language':'en','status':'ok','result':{'source_text':'abc'}}]
        report={'summary':[{'model':'ocr','attempts':1,'success_rate':1,'cer':.5,
                           'by_language':{'en':{'attempts':1,'success_rate':1,'cer':.5}}}]}
        with self.assertRaisesRegex(ValueError,'recorded results'):
            manage_policy.verify_scores(report,rows,{'one':{'text':'abc'}},evaluate_models,'ocr')

    def test_configuration_change_rejects_policy_before_model_use(self):
        policy={'status':'validated','engine_sha256':'a'*64,
                'extraction':[{'name':'extract','digest':'b'*64}], 'ocr':[{'name':'ocr','digest':'c'*64}]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json';path.write_text(json.dumps(policy))
            with self.assertRaisesRegex(PolicyError,'configuration changed'):
                load_policy(path,expected_engine='d'*64)
            self.assertEqual(load_policy(path,expected_engine='a'*64)['status'],'validated')


if __name__=='__main__':unittest.main()
