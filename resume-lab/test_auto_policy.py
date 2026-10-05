import unittest

from auto_policy import PolicyError, attempt_stage, candidates, check_profile


class SelectionTests(unittest.TestCase):
    def test_malformed_policy_and_null_digests_are_rejected(self):
        inventory = [{'name':'tested','digest':None,'capabilities':['completion']}]
        for policy in [None, [], {'extraction':None}, {'extraction':[None]},
                       {'extraction':[{'name':'tested','digest':None}]}]:
            with self.subTest(policy=policy), self.assertRaises(PolicyError):
                candidates(policy,inventory,'extraction')

    def test_unknown_changed_and_incompatible_models_are_not_promoted(self):
        policy = {'extraction':[{'name':'tested','digest':'a'*64}]}
        for inventory in [[], [{'name':'unknown','digest':'a'*64,'capabilities':['completion']}],
                          [{'name':'tested','digest':'b'*64,'capabilities':['completion']}],
                          [{'name':'tested','digest':'a'*64,'capabilities':['vision']}]]:
            with self.subTest(inventory=inventory), self.assertRaises(PolicyError):
                candidates(policy,inventory,'extraction')

    def test_missing_primary_uses_only_validated_fallback(self):
        policy = {'ocr':[{'name':'primary','digest':'a'*64},{'name':'fallback','digest':'b'*64}]}
        self.assertEqual(candidates(policy,[{'name':'fallback','digest':'b'*64,'capabilities':['vision']}],'ocr'),['fallback'])

    def test_failed_validation_retries_and_records_actual_model(self):
        def call(name):
            return {'source_text':'Mira Python','schema_valid':True,
                    'profile':{'full_name':'Invented' if name=='primary' else 'Mira','skills':['Python']}}
        result, model, attempts = attempt_stage(['primary','fallback'],call,check_profile,(PolicyError,))
        self.assertEqual(model,'fallback')
        self.assertEqual([a['status'] for a in attempts],['error','ok'])
        self.assertEqual(result['profile']['full_name'],'Mira')

    def test_all_failures_raise_instead_of_returning_fake_profile(self):
        def fail(_):
            raise PolicyError('unavailable')
        with self.assertRaisesRegex(PolicyError,'All validated models failed'):
            attempt_stage(['one','two'],fail,lambda _:None,(PolicyError,))

    def test_missing_identity_is_allowed_if_other_facts_exist(self):
        check_profile({'schema_valid':True,'source_text':'Python', 'profile':{'full_name':'','skills':['Python']}})
        with self.assertRaisesRegex(PolicyError,'empty profile'):
            check_profile({'schema_valid':True,'source_text':'Python', 'profile':{'full_name':'','skills':[]}})


if __name__ == '__main__':
    unittest.main()

