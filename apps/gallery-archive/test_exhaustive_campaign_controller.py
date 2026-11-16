"""Regression: stop only after exhaustive SHA coverage or safe budget/stall."""
import unittest
from exhaustive_campaign_controller import decide


def state(m, n, covered, recent):
    return {'schema_version':1,'model':m,'last_cycle_size':n,
            'attempted_ids':[f'{i:032x}' for i in range(covered)],
            'last_run_attempts':recent}


class CampaignControllerTests(unittest.TestCase):
    def test_continue_when_mimmi_unfinished_but_yui_finished(self):
        a=decide({'mimmi':state('mimmi',4571,256,256),
                  'yui':state('yui',3227,3227,0)},step=1)
        self.assertTrue(a['dispatch'])
        self.assertEqual(a['models']['mimmi']['remaining'],4315)
        self.assertEqual(a['models']['yui']['remaining'],0)

    def test_full_coverage_stops_and_does_not_wrap(self):
        a=decide({'mimmi':state('mimmi',4571,4571,55),
                  'yui':state('yui',3227,3227,0)},step=31)
        self.assertFalse(a['dispatch'])
        self.assertTrue(a['all_attempted'])

    def test_no_progress_aborts_futile_loop(self):
        a=decide({'mimmi':state('mimmi',10,2,0),
                  'yui':state('yui',10,3,0)},step=10)
        self.assertFalse(a['dispatch'])
        self.assertTrue(a['no_progress'])

    def test_max_steps_aborts(self):
        a=decide({'mimmi':state('mimmi',100,55,14),
                  'yui':state('yui',100,100,0)},step=64)
        self.assertFalse(a['dispatch'])
        self.assertTrue(a['max_steps_reached'])

    def test_pending_unreadable_retry_keeps_campaign_running_once(self):
        mimmi=state('mimmi',10,10,5)
        mimmi['retry_pending_ids']=[f'{i:032x}' for i in range(3)]
        a=decide({'mimmi':mimmi,'yui':state('yui',10,10,0)},step=8)
        self.assertTrue(a['dispatch'])
        self.assertEqual(a['models']['mimmi']['pending_retry'],3)
        self.assertEqual(a['models']['mimmi']['remaining'],3)
        mimmi['retry_pending_ids']=[]
        mimmi['unverified_after_retry_ids']=[f'{i:032x}' for i in range(3)]
        a=decide({'mimmi':mimmi,'yui':state('yui',10,10,0)},step=9)
        self.assertFalse(a['dispatch'])
        self.assertTrue(a['all_attempted'])
        self.assertEqual(a['models']['mimmi']['unverified_after_retry'],3)

    def test_remaining_source_page_leads_continue_after_all_photo_shas_done(self):
        mimmi=state('mimmi',5,5,0)
        mimmi['source_pending_pages']=[{
            'album_id':'pop-kitty',
            'link':{'url':f'https://source-gallery.org/album/{i}'}
        } for i in range(5)]
        mimmi['last_source_pages_reviewed']=2
        other=state('yui',10,10,0)
        progress=decide({'mimmi':mimmi,'yui':other},step=32)
        self.assertTrue(progress['dispatch'])
        self.assertEqual(progress['models']['mimmi']['pending_source_page_reviews'],5)
        self.assertEqual(progress['models']['mimmi']['remaining'],5)
        # Once the candidate queue is fully exhausted, no phantom further
        # run should dispatch, regardless of the last positive review count.
        mimmi['source_pending_pages']=[]
        finished=decide({'mimmi':mimmi,'yui':other},step=33)
        self.assertFalse(finished['dispatch'])
        self.assertTrue(finished['all_attempted'])
        bad=state('mimmi',5,5,0)
        bad['source_pending_pages']=[{'album_id':'a','link':{'url':'https://site.org/a'}},
                                     {'album_id':'b','link':{'url':'https://site.org/a'}}]
        with self.assertRaisesRegex(ValueError,'CORRUPT_SOURCE_REVIEW'):
            decide({'mimmi':bad,'yui':other},step=34)

    def test_invalid_checkpoint_aborts_rather_than_research_from_scratch(self):
        with self.assertRaisesRegex(ValueError,'INVALID_CAMPAIGN'):
            decide({'mimmi':state('yui',9,1,1),'yui':state('yui',5,1,1)},step=1)
        with self.assertRaisesRegex(ValueError,'CORRUPT'):
            a=state('mimmi',2,3,2)
            decide({'mimmi':a,'yui':state('yui',10,1,1)},step=1)


if __name__=='__main__':
    unittest.main()
