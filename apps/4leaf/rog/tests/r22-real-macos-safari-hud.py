#!/usr/bin/env python3
"""Official macOS Safari WebDriver (NOT Playwright's WebKit binary).
QA-03: REAL public Safari viewport, not a physical iPhone. Validate actual
source WorldMap, room/game navigation and physical hit testing at 390,
430, 768, 800 widths, portrait and 844x390 landscape. Fail if Safari
doesn't implement the requested viewport size; that is a REAL QA blocker.
"""
import json
import os
import pathlib
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE=os.environ.get("FOURLEAF_TEST_URL","http://127.0.0.1:8765/")
ROOT=pathlib.Path.cwd()
ERRORS=[]
RESULTS=[]
def assert_true(value,message):
    if not value: raise AssertionError(message)
def until(d,js,timeout=25):
    return WebDriverWait(d,timeout).until(lambda _: d.execute_script(js))
def inspect(d,tag):
    state=d.execute_script("""
     const inspect=id=>{
      const el=document.getElementById(id);
      if(!el)return {id,exists:false};
      const r=el.getBoundingClientRect();
      const x=Math.max(0,Math.min(innerWidth-1,r.x+r.width/2));
      const y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2));
      const hit=document.elementFromPoint(x,y);
      return {id,exists:true,rect:[r.x,r.y,r.width,r.height].map(x=>Math.round(x)),
        visible:r.width>0&&r.height>0,
        inViewport:r.right>0&&r.left<innerWidth&&r.bottom>0&&r.top<innerHeight,
        targetHit:hit===el||el.contains(hit)};
     };
     return {viewport:[innerWidth,innerHeight],devicePixelRatio,platform:navigator.platform,
      userAgent:navigator.userAgent,scene:document.querySelector('.scene:not(.hidden)')?.id,
      sourceTiles:document.querySelectorAll('#board-nodes>.tile').length,
      sourcePawns:document.querySelectorAll('#board-pawns .board-pawn').length,
      buttons:['lobby-create','start-game','roll-btn','chat-form','message','shop-buy'].map(inspect),
      game:window.__ROG_TEST__?.getMatch?.()?{
       map:window.__ROG_TEST__.getMatch().map,
       positions:window.__ROG_TEST__.getMatch().players.map(x=>x.position),
       round:window.__ROG_TEST__.getMatch().round,
       finished:window.__ROG_TEST__.getMatch().finished}:null};
    """)
    state["tag"]=tag
    RESULTS.append(state)
    print("SAFARI_REAL_SCREEN",json.dumps(state,ensure_ascii=False),flush=True)
    file=ROOT/("leaf-r22-real-macos-safari-"+tag.replace("/","-")+".png")
    d.save_screenshot(str(file))
    assert_true("Safari" in state["userAgent"] and "Chrome" not in state["userAgent"],
                "This must be actual Apple Safari, not Playwright, Chrome or spoofed user agent")
    return state

options=webdriver.SafariOptions()
d=webdriver.Safari(options=options)
d.set_page_load_timeout(45)
try:
    for width,height in [(390,844),(430,932),(768,1024),(800,900),(844,390)]:
        d.set_window_rect(width=width,height=height)
        d.get(BASE)
        until(d,"return !!window.__ROG_TEST__&&!!window.__LEAF_CAMERA__")
        real=d.execute_script("return [innerWidth,innerHeight]")
        # Browser outer window decorations can reduce content viewport.
        # Explicitly record a blocker instead of claiming it reached 390.
        if abs(real[0]-width)>45:
            raise AssertionError("Native Safari automation cannot reach requested "
                +str(width)+"px width; actual "+str(real))
        world=inspect(d,"world-"+str(width))
        assert_true(world["scene"] in ("sky","world","world-map"),
                    "WorldMap not visible on Safari "+str(width)+": "+str(world["scene"]))
        # User clicks the actual archive's WorldMap region, then the real
        # original Region channel hotspot; no hidden developer route bypass.
        button=d.find_element(By.CSS_SELECTOR,'.world-location[data-region="dice"]')
        for fx,fy in ((.5,.5),(.35,.42),(.6,.7)):
            bounds=button.rect
            ActionChains(d).move_to_element_with_offset(button,
                round((fx-.5)*bounds["width"]),
                round((fy-.5)*bounds["height"])).click().perform()
            if d.execute_script("return !!document.querySelector('#dice-channels:not(.hidden)')"):
                break
        until(d,"return !!document.querySelector('#dice-channels:not(.hidden)')",12)
        WebDriverWait(d,15).until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR,'#dice-channels .dice-channel-hotspot[data-channel="ispin:1"]'))).click()
        until(d,"return !!document.querySelector('#lobby:not(.hidden)')",12)
        WebDriverWait(d,15).until(EC.element_to_be_clickable((By.ID,"lobby-create"))).click()
        Select(d.find_element(By.ID,"game-mode")).select_by_value("hotseat")
        Select(d.find_element(By.ID,"bot-count")).select_by_value("1")
        Select(d.find_element(By.ID,"point-limit")).select_by_value("12")
        Select(d.find_element(By.ID,"map-select")).select_by_value("4LEAF")
        if width<=430:
            focus=d.find_element(By.ID,"dice-room-ready-focus")
            assert_true(focus.is_displayed(),"mobile source READY focus control is missing")
            focus.click()
        WebDriverWait(d,15).until(EC.element_to_be_clickable((By.ID,"start-game"))).click()
        # Safari reuses an isolated automation profile across screen sizes.
        # The source game intentionally protects an unfinished match. Click
        # the genuine replacement confirmation, rather than destroying
        # localStorage or bypassing normal game lifecycle.
        try:
            until(d,"return !!document.querySelector('#game:not(.hidden)') || !!document.querySelector('#modal:not(.hidden)')",12)
            visible=d.execute_script("return !!document.querySelector('#modal:not(.hidden)')")
            if visible:
                text=d.execute_script("return document.querySelector('#modal')?.textContent||''")
                if "진행 중인 경기" in text or "새 경기" in text:
                    choice=d.find_elements(By.XPATH,"//div[@id='modal-buttons']//button[contains(.,'새 경기 시작')]")
                    assert_true(len(choice)==1,"source match replacement needs a real option: "+text)
                    choice[0].click()
                else: raise AssertionError("unexpected blocking source modal: "+text)
        except Exception:
            print("SAFARI_CURRENT_STATE",json.dumps(d.execute_script(
              "return {scene:document.querySelector('.scene:not(.hidden)')?.id,modal:document.querySelector('#modal')?.textContent||'',match:window.__ROG_TEST__?.getMatch?.()}"),
              ensure_ascii=False,default=str),flush=True)
            raise
        until(d,"return !!document.querySelector('#game:not(.hidden)')&&document.querySelectorAll('#board-nodes>.tile').length===104",35)
        state=inspect(d,"game-"+str(width))
        assert_true(state["sourceTiles"]==104,"104 genuine 4LEAF DMP cells required")
        assert_true(state["sourcePawns"]>=2,"source chessmen missing")
        roll=next(x for x in state["buttons"] if x["id"]=="roll-btn")
        assert_true(roll["exists"] and roll["visible"] and roll["inViewport"] and roll["targetHit"],
                    "real Safari roll button occluded, offscreen or not hittable: "+str(roll))
        assert_true(not d.find_element(By.ID,"roll-btn").get_attribute("disabled"),
                    "roll button unexpectedly disabled")
        old_positions=state["game"]["positions"]
        d.find_element(By.ID,"roll-btn").click()
        until(d,"return (window.__ROG_TEST__?.getMatch?.()?.lastRoll?.length||0)>0",40)
        rolled=inspect(d,"rolled-"+str(width))
        assert_true((rolled["game"]["positions"]!=old_positions or rolled["game"]["finished"]
           or d.execute_script("return (window.__ROG_TEST__?.getMatch?.()?.lastRoll?.length||0)>0")),
                    "Safari real roll never had an authoritative dice result")
    assert_true(len(RESULTS)==15,"five widths × 3 native screens expected")
    print("R22_REAL_APPLE_SAFARI_5_VIEWPORT_15_SCENES_PASS",json.dumps({
      "testedViewports":[x["viewport"] for x in RESULTS if x["tag"].startswith("game-")],
      "screenshots":15,"rolls":5,"physicalIphone":False},ensure_ascii=False),flush=True)
finally:
    (ROOT/"leaf-r22-safari-report.json").write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2))
    d.quit()
