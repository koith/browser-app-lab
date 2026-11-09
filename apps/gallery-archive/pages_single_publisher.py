"""Honor the existing Pages mode without admin changes or competing deploys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from pages_deployment_identity import REPO,validate

STAMP='https://koith.github.io/browser-app-lab/gallery-deployment.json'

def publisher(config):
    if config.get('build_type')=='workflow':return 'workflow'
    if config.get('build_type')=='legacy' and config.get('source')=={'branch':'main','path':'/'}:
        return 'native'
    raise ValueError('Pages mode/source does not match this repository main root')

def pages_api(method='GET',suffix=''):
    # The job token already has Pages write/read, never administration.
    token=os.environ['GH_TOKEN']
    request=Request('https://api.github.com/repos/'+REPO+'/pages'+suffix,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'},method=method)
    with urlopen(request,timeout=30) as response:
        body=response.read()
        return json.loads(body) if body else None

def exact_source():
    source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if source!=os.environ.get('GITHUB_SHA') or os.environ.get('GITHUB_REPOSITORY')!=REPO:
        raise ValueError('Publisher checkout/trigger identity differs')
    return source


GALLERY_TREES = ('mimmi-gallery', 'yui-gallery')

def _github_api(path):
    """Read only: use the existing Actions token for trusted GitHub commit/tree facts."""
    request=Request('https://api.github.com/repos/'+REPO+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
                 'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'})
    with urlopen(request,timeout=30) as response:
        return json.loads(response.read())

def _gallery_subtree_shas(commit):
    """Compare Git tree objects, not truncated 300-file comparison results."""
    if not isinstance(commit,str) or len(commit)!=40 or any(ch not in '0123456789abcdef' for ch in commit):
        raise ValueError('Invalid deployed commit')
    data=_github_api('/git/commits/'+commit)
    root=_github_api('/git/trees/'+data['tree']['sha'])
    apps=next((x for x in root['tree'] if x.get('path')=='apps' and x.get('type')=='tree'),None)
    if apps is None:raise ValueError('Missing apps tree')
    sub=_github_api('/git/trees/'+apps['sha'])
    result={}
    for name in GALLERY_TREES:
        item=next((x for x in sub['tree'] if x.get('path')==name and x.get('type')=='tree'),None)
        if item is None:raise ValueError('Missing gallery tree '+name)
        result[name]=item['sha']
    return result

def pages_gallery_equivalent(source,published):
    """Only a descendant commit with byte-identical gallery trees is acceptable."""
    if source==published:return True
    if not all(isinstance(x,str) and len(x)==40 and all(c in '0123456789abcdef' for c in x)
               for x in (source,published)):return False
    comparison=_github_api('/compare/'+source+'...'+published+'?per_page=1')
    if comparison.get('status')!='ahead' or comparison.get('behind_by')!=0:
        return False
    return _gallery_subtree_shas(source)==_gallery_subtree_shas(published)

def wait_native(source, allow_gallery_equivalent=False):
    # The pre-existing deployment window is 30 minutes. This observes the one
    # native publisher; it never uploads a second competing photo artifact.
    deadline=time.monotonic()+1800
    last=None
    equivalence_cache={}
    while time.monotonic()<deadline:
        try:
            with urlopen(STAMP,timeout=30) as response:raw=response.read()
            try:
                observed=validate(raw,source)
                if observed.get('build_kind')!='github-pages-jekyll':
                    raise ValueError('Expected the selected native publisher')
                print('NATIVE_PAGES_EXACT_SOURCE_VISIBLE',source,flush=True)
                return
            except ValueError:
                if not allow_gallery_equivalent:raise
                # The static publisher still needs exact identity; only the
                # photo QA accepts a later *native* commit with identical assets.
                data=json.loads(raw)
                if not isinstance(data,dict):raise
                published=data.get('source_commit')
                observed=validate(raw,published)
                if observed.get('build_kind')!='github-pages-jekyll':
                    raise ValueError('Cannot use a non-native gallery equivalent')
                if published not in equivalence_cache:
                    equivalence_cache[published]=pages_gallery_equivalent(source,published)
                if not equivalence_cache[published]:
                    raise ValueError('Published Pages is not a descendant with identical galleries')
                print('NATIVE_PAGES_GALLERY_EQUIVALENT_PASS',
                      'requested='+source,'published='+published,flush=True)
                return
        except (HTTPError,URLError,ValueError) as error:
            state=str(error)
            if state!=last:print('WAITING_FOR_NATIVE_PAGES_SOURCE',state[:200],flush=True);last=state
        time.sleep(15)
    raise TimeoutError('Native Pages did not expose the exact committed source identity')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--select',type=Path);p.add_argument('--wait-native',action='store_true');p.add_argument('--wait-native-gallery-equivalent',action='store_true');args=p.parse_args()
    source=exact_source()
    if args.select:
        selected=publisher(pages_api())
        with args.select.open('a') as stream:stream.write('publisher='+selected+'\n')
        print('EXISTING_PAGES_SINGLE_PUBLISHER',selected,flush=True)
    elif args.wait_native or args.wait_native_gallery_equivalent:
        if publisher(pages_api())!='native':raise ValueError('Native publisher mode changed')
        if args.wait_native and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch':
            pages_api('POST','/builds')
        wait_native(source,allow_gallery_equivalent=args.wait_native_gallery_equivalent)
    else:p.error('Choose --select or --wait-native')
