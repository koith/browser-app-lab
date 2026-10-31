"""Actual CI matrix arguments must fit the executable parser and cover every photo."""
import contextlib
import io
import itertools
from pathlib import Path
import unittest

import yaml
from qa_new_physical_photos import parse_cli


class PhysicalMatrixTests(unittest.TestCase):
    def test_every_real_matrix_job_parses_and_partitions_all_photos(self):
        root=Path(__file__).resolve().parents[2]
        workflow=yaml.safe_load((root/'.github/workflows/gallery-newly-stored-photo-qa.yml').read_text())
        matrix=workflow['jobs']['actual-deployed-originals']['strategy']['matrix']
        axes={k:v for k,v in matrix.items() if k!='include'}
        rows=[dict(zip(axes,values)) for values in itertools.product(*axes.values())]+matrix['include']
        mimmi=[r for r in rows if r['model']=='mimmi']
        for first,second in zip(mimmi[::2],mimmi[1::2]):
            self.assertEqual(first['shard'],second['shard'])
            self.assertEqual({first['browser'],second['browser']},{'chromium','webkit'})
        for row in rows:
            args=parse_cli(['--model',row['model'],'--browser',row['browser'],
                '--shard',str(row['shard']),'--shards',str(row['shards']),'--out','unused.json'])
            self.assertEqual((args.shard,args.shards),(row['shard'],row['shards']))
        for model,browser in itertools.product(['mimmi','yui'],['chromium','webkit']):
            jobs=[r for r in rows if r['model']==model and r['browser']==browser]
            for count in [1,12,558,991,1200]:
                positions=[i for r in jobs for i in range(count) if i%r['shards']==r['shard']]
                self.assertEqual(sorted(positions),list(range(count)),(model,browser,count))

    def test_invalid_and_unbounded_shards_still_fail(self):
        for shard,shards in [(0,0),(0,25),(-1,24),(24,24)]:
            with self.subTest(shard=shard,shards=shards),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_cli(['--model','mimmi','--browser','webkit','--shard',str(shard),
                               '--shards',str(shards),'--out','unused.json'])


if __name__=='__main__':unittest.main(verbosity=2)
