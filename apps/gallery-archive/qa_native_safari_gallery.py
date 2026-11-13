#!/usr/bin/env python3
"""Native Apple Safari Desktop smoke against BOTH deployed photo galleries.

This is real macOS Safari WebDriver (not Playwright WebKit). It is NOT a
physical iPhone/Safari acceptance test: report that limitation explicitly.
"""
import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = "https://koith.github.io/browser-app-lab/apps"
MODELS = ("mimmi", "yui")


def ready(driver):
    return driver.execute_script("""
        return document.readyState === 'complete'
            && typeof stored !== 'undefined' && stored.length > 0
            && document.querySelectorAll('#albumgrid .album').length > 0;
    """)


def check_model(driver, model):
    url = f"{ROOT}/{model}-gallery/"
    driver.get(url)
    wait = WebDriverWait(driver, 65, poll_frequency=.7)
    wait.until(ready)
    cards = driver.execute_script("""
        return [...document.querySelectorAll('#albumgrid .album')]
            .filter(e => e.offsetParent !== null).length;
    """)
    assert cards > 0, (model, "no real album cards")
    # Prefer a genuine immutable Pages-JPEG album: first image is usable
    # without depending on a Cloudflare private-owner media token.
    chosen = driver.execute_script("""
        const cards=[...document.querySelectorAll('#albumgrid .album')];
        const card=cards.find(e=>{
          const img=e.querySelector('img[src]');
          return img && new URL(img.src).pathname.includes('/stored-albums/');
        }) || cards[0];
        if (!card) return null;
        const image=card.querySelector('img');
        const photo = image?.getAttribute('src') || '';
        card.click();
        return {id:card.dataset.id||'', url:photo};
    """)
    assert chosen, (model, "no clickable gallery card")
    wait.until(lambda d: d.execute_script("""
        return !document.querySelector('#detail')?.hidden
            && document.querySelectorAll('#detailphotos button.photo').length > 0;
    """))
    count = driver.execute_script(
        "return document.querySelectorAll('#detailphotos button.photo').length")
    # Exercise the real photo button rather than setting JS state directly.
    driver.execute_script("""
        const photos=[...document.querySelectorAll('#detailphotos button.photo')];
        const chosen=photos.find(e=>{
          const img=e.querySelector('img[src]');
          return img && new URL(img.src).pathname.includes('/stored-albums/');
        }) || photos[0];
        if (chosen) chosen.click();
    """)
    wait.until(lambda d: d.execute_script("""
        return document.querySelector('#lightbox')?.classList.contains('open')
            && document.querySelector('#full')?.complete
            && document.querySelector('#full')?.naturalWidth > 0;
    """))
    real = driver.execute_script("""
        const img=document.querySelector('#full'), src=new URL(img.currentSrc);
        return {bytes_source:src.origin, dimensions:[img.naturalWidth,img.naturalHeight],
          gallery_title:document.title, lightbox:true,
          image_src_protocol:src.protocol, photo_count:+document.querySelectorAll('#detailphotos button.photo').length};
    """)
    assert real["image_src_protocol"] == "https:"
    assert min(real["dimensions"]) >= 300
    driver.find_element(By.ID, "close").click()
    wait.until(lambda d: not d.execute_script(
        "return document.querySelector('#lightbox')?.classList.contains('open')"))
    driver.refresh()
    wait.until(ready)
    assert driver.execute_script("return document.querySelectorAll('#albumgrid .album').length") > 0
    result = {"model":model, "engine":"real macOS Safari / safaridriver",
              "album_cards":cards, "opened_album":chosen["id"],
              "album_photo_buttons":count,
              "full_image_width":real["dimensions"][0],
              "full_image_height":real["dimensions"][1],
              "close_and_reload":"PASS", "actual_physical_iPhone":"NOT_TESTED"}
    print("NATIVE_SAFARI_GALLERY_REAL_URL_SHA_SAFE_SMOKE",json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    print("NATIVE_SAFARI_ENV",json.dumps({
        "macos": os.uname().sysname, "physical_iphone":False}),flush=True)
    safari = webdriver.Safari()
    safari.set_page_load_timeout(85)
    safari.set_window_size(430, 932)  # phone-like layout, NOT real iPhone hardware
    try:
        results = [check_model(safari, model) for model in MODELS]
    finally:
        safari.quit()
    assert len(results)==2
    print("G11_BOTH_MODELS_NATIVE_SAFARI_DESKTOP_PASS_PHYSICAL_IPHONE_UNVERIFIED",flush=True)


if __name__ == "__main__":
    main()
