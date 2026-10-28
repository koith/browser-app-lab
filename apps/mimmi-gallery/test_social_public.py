#!/usr/bin/env python3
from collect_social_public import public_image,social_page,photos_in_profile
def main():
    assert social_page("https://twoucan.com/profile/Mimmi_official")
    assert not social_page("https://twoucan.com/profile/SomeoneElse")
    assert public_image("https://pbs.twimg.com/media/FjxHK8PVEAA4d1_.jpg")
    for u in ("https://pbs.twimg.com/profile_images/a.jpg","http://pbs.twimg.com/media/a.jpg",
              "https://evil.example/media/a.jpg","https://pbs.twimg.com/media/sound.mp4"):
        assert not public_image(u),u
    html='<h1>Mimmissu17</h1><p>@Mimmi_official</p><a href="https://pbs.twimg.com/media/FjxHK8PVEAA4d1_.jpg">photo</a><img src="https://pbs.twimg.com/media/FjxHK8PVEAA4d1_.jpg"><img src="https://evil.example/a.jpg">'
    photos,ok=photos_in_profile(html,"https://twoucan.com/profile/Mimmi_official")
    assert ok and len(photos)==1,photos
    assert photos_in_profile(html.replace("@Mimmi_official","@Somebody"),"https://twoucan.com/profile/Mimmi_official")==([],False)
    print("MIMMI_OFFICIAL_SOCIAL_IDENTITY_AND_IMAGE_URL_PASS")
if __name__=="__main__":main()
