"""Real source-markup shapes: full-size body links, observed parts, no previews/AI mixing."""
from pathlib import Path
from tempfile import TemporaryDirectory
from http_album_collector import discover, fourkup_individual_links
origin='https://4kup.net/sweetbox-yui-cream-part1/'
large=lambda n:'https://lh5.ggpht.com/example/s0-e7/SWEETBOX-Yui-CREAM-4kUp-'+str(n).zfill(3)+'.webp'
preview=large(1).replace('/s0-e7/','/h1000-e7/')
def body(images,other=''):
 return '<h1>[SWEETBOX] Yui (유이) CREAM</h1><div class="entry-content">'+images+'</div>'+other
class Client:
 def get(self,url):
  if url==origin:return body('<a href="'+large(1)+'"><img src="'+preview+'"></a>', '<a href="'+origin.replace('part1','part2')+'">Part2</a><img src="'+large(3)+'">')
  assert url==origin.replace('part1','part2')
  return body('<img src="https://blogger.googleusercontent.com/img/b/example/s0/SWEETBOX-Yui-CREAM-002.webp">')
with TemporaryDirectory() as temp:
 photos,pages=discover({'url':origin,'adapter':'4kup','expected':2},Client(),Path(temp))
 assert set(photos)=={1,2} and len(pages)==2
 assert all('/h1000-e7/' not in u for u in photos.values())
for html in [body('<img src="'+preview+'">'),body('<img src="'+large(1).replace('SWEETBOX-Yui','AI-Enhanced-SWEETBOX-Yui')+'">'),body('<img src="'+large(1)+'">').replace('Yui (유이)','another model')]:
 try:fourkup_individual_links(html,origin,{'expected':2})
 except ValueError:pass
 else:raise AssertionError('Preview-only, AI-mixed, or unrelated source accepted')
print('PUBLIC_4KUP_FULL_BODY_LINKS_OBSERVED_PARTS_AND_NO_PREVIEW_OR_AI_SUBSTITUTION_PASS')
