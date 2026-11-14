'use strict';
/* Public 2003-01-05 archived 4LEAF Magic Carden market listing.
 * Archival snapshot: https://4leafmemorial.geld.kr/1451
 * Prices are the EXACT newspaper listing at that date, not immutable
 * original Dice/EXE data or the 2002 installer price formula.
 * Shop prices were dynamically adjusted in 2003; 2003-01-15 changes are
 * recorded separately at https://4leafmemorial.geld.kr/1454.
 * Exact CHR Korean-name matches are source-grounded; spelling/roman aliases
 * are explicitly INFERRED and may be wrong. Historical 2004 EXE price
 * aliases or 50%-resale are not claimed recovered. */
window.ORIGINAL_LEAF_SHOP_PRICE_SNAPSHOT_20030105=Object.freeze({
 date:'2003-01-05',
 source:'https://4leafmemorial.geld.kr/1451',
 kind:'archived-historical-shop-list/dynamic-market-snapshot',
 historicalExeRetailTableExtracted:false,
 serializedCardResale2003Jan15GP:1000,
 serializedCardResaleSource:'https://4leafmemorial.geld.kr/1454',
 serializedCardResaleAppliesToNormalBoughtCards:false,
 // Native CHR ID+exact local name gated candidate spellings, not verified historical identity.
 orthographicAliases:Object.freeze({
  "0058": {
    "chrName": "오스만누리파사",
    "archiveName": "오스만누리파샤"
  },
  "0065": {
    "chrName": "해럴드깁슨",
    "archiveName": "헤럴드깁슨"
  },
  "0126": {
    "chrName": "네리샤",
    "archiveName": "네리사"
  },
  "0137": {
    "chrName": "살라딘2",
    "archiveName": "살라딘II"
  },
  "0139": {
    "chrName": "아마딘",
    "archiveName": "아만딘"
  },
  "0143": {
    "chrName": "죠안2",
    "archiveName": "죠안II"
  },
  "0147": {
    "chrName": "크리스티앙2",
    "archiveName": "크리스티앙II"
  },
  "0158": {
    "chrName": "고렘",
    "archiveName": "골렘"
  },
  "0166": {
    "chrName": "팬텀 데미안",
    "archiveName": "팬텀데미안"
  },
  "0167": {
    "chrName": "펜텀 마리아",
    "archiveName": "팬텀마리아"
  },
  "0168": {
    "chrName": "펜텀 유진",
    "archiveName": "팬텀유진"
  }
}),
 prices:Object.freeze({
  "슈": 2100,
  "닐라": 1450,
  "케이트호크": 1700,
  "루크랜서드": 1700,
  "파일럿": 50,
  "솔져": 50,
  "제국나이트": 50,
  "무슬림": 80,
  "노포크": 1350,
  "라쉬카": 1300,
  "롤랑": 1600,
  "리슐리외": 2100,
  "마르자나": 5100,
  "마리아애슬린": 1600,
  "마법사": 80,
  "말콤": 1700,
  "무카파": 2700,
  "바시바조크": 50,
  "바이올라": 2000,
  "바자": 1240,
  "발라": 3800,
  "보르스": 1400,
  "사피알딘": 1600,
  "샤프리아르": 1500,
  "세시": 1250,
  "시즈": 2300,
  "심넬램버트": 2200,
  "아델라이데": 1500,
  "아두스베이": 1950,
  "알가지": 50,
  "알무파샤": 2800,
  "알아샤": 2200,
  "알이스파니히": 1050,
  "알파라비": 1600,
  "엘핀스톤": 2300,
  "오스만누리파샤": 2800,
  "올리비에": 2600,
  "워락": 80,
  "이븐사이드": 1900,
  "이븐시나": 2350,
  "이슈탈": 1200,
  "자바카스": 1150,
  "죠엘": 6300,
  "크리스티나": 1700,
  "팬드래건나이트": 50,
  "헤럴드깁슨": 1700,
  "헤이스팅스": 3200,
  "나탈리": 4200,
  "네리사": 1250,
  "디에네": 1200,
  "란": 5500,
  "레드헤드": 2700,
  "루시엔": 2600,
  "리엔": 2600,
  "마리아": 3000,
  "손나딘": 1850,
  "아만딘": 1500,
  "아셀라스": 1900,
  "쥬디": 5800,
  "좀비": 3000,
  "해골": 3000,
  "기파랑": 6200,
  "록슬리": 5400,
  "버몬트": 20000,
  "벨제부르": 10000,
  "살라딘": 37000,
  "셰라자드": 35000,
  "시안": 10500,
  "알바티니": 7000,
  "얀지슈카": 5500,
  "죠안": 7000,
  "지그문트": 8000,
  "철가면": 28000,
  "크리스티앙": 29000,
  "플랑드르": 4800,
  "데미안": 34000,
  "리차드": 3400,
  "베라모드": 10000,
  "살라딘II": 45000,
  "아슈레이": 13000,
  "엠블라": 7500,
  "죠안II": 10500,
  "카를로스": 9000,
  "크리스티앙II": 30000,
  "골렘": 8000,
  "아지다하카": 21000,
  "강화병": 6800,
  "루칼드": 20000,
  "바룬": 18000,
  "엘더마스터": 5000,
  "제이슨": 25000,
  "켄": 6000,
  "팬텀데미안": 34000,
  "팬텀마리아": 21000,
  "팬텀유진": 26000,
  "하이델룬": 65000,
  "흑태자": 115000
})
});

/* Six CHANGED exact store prices on 2003-01-15, as published in
 * contemporaneous 4LEAF Street's archived report. The other 91 values are
 * NOT asserted unchanged; they retain the older Jan 05 snapshot with its
 * distinct source attribution. This is NOT the lost live-server price table. */
window.ORIGINAL_LEAF_SHOP_PRICE_CHANGES_20030115=Object.freeze({
 date:'2003-01-15',
 source:'https://4leafmemorial.geld.kr/1454',
 verifiedChangedEntries:6,
 sourceType:'2003-primary-contemporary-press-not-live-EXE',
 exactChangeOnly:true,
 changes:Object.freeze({
  '노포크':Object.freeze({before:1350,after:1400}),
  '마르자나':Object.freeze({before:5100,after:5500}),
  '자바카스':Object.freeze({before:1150,after:1300}),
  '크리스티나':Object.freeze({before:1700,after:1900}),
  '죠안':Object.freeze({before:7000,after:7500}),
  '흑태자':Object.freeze({before:115000,after:118000})
 })
});
