"""Accept only the requested actor's explicitly visible large photo addresses."""
import tempfile
from pathlib import Path
from http_album_collector import discover

album='69fe5f89416c6b5fd5aaf760'
origin='https://www.girl-atlas.com/album?id='+album
target={'url':origin,'adapter':'girlatlas','expected':2}
def html(title='[AI Enhanced] Yui (유이)',count='2/2',wrong_path=False):
 prefix='/static/albums/2026-05-08/'+('another-album' if wrong_path else album)+'/'
 return ('<h1>'+title+'</h1><a href="/tag?id=68f545da0e41b873a9cfea1c">Yui</a>'
         '<label>Photos</label><div class="field-control">'+count+'</div>'
         +''.join('<a data-fancybox="Photo" data-src="'+prefix+str(i)+'.jpg!lrg" index="'+str(i)+'" visible="True"><img data-src="'+prefix+str(i)+'.jpg!sml"></a>' for i in range(2))
         +'<a data-fancybox="Photo" data-src="/hidden-file.jpg" index="2" visible="False">Login</a>')
class Client:
 def __init__(self,body):self.body=body
 def get(self,url):assert url==origin;return self.body
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 photos,pages=discover(target,Client(html()),root)
 assert set(photos)=={1,2} and all(u.endswith('!lrg') for u in photos.values())
 assert pages==[origin]
 for i,body in enumerate([html(title='Yui, another model'),html(count='1/2'),html(wrong_path=True)]):
  cache=root/str(i);cache.mkdir()
  try:discover(target,Client(body),cache)
  except ValueError:pass
  else:raise AssertionError('Unconfirmed actor, count or image scope accepted')
print('PUBLIC_GIRLATLAS_ACTOR_COUNT_VISIBILITY_AND_LARGE_LINK_SCOPE_PASS')
