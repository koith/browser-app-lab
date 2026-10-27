"""OCR may establish a site mark's presence, never establish absence."""
import hashlib,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from review_site_watermarks import review
with tempfile.TemporaryDirectory() as temp:
 p=Path(temp)/'photo.png';Image.new('RGB',(600,900),'gray').save(p);raw=p.read_bytes();meta={'sha256':hashlib.sha256(raw).hexdigest()}
 def output(text,y=850,confidence=95):
  return SimpleNamespace(returncode=0,stdout='left\ttop\twidth\theight\tconf\ttext\n10\t'+str(y)+'\t120\t20\t'+str(confidence)+'\t'+text+'\n')
 for text,y,conf,expected in [('PixiBB.COM',850,95,'present'),('ARTGRAVIA',850,95,'unknown'),('PixiBB.COM',850,25,'unknown'),('PixiBB.COM',400,95,'unknown'),('',850,95,'unknown')]:
  with patch('review_site_watermarks.subprocess.run',return_value=output(text,y,conf)):
   result=review(p,meta);assert result['status']==expected
   if expected=='present':assert result['sha256']==meta['sha256']
 assert p.read_bytes()==raw
 with patch('review_site_watermarks.subprocess.run',side_effect=FileNotFoundError):assert review(p,meta)=={'status':'unknown'}
print('OCR_SITE_MARK_PRESENCE_ONLY_NO_ABSENCE_CLAIM_OR_PIXEL_EDIT_PASS')
