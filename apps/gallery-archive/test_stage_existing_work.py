import unittest
from pathlib import Path
from stage_existing_work import reviewed_work

ROOT=Path(__file__).resolve().parents[2]


class ExistingWorkScopeTests(unittest.TestCase):
    def test_reviewed_scope_never_creates_an_unowned_or_other_model_work(self):
        aid='v2ph-actor-z63984ma'
        owner={'schema_version':1,'model':'mimmi','albums':[{'id':aid,'images':[{'number':1}]}]}
        book,previous=reviewed_work(ROOT,owner,'mimmi',aid)
        self.assertEqual(book['id'],previous['id']);self.assertTrue(book['visual_reference_required'])
        for model,work,doc in [('yui',aid,owner),('mimmi','unreviewed-work',owner),
                               ('mimmi','../unsafe',owner),('mimmi',aid,{**owner,'albums':[]})]:
            with self.subTest(model=model,work=work),self.assertRaises(ValueError):
                reviewed_work(ROOT,doc,model,work)


if __name__=='__main__':unittest.main(verbosity=2)
