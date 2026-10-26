"""Extract only visible PixiBB Yui photos and explicitly linked public pages."""
import hashlib,re
from html import unescape
from gallery_dl.extractor.common import Extractor,Message

class PixibbYuiExtractor(Extractor):
    category='yui_pixibb'
    subcategory='album'
    pattern=r'https?://sexy\.pixibb\.com/([^/?#]+)/(?:\?.*)?$'
    directory_fmt=('YUI','{album_id}')
    filename_fmt='{num:04}.{extension}'
    archive_fmt='{album_id}_{num}'
    def __init__(self,match):
        super().__init__(match)
        self.slug=match.group(1)
    def items(self):
        origin='https://sexy.pixibb.com/'+self.slug+'/'
        html=self.request(origin).text
        if 'https://hub.pixibb.com/model/yui/' not in html:
            raise ValueError('Korean Yui model identity not confirmed')
        heading=re.search(r'<title>(.*?)</title>',html,re.S)
        if not heading:raise ValueError('Missing public title')
        title=unescape(heading.group(1)).replace(' | PixiBB','').strip()
        count=re.search(r'\((\d+) photos?',title,re.I)
        if not count:raise ValueError('No advertised photo count')
        expected=int(count.group(1));aid='pixibb-'+hashlib.sha256(self.slug.encode()).hexdigest()[:12]
        pages={1:origin};selected={}
        for href in re.findall(r'href=["\x27]([^"\x27]+)',html):
            match=re.fullmatch(re.escape(origin)+r'(\d+)/',unescape(href))
            if match and 1<int(match.group(1))<=100:pages[int(match.group(1))]=unescape(href)
        for page,url in sorted(pages.items()):
            text=html if page==1 else self.request(url).text
            for image in re.findall(r'(?:src|data-src)=["\x27]([^"\x27]+)',text):
                image=unescape(image)
                match=re.fullmatch(r'https://(?:imgx\d{3}|images\d{2})\.pixibb\.com/[^"<> ]+/[^/]+-(\d{3,4})\.(jpg|jpeg|png|webp)',image,re.I)
                if match:
                    number=int(match.group(1))
                    if number in selected and selected[number]!=image:raise ValueError('Conflicting sequence')
                    selected[number]=image
        if set(selected)!=set(range(1,expected+1)):
            raise ValueError(f'Incomplete publicly visible sequence {len(selected)}/{expected}')
        common={'album_id':aid,'title':title,'expected':expected,'source_page':origin,
                'ai_enhanced':'AI Enhanced' in title,'publisher_original_verified':False}
        yield Message.Directory,None,common
        for number,url in sorted(selected.items()):
            yield Message.Url,url,{**common,'num':number,'image_url':url,'extension':url.rsplit('.',1)[-1]}
