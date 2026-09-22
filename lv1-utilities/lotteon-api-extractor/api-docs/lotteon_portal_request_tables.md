# LotteON Portal Request-Body Tables Artifact (Pre-Translation Raw Capture)

> [!IMPORTANT]
> This artifact fulfills **Item 1 of the Audit Demand**. It presents the exact portal request-body parameter tables for `POST /v1/openapi/product/v1/product/registration/request` (API 87) and `POST /v1/openapi/product/v1/product/modification/request` (API 90) as rendered by LotteON API Center, including raw margin pixel offsets, calculated depth levels, required flags (`O`/`X`/`△`), types, and original Korean field descriptions.

---

## 1. Product Registration Request Table (`POST /v1/openapi/product/v1/product/registration/request`)

| Row # | Field Name | Margin (px) | Depth Level | Required | Type | Length | Description (Korean) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `spdLst` | 0px | Level 0 | **** | `array` |  | 등록상품목록 |
| 2 | `trGrpCd` | 14px | Level 1 | **O** | `string` | 11 | 거래처그룹코드 |
| 3 | `trNo` | 14px | Level 1 | **O** | `string` | 11 | 거래처번호 |
| 4 | `lrtrNo` | 14px | Level 1 | **** | `string` | 11 | 하위거래처번호 |
| 5 | `scatNo` | 14px | Level 1 | **O** | `string` | 100 | 표준카테고리번호 |
| 6 | `dcatLst` | 14px | Level 1 | **O** | `array` |  | 전시카테고리목록
 속성모듈의 API를 통하여 표준카테고리에 매핑된 전시카테고리를 정보를 받는다.
 매핑된 전시카테고리 중에서 하나 이상 선택하여 입력한다.
 날개매장을 가지는 계열사는 해당 날개매장의 몰구분코드 전시카테고리를 하나 이상 등록하여야 한다. 날개매장을 가진 계열사가 롯데ON 전시카테고리만 등록하는 건 불가하다. |
| 7 | `mallCd` | 30px | Level 2 | **O** | `string` | 20 | 몰구분코드 [공통코드 : MALL_DVS_CD]
 


공통코드값
공통코드명


LTON
롯데ON |
| 8 | `LTON` | 0px | Level 0 | **롯데ON** | `` |  |  |
| 9 | `lfDcatNo` | 30px | Level 2 | **O** | `string` | 100 | leaf전시카테고리번호 |
| 10 | `epdNo` | 14px | Level 1 | **△** | `string` | 30 | 업체상품번호
 계열사의 경우 필수값. 업체상품번호에 계열사 prefix가 붙어 판매자상품번호가 생성된다. |
| 11 | `prdByMaxPurPsbQtyYn` | 14px | Level 1 | **** | `string` | 1 | 상품별최대구매수량여부[Y,N] |
| 12 | `dlcrtYn` | 14px | Level 1 | **** | `string` | 1 | 딜크릿여부[Y,N] |
| 13 | `slTypCd` | 14px | Level 1 | **O** | `string` | 20 | 판매유형코드 [공통코드 : SL_TYP_CD]
 사은품은 사은품등록 API를 사용한다.
 


공통코드값
공통코드명


GNRL
일반판매상품


CNSL
상담판매상품 |
| 14 | `GNRL` | 0px | Level 0 | **일반판매상품** | `` |  |  |
| 15 | `CNSL` | 0px | Level 0 | **상담판매상품** | `` |  |  |
| 16 | `pdTypCd` | 14px | Level 1 | **O** | `string` | 20 | 상품유형코드 [공통코드 : PD_TYP_CD]
 사은품은 사은품등록 API를 사용한다.
 


공통코드값
공통코드명


GNRL_GNRL
일반판매_일반상품


GNRL_ECPN
일반판매_e쿠폰상품


GNRL_GFTV
일반판매_상품권


GNRL_ZRWON
일반판매_0원상품


CNSL_CNSL
상담판매_상담상품 |
| 17 | `GNRL_GNRL` | 0px | Level 0 | **일반판매_일반상품** | `` |  |  |
| 18 | `GNRL_ECPN` | 0px | Level 0 | **일반판매_e쿠폰상품** | `` |  |  |
| 19 | `GNRL_GFTV` | 0px | Level 0 | **일반판매_상품권** | `` |  |  |
| 20 | `GNRL_ZRWON` | 0px | Level 0 | **일반판매_0원상품** | `` |  |  |
| 21 | `CNSL_CNSL` | 0px | Level 0 | **상담판매_상담상품** | `` |  |  |
| 22 | `gftvShpCd` | 14px | Level 1 | **△** | `string` | 20 | 상품권형태코드 [공통코드 : GFTV_SHP_CD]
 상품유형구분코드가 GNRL_GFTV(상품권)인 경우에는 필수 입력
 


공통코드값
공통코드명


MBL
모바일


PPR
지류 |
| 23 | `MBL` | 0px | Level 0 | **모바일** | `` |  |  |
| 24 | `PPR` | 0px | Level 0 | **지류** | `` |  |  |
| 25 | `spdNm` | 14px | Level 1 | **O** | `string` | 150 | 판매자상품명
 입력된 판매자상품명은 상품명 정제를 거쳐 전시상품명으로 노출된다. |
| 26 | `brdNo` | 14px | Level 1 | **** | `string` | 7 | 브랜드번호 [속성모듈 제공 항목]
 속성모듈 API를 통하여 수신된 브랜드번호를 입력한다. |
| 27 | `mfcrNm` | 14px | Level 1 | **** | `string` | 100 | 제조사명
 TXT 값으로 입력한다. |
| 28 | `oplcCd` | 14px | Level 1 | **O** | `string` | 20 | 원산지코드 [공통코드 : OPLC_CD]
 기타인 경우에는 "상품상세 참조"코드 입력 |
| 29 | `mdlNo` | 14px | Level 1 | **** | `string` | 62 | 모델번호 |
| 30 | `barCd` | 14px | Level 1 | **** | `string` | 20 | 바코드 |
| 31 | `tdfDvsCd` | 14px | Level 1 | **O** | `string` | 20 | 과세유형코드 [공통코드 : TDF_DVS_CD]
 


공통코드값
공통코드명


01
과세


02
면세


03
영세


04
해당없음 |
| 32 | `01` | 0px | Level 0 | **과세** | `` |  |  |
| 33 | `02` | 0px | Level 0 | **면세** | `` |  |  |
| 34 | `03` | 0px | Level 0 | **영세** | `` |  |  |
| 35 | `04` | 0px | Level 0 | **해당없음** | `` |  |  |
| 36 | `slStrtDttm` | 14px | Level 1 | **O** | `string` | 14 | 판매시작일시 [YYYYMMDDHH24MISS ex) 20190801100000] |
| 37 | `slEndDttm` | 14px | Level 1 | **O** | `string` | 14 | 판매종료일시 [YYYYMMDDHH24MISS ex) 20190801100000] |
| 38 | `pdItmsInfo` | 14px | Level 1 | **O** | `object` |  | 상품품목고시정보
- 23년 1월 상품정보제공고시 개정반영 다운로드
- 기존 대비 신규 품목고시 변경 다운로드
 - 품목코드가 23번 유아동인 경우  표준카테고리에 따라 안전인증목록이 필수값이다. |
| 39 | `pdItmsCd` | 30px | Level 2 | **O** | `string` | 20 | 상품품목코드 [공통코드 : PD_ITMS_CD]
 


공통코드값
공통코드명


01
[01]의류


02
[02]구두/신발


03
[03]가방


04
[04]패션잡화(모자/벨트/액세서리 등)


05
[05]침구류/커튼


06
[06]가구(침대/소파/싱크대/DIY제품 등)


07
[07]영상가전(TV류)


08
[08]가정용 전기제품(냉장고/세탁기/식기세척기/전자레인지 등)


09
[09]계절가전(에어컨/온풍기 등)


10
[10]사무용기기(컴퓨터/노트북/프린터 등)


11
[11]광학기기(디지털카메라/캠코더 등)


12
[12]소형전자(MP3/전자사전 등)


13
[13]휴대형 통신기기(휴대폰/태블릿 등)


14
[14]내비게이션


15
[15]자동차용품(자동차부품/기타 자동차용품 등)


16
[16]의료기기


17
[17]주방용품


18
[18]화장품


19
[19]귀금속/보석/시계류


20
[20] 농수축산물


21
[21]가공식품


22
[22]건강기능식품


23
[23]어린이제품


24
[24]악기


25
[25]스포츠용품


26
[26]서적


27
[27]호텔/펜션 예약


28
[28]여행 상품


29
[29]항공권


30
[30]자동차 대여 서비스(렌터카)


31
[31]물품대여 서비스(정수기,비데,공기청정기 등)


32
[32]물품대여 서비스(서적,유아용품,행사용품 등)


33
[33]디지털 콘텐츠(음원,게임,인터넷강의 등)


34
[34]상품권/쿠폰


35
[35]모바일쿠폰


36
[36]영화/공연


37
[37]기타(용역)


38
[38]기타(재화)


39
[39]생활화학제품


40
[40]살생물제품 |
| 40 | `01` | 0px | Level 0 | **[01]의류** | `` |  |  |
| 41 | `02` | 0px | Level 0 | **[02]구두/신발** | `` |  |  |
| 42 | `03` | 0px | Level 0 | **[03]가방** | `` |  |  |
| 43 | `04` | 0px | Level 0 | **[04]패션잡화(모자/벨트/액세서리 등)** | `` |  |  |
| 44 | `05` | 0px | Level 0 | **[05]침구류/커튼** | `` |  |  |
| 45 | `06` | 0px | Level 0 | **[06]가구(침대/소파/싱크대/DIY제품 등)** | `` |  |  |
| 46 | `07` | 0px | Level 0 | **[07]영상가전(TV류)** | `` |  |  |
| 47 | `08` | 0px | Level 0 | **[08]가정용 전기제품(냉장고/세탁기/식기세척기/전자레인지 등)** | `` |  |  |
| 48 | `09` | 0px | Level 0 | **[09]계절가전(에어컨/온풍기 등)** | `` |  |  |
| 49 | `10` | 0px | Level 0 | **[10]사무용기기(컴퓨터/노트북/프린터 등)** | `` |  |  |
| 50 | `11` | 0px | Level 0 | **[11]광학기기(디지털카메라/캠코더 등)** | `` |  |  |
| 51 | `12` | 0px | Level 0 | **[12]소형전자(MP3/전자사전 등)** | `` |  |  |
| 52 | `13` | 0px | Level 0 | **[13]휴대형 통신기기(휴대폰/태블릿 등)** | `` |  |  |
| 53 | `14` | 0px | Level 0 | **[14]내비게이션** | `` |  |  |
| 54 | `15` | 0px | Level 0 | **[15]자동차용품(자동차부품/기타 자동차용품 등)** | `` |  |  |
| 55 | `16` | 0px | Level 0 | **[16]의료기기** | `` |  |  |
| 56 | `17` | 0px | Level 0 | **[17]주방용품** | `` |  |  |
| 57 | `18` | 0px | Level 0 | **[18]화장품** | `` |  |  |
| 58 | `19` | 0px | Level 0 | **[19]귀금속/보석/시계류** | `` |  |  |
| 59 | `20` | 0px | Level 0 | **[20] 농수축산물** | `` |  |  |
| 60 | `21` | 0px | Level 0 | **[21]가공식품** | `` |  |  |
| 61 | `22` | 0px | Level 0 | **[22]건강기능식품** | `` |  |  |
| 62 | `23` | 0px | Level 0 | **[23]어린이제품** | `` |  |  |
| 63 | `24` | 0px | Level 0 | **[24]악기** | `` |  |  |
| 64 | `25` | 0px | Level 0 | **[25]스포츠용품** | `` |  |  |
| 65 | `26` | 0px | Level 0 | **[26]서적** | `` |  |  |
| 66 | `27` | 0px | Level 0 | **[27]호텔/펜션 예약** | `` |  |  |
| 67 | `28` | 0px | Level 0 | **[28]여행 상품** | `` |  |  |
| 68 | `29` | 0px | Level 0 | **[29]항공권** | `` |  |  |
| 69 | `30` | 0px | Level 0 | **[30]자동차 대여 서비스(렌터카)** | `` |  |  |
| 70 | `31` | 0px | Level 0 | **[31]물품대여 서비스(정수기,비데,공기청정기 등)** | `` |  |  |
| 71 | `32` | 0px | Level 0 | **[32]물품대여 서비스(서적,유아용품,행사용품 등)** | `` |  |  |
| 72 | `33` | 0px | Level 0 | **[33]디지털 콘텐츠(음원,게임,인터넷강의 등)** | `` |  |  |
| 73 | `34` | 0px | Level 0 | **[34]상품권/쿠폰** | `` |  |  |
| 74 | `35` | 0px | Level 0 | **[35]모바일쿠폰** | `` |  |  |
| 75 | `36` | 0px | Level 0 | **[36]영화/공연** | `` |  |  |
| 76 | `37` | 0px | Level 0 | **[37]기타(용역)** | `` |  |  |
| 77 | `38` | 0px | Level 0 | **[38]기타(재화)** | `` |  |  |
| 78 | `39` | 0px | Level 0 | **[39]생활화학제품** | `` |  |  |
| 79 | `40` | 0px | Level 0 | **[40]살생물제품** | `` |  |  |
| 80 | `pdItmsArtlLst` | 30px | Level 2 | **O** | `array` | 4000 | 상품품목항목목록 |
| 81 | `pdArtlCd` | 44px | Level 3 | **O** | `string` | 20 | 상품항목코드 |
| 82 | `pdArtlCnts` | 44px | Level 3 | **O** | `string` | 4000 | 상품항목내용
 해당 고시정보항목의 항목값을 입력한다. |
| 83 | `impPrxCd` | 14px | Level 1 | **△** | `string` | 20 | 수입대행코드 [공통코드 : IMP_PRX_CD]
 안전인증목록의 KC인증 입력시에 입력한다.
 


공통코드값
공통코드명


PUR_PRX
구매대행


PRL_IMP
병행수입


NONE
해당없음 |
| 84 | `PUR_PRX` | 0px | Level 0 | **구매대행** | `` |  |  |
| 85 | `PRL_IMP` | 0px | Level 0 | **병행수입** | `` |  |  |
| 86 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 87 | `sftyAthnLst` | 14px | Level 1 | **** | `array` | 4000 | 안전인증목록
 안전인증정보 입력시 하단의 항목을 입력한다. |
| 88 | `sftyAthnTypCd` | 30px | Level 2 | **O** | `string` | 20 | 안전인증유형코드 [공통코드 : SFTY_ATHN_TYP_CD]
 'KC인증'에 해당할 경우 수입대행코드는 필수 값이다.
 


공통코드값
공통코드명
비고


CHL_ATHN
[어린이제품] 안전인증
 


CHL_CFM
[어린이제품] 안전확인
 


CHL_SUPS
[어린이제품] 공급자적합성확인
 


ELC_AHTN
[전기용품] 안전인증
수입대행코드 필수


ELC_CFM
[전기용품] 안전확인
수입대행코드 필수


ELC_SUPS
전기용품] 공급자적합성확인
수입대행코드 필수


LIFE_ATHN
[생활용품] 안전인증
수입대행코드 필수


LIFE_CFM
[생활용품] 안전확인
수입대행코드 필수


LIFE_SUPS
[전기용품] 공급자적합성확인
수입대행코드 필수


LIFE_STD
[생활용품] 안전기준준수
수입대행코드 필수


KC_CHL_PKG
[KC인증] 어린이보호포장
수입대행코드 필수


ETC
KC기타
수입대행코드 필수


CMCN_TNTT
[방송통신기자재] 잠정인증
수입대행코드 필수


CMCN_REG
[방송통신기자재] 적합등록
수입대행코드 필수


CMCN_ATHN
[방송통신기자재] 적합인증
수입대행코드 필수


CHEM_BIOC
[살생물제품] 승인번호
 


CHEM_LIFE
[생활화학제품] 안전기준적합확인신고번호
 


MTR_APRV
[계량기] 형식 승인
수입대행코드 필수


DRT_IPT
직접입력
수입대행코드 필수


DTL_REFC
상품상세 참조
수입대행코드 필수 |
| 89 | `CHL_ATHN` | 0px | Level 0 | **[어린이제품] 안전인증** | `` |  |  |
| 90 | `CHL_CFM` | 0px | Level 0 | **[어린이제품] 안전확인** | `` |  |  |
| 91 | `CHL_SUPS` | 0px | Level 0 | **[어린이제품] 공급자적합성확인** | `` |  |  |
| 92 | `ELC_AHTN` | 0px | Level 0 | **[전기용품] 안전인증** | `수입대행코드 필수` |  |  |
| 93 | `ELC_CFM` | 0px | Level 0 | **[전기용품] 안전확인** | `수입대행코드 필수` |  |  |
| 94 | `ELC_SUPS` | 0px | Level 0 | **전기용품] 공급자적합성확인** | `수입대행코드 필수` |  |  |
| 95 | `LIFE_ATHN` | 0px | Level 0 | **[생활용품] 안전인증** | `수입대행코드 필수` |  |  |
| 96 | `LIFE_CFM` | 0px | Level 0 | **[생활용품] 안전확인** | `수입대행코드 필수` |  |  |
| 97 | `LIFE_SUPS` | 0px | Level 0 | **[전기용품] 공급자적합성확인** | `수입대행코드 필수` |  |  |
| 98 | `LIFE_STD` | 0px | Level 0 | **[생활용품] 안전기준준수** | `수입대행코드 필수` |  |  |
| 99 | `KC_CHL_PKG` | 0px | Level 0 | **[KC인증] 어린이보호포장** | `수입대행코드 필수` |  |  |
| 100 | `ETC` | 0px | Level 0 | **KC기타** | `수입대행코드 필수` |  |  |
| 101 | `CMCN_TNTT` | 0px | Level 0 | **[방송통신기자재] 잠정인증** | `수입대행코드 필수` |  |  |
| 102 | `CMCN_REG` | 0px | Level 0 | **[방송통신기자재] 적합등록** | `수입대행코드 필수` |  |  |
| 103 | `CMCN_ATHN` | 0px | Level 0 | **[방송통신기자재] 적합인증** | `수입대행코드 필수` |  |  |
| 104 | `CHEM_BIOC` | 0px | Level 0 | **[살생물제품] 승인번호** | `` |  |  |
| 105 | `CHEM_LIFE` | 0px | Level 0 | **[생활화학제품] 안전기준적합확인신고번호** | `` |  |  |
| 106 | `MTR_APRV` | 0px | Level 0 | **[계량기] 형식 승인** | `수입대행코드 필수` |  |  |
| 107 | `DRT_IPT` | 0px | Level 0 | **직접입력** | `수입대행코드 필수` |  |  |
| 108 | `DTL_REFC` | 0px | Level 0 | **상품상세 참조** | `수입대행코드 필수` |  |  |
| 109 | `sftyAthnOrgnNm` | 30px | Level 2 | **** | `String` | 100 | 안전인증기관명 |
| 110 | `sftyAthnNo` | 30px | Level 2 | **O** | `string` | 100 | 안전인증번호 |
| 111 | `scatAttrLst` | 14px | Level 1 | **** | `array` | 4000 | 표준카테고리속성목록
 표준카테고리에 매핑된 상품속성 입력시 하단의 항목을 입력한다. |
| 112 | `optCd` | 30px | Level 2 | **O** | `string` | 20 | 옵션코드 [속성모듈 제공 항목] |
| 113 | `optValCd` | 30px | Level 2 | **O** | `string` | 20 | 옵션값코드 [속성모듈 제공 항목]
 옵션값에 해당하는 옵션값코드를 입력한다. |
| 114 | `optVal` | 30px | Level 2 | **O** | `string` | 200 | 옵션값 [속성모듈 제공 항목]
 해당하는 옵션값을 입력한다. |
| 115 | `dtlsVal` | 30px | Level 2 | **** | `string` | 4000 | 세부값
 세부값을 입력하는 경우
 1. 범위값에 대한 고정값 입력시
 2. 옵션값에 대한 추가 표현 |
| 116 | `itypOptLst` | 14px | Level 1 | **** | `array` | 4000 | 입력형옵션목록
 최대 5개의 입력형옵션을 설정할 수 있다. |
| 117 | `itypOptDvsCd` | 30px | Level 2 | **O** | `string` | 20 | 입력형옵션구분코드 [공통코드 : ITYP_OPT_DVS_CD]
 


공통코드값
공통코드명


NO
숫자


TXT
텍스트


DATE
달력형


LIST
목록선택형


TIME
시간선택형 |
| 118 | `NO` | 0px | Level 0 | **숫자** | `` |  |  |
| 119 | `TXT` | 0px | Level 0 | **텍스트** | `` |  |  |
| 120 | `DATE` | 0px | Level 0 | **달력형** | `` |  |  |
| 121 | `LIST` | 0px | Level 0 | **목록선택형** | `` |  |  |
| 122 | `TIME` | 0px | Level 0 | **시간선택형** | `` |  |  |
| 123 | `itypOptNm` | 30px | Level 2 | **O** | `string` | 200 | 입력형옵션명 |
| 124 | `itypOptValLst` | 30px | Level 2 | **△** | `array` |  | 입력옵션값목록 [마트, 슈퍼 전용]
 입력형옵션구분코드가 목록선택행일 때만 입력한다. |
| 125 | `itypOptVal` | 44px | Level 3 | **O** | `string` | 4000 | 입력형옵션값 [마트, 슈퍼 전용] |
| 126 | `purPsbQtyInfo` | 14px | Level 1 | **O** | `object` |  | 구매가능수량정보 |
| 127 | `itmByMinPurYn` | 30px | Level 2 | **O** | `string` | 1 | 단품별최소구매여부 [Y, N] |
| 128 | `itmByMinPurQty` | 30px | Level 2 | **△** | `number` | 6 | 단품별최소구매수량
 단품별최소구매여부가 Y인 경우 필수입력한다. |
| 129 | `itmByMinPurMtpYn` | 30px | Level 2 | **△** | `string` | 1 | 단품별최소구매배수여부
 단품별최소구매여부가 Y인 경우 입력 가능하고 미입력 시 N으로 설정된다. |
| 130 | `itmByMaxPurPsbQtyYn` | 30px | Level 2 | **O** | `string` | 1 | 단품별최대구매가능수량여부 [Y, N] |
| 131 | `maxPurQty` | 30px | Level 2 | **△** | `number` | 6 | 단품별최대구매수량
 단품별최대구매가능수량여부가 Y인 경우 필수입력한다. |
| 132 | `maxPurLmtTypCd` | 30px | Level 2 | **O** | `string` | 20 | 단품별최대구매제한구분코드 [공통코드 : MAX_PUR_LMT_TYP_CD]
 


공통코드값
공통코드명


ONCE
1회제한


PERIOD
기간제한


FIXED
특정일자 제한



 미입력 시 기간제한(PERIOD)로 적용되고 단품별최대구매제한기간(maxPurLmtPrd)은 1일로 설정 된다. |
| 133 | `ONCE` | 0px | Level 0 | **1회제한** | `` |  |  |
| 134 | `PERIOD` | 0px | Level 0 | **기간제한** | `` |  |  |
| 135 | `FIXED` | 0px | Level 0 | **특정일자 제한** | `` |  |  |
| 136 | `maxPurLmtPrd` | 30px | Level 2 | **△** | `number` | 5 | 단품별최대구매제한기간
 단품별최대구매제한구분코드가 기간제한(PERIOD)일 경우 필수입력한다. |
| 137 | `maxPurLmtStrtDttm` | 30px | Level 2 | **△** | `string` | 14 | 단품별최대구매제한시작일자
 단품별최대구매제한구분코드가 특정일자 제한(FIXED)일 경우 필수입력한다. [YYYYMMDDHH24MISS ex) 20190801100000]
 - 시간단위 설정 시 YYYYMMDDHH24까지만 설정 가능하고 분초는 0000으로 고정
 - 날짜단위 설정 시 YYYYMMDD까지만 설정 가능하고 시작일시 시분초는 000000 고정 |
| 138 | `maxPurLmtEndDttm` | 30px | Level 2 | **△** | `string` | 14 | 단품별최대구매제한종료일자
 단품별최대구매제한구분코드가 특정일자 제한(FIXED)일 경우 필수입력한다. [YYYYMMDDHH24MISS ex) 20190801100000]
 - 시간단위 설정 시 YYYYMMDDHH24까지만 설정 가능하고 분초는 0000으로 고정
 - 날짜단위 설정 시 YYYYMMDD까지만 설정 가능하고 종료일시 시분초는 235959 고정 |
| 139 | `ageLmtCd` | 14px | Level 1 | **O** | `string` | 20 | 연령제한코드 [공통코드 : AGE_LMT_CD]
 


공통코드값
공통코드명


0
전연령 구매가능


15
15세이상 구매가능


19
19세이상 구매가능 |
| 140 | `0` | 0px | Level 0 | **전연령 구매가능** | `` |  |  |
| 141 | `15` | 0px | Level 0 | **15세이상 구매가능** | `` |  |  |
| 142 | `19` | 0px | Level 0 | **19세이상 구매가능** | `` |  |  |
| 143 | `prstPsbYn` | 14px | Level 1 | **** | `string` | 1 | 선물가능여부 [Y, N]
 디폴트:N |
| 144 | `prstPckPsbYn` | 14px | Level 1 | **O** | `string` | 1 | 선물포장가능여부 [Y, N] |
| 145 | `prstMsgPsbYn` | 14px | Level 1 | **O** | `string` | 1 | 선물메시지가능여부 [Y, N] |
| 146 | `prcCmprEpsrYn` | 14px | Level 1 | **** | `string` | 1 | 가격비교노출여부 [Y, N]
 디폴트:Y |
| 147 | `bookCultCstDdctYn` | 14px | Level 1 | **** | `string` | 1 | 도서문화비 공제여부 [Y, N]
 디폴트:N
 거래처와 표준카테고리가 모두 도서문화비 공제대상에 해당하는 경우에만 공제여부가 Y이다. |
| 148 | `isbnCd` | 14px | Level 1 | **△** | `string` | 20 | ISBN
 도서문화비 공제여부가 Y이고 카테고리가 도서관련 카테고리일 경우 ISBN NO를 입력한다. |
| 149 | `impCoNm` | 14px | Level 1 | **** | `string` | 100 | 수입사명
 TXT 입력 |
| 150 | `impDvsCd` | 14px | Level 1 | **△** | `string` | 20 | 수입구분코드 [공통코드 : IMP_DVS_CD]
 수입사명이 있는 경우 입력한다.
 


공통코드값
공통코드명


DRC_IMP
공식수입


PRL_IMP
병행수입


NONE
해당없음 |
| 151 | `DRC_IMP` | 0px | Level 0 | **공식수입** | `` |  |  |
| 152 | `PRL_IMP` | 0px | Level 0 | **병행수입** | `` |  |  |
| 153 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 154 | `cshbltyPdYn` | 14px | Level 1 | **** | `string` | 1 | 환금성상품여부 [Y, N]
 표준카테고리 속성을 상속 받는다.
 환금성 상품으로 설정되는 경우 주문에서 결제수단에 따라 구매가 제한된다.
 디폴트:N |
| 155 | `etvPdYn` | 14px | Level 1 | **** | `string` | 1 | [홈쇼핑]eTV상품여부
 디폴트:N |
| 156 | `dnDvPdYn` | 14px | Level 1 | **** | `string` | 1 | [슈퍼]새벽배송상품여부
 디폴트:N |
| 157 | `toysPdYn` | 14px | Level 1 | **** | `string` | 1 | [마트] 토이저러스상품여부 [Y, N] |
| 158 | `intgSlPdNo` | 14px | Level 1 | **** | `string` | 30 | [엘롯데] 통합판매상품번호
 백화점 통판 판매상품 고유코드(통판연동상품인 경우에만 사용)이다.
 파트너플러스엘롯데에서 연동된 상품일 경우에만 사용된다. |
| 159 | `nmlPdYn` | 14px | Level 1 | **** | `string` | 1 | [엘롯데] 정상상품여부 [Y, N]
 디폴트:N |
| 160 | `lnchYm` | 14px | Level 1 | **** | `string` | 6 | 출시년월 |
| 161 | `prmmPdYn` | 14px | Level 1 | **** | `string` | 1 | [엘롯데] 프리미엄상품여부
 디폴트:N |
| 162 | `newPrdYn` | 0px | Level 0 | **** | `string` | 1 | [엘롯데] 신상품여부 [Y, N]
 디폴트:N |
| 163 | `excluYn` | 0px | Level 0 | **** | `string` | 1 | [엘롯데] 익스클루시브상품여부 [Y, N]
 디폴트:N |
| 164 | `prmmPdInfo` | 14px | Level 1 | **** | `object` |  | [엘롯데]프리미엄상품설명정보
 프리미엄상품여부가 Y인 경우 입력한다. |
| 165 | `origQrtbImgFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본조견표이미지파일명(경로) |
| 166 | `origActlMeasSzImgFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본실측정사이즈이미지파일명(경로) |
| 167 | `origMeasImgCntsFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본실측정사이즈내용파일명(경로) |
| 168 | `origAvnPdDtlEpnFileNm` | 30px | Level 2 | **O** | `string` | 200 | 원본에비뉴엘상품상세설명파일명(경로) |
| 169 | `otltPdYn` | 14px | Level 1 | **** | `string` | 1 | [엘롯데] 아울렛상품여부 [Y, N]
 디폴트:N |
| 170 | `prmmInstPdYn` | 14px | Level 1 | **** | `string` | 1 | [하이마트] 프리미엄설치상품여부 [Y, N]
 디폴트:N |
| 171 | `brkHmapPkcpPsbYn` | 14px | Level 1 | **** | `string` | 1 | 폐가전수거여부 [Y, N]
 디폴트:N |
| 172 | `ctrtTypCd` | 14px | Level 1 | **** | `string` | 20 | 계약유형코드[공통코드 : CTRT_TYP_CD]
 


공통코드값
공통코드명


A
중개


B
위수탁 |
| 173 | `A` | 0px | Level 0 | **중개** | `` |  |  |
| 174 | `B` | 0px | Level 0 | **위수탁** | `` |  |  |
| 175 | `pdSzInfo` | 14px | Level 1 | **** | `object` | 4000 | 배송사이즈정보
 정수만 입력 가능하다. |
| 176 | `pdWdthSz` | 30px | Level 2 | **** | `number` | 100 | 상품가로사이즈 (cm) |
| 177 | `pdLnthSz` | 30px | Level 2 | **** | `number` | 100 | 상품세로사이즈 (cm) |
| 178 | `pdHghtSz` | 30px | Level 2 | **** | `number` | 100 | 상품높이사이즈 (cm) |
| 179 | `pckWdthSz` | 30px | Level 2 | **** | `number` | 100 | 포장가로사이즈 (cm) |
| 180 | `pckLnthSz` | 30px | Level 2 | **** | `number` | 100 | 포장세로사이즈 (cm) |
| 181 | `pckHghtSz` | 30px | Level 2 | **** | `number` | 100 | 포장높이사이즈 (cm) |
| 182 | `pdStatCd` | 14px | Level 1 | **O** | `string` | 20 | 상품상태코드 [공통코드 : PD_STAT_CD]
 상품상태코드가 새상품(NEW)이 아닌 경우에는 파일유형코드와 파일구분코드를 USD로 하여 상품상태이미지를 반드시 등록하여야 한다.
 


공통코드값
공통코드명


NEW
새상품


DP
전시상품


RFRBSH
리퍼상품


SCRTC
스크레치상품


RTRN_NRML
반품(정상)상품


RTRN_DMG
반품(박스훼손)상품


USD
중고상품 |
| 183 | `NEW` | 0px | Level 0 | **새상품** | `` |  |  |
| 184 | `DP` | 0px | Level 0 | **전시상품** | `` |  |  |
| 185 | `RFRBSH` | 0px | Level 0 | **리퍼상품** | `` |  |  |
| 186 | `SCRTC` | 0px | Level 0 | **스크레치상품** | `` |  |  |
| 187 | `RTRN_NRML` | 0px | Level 0 | **반품(정상)상품** | `` |  |  |
| 188 | `RTRN_DMG` | 0px | Level 0 | **반품(박스훼손)상품** | `` |  |  |
| 189 | `USD` | 0px | Level 0 | **중고상품** | `` |  |  |
| 190 | `dpYn` | 14px | Level 1 | **** | `string` | 1 | 전시여부 [Y, N]
 디폴트:Y |
| 191 | `ltonDpYn` | 14px | Level 1 | **** | `string` | 1 | LotteOn전시여부 [엘롯데, 마트, 슈퍼, 롭스 전용]
 N인 경우 LotteOn 비전시
 디폴트:Y |
| 192 | `scKwdLst` | 14px | Level 1 | **** | `array` | 4000 | 검색키워드목록
 5개 이하만 등록 가능 |
| 193 | `pdFileLst` | 14px | Level 1 | **△** | `array` | 4000 | 상품콘텐츠파일목록
 상품상태코드가 새상품(NEW)이 아닌 경우에는 파일유형코드와 파일구분코드를 USD로 하여 상품상태이미지를 반드시 등록하여야 한다. |
| 194 | `fileTypCd` | 30px | Level 2 | **O** | `string` | 20 | 파일유형코드 [공통코드 : FILE_TYP_CD]
 


공통코드값
공통코드명


USD
상품상태


TAG_LBL
Tag/케어라벨


PD
상품 |
| 195 | `USD` | 0px | Level 0 | **상품상태** | `` |  |  |
| 196 | `TAG_LBL` | 0px | Level 0 | **Tag/케어라벨** | `` |  |  |
| 197 | `PD` | 0px | Level 0 | **상품** | `` |  |  |
| 198 | `fileDvsCd` | 30px | Level 2 | **O** | `string` | 20 | 파일구분코드 [공통코드 : FILE_DVS_CD]
 


공통코드값
공통코드명


3D
상품3D이미지


USD
상품유형(중고)


WDTH
상품가로형


TAG_LBL
Tag/케어라벨


VDO_URL
상품동영상_URL


VDO_FILE
상품동영상_FILE


VDO_FILE_HM
홈쇼핑_동영상_FILE




 * VDO_FILE_HM 는 ETV 사용가능 거래처만 등록 가능 |
| 199 | `3D` | 0px | Level 0 | **상품3D이미지** | `` |  |  |
| 200 | `USD` | 0px | Level 0 | **상품유형(중고)** | `` |  |  |
| 201 | `WDTH` | 0px | Level 0 | **상품가로형** | `` |  |  |
| 202 | `TAG_LBL` | 0px | Level 0 | **Tag/케어라벨** | `` |  |  |
| 203 | `VDO_URL` | 0px | Level 0 | **상품동영상_URL** | `` |  |  |
| 204 | `VDO_FILE` | 0px | Level 0 | **상품동영상_FILE** | `` |  |  |
| 205 | `VDO_FILE_HM` | 0px | Level 0 | **홈쇼핑_동영상_FILE** | `` |  |  |
| 206 | `origFileNm` | 30px | Level 2 | **O** | `string` | 200 | 원본파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) https://abc.com/12/34/56/78_90.mp4 |
| 207 | `dpStrtDttm` | 30px | Level 2 | **** | `string` | 14 | 전시시작일시 [YYYYMMDDHH24MISS ex) 20190801100000]
 * VDO_FILE_HM 등록인 경우 필수 입력 |
| 208 | `dpEndDttm` | 30px | Level 2 | **** | `string` | 14 | 전시종료일시 [YYYYMMDDHH24MISS ex) 20190801100000]
 * VDO_FILE_HM 등록인 경우 필수 입력 |
| 209 | `epnLst` | 14px | Level 1 | **O** | `array` | 4000 | 상품설명목록 |
| 210 | `pdEpnTypCd` | 30px | Level 2 | **O** | `string` | 20 | 상품설명유형코드 [공통코드 : PD_EPN_TYP_CD]
 


공통코드값
공통코드명


DSCRP
상품기술서


AS_CNTS
A/S내용설명


PRCTN
주의사항설명




 상세정보를 이미지로 등록 시 시각 약자
 고객을 위해 이미지 대체 텍스트 (alt)
 입력 필요 |
| 211 | `DSCRP` | 0px | Level 0 | **상품기술서** | `` |  |  |
| 212 | `AS_CNTS` | 0px | Level 0 | **A/S내용설명** | `` |  |  |
| 213 | `PRCTN` | 0px | Level 0 | **주의사항설명** | `` |  |  |
| 214 | `cnts` | 30px | Level 2 | **O** | `string` |  | 내용
 html입력시 사용한다.
  
 ⚠️ 주의사항 (이미지 URL 사용 관련)

 기존 상품의 HTML을 복사하여 기술서를 작성할 경우,
doc-pub.lotteon.com/ec/public 경로의 이미지 URL이 포함되지 않도록 주의해야 합니다.

 * 해당 경로(ec/public)는 임시 또는 비영구 저장 경로로, 일정 시점 이후 이미지가 삭제되거나 접근이 불가능해질 수 있습니다.

 * 따라서 해당 URL을 그대로 사용할 경우, 상품 상세 페이지에서 이미지가 정상적으로 노출되지 않을 수 있습니다.

[권장 방법]

 * 셀러어드민에서 해당 이미지를 재업로드 후 저장하면, 신규 영구 저장 경로로 자동 변경됨

 * 기존 HTML을 재사용할 경우, 이미지 URL을 신규 업로드 경로로 교체 후 사용 |
| 215 | `onnuriPyPsbYn` | 14px | Level 1 | **** | `string` | 1 | 온누리결제가능여부(일반셀러)
 디폴트:N |
| 216 | `cnclPsbYn` | 14px | Level 1 | **** | `string` | 1 | 취소가능여부 [Y, N]
 취소 불가인 상품인 경우에는 'N'으로 설정
 디폴트:Y |
| 217 | `dmstOvsDvDvsCd` | 14px | Level 1 | **** | `string` | 20 | 국내해외배송구분코드 [공통코드 : DMST_OVS_DV_DVS_CD]
 디폴트:국내배송
 해외배송인 경우 발송예정일수를 최대 30일까지 입력할 수 있다.
 


공통코드값
공통코드명


DMST
국내배송


OVS
해외배송 |
| 218 | `DMST` | 0px | Level 0 | **국내배송** | `` |  |  |
| 219 | `OVS` | 0px | Level 0 | **해외배송** | `` |  |  |
| 220 | `pstkYn` | 14px | Level 1 | **** | `string` | 1 | 선재고여부 [Y, N]
 디폴트:N |
| 221 | `dvProcTypCd` | 14px | Level 1 | **O** | `string` | 20 | 배송처리유형코드 [공통코드 : DV_PROC_TYP_CD]
 


공통코드값
공통코드명


LO_ENTP
업체배송


LO_ENTP_DGNN
업체지정배송


LO_CNTR
센터배송


LO_ECPN
e쿠폰 |
| 222 | `LO_ENTP` | 0px | Level 0 | **업체배송** | `` |  |  |
| 223 | `LO_ENTP_DGNN` | 0px | Level 0 | **업체지정배송** | `` |  |  |
| 224 | `LO_CNTR` | 0px | Level 0 | **센터배송** | `` |  |  |
| 225 | `LO_ECPN` | 0px | Level 0 | **e쿠폰** | `` |  |  |
| 226 | `dvPdTypCd` | 14px | Level 1 | **O** | `string` | 20 | 배송상품유형코드 [공통코드 : DV_PD_TYP_CD]
상품유형별_배송상품유형코드



공통코드값
공통코드명
최대발송예정일수


GNRL
일반상품
3


OD_MFG
주문제작상품
15


CHRG_INST
유료설치상품
30


FREE_INST
무료설치상품
3


GFTV
상품권
3


ECPN
e쿠폰
0 |
| 227 | `GNRL` | 0px | Level 0 | **일반상품** | `3` |  |  |
| 228 | `OD_MFG` | 0px | Level 0 | **주문제작상품** | `15` |  |  |
| 229 | `CHRG_INST` | 0px | Level 0 | **유료설치상품** | `30` |  |  |
| 230 | `FREE_INST` | 0px | Level 0 | **무료설치상품** | `3` |  |  |
| 231 | `GFTV` | 0px | Level 0 | **상품권** | `3` |  |  |
| 232 | `ECPN` | 0px | Level 0 | **e쿠폰** | `0` |  |  |
| 233 | `sndBgtNday` | 14px | Level 1 | **** | `number` | 8 | 발송예정일수
 배송상품유형코드에 따라 최대 발송예정일수를 입력한다. |
| 234 | `sndBgtDdInfo` | 14px | Level 1 | **** | `object` |  | 발송예정일정보 |
| 235 | `nldySndCloseTm` | 30px | Level 2 | **O** | `string` | 4 | 평일 발송마감시간 [HH24MI ex) 1000]
 
발송예정일이 '0'일(오늘발송)로 설정된 경우에만 적용 
00분, 30분만 등록 가능
국내배송 : 06:00 ~ 23:00 설정 가능
해외배송 : 00:30 ~ 23:30 설정 가능 |
| 236 | `satSndPsbYn` | 30px | Level 2 | **O** | `string` | 1 | 토요일 발송가능여부 [Y, N]
 거래처정보가 토요일기본상태 : 근무안함 일 경우 Y 사용불가 |
| 237 | `satSndCloseTm` | 30px | Level 2 | **△** | `string` | 4 | 토요일 발송마감시간 [HH24MI ex) 1000]
 토요일 발송 가능여부 Y인 경우 필수
 00분, 30분만 등록 가능 |
| 238 | `dvRgsprGrpCd` | 14px | Level 1 | **O** | `string` | 20 | 배송가능지역코드[공통코드 : DV_RGSPR_GRP_CD] |
| 239 | `dvMnsCd` | 14px | Level 1 | **O** | `string` | 20 | 배송수단코드 [공통코드 : DV_MNS_CD]
 단건만 입력가능
 [마트 제외] 마트는 점포별 관리 API를 사용한다.
 


공통코드값
공통코드명


DPCL
일반택배


DGNN_DV
직접배송


REG_MAIL
등기우편


ZIP
일반우편


NONE_DV
무배송(e쿠폰)


ETC
기타 |
| 240 | `DPCL` | 0px | Level 0 | **일반택배** | `` |  |  |
| 241 | `DGNN_DV` | 0px | Level 0 | **직접배송** | `` |  |  |
| 242 | `REG_MAIL` | 0px | Level 0 | **등기우편** | `` |  |  |
| 243 | `ZIP` | 0px | Level 0 | **일반우편** | `` |  |  |
| 244 | `NONE_DV` | 0px | Level 0 | **무배송(e쿠폰)** | `` |  |  |
| 245 | `ETC` | 0px | Level 0 | **기타** | `` |  |  |
| 246 | `owhpNo` | 14px | Level 1 | **O** | `string` | 20 | 출고지번호거래처 API "(일반 Seller용) 판매자 출고지/반품지 등록"을 통하여 등록된 출고지번호를 입력한다. |
| 247 | `hdcCd` | 14px | Level 1 | **** | `string` | 20 | 택배사코드 [공통코드 : DV_CO_CD]
 *업데이트로 인해 값이 다를 수 있으므로
 공통 메뉴의 [공통코드 상세조회]를 통해 입력 필요. 
 


공통코드값
공통코드명


0001
롯데택배


0002
CJ대한통운


0003
현대택배


0004
우체국택배


0005
로젠택배


...
...


etc
etc


9999
기타택배 |
| 248 | `0001` | 0px | Level 0 | **롯데택배** | `` |  |  |
| 249 | `0002` | 0px | Level 0 | **CJ대한통운** | `` |  |  |
| 250 | `0003` | 0px | Level 0 | **현대택배** | `` |  |  |
| 251 | `0004` | 0px | Level 0 | **우체국택배** | `` |  |  |
| 252 | `0005` | 0px | Level 0 | **로젠택배** | `` |  |  |
| 253 | `...` | 0px | Level 0 | **...** | `` |  |  |
| 254 | `etc` | 0px | Level 0 | **etc** | `` |  |  |
| 255 | `9999` | 0px | Level 0 | **기타택배** | `` |  |  |
| 256 | `cstAdtnLst` | 14px | Level 1 | **** | `array` |  | 비용추가목록
 관세/부가세, 배송비/설치비, 현장결제비로 묶어서 이 중 하나를 등록한다.



비용추가유형상세코드
비용추가유형상세명


TX_01
관세


TX_02
부가세


LOGI_01
배송비


LOGI_02
설치비


TRVL_01
현장결제비 |
| 257 | `비용추가유형상세코드` | 0px | Level 0 | **비용추가유형상세명** | `` |  |  |
| 258 | `TX_01` | 0px | Level 0 | **관세** | `` |  |  |
| 259 | `TX_02` | 0px | Level 0 | **부가세** | `` |  |  |
| 260 | `LOGI_01` | 0px | Level 0 | **배송비** | `` |  |  |
| 261 | `LOGI_02` | 0px | Level 0 | **설치비** | `` |  |  |
| 262 | `TRVL_01` | 0px | Level 0 | **현장결제비** | `` |  |  |
| 263 | `cstAdtnTypDtlCd` | 30px | Level 2 | **** | `string` |  | 비용추가유형상세코드 : 위 표 참고. |
| 264 | `cstAdtnTypDtlVal` | 30px | Level 2 | **** | `string` | 1 | 비용추가유형상세값 [Y/N] |
| 265 | `dvCstPolNo` | 14px | Level 1 | **O** | `string` | 30 | 배송비정책번호
 거래처의 API를 통해 선등록된 배송비정책번호를 입력한다.
 (신규 배송비 정책 등록 후 약 5분정도 딜레이가 있을 수 있어 신규 배송비 정책에 대해서는 5분 뒤에 연동해야 함.) |
| 266 | `adtnDvCstPolNo` | 14px | Level 1 | **** | `string` | 30 | 추가배송비정책번호
 거래처의 API를 통해 선등록된 추가배송비정책번호를 입력한다.
 (신규 배송비 정책 등록 후 약 5분정도 딜레이가 있을 수 있어 신규 배송비 정책에 대해서는 5분 뒤에 연동해야 함.) |
| 267 | `cmbnDvPsbYn` | 14px | Level 1 | **** | `string` | 1 | 합배송가능여부 [Y, N]
 디폴트:Y |
| 268 | `dvCstStdQty` | 14px | Level 1 | **** | `number` | 10 | 배송비기준수량
 배송비를 1로 설정하는 경우 주문 수량 만큼 배송비가 부과된다.
 디폴트:0 |
| 269 | `qckDvUseYn` | 14px | Level 1 | **** | `string` | 1 | 퀵배송사용여부 [Y, N]
 디폴트:N
 백화점, 마트, 슈퍼, 하이마트 제외하고 퀵배송여부 Y설정 불가능 |
| 270 | `crdayDvPsbYn` | 14px | Level 1 | **** | `string` | 1 | 당일배송가능여부 [Y, N]
 디폴트:N |
| 271 | `crdayDvInfo` | 14px | Level 1 | **△** | `object` | 4000 | 당일배송정보
 당일배송가능여부가 Y인 경우 필수값 |
| 272 | `odCloseTm` | 30px | Level 2 | **O** | `string` | 4 | 주문마감시간 [HH24MI ex) 1000]
 당일배송가능여부가 Y인 경우 필수값 |
| 273 | `spicUseYn` | 14px | Level 1 | **** | `string` | 1 | 스마트픽사용여부 [Y, N]
 디폴트:N |
| 274 | `spicInfo` | 14px | Level 1 | **△** | `object` |  | 스마트픽정보
 스마트픽사용여부 Y인 경우 필수 |
| 275 | `spicTypCdLst` | 30px | Level 2 | **O** | `array` | 4000 | 스마트픽유형코드목록 [공통코드 : SPIC_TYP_CD]
 해당되는 스마트픽유형코드들을 입력한다.



공통코드값
공통코드명


STR
매장픽업(스토어픽)


CRSS
내주변픽업(크로스픽)


RVS
리버스픽 |
| 276 | `STR` | 0px | Level 0 | **매장픽업(스토어픽)** | `` |  |  |
| 277 | `CRSS` | 0px | Level 0 | **내주변픽업(크로스픽)** | `` |  |  |
| 278 | `RVS` | 0px | Level 0 | **리버스픽** | `` |  |  |
| 279 | `strPicTypLst` | 30px | Level 2 | **△** | `array` | 4000 | 스토어픽유형목록 [엘롯데 전용]
 스마트픽유형에 스토어픽이 있는 경우 필수값 |
| 280 | `trGrpCd` | 44px | Level 3 | **O** | `string` | 11 | 거래처그룹코드 [엘롯데 전용] |
| 281 | `trNo` | 44px | Level 3 | **O** | `string` | 11 | 거래처번호 [엘롯데 전용] |
| 282 | `lrtrNo` | 44px | Level 3 | **O** | `string` | 11 | 하위거래처번호 [엘롯데 전용] |
| 283 | `shopPkupYn` | 44px | Level 3 | **O** | `string` | 1 | 매장픽업여부 [엘롯데 전용] |
| 284 | `lckPkupYn` | 44px | Level 3 | **O** | `string` | 1 | 락커픽업여부 [엘롯데 전용] |
| 285 | `dskPkupYn` | 44px | Level 3 | **O** | `string` | 1 | 데스크픽업여부 [엘롯데 전용] |
| 286 | `spicEusePdYn` | 14px | Level 1 | **** | `string` | 1 | 스마트픽전용상품여부 [Y, N]
 디폴트N |
| 287 | `spicEusePdTypCd` | 14px | Level 1 | **△** | `string` | 20 | 스마트픽전용상품유형코드 [공통코드 : SPIC_EUSE_PD_TYP_CD]
 스마트픽전용상품여부 Y인 경우 필수
 


공통코드값
공통코드명


GNRL
일반


RAO_ XCHG
실물교환


SITE_PY
현장결제 |
| 288 | `GNRL` | 0px | Level 0 | **일반** | `` |  |  |
| 289 | `RAO_ XCHG` | 0px | Level 0 | **실물교환** | `` |  |  |
| 290 | `SITE_PY` | 0px | Level 0 | **현장결제** | `` |  |  |
| 291 | `hpDdDvPsbYn` | 14px | Level 1 | **** | `string` | 1 | 희망일배송가능여부 [Y, N]
 디폴트:N |
| 292 | `hpDdDvPsbPrd` | 14px | Level 1 | **△** | `number` | 10 | 희망일배송가능기간
 희망일배송가능여부 Y인 경우 필수 |
| 293 | `mpbPdYn` | 14px | Level 1 | **** | `string` | 1 | MPB 상품여부 [Y,N]
 디폴트:N |
| 294 | `saveTypCd` | 14px | Level 1 | **** | `string` | 20 | 저장유형코드 [공통코드 : SAVE_TYP_CD]
 디폴트:해당없음
 


공통코드값
공통코드명


RFRG
냉장


FRZN
냉동


FRSH
신선


NONE
해당없음 |
| 295 | `RFRG` | 0px | Level 0 | **냉장** | `` |  |  |
| 296 | `FRZN` | 0px | Level 0 | **냉동** | `` |  |  |
| 297 | `FRSH` | 0px | Level 0 | **신선** | `` |  |  |
| 298 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 299 | `shopCnvMsgPsbYn` | 14px | Level 1 | **** | `string` | 1 | [백화점] 매장전달메시지가능여부 [Y, N]
 디폴트:N |
| 300 | `rgnLmtPdYn` | 14px | Level 1 | **** | `string` | 1 | [하이마트] 지역한정상품여부 [Y, N]
 디폴트:N |
| 301 | `fprdDvPsbYn` | 14px | Level 1 | **** | `string` | 1 | [마트, 슈퍼] 정기배송가능여부 [Y, N]
 디폴트:N |
| 302 | `spcfSqncPdYn` | 14px | Level 1 | **** | `string` | 1 | [슈퍼]특정회차상품여부
 디폴트:N |
| 303 | `rtngPsbYn` | 14px | Level 1 | **** | `string` | 1 | 반품가능여부 [Y, N]
 디폴트:Y |
| 304 | `xchgPsbYn` | 14px | Level 1 | **** | `string` | 1 | 교환가능여부 [Y, N]
 디폴트:Y |
| 305 | `cmbnRtngPsbYn` | 14px | Level 1 | **** | `string` | 1 | 합반품가능여부 [Y, N]
 합배송가능여부가 Y인 경우 Y선택 가능. N인 경우 N만 선택 가능 |
| 306 | `rtngHdcCd` | 14px | Level 1 | **** | `string` | 20 | 반품택배사코드
 택배사코드 [공통코드 : DV_CO_CD]
 *업데이트로 인해 값이 다를 수 있으므로
 공통 메뉴의 [공통코드 상세조회]를 통해 입력 필요. 
 


공통코드값
공통코드명


0001
롯데택배


0002
CJ대한통운


0003
현대택배


0004
우체국택배


0005
로젠택배


0006
한진택배


0014
GTX 로지스 택배


0016
KGB택배


0023
건영택배


0024
경동택배


0025
고려택배


0027
대신정기화물택배


0028
대신택배


0031
드림택배


0037
엘로우캡택배


0040
이노지스택배


0042
일양택배


0043
천일택배


0044
편의점택배


0046
하나로택배


0048
한의사랑택배


0049
합동택배


0050
호남택배


etc
etc


9999
기타택배 |
| 307 | `0001` | 0px | Level 0 | **롯데택배** | `` |  |  |
| 308 | `0002` | 0px | Level 0 | **CJ대한통운** | `` |  |  |
| 309 | `0003` | 0px | Level 0 | **현대택배** | `` |  |  |
| 310 | `0004` | 0px | Level 0 | **우체국택배** | `` |  |  |
| 311 | `0005` | 0px | Level 0 | **로젠택배** | `` |  |  |
| 312 | `0006` | 0px | Level 0 | **한진택배** | `` |  |  |
| 313 | `0014` | 0px | Level 0 | **GTX 로지스 택배** | `` |  |  |
| 314 | `0016` | 0px | Level 0 | **KGB택배** | `` |  |  |
| 315 | `0023` | 0px | Level 0 | **건영택배** | `` |  |  |
| 316 | `0024` | 0px | Level 0 | **경동택배** | `` |  |  |
| 317 | `0025` | 0px | Level 0 | **고려택배** | `` |  |  |
| 318 | `0027` | 0px | Level 0 | **대신정기화물택배** | `` |  |  |
| 319 | `0028` | 0px | Level 0 | **대신택배** | `` |  |  |
| 320 | `0031` | 0px | Level 0 | **드림택배** | `` |  |  |
| 321 | `0037` | 0px | Level 0 | **엘로우캡택배** | `` |  |  |
| 322 | `0040` | 0px | Level 0 | **이노지스택배** | `` |  |  |
| 323 | `0042` | 0px | Level 0 | **일양택배** | `` |  |  |
| 324 | `0043` | 0px | Level 0 | **천일택배** | `` |  |  |
| 325 | `0044` | 0px | Level 0 | **편의점택배** | `` |  |  |
| 326 | `0046` | 0px | Level 0 | **하나로택배** | `` |  |  |
| 327 | `0048` | 0px | Level 0 | **한의사랑택배** | `` |  |  |
| 328 | `0049` | 0px | Level 0 | **합동택배** | `` |  |  |
| 329 | `0050` | 0px | Level 0 | **호남택배** | `` |  |  |
| 330 | `etc` | 0px | Level 0 | **etc** | `` |  |  |
| 331 | `9999` | 0px | Level 0 | **기타택배** | `` |  |  |
| 332 | `rtngRtrvPsbYn` | 14px | Level 1 | **** | `string` | 1 | 반품회수가능여부 [Y, N]
 디폴트:Y |
| 333 | `rtrpNo` | 14px | Level 1 | **O** | `string` | 20 | 회수지번호
거래처 API "(일반 Seller용) 판매자 출고지/반품지 등록"을 통하여 등록된 회수지번호를 입력한다. |
| 334 | `rntlPdInfo` | 14px | Level 1 | **△** | `object` | 4000 | 렌탈상품정보
 상품유형이 렌탈일 경우 필수값 |
| 335 | `dutyUsePrd` | 30px | Level 2 | **O** | `number` | 22 | 의무사용기간 |
| 336 | `instCst` | 30px | Level 2 | **O** | `number` | 22 | 설치비용 |
| 337 | `regCst` | 30px | Level 2 | **O** | `number` | 22 | 등록비용 |
| 338 | `cnsmrSlPrc` | 30px | Level 2 | **O** | `number` | 22 | 소비자판매가 |
| 339 | `mmRntlCst` | 30px | Level 2 | **O** | `number` | 22 | 월렌탈비용 |
| 340 | `vatInclYn` | 30px | Level 2 | **O** | `string` | 1 | 부가세포함여부 [Y, N]
 디폴트 : Y |
| 341 | `opngPdInfo` | 14px | Level 1 | **△** | `object` |  | 개통형상품정보
 상품유형구분코드가 일반판매_0원상품(GNRL_ZRWON)에 해당하는 개통형상품인 경우 필수입력한다. |
| 342 | `mvCmcoCd` | 30px | Level 2 | **O** | `string` | 20 | 이동통신사코드 [공통코드 : MV_CMCO_CD]
 


공통코드값
공통코드명


SKT
SKT


KT
KT


LGT
LGT


CJH
CJ헬로비전


S1
에스원


MLG
미디어로그


KTM
KTM모바일


SKLINK
SK텔링크


RFRBSH
리퍼비쉬


PNPLAY
핀플레이


SLF_SFC
자급제폰 |
| 343 | `SKT` | 0px | Level 0 | **SKT** | `` |  |  |
| 344 | `KT` | 0px | Level 0 | **KT** | `` |  |  |
| 345 | `LGT` | 0px | Level 0 | **LGT** | `` |  |  |
| 346 | `CJH` | 0px | Level 0 | **CJ헬로비전** | `` |  |  |
| 347 | `S1` | 0px | Level 0 | **에스원** | `` |  |  |
| 348 | `MLG` | 0px | Level 0 | **미디어로그** | `` |  |  |
| 349 | `KTM` | 0px | Level 0 | **KTM모바일** | `` |  |  |
| 350 | `SKLINK` | 0px | Level 0 | **SK텔링크** | `` |  |  |
| 351 | `RFRBSH` | 0px | Level 0 | **리퍼비쉬** | `` |  |  |
| 352 | `PNPLAY` | 0px | Level 0 | **핀플레이** | `` |  |  |
| 353 | `SLF_SFC` | 0px | Level 0 | **자급제폰** | `` |  |  |
| 354 | `owhPrc` | 30px | Level 2 | **** | `number` | 22 | 출고가 |
| 355 | `joinAplUrl` | 30px | Level 2 | **** | `string` | 200 | 가입신청서 URL |
| 356 | `sptAmt` | 30px | Level 2 | **** | `number` | 22 | 지원금액 |
| 357 | `adtnSptAmt` | 30px | Level 2 | **** | `number` | 22 | 추가지원금액 |
| 358 | `stkMgtYn` | 14px | Level 1 | **O** | `string` | 1 | 재고관리여부 [Y, N]
 'N'인 경우 재고가 999,999,999로 들어간다. 웹재고를 관리하지 않는다. |
| 359 | `sitmYn` | 14px | Level 1 | **O** | `string` | 1 | 판매자단품여부 [Y, N]
 Y이면 단품속성목록을 설정해야 한다.
 N이면 단품속성목록을 설정 안한다. 옵션이 없는 단품 한가지로 설정된다. |
| 360 | `thdyPdYn` | 14px | Level 1 | **** | `string` | 1 | 명절상품여부 [Y, N]
 Y이고 [마트]일 경우 명절배송처리유형코드를 설정해야 한다. |
| 361 | `thdyDvProcTypCd` | 14px | Level 1 | **△** | `string` | 20 | [마트] 명절배송처리유형코드 [공통코드 : THDY_DV_PROC_TYP_CD]
 명절상품여부 Y이고 마트일 경우 필수값
 


공통코드값
공통코드명


LM_SHOP
명절근거리


LM_DRECT_DPCL
명절 근거리 + 명절택배


LM_SHOP_DPCL
명절택배


LM_ENTP_DPCL
명절업체배송


LM_SHOP_RFRG
명절냉장배송


LM_SHOP_FRZN
명절냉동배송 |
| 362 | `LM_SHOP` | 0px | Level 0 | **명절근거리** | `` |  |  |
| 363 | `LM_DRECT_DPCL` | 0px | Level 0 | **명절 근거리 + 명절택배** | `` |  |  |
| 364 | `LM_SHOP_DPCL` | 0px | Level 0 | **명절택배** | `` |  |  |
| 365 | `LM_ENTP_DPCL` | 0px | Level 0 | **명절업체배송** | `` |  |  |
| 366 | `LM_SHOP_RFRG` | 0px | Level 0 | **명절냉장배송** | `` |  |  |
| 367 | `LM_SHOP_FRZN` | 0px | Level 0 | **명절냉동배송** | `` |  |  |
| 368 | `itmLst` | 14px | Level 1 | **O** | `array` |  | 단품목록 |
| 369 | `eitmNo` | 30px | Level 2 | **** | `string` | 30 | 업체단품번호 |
| 370 | `rprtSitmYn` | 30px | Level 2 | **** | `string` | 1 | 대표단품여부 [Y, N]
 - 전체단품 중 1개 설정 가능. |
| 371 | `sortSeq` | 30px | Level 2 | **O** | `number` | 10 | 정렬순번 (Front에 노출되는 정렬되는 조건은 아니며 Front 노출 순서 조정 필요 할 경우 optSrtLst 필드로 등록해야 함) |
| 372 | `itmOptLst` | 30px | Level 2 | **△** | `array` |  | 단품속성목록
 판매자단품여부가 Y인 경우 필수값 |
| 373 | `optCd` | 44px | Level 3 | **△** | `string` | 20 | 옵션코드 [속성모듈 제공 항목]
 단품의 옵션에 해당하는 옵션코드를 입력하여야 한다. |
| 374 | `optNm` | 44px | Level 3 | **O** | `string` | 200 | 옵션명 [속성모듈 제공 항목]
 해당 단품의 옵션명을 입력한다. |
| 375 | `optValCd` | 44px | Level 3 | **△** | `string` | 20 | 옵션값코드 [속성모듈 제공 항목]
 입력하고자 하는 옵션값의 옵션값코드가 존재하지 않는 경우에는 옵션값만 입력한다. |
| 376 | `optVal` | 44px | Level 3 | **O** | `string` | 4000 | 옵션값 [속성모듈 제공 항목]
 해당 단품의 옵션값을 입력한다. |
| 377 | `dtlsVal` | 44px | Level 3 | **** | `string` | 4000 | 세부값
 세부값을 입력하는 경우
 1. 범위값에 대한 고정값 입력시
 2. 옵션값에 대한 추가 표현 |
| 378 | `itmImgLst` | 30px | Level 2 | **O** | `array` |  | 단품이미지목록
 단품당 하나 이상의 이미지를 등록하여야 한다.
 단품당 최대 10개의 이미지를 등록할 수 있다. |
| 379 | `epsrTypCd` | 44px | Level 3 | **O** | `string` | 20 | 노출유형코드 [공통코드 : EPSR_TYP_CD]
 


공통코드값
공통코드명


IMG
이미지 |
| 380 | `IMG` | 0px | Level 0 | **이미지** | `` |  |  |
| 381 | `epsrTypDtlCd` | 44px | Level 3 | **O** | `string` | 20 | 노출유형상세코드 [공통코드 : EPSR_TYP_DTL_CD]
 


공통코드값
공통코드명


IMG_SQRE
노출유형:이미지 > 정사각형


IMG_LNTH
노출유형:이미지 > 세로형 |
| 382 | `IMG_SQRE` | 0px | Level 0 | **노출유형:이미지 > 정사각형** | `` |  |  |
| 383 | `IMG_LNTH` | 0px | Level 0 | **노출유형:이미지 > 세로형** | `` |  |  |
| 384 | `origImgFileNm` | 44px | Level 3 | **O** | `string` | 200 | 원본이미지파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) https://abc.com/12/34/56/78_90.jpg
 (등록가능한 확장자 : jpg, jpeg, png) |
| 385 | `rprtImgYn` | 44px | Level 3 | **O** | `string` | 1 | 대표이미지여부 [Y, N]
 대표이미지는 단품별 하나만 설정 가능 |
| 386 | `clrchipLst` | 30px | Level 2 | **** | `array` |  | 컬러칩이미지목록
 단품당 1개 등록 가능 리스트 중 첫번째 등록된 파일로 반영된다. |
| 387 | `origImgFileNm` | 44px | Level 3 | **O** | `string` | 200 | 원본이미지파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) https://abc.com/12/34/56/78_90.jpg |
| 388 | `pdUtStdInfo` | 30px | Level 2 | **** | `object` | 4000 | 상품단위기준정보 |
| 389 | `pdCapa` | 44px | Level 3 | **** | `number` | 10 | 상품총용량
 기준단위와 기준용량은 표준카테고리 매핑 정보를 따른다.
 ex) 표준카테고리에 기준단위가 ml, 기준용량이 100으로 매핑되어 있는 경우 100ml당 가격이 표시된다. |
| 390 | `stdUtCd` | 45px | Level 3 | **** | `number` | 10 | 기준단위
 상품용량에 대한 기준 단위. 표준카테고리 매핑 정보에 설정된 대표값 또는 추가값을 입력할 수 있다. |
| 391 | `stdCapa` | 45px | Level 3 | **** | `number` | 10 | 기준용량
 표준카테고리 매핑에 설정된 기준단위별 용량을 입력한다. |
| 392 | `slPrc` | 30px | Level 2 | **O** | `number` | 22 | 판매가 |
| 393 | `stkQty` | 30px | Level 2 | **△** | `number` | 10 | 재고수량
 재고관리여부가 Y인 경우에는 필수값 |
| 394 | `optSrtLst` | 15px | Level 1 | **** | `array` | 5 | 옵션정렬목록
 단품에 적용된 옵션코드의 순서와 해당 옵션코드의 값코드 순서를 지정한다. |
| 395 | `optSeq` | 30px | Level 2 | **O** | `number` | 1 | 옵션순번 |
| 396 | `optNm` | 30px | Level 2 | **O** | `string` | 200 | 옵션명 |
| 397 | `optCd` | 30px | Level 2 | **△** | `string` | 20 | 옵션코드
 단품옵션에 옵션코드를 입력한 경우 필수 |
| 398 | `optValSrtLst` | 30px | Level 2 | **O** | `array` | 500 | 옵션값순번목록 |
| 399 | `optValSeq` | 45px | Level 3 | **O** | `number` | 1 | 옵션값순번 |
| 400 | `optVal` | 45px | Level 3 | **O** | `string` |  | 옵션값 |
| 401 | `optValCd` | 45px | Level 3 | **△** | `string` | 20 | 옵션값코드
 단품옵션에 옵션값코드를 입력한 경우 필수 |
| 402 | `dtlsVal` | 45px | Level 3 | **△** | `string` |  | 세부값
 단품옵션에 세부값을 입력한 경우 필수 |
| 403 | `slrRcPdLst` | 14px | Level 1 | **** | `array` | 4000 | 셀러추천상품목록
 최대 10개까지 등록 가능하다. |
| 404 | `slrRcSpdNo` | 30px | Level 2 | **O** | `string` | 30 | 셀러추천판매자상품번호 |
| 405 | `slrRcSitmNo` | 30px | Level 2 | **O** | `string` | 30 | 셀러추천판매자단품번호 |
| 406 | `epsrPrirRnkg` | 30px | Level 2 | **O** | `number` | 3 | 노출우선순위 |
| 407 | `adtnPdYn` | 14px | Level 1 | **O** | `string` | 1 | 추가상품사용여부 [Y, N]
 디폴트:N |
| 408 | `adtnPdInfo` | 14px | Level 1 | **** | `Object` |  | 추가상품정보 |
| 409 | `sortCd` | 30px | Level 2 | **O** | `string` | 20 | 추가상품정렬코드 [공통코드 : ADTN_PD_SORT_CD]
 


공통코드값
공통코드명


REGIST_ASC
등록순


NAME_ASC
가나다순


PRICE_ASC
낮은가격순


PRICE_DESC
높은가격순 |
| 410 | `REGIST_ASC` | 0px | Level 0 | **등록순** | `` |  |  |
| 411 | `NAME_ASC` | 0px | Level 0 | **가나다순** | `` |  |  |
| 412 | `PRICE_ASC` | 0px | Level 0 | **낮은가격순** | `` |  |  |
| 413 | `PRICE_DESC` | 0px | Level 0 | **높은가격순** | `` |  |  |
| 414 | `adtnTypeLst` | 30px | Level 2 | **O** | `Array` | 10 | 추가유형목록 |
| 415 | `adtnTypNm` | 44px | Level 3 | **O** | `string` | 100 | 추가유형명 |
| 416 | `epsrPrirRnkg` | 44px | Level 3 | **O** | `number` | 3 | 노출우선순위 |
| 417 | `adtnPdLst` | 44px | Level 3 | **O** | `Array` | 10 | 추가상품목록 |
| 418 | `adtnPdNm` | 60px | Level 4 | **O** | `string` | 100 | 추가상품명 |
| 419 | `epdNo` | 60px | Level 4 | **** | `String` | 30 | 업체상품번호 |
| 420 | `epsrPrirRnkg` | 60px | Level 4 | **** | `number` | 3 | 노출우선순위 |
| 421 | `slPrc` | 60px | Level 4 | **O** | `number` | 10 | 판매가 |
| 422 | `useYn` | 60px | Level 4 | **O** | `number` | 1 | 사용여부 [Y, N] |
| 423 | `rtrvTypCd` | 30px | Level 2 | **X** | `string` | 20 | 회수유형코드 [공통코드: RTRV_TYP_CD]
 계약유형이 중개일 경우에만 해당.
 


공통코드값
공통코드명


ENTP_RTRV
업체회수


DGNN_RTRV
자동회수 |
| 424 | `ENTP_RTRV` | 0px | Level 0 | **업체회수** | `` |  |  |
| 425 | `DGNN_RTRV` | 0px | Level 0 | **자동회수** | `` |  |  |

---

## 2. Product Modification Request Table (`POST /v1/openapi/product/v1/product/modification/request`)

| Row # | Field Name | Margin (px) | Depth Level | Required | Type | Length | Description (Korean) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `spdLst` | 0px | Level 0 | **** | `array` |  | 수정상품목록 |
| 2 | `trGrpCd` | 15px | Level 1 | **O** | `string` | 11 | 거래처그룹코드 |
| 3 | `trNo` | 15px | Level 1 | **O** | `string` | 11 | 거래처번호 |
| 4 | `lrtrNo` | 15px | Level 1 | **** | `string` | 11 | 하위거래처번호 |
| 5 | `dcatLst` | 15px | Level 1 | **** | `array` |  | 전시카테고리목록
 속성모듈의 API를 통하여 표준카테고리에 매핑된 전시카테고리를 정보를 받는다.
 매핑된 전시카테고리 중에서 하나 이상 선택하여 입력한다. |
| 6 | `mallCd` | 30px | Level 2 | **** | `string` | 20 | 몰구분코드 [공통코드 : MALL_DVS_CD]
 


공통코드값
공통코드명


LTON
롯데ON |
| 7 | `LTON` | 0px | Level 0 | **롯데ON** | `` |  |  |
| 8 | `lfDcatNo` | 30px | Level 2 | **** | `string` | 100 | leaf전시카테고리번호 |
| 9 | `spdNo` | 15px | Level 1 | **O** | `string` | 30 | 판매자상품번호 |
| 10 | `spdNm` | 15px | Level 1 | **** | `string` | 150 | 판매자상품명
 입력된 판매자상품명은 상품명 정제를 거쳐 전시상품명으로 노출된다. |
| 11 | `brdNo` | 15px | Level 1 | **** | `string` | 7 | 브랜드번호 [속성모듈 제공 항목]
 속성모듈 API를 통하여 수신된 브랜드번호를 입력한다. |
| 12 | `mfcrNm` | 15px | Level 1 | **** | `string` | 100 | 제조사명
 TXT 값으로 입력한다. |
| 13 | `prdByMaxPurPsbQtyYn` | 14px | Level 1 | **** | `string` | 1 | 상품별최대구매수량여부[Y,N] |
| 14 | `oplcCd` | 15px | Level 1 | **** | `string` | 20 | 원산지코드 [공통코드 : OPLC_CD]
 기타인 경우에는 "상품상세 참조"코드 입력 |
| 15 | `mdlNo` | 15px | Level 1 | **** | `string` | 62 | 모델번호 |
| 16 | `barCd` | 15px | Level 1 | **** | `string` | 20 | 바코드 |
| 17 | `tdfDvsCd` | 15px | Level 1 | **** | `string` | 20 | 과면세구분코드 [공통코드 : TDF_DVS_CD]
 


공통코드값
공통코드명


01
과세


02
면세


03
영세


04
해당없음 |
| 18 | `01` | 0px | Level 0 | **과세** | `` |  |  |
| 19 | `02` | 0px | Level 0 | **면세** | `` |  |  |
| 20 | `03` | 0px | Level 0 | **영세** | `` |  |  |
| 21 | `04` | 0px | Level 0 | **해당없음** | `` |  |  |
| 22 | `slStrtDttm` | 15px | Level 1 | **** | `string` | 14 | 판매시작일시 [YYYYMMDDHH24MISS ex) 20190801100000] |
| 23 | `slEndDttm` | 15px | Level 1 | **** | `string` | 14 | 판매종료일시 [YYYYMMDDHH24MISS ex) 20190801100000] |
| 24 | `pdItmsInfo` | 15px | Level 1 | **** | `object` |  | 상품품목고시정보 |
| 25 | `pdItmsCd` | 30px | Level 2 | **** | `string` | 20 | 상품품목코드 [공통코드 : PD_ITMS_CD]
 


공통코드값
공통코드명


01
[01]의류


02
[02]구두/신발


03
[03]가방


04
[04]패션잡화(모자/벨트/액세서리 등)


05
[05]침구류/커튼


06
[06]가구(침대/소파/싱크대/DIY제품 등)


07
[07]영상가전(TV류)


08
[08]가정용 전기제품(냉장고/세탁기/식기세척기/전자레인지 등)


09
[09]계절가전(에어컨/온풍기 등)


10
[10]사무용기기(컴퓨터/노트북/프린터 등)


11
[11]광학기기(디지털카메라/캠코더 등)


12
[12]소형전자(MP3/전자사전 등)


13
[13]휴대형 통신기기(휴대폰/태블릿 등)


14
[14]내비게이션


15
[15]자동차용품(자동차부품/기타 자동차용품 등)


16
[16]의료기기


17
[17]주방용품


18
[18]화장품


19
[19]귀금속/보석/시계류


20
[20] 농수축산물


21
[21]가공식품


22
[22]건강기능식품


23
[23]어린이제품


24
[24]악기


25
[25]스포츠용품


26
[26]서적


27
[27]호텔/펜션 예약


28
[28]여행패키지


29
[29]항공권


30
[30]자동차 대여 서비스(렌터카)


31
[31]물품대여 서비스(정수기,비데,공기청정기 등)


32
[32]물품대여 서비스(서적,유아용품,행사용품 등)


33
[33]디지털 콘텐츠(음원,게임,인터넷강의 등)


34
[34]상품권/쿠폰


35
[35]모바일쿠폰


36
[36]영화/공연


37
[37]기타(용역)


38
[38]기타(재화)


39
[39]생활화학제품


40
[40]살생물제품 |
| 26 | `01` | 0px | Level 0 | **[01]의류** | `` |  |  |
| 27 | `02` | 0px | Level 0 | **[02]구두/신발** | `` |  |  |
| 28 | `03` | 0px | Level 0 | **[03]가방** | `` |  |  |
| 29 | `04` | 0px | Level 0 | **[04]패션잡화(모자/벨트/액세서리 등)** | `` |  |  |
| 30 | `05` | 0px | Level 0 | **[05]침구류/커튼** | `` |  |  |
| 31 | `06` | 0px | Level 0 | **[06]가구(침대/소파/싱크대/DIY제품 등)** | `` |  |  |
| 32 | `07` | 0px | Level 0 | **[07]영상가전(TV류)** | `` |  |  |
| 33 | `08` | 0px | Level 0 | **[08]가정용 전기제품(냉장고/세탁기/식기세척기/전자레인지 등)** | `` |  |  |
| 34 | `09` | 0px | Level 0 | **[09]계절가전(에어컨/온풍기 등)** | `` |  |  |
| 35 | `10` | 0px | Level 0 | **[10]사무용기기(컴퓨터/노트북/프린터 등)** | `` |  |  |
| 36 | `11` | 0px | Level 0 | **[11]광학기기(디지털카메라/캠코더 등)** | `` |  |  |
| 37 | `12` | 0px | Level 0 | **[12]소형전자(MP3/전자사전 등)** | `` |  |  |
| 38 | `13` | 0px | Level 0 | **[13]휴대형 통신기기(휴대폰/태블릿 등)** | `` |  |  |
| 39 | `14` | 0px | Level 0 | **[14]내비게이션** | `` |  |  |
| 40 | `15` | 0px | Level 0 | **[15]자동차용품(자동차부품/기타 자동차용품 등)** | `` |  |  |
| 41 | `16` | 0px | Level 0 | **[16]의료기기** | `` |  |  |
| 42 | `17` | 0px | Level 0 | **[17]주방용품** | `` |  |  |
| 43 | `18` | 0px | Level 0 | **[18]화장품** | `` |  |  |
| 44 | `19` | 0px | Level 0 | **[19]귀금속/보석/시계류** | `` |  |  |
| 45 | `20` | 0px | Level 0 | **[20] 농수축산물** | `` |  |  |
| 46 | `21` | 0px | Level 0 | **[21]가공식품** | `` |  |  |
| 47 | `22` | 0px | Level 0 | **[22]건강기능식품** | `` |  |  |
| 48 | `23` | 0px | Level 0 | **[23]어린이제품** | `` |  |  |
| 49 | `24` | 0px | Level 0 | **[24]악기** | `` |  |  |
| 50 | `25` | 0px | Level 0 | **[25]스포츠용품** | `` |  |  |
| 51 | `26` | 0px | Level 0 | **[26]서적** | `` |  |  |
| 52 | `27` | 0px | Level 0 | **[27]호텔/펜션 예약** | `` |  |  |
| 53 | `28` | 0px | Level 0 | **[28]여행패키지** | `` |  |  |
| 54 | `29` | 0px | Level 0 | **[29]항공권** | `` |  |  |
| 55 | `30` | 0px | Level 0 | **[30]자동차 대여 서비스(렌터카)** | `` |  |  |
| 56 | `31` | 0px | Level 0 | **[31]물품대여 서비스(정수기,비데,공기청정기 등)** | `` |  |  |
| 57 | `32` | 0px | Level 0 | **[32]물품대여 서비스(서적,유아용품,행사용품 등)** | `` |  |  |
| 58 | `33` | 0px | Level 0 | **[33]디지털 콘텐츠(음원,게임,인터넷강의 등)** | `` |  |  |
| 59 | `34` | 0px | Level 0 | **[34]상품권/쿠폰** | `` |  |  |
| 60 | `35` | 0px | Level 0 | **[35]모바일쿠폰** | `` |  |  |
| 61 | `36` | 0px | Level 0 | **[36]영화/공연** | `` |  |  |
| 62 | `37` | 0px | Level 0 | **[37]기타(용역)** | `` |  |  |
| 63 | `38` | 0px | Level 0 | **[38]기타(재화)** | `` |  |  |
| 64 | `39` | 0px | Level 0 | **[39]생활화학제품** | `` |  |  |
| 65 | `40` | 0px | Level 0 | **[40]살생물제품** | `` |  |  |
| 66 | `pdItmsArtlLst` | 30px | Level 2 | **** | `array` | 4000 | 상품품목항목목록 |
| 67 | `pdArtlCd` | 45px | Level 3 | **** | `string` | 20 | 상품항목코드 |
| 68 | `pdArtlCnts` | 45px | Level 3 | **** | `string` | 4000 | 상품항목내용
 해당 고시정보항목의 항목값을 입력한다. |
| 69 | `impPrxCd` | 14px | Level 1 | **△** | `string` | 20 | 수입대행코드 [공통코드 : IMP_PRX_CD]
 안전인증목록의 KC인증 입력시에 입력한다.
 


공통코드값
공통코드명


PUR_PRX
구매대행


PRL_IMP
병행수입


NONE
해당없음 |
| 70 | `PUR_PRX` | 0px | Level 0 | **구매대행** | `` |  |  |
| 71 | `PRL_IMP` | 0px | Level 0 | **병행수입** | `` |  |  |
| 72 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 73 | `sftyAthnLst` | 15px | Level 1 | **** | `array` | 4000 | 안전인증목록
 안전인증정보 입력시 하단의 항목을 입력한다. |
| 74 | `sftyAthnTypCd` | 30px | Level 2 | **** | `string` | 20 | 안전인증유형코드 [공통코드 : SFTY_ATHN_TYP_CD]
 'KC인증'에 해당할 경우 수입대행코드는 필수 값이다.
 


공통코드값
공통코드명
비고


CHL_ATHN
[어린이제품] 안전인증
 


CHL_CFM
[어린이제품] 안전확인
 


CHL_SUPS
[어린이제품] 공급자적합성확인
 


ELC_ATHN
[전기용품] 안전인증
수입대행코드필수


ELC_CFM
[전기용품] 안전확인
수입대행코드필수


ELC_SUPS
[전기용품] 공급자적합성확인
수입대행코드필수


LIFE_ATHN
[생활용품] 안전인증
수입대행코드필수


LIFE_CFM
[생활용품] 안전확인
수입대행코드필수


LIFE_SUPS
[전기용품] 공급자적합성확인
수입대행코드필수


LIFE_STD
[생활용품] 안전기준준수
수입대행코드필수


KC_CHL_PKG
[KC인증] 어린이보호포장
수입대행코드필수


ETC
KC기타
수입대행코드필수


CMCN_TNTT
[방송통신기자재] 잠정인증
수입대행코드필수


CMCN_REG
[방송통신기자재] 적합등록
수입대행코드필수


CMCN_ATHN
[방송통신기자재] 적합인증
수입대행코드필수


CHEM_BIOC
[살생물제품] 승인번호
 


CHEM_LIFE
[생활화학제품] 안전기준적합확인신고번호
 


MTR_APRV
[계량기] 형식 승인
수입대행코드필수


DRT_IPT
직접입력
수입대행코드필수


DTL_REFC
상품상세 참조
수입대행코드필수 |
| 75 | `CHL_ATHN` | 0px | Level 0 | **[어린이제품] 안전인증** | `` |  |  |
| 76 | `CHL_CFM` | 0px | Level 0 | **[어린이제품] 안전확인** | `` |  |  |
| 77 | `CHL_SUPS` | 0px | Level 0 | **[어린이제품] 공급자적합성확인** | `` |  |  |
| 78 | `ELC_ATHN` | 0px | Level 0 | **[전기용품] 안전인증** | `수입대행코드필수` |  |  |
| 79 | `ELC_CFM` | 0px | Level 0 | **[전기용품] 안전확인** | `수입대행코드필수` |  |  |
| 80 | `ELC_SUPS` | 0px | Level 0 | **[전기용품] 공급자적합성확인** | `수입대행코드필수` |  |  |
| 81 | `LIFE_ATHN` | 0px | Level 0 | **[생활용품] 안전인증** | `수입대행코드필수` |  |  |
| 82 | `LIFE_CFM` | 0px | Level 0 | **[생활용품] 안전확인** | `수입대행코드필수` |  |  |
| 83 | `LIFE_SUPS` | 0px | Level 0 | **[전기용품] 공급자적합성확인** | `수입대행코드필수` |  |  |
| 84 | `LIFE_STD` | 0px | Level 0 | **[생활용품] 안전기준준수** | `수입대행코드필수` |  |  |
| 85 | `KC_CHL_PKG` | 0px | Level 0 | **[KC인증] 어린이보호포장** | `수입대행코드필수` |  |  |
| 86 | `ETC` | 0px | Level 0 | **KC기타** | `수입대행코드필수` |  |  |
| 87 | `CMCN_TNTT` | 0px | Level 0 | **[방송통신기자재] 잠정인증** | `수입대행코드필수` |  |  |
| 88 | `CMCN_REG` | 0px | Level 0 | **[방송통신기자재] 적합등록** | `수입대행코드필수` |  |  |
| 89 | `CMCN_ATHN` | 0px | Level 0 | **[방송통신기자재] 적합인증** | `수입대행코드필수` |  |  |
| 90 | `CHEM_BIOC` | 0px | Level 0 | **[살생물제품] 승인번호** | `` |  |  |
| 91 | `CHEM_LIFE` | 0px | Level 0 | **[생활화학제품] 안전기준적합확인신고번호** | `` |  |  |
| 92 | `MTR_APRV` | 0px | Level 0 | **[계량기] 형식 승인** | `수입대행코드필수` |  |  |
| 93 | `DRT_IPT` | 0px | Level 0 | **직접입력** | `수입대행코드필수` |  |  |
| 94 | `DTL_REFC` | 0px | Level 0 | **상품상세 참조** | `수입대행코드필수` |  |  |
| 95 | `sftyAthnOrgnNm` | 30px | Level 2 | **** | `String` | 100 | 안전인증기관명 |
| 96 | `sftyAthnNo` | 30px | Level 2 | **** | `string` | 100 | 안전인증번호 |
| 97 | `itypOptDelYn` | 0px | Level 0 | **** | `string` | 1 | 입력형옵션삭제여부 |
| 98 | `itypOptLst` | 15px | Level 1 | **** | `array` | 4000 | 입력형옵션목록
 최대 5개의 입력형옵션을 설정할 수 있다. |
| 99 | `itypOptDvsCd` | 30px | Level 2 | **** | `string` | 20 | 입력형옵션구분코드 [공통코드 : ITYP_OPT_DVS_CD]
 


공통코드값
공통코드명


NO
숫자


TXT
텍스트


DATE
달력형


TIME
시간선택형


LIST
목록선택형 |
| 100 | `NO` | 0px | Level 0 | **숫자** | `` |  |  |
| 101 | `TXT` | 0px | Level 0 | **텍스트** | `` |  |  |
| 102 | `DATE` | 0px | Level 0 | **달력형** | `` |  |  |
| 103 | `TIME` | 0px | Level 0 | **시간선택형** | `` |  |  |
| 104 | `LIST` | 0px | Level 0 | **목록선택형** | `` |  |  |
| 105 | `itypOptNm` | 30px | Level 2 | **** | `string` | 200 | 입력형옵션명 |
| 106 | `itypOptValLst` | 30px | Level 2 | **** | `array` |  | 입력옵션값목록 [마트, 슈퍼 전용]
 입력형옵션구분코드가 목록선택행일 때만 입력한다. |
| 107 | `itypOptVal` | 45px | Level 3 | **** | `string` | 4000 | 입력형옵션값 [마트, 슈퍼 전용] |
| 108 | `purPsbQtyInfo` | 15px | Level 1 | **** | `object` |  | 구매가능수량정보 |
| 109 | `itmByMinPurYn` | 30px | Level 2 | **** | `string` | 1 | 단품별최소구매여부 [Y, N] |
| 110 | `itmByMinPurQty` | 30px | Level 2 | **** | `number` | 6 | 단품별최소구매수량
 단품별최소구매여부가 Y인 경우 필수입력한다. |
| 111 | `itmByMinPurMtpYn` | 30px | Level 2 | **△** | `string` | 1 | 단품별최소구매배수여부
 단품별최소구매여부가 Y인 경우 입력 가능하고 미입력 시 N으로 설정된다. |
| 112 | `itmByMaxPurPsbQtyYn` | 30px | Level 2 | **** | `string` | 1 | 단품별최대구매가능수량여부 [Y, N] |
| 113 | `maxPurQty` | 30px | Level 2 | **** | `number` | 6 | 단품별최대구매수량
 단품별최대구매가능수량여부가 Y인 경우 필수입력한다. |
| 114 | `maxPurLmtTypCd` | 30px | Level 2 | **O** | `string` | 20 | 단품별최대구매제한구분코드 [공통코드 : MAX_PUR_LMT_TYP_CD]
 


공통코드값
공통코드명


ONCE
1회제한


PERIOD
기간제한


FIXED
특정일자 제한



 미입력 시 기간제한(PERIOD)로 적용되고 단품별최대구매제한기간(maxPurLmtPrd)은 1일로 설정 된다. |
| 115 | `ONCE` | 0px | Level 0 | **1회제한** | `` |  |  |
| 116 | `PERIOD` | 0px | Level 0 | **기간제한** | `` |  |  |
| 117 | `FIXED` | 0px | Level 0 | **특정일자 제한** | `` |  |  |
| 118 | `maxPurLmtPrd` | 30px | Level 2 | **△** | `number` | 5 | 단품별최대구매제한기간
 단품별최대구매제한구분코드가 기간제한(PERIOD)일 경우 필수입력한다. |
| 119 | `maxPurLmtStrtDttm` | 30px | Level 2 | **△** | `string` | 14 | 단품별최대구매제한시작일자
 단품별최대구매제한구분코드가 특정일자 제한(FIXED)일 경우 필수입력한다. [YYYYMMDDHH24MISS ex) 20190801100000]
 - 시간단위 설정 시 YYYYMMDDHH24까지만 설정 가능하고 분초는 0000으로 고정
 - 날짜단위 설정 시 YYYYMMDD까지만 설정 가능하고 시작일시 시분초는 000000 고정 |
| 120 | `maxPurLmtEndDttm` | 30px | Level 2 | **△** | `string` | 14 | 단품별최대구매제한종료일자
 단품별최대구매제한구분코드가 특정일자 제한(FIXED)일 경우 필수입력한다. [YYYYMMDDHH24MISS ex) 20190801100000]
 - 시간단위 설정 시 YYYYMMDDHH24까지만 설정 가능하고 분초는 0000으로 고정
 - 날짜단위 설정 시 YYYYMMDD까지만 설정 가능하고 종료일시 시분초는 235959 고정 |
| 121 | `prstPsbYn` | 15px | Level 1 | **** | `string` | 1 | 선물가능여부 [Y, N]
 디폴트:N |
| 122 | `prstPckPsbYn` | 15px | Level 1 | **** | `string` | 1 | 선물포장가능여부 [Y, N] |
| 123 | `prstMsgPsbYn` | 15px | Level 1 | **** | `string` | 1 | 선물메시지가능여부 [Y, N] |
| 124 | `prcCmprEpsrYn` | 15px | Level 1 | **** | `string` | 1 | 가격비교노출여부 [Y, N]
 디폴트:Y |
| 125 | `bookCultCstDdctYn` | 15px | Level 1 | **** | `string` | 1 | 도서문화비 공제여부 [Y, N]
 디폴트:N
 거래처와 표준카테고리가 모두 도서문화비 공제대상에 해당하는 경우에만 공제여부가 Y이다. |
| 126 | `isbnCd` | 15px | Level 1 | **** | `string` | 20 | ISBN
 도서문화비 공제여부가 Y이고 카테고리가 도서관련 카테고리일 경우 ISBN NO를 입력한다. |
| 127 | `impCoNm` | 15px | Level 1 | **** | `string` | 100 | 수입사명
 TXT 입력 |
| 128 | `impDvsCd` | 15px | Level 1 | **** | `string` | 20 | 수입구분코드 [공통코드 : IMP_DVS_CD]
 수입사명이 있는 경우 입력한다.
 


공통코드값
공통코드명


DRC_IMP
공식수입


PRL_IMP
병행수입


NONE
해당없음 |
| 129 | `DRC_IMP` | 0px | Level 0 | **공식수입** | `` |  |  |
| 130 | `PRL_IMP` | 0px | Level 0 | **병행수입** | `` |  |  |
| 131 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 132 | `cshbltyPdYn` | 15px | Level 1 | **** | `string` | 1 | 환금성상품여부 [Y, N]
 표준카테고리 속성을 상속 받는다.
 환금성 상품으로 설정되는 경우 주문에서 결제수단에 따라 구매가 제한된다.
 디폴트:N |
| 133 | `dnDvPdYn` | 15px | Level 1 | **** | `string` | 1 | [슈퍼]새벽배송상품여부
 디폴트:N |
| 134 | `toysPdYn` | 15px | Level 1 | **** | `string` | 1 | [마트] 토이저러스상품여부 [Y, N] |
| 135 | `intgSlPdNo` | 15px | Level 1 | **** | `string` | 30 | [엘롯데] 통합판매상품번호
 백화점 통판 판매상품 고유코드(통판연동상품인 경우에만 사용)이다.
 파트너플러스엘롯데에서 연동된 상품일 경우에만 사용된다. |
| 136 | `nmlPdYn` | 15px | Level 1 | **** | `string` | 1 | [엘롯데] 정상상품여부 [Y, N]
 디폴트:N |
| 137 | `lnchYm` | 15px | Level 1 | **** | `string` | 6 | 출시년월 |
| 138 | `prmmPdYn` | 15px | Level 1 | **** | `string` | 1 | [엘롯데] 프리미엄상품여부
 디폴트:N |
| 139 | `prmmPdInfo` | 15px | Level 1 | **** | `object` |  | [엘롯데]프리미엄상품설명정보
 프리미엄상품여부가 Y인 경우 입력한다. |
| 140 | `origQrtbImgFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본조견표이미지파일명(경로) |
| 141 | `origActlMeasSzImgFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본실측정사이즈이미지파일명(경로) |
| 142 | `origMeasImgCntsFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본실측정사이즈내용파일명(경로) |
| 143 | `origAvnPdDtlEpnFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본에비뉴엘상품상세설명파일명(경로) |
| 144 | `otltPdYn` | 15px | Level 1 | **** | `string` | 1 | [엘롯데] 아울렛상품여부 [Y, N]
 디폴트:N |
| 145 | `prmmInstPdYn` | 15px | Level 1 | **** | `string` | 1 | [하이마트] 프리미엄설치상품여부 [Y, N]
 디폴트:N |
| 146 | `brkHmapPkcpPsbYn` | 15px | Level 1 | **** | `string` | 1 | 폐가전수거여부 [Y, N]
 디폴트:N |
| 147 | `pdSzInfo` | 15px | Level 1 | **** | `object` | 4000 | 배송사이즈정보 |
| 148 | `pdWdthSz` | 30px | Level 2 | **** | `number` | 100 | 상품가로사이즈 (cm) |
| 149 | `pdLnthSz` | 30px | Level 2 | **** | `number` | 100 | 상품세로사이즈 (cm) |
| 150 | `pdHghtSz` | 30px | Level 2 | **** | `number` | 100 | 상품높이사이즈 (cm) |
| 151 | `pckWdthSz` | 30px | Level 2 | **** | `number` | 100 | 포장가로사이즈 (cm) |
| 152 | `pckLnthSz` | 30px | Level 2 | **** | `number` | 100 | 포장세로사이즈 (cm) |
| 153 | `pckHghtSz` | 30px | Level 2 | **** | `number` | 100 | 포장높이사이즈 (cm) |
| 154 | `dpYn` | 15px | Level 1 | **** | `string` | 1 | 전시여부 [Y, N]
 디폴트:Y |
| 155 | `ltonDpYn` | 15px | Level 1 | **** | `string` | 1 | LotteOn전시여부 [엘롯데, 마트, 슈퍼, 롭스 전용]
 N인 경우 LotteOn 비전시
 디폴트:Y |
| 156 | `pdFileLst` | 15px | Level 1 | **** | `array` | 4000 | 상품콘텐츠파일목록
 상품상태코드가 새상품(NEW)이 아닌 경우에는 파일유형코드와 파일구분코드를 USD로 하여 상품상태이미지를 반드시 등록하여야 한다.

 * pdFileLst = [] 일 경우 상품콘텐츠파일목록 삭제 |
| 157 | `fileTypCd` | 30px | Level 2 | **** | `string` | 20 | 파일유형코드 [공통코드 : FILE_TYP_CD]
 


공통코드값
공통코드명


USD
상품상태


TAG_LBL
Tag/케어라벨


PD
상품 |
| 158 | `USD` | 0px | Level 0 | **상품상태** | `` |  |  |
| 159 | `TAG_LBL` | 0px | Level 0 | **Tag/케어라벨** | `` |  |  |
| 160 | `PD` | 0px | Level 0 | **상품** | `` |  |  |
| 161 | `fileDvsCd` | 30px | Level 2 | **** | `string` | 20 | 파일구분코드 [공통코드 : FILE_DVS_CD]
 


공통코드값
공통코드명


3D
상품3D이미지


USD
상품유형(중고)


WDTH
상품가로형


TAG_LBL
Tag/케어라벨


VDO_URL
상품동영상_URL


VDO_FILE
상품동영상_FILE


VDO_FILE_HM
홈쇼핑_동영상_FILE




 * VDO_FILE_HM 는 ETV 사용가능 거래처만 등록 가능 |
| 162 | `3D` | 0px | Level 0 | **상품3D이미지** | `` |  |  |
| 163 | `USD` | 0px | Level 0 | **상품유형(중고)** | `` |  |  |
| 164 | `WDTH` | 0px | Level 0 | **상품가로형** | `` |  |  |
| 165 | `TAG_LBL` | 0px | Level 0 | **Tag/케어라벨** | `` |  |  |
| 166 | `VDO_URL` | 0px | Level 0 | **상품동영상_URL** | `` |  |  |
| 167 | `VDO_FILE` | 0px | Level 0 | **상품동영상_FILE** | `` |  |  |
| 168 | `VDO_FILE_HM` | 0px | Level 0 | **홈쇼핑_동영상_FILE** | `` |  |  |
| 169 | `origFileNm` | 30px | Level 2 | **** | `string` | 200 | 원본파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) http://abc.com/12/34/56/78_90.mp4 |
| 170 | `dpStrtDttm` | 30px | Level 2 | **** | `string` | 14 | 전시시작일시 [YYYYMMDDHH24MISS ex) 20190801100000]
 * VDO_FILE_HM 등록인 경우 필수 입력 |
| 171 | `dpEndDttm` | 30px | Level 2 | **** | `string` | 14 | 전시종료일시 [YYYYMMDDHH24MISS ex) 20190801100000]
 * VDO_FILE_HM 등록인 경우 필수 입력 |
| 172 | `epnLst` | 15px | Level 1 | **** | `array` | 4000 | 상품설명목록 |
| 173 | `pdEpnTypCd` | 30px | Level 2 | **** | `string` | 20 | 상품설명유형코드 [공통코드 : PD_EPN_TYP_CD]
 


공통코드값
공통코드명


DSCRP
상품기술서


AS_CNTS
A/S내용설명


PRCTN
주의사항설명




 상세정보를 이미지로 등록 시 시각 약자
 고객을 위해 이미지 대체 텍스트 (alt)
 입력 필요 |
| 174 | `DSCRP` | 0px | Level 0 | **상품기술서** | `` |  |  |
| 175 | `AS_CNTS` | 0px | Level 0 | **A/S내용설명** | `` |  |  |
| 176 | `PRCTN` | 0px | Level 0 | **주의사항설명** | `` |  |  |
| 177 | `cnts` | 30px | Level 2 | **** | `string` |  | 내용
 html입력시 사용한다. |
| 178 | `onnuriPyPsbYn` | 15px | Level 1 | **** | `string` | 1 | 온누리결제가능여부(일반셀러)
 디폴트:N |
| 179 | `cnclPsbYn` | 15px | Level 1 | **** | `string` | 1 | 취소가능여부 [Y, N]
 취소 불가인 상품인 경우에는 'N'으로 설정
 디폴트:Y |
| 180 | `dvPdTypCd` | 15px | Level 1 | **** | `string` | 20 | 배송상품유형코드 [공통코드 : DV_PD_TYP_CD]
상품유형별_배송상품유형코드



공통코드값
공통코드명
최대발송예정일수


GNRL
일반상품
3


OD_MFG
주문제작상품
15


FREE_INST
무료설치상품
3


CHRG_INST
유료설치상품
3


PRMM_INST
프리미엄설치상품
365


ECPN
e쿠폰
0


GFTV
상품권
3 |
| 181 | `GNRL` | 0px | Level 0 | **일반상품** | `3` |  |  |
| 182 | `OD_MFG` | 0px | Level 0 | **주문제작상품** | `15` |  |  |
| 183 | `FREE_INST` | 0px | Level 0 | **무료설치상품** | `3` |  |  |
| 184 | `CHRG_INST` | 0px | Level 0 | **유료설치상품** | `3` |  |  |
| 185 | `PRMM_INST` | 0px | Level 0 | **프리미엄설치상품** | `365` |  |  |
| 186 | `ECPN` | 0px | Level 0 | **e쿠폰** | `0` |  |  |
| 187 | `GFTV` | 0px | Level 0 | **상품권** | `3` |  |  |
| 188 | `sndBgtNday` | 15px | Level 1 | **** | `number` | 8 | 발송예정일수
 배송상품유형코드에 따라 최대 발송예정일수를 입력한다. |
| 189 | `sndBgtDdInfo` | 15px | Level 1 | **** | `object` |  | 발송예정일정보 |
| 190 | `nldySndCloseTm` | 30px | Level 2 | **** | `string` | 4 | 평일 발송마감시간 [HH24MI ex) 1000]
 
발송예정일이 '0'일(오늘발송)로 설정된 경우에만 적용
00분, 30분만 등록 가능
국내배송 : 06:00 ~ 23:00 설정 가능
해외배송 : 00:30 ~ 23:30 설정 가능 |
| 191 | `satSndPsbYn` | 30px | Level 2 | **** | `string` | 1 | 토요일 발송가능여부 [Y, N]
 거래처정보가 토요일기본상태 : 근무안함 일 경우 Y 사용불가 |
| 192 | `satSndCloseTm` | 30px | Level 2 | **** | `string` | 4 | 토요일 발송마감시간 [HH24MI ex) 1000]
 토요일 발송 가능여부 Y인 경우 필수
 00분, 30분만 등록 가능 |
| 193 | `dvRgsprGrpCd` | 15px | Level 1 | **** | `string` | 20 | 배송가능지역코드
 배송모듈을 통하여 관리되는 코드를 입력한다. |
| 194 | `dvMnsCd` | 15px | Level 1 | **** | `string` | 20 | 배송수단코드 [공통코드 : DV_MNS_CD]
 단건만 입력가능
 


공통코드값
공통코드명


DPCL
일반택배


DGNN_DV
직접배송


REG_MAIL
등기


ZIP
우편


NONE_DV
무배송(e쿠폰)


ETC
기타 |
| 195 | `DPCL` | 0px | Level 0 | **일반택배** | `` |  |  |
| 196 | `DGNN_DV` | 0px | Level 0 | **직접배송** | `` |  |  |
| 197 | `REG_MAIL` | 0px | Level 0 | **등기** | `` |  |  |
| 198 | `ZIP` | 0px | Level 0 | **우편** | `` |  |  |
| 199 | `NONE_DV` | 0px | Level 0 | **무배송(e쿠폰)** | `` |  |  |
| 200 | `ETC` | 0px | Level 0 | **기타** | `` |  |  |
| 201 | `owhpNo` | 15px | Level 1 | **** | `string` | 20 | 출고지번호
 거래처 API "(일반 Seller용) 판매자 출고지/반품지 등록"을 통하여 등록된 출고지번호를 입력한다. |
| 202 | `hdcCd` | 15px | Level 1 | **** | `string` | 20 | 택배사코드 [공통코드 : DV_CO_CD]
 *업데이트로 인해 값이 다를 수 있으므로
 공통 메뉴의 [공통코드 상세조회]를 통해 입력 필요. 
 


공통코드값
공통코드명


0001
롯데택배


0003
현대택배


0004
우체국택배


0005
로젠택배


...
...


etc
etc


9999
기타택배 |
| 203 | `0001` | 0px | Level 0 | **롯데택배** | `` |  |  |
| 204 | `0003` | 0px | Level 0 | **현대택배** | `` |  |  |
| 205 | `0004` | 0px | Level 0 | **우체국택배** | `` |  |  |
| 206 | `0005` | 0px | Level 0 | **로젠택배** | `` |  |  |
| 207 | `...` | 0px | Level 0 | **...** | `` |  |  |
| 208 | `etc` | 0px | Level 0 | **etc** | `` |  |  |
| 209 | `9999` | 0px | Level 0 | **기타택배** | `` |  |  |
| 210 | `cstAdtnLst` | 14px | Level 1 | **** | `array` |  | 비용추가목록
 관세/부가세, 배송비/설치비, 현장결제비로 묶어서 이 중 하나를 등록한다.



비용추가유형상세코드
비용추가유형상세명


TX_01
관세


TX_02
부가세


LOGI_01
배송비


LOGI_02
설치비


TRVL_01
현장결제비 |
| 211 | `비용추가유형상세코드` | 0px | Level 0 | **비용추가유형상세명** | `` |  |  |
| 212 | `TX_01` | 0px | Level 0 | **관세** | `` |  |  |
| 213 | `TX_02` | 0px | Level 0 | **부가세** | `` |  |  |
| 214 | `LOGI_01` | 0px | Level 0 | **배송비** | `` |  |  |
| 215 | `LOGI_02` | 0px | Level 0 | **설치비** | `` |  |  |
| 216 | `TRVL_01` | 0px | Level 0 | **현장결제비** | `` |  |  |
| 217 | `cstAdtnTypDtlCd` | 30px | Level 2 | **** | `string` |  | 비용추가유형상세코드 : 위 표 참고. |
| 218 | `cstAdtnTypDtlVal` | 30px | Level 2 | **** | `string` | 1 | 비용추가유형상세값 [Y/N] |
| 219 | `dvCstPolNo` | 15px | Level 1 | **** | `string` | 30 | 배송비정책번호
 거래처의 API를 통해 선등록된 배송비정책번호를 입력한다.
 (신규 배송비 정책 등록 후 약 5분정도 딜레이가 있을 수 있어 신규 배송비 정책에 대해서는 5분 뒤에 연동해야 함.) |
| 220 | `adtnDvCstPolNo` | 15px | Level 1 | **** | `string` | 30 | 추가배송비정책번호
 거래처의 API를 통해 선등록된 추가배송비정책번호를 입력한다.
 (신규 배송비 정책 등록 후 약 5분정도 딜레이가 있을 수 있어 신규 배송비 정책에 대해서는 5분 뒤에 연동해야 함.) |
| 221 | `cmbnDvPsbYn` | 15px | Level 1 | **** | `string` | 1 | 합배송가능여부 [Y, N]
 디폴트:Y |
| 222 | `dvCstStdQty` | 15px | Level 1 | **** | `number` | 10 | 배송비기준수량
 디폴트:0 |
| 223 | `qckDvUseYn` | 15px | Level 1 | **** | `string` | 1 | 퀵배송사용여부 [Y, N]
 디폴트:N
 백화점, 마트, 슈퍼, 하이마트 제외하고 퀵배송여부 Y설정 불가능 |
| 224 | `crdayDvPsbYn` | 15px | Level 1 | **** | `string` | 1 | 당일배송가능여부 [Y, N]
 디폴트:N |
| 225 | `crdayDvInfo` | 15px | Level 1 | **** | `object` | 4000 | 당일배송정보
 당일배송가능여부가 Y인 경우 필수값 |
| 226 | `odCloseTm` | 30px | Level 2 | **** | `string` | 4 | 주문마감시간 [HH24MI ex) 1000]
 당일배송가능여부가 Y인 경우 필수값 |
| 227 | `spicUseYn` | 15px | Level 1 | **** | `string` | 1 | 스마트픽사용여부 [Y, N]
 디폴트:N |
| 228 | `spicInfo` | 15px | Level 1 | **** | `object` |  | 스마트픽정보
 스마트픽사용여부 Y인 경우 필수 |
| 229 | `spicTypCdLst` | 30px | Level 2 | **** | `array` | 4000 | 스마트픽유형코드목록 [공통코드 : SPIC_TYP_CD]
 해당되는 스마트픽유형코드들을 입력한다.



공통코드값
공통코드명


STR
매장픽업


CRSS
내주변픽업


RVS
리버스픽 |
| 230 | `STR` | 0px | Level 0 | **매장픽업** | `` |  |  |
| 231 | `CRSS` | 0px | Level 0 | **내주변픽업** | `` |  |  |
| 232 | `RVS` | 0px | Level 0 | **리버스픽** | `` |  |  |
| 233 | `strPicTypLst` | 30px | Level 2 | **** | `array` | 4000 | 스토어픽유형목록 [엘롯데 전용]
 스마트픽유형에 스토어픽이 있는 경우 필수값 |
| 234 | `trGrpCd` | 45px | Level 3 | **** | `string` | 11 | 거래처그룹코드 [엘롯데 전용] |
| 235 | `trNo` | 45px | Level 3 | **** | `string` | 11 | 거래처번호 [엘롯데 전용] |
| 236 | `lrtrNo` | 45px | Level 3 | **** | `string` | 11 | 하위거래처번호 [엘롯데 전용] |
| 237 | `shopPkupYn` | 45px | Level 3 | **** | `string` | 1 | 매장픽업여부 [엘롯데 전용] |
| 238 | `lckPkupYn` | 45px | Level 3 | **** | `string` | 1 | 락커픽업여부 [엘롯데 전용] |
| 239 | `dskPkupYn` | 45px | Level 3 | **** | `string` | 1 | 데스크픽업여부 [엘롯데 전용] |
| 240 | `spicEusePdYn` | 15px | Level 1 | **** | `string` | 1 | 스마트픽전용상품여부 [Y, N]
 디폴트N |
| 241 | `spicEusePdTypCd` | 15px | Level 1 | **** | `string` | 20 | 스마트픽전용상품유형코드 [공통코드 시트 참고] 스마트픽전용상품여부 Y인 경우 필수 [공통코드 : SPIC_EUSE_PD_TYP_CD]
 


공통코드값
공통코드명


GNRL
일반


RAO_ XCHG
실물교환


SITE_PY
현장결제 |
| 242 | `GNRL` | 0px | Level 0 | **일반** | `` |  |  |
| 243 | `RAO_ XCHG` | 0px | Level 0 | **실물교환** | `` |  |  |
| 244 | `SITE_PY` | 0px | Level 0 | **현장결제** | `` |  |  |
| 245 | `hpDdDvPsbYn` | 15px | Level 1 | **** | `string` | 1 | 희망일배송가능여부 [Y, N]
 디폴트:N |
| 246 | `hpDdDvPsbPrd` | 15px | Level 1 | **** | `number` | 10 | 희망일배송가능기간
 희망일배송가능여부 Y인 경우 필수 |
| 247 | `saveTypCd` | 15px | Level 1 | **** | `string` | 20 | 저장유형코드 [공통코드 : SAVE_TYP_CD]
 디폴트:해당없음
 


공통코드값
공통코드명


RFRG
냉장


FRZN
냉동


FRSH
신선


NONE
해당없음 |
| 248 | `RFRG` | 0px | Level 0 | **냉장** | `` |  |  |
| 249 | `FRZN` | 0px | Level 0 | **냉동** | `` |  |  |
| 250 | `FRSH` | 0px | Level 0 | **신선** | `` |  |  |
| 251 | `NONE` | 0px | Level 0 | **해당없음** | `` |  |  |
| 252 | `shopCnvMsgPsbYn` | 15px | Level 1 | **** | `string` | 1 | [백화점] 매장전달메시지가능여부 [Y, N]
 디폴트:N |
| 253 | `rgnLmtPdYn` | 15px | Level 1 | **** | `string` | 1 | [하이마트] 지역한정상품여부 [Y, N]
 디폴트:N |
| 254 | `fprdDvPsbYn` | 15px | Level 1 | **** | `string` | 1 | [마트, 슈퍼] 정기배송가능여부 [Y, N]
 디폴트:N |
| 255 | `spcfSqncPdYn` | 15px | Level 1 | **** | `string` | 1 | [슈퍼]특정회차상품여부
 디폴트:N |
| 256 | `rtngPsbYn` | 15px | Level 1 | **** | `string` | 1 | 반품가능여부 [Y, N]
 디폴트:Y |
| 257 | `xchgPsbYn` | 15px | Level 1 | **** | `string` | 1 | 교환가능여부 [Y, N]
 디폴트:Y |
| 258 | `cmbnRtngPsbYn` | 15px | Level 1 | **** | `string` | 1 | 합반품가능여부 [Y, N]
 합배송가능여부가 Y인 경우 Y선택 가능. N인 경우 N만 선택 가능 |
| 259 | `rtngHdcCd` | 15px | Level 1 | **** | `string` | 20 | 택배사코드 [공통코드 : DV_CO_CD]
 *업데이트로 인해 값이 다를 수 있으므로
 공통 메뉴의 [공통코드 상세조회]를 통해 입력 필요. 
 


공통코드값
공통코드명


0001
롯데택배


0002
CJ대한통운


0003
현대택배


0004
우체국택배


0005
로젠택배


0006
한진택배


0014
GTX 로지스 택배


0016
KGB택배


0023
건영택배


0024
경동택배


0025
고려택배


0027
대신정기화물택배


0028
대신택배


0031
드림택배


0037
엘로우캡택배


0040
이노지스택배


0042
일양택배


0043
천일택배


0044
편의점택배


0046
하나로택배


0048
한의사랑택배


0049
합동택배


0050
호남택배


etc
etc


9999
기타택배 |
| 260 | `0001` | 0px | Level 0 | **롯데택배** | `` |  |  |
| 261 | `0002` | 0px | Level 0 | **CJ대한통운** | `` |  |  |
| 262 | `0003` | 0px | Level 0 | **현대택배** | `` |  |  |
| 263 | `0004` | 0px | Level 0 | **우체국택배** | `` |  |  |
| 264 | `0005` | 0px | Level 0 | **로젠택배** | `` |  |  |
| 265 | `0006` | 0px | Level 0 | **한진택배** | `` |  |  |
| 266 | `0014` | 0px | Level 0 | **GTX 로지스 택배** | `` |  |  |
| 267 | `0016` | 0px | Level 0 | **KGB택배** | `` |  |  |
| 268 | `0023` | 0px | Level 0 | **건영택배** | `` |  |  |
| 269 | `0024` | 0px | Level 0 | **경동택배** | `` |  |  |
| 270 | `0025` | 0px | Level 0 | **고려택배** | `` |  |  |
| 271 | `0027` | 0px | Level 0 | **대신정기화물택배** | `` |  |  |
| 272 | `0028` | 0px | Level 0 | **대신택배** | `` |  |  |
| 273 | `0031` | 0px | Level 0 | **드림택배** | `` |  |  |
| 274 | `0037` | 0px | Level 0 | **엘로우캡택배** | `` |  |  |
| 275 | `0040` | 0px | Level 0 | **이노지스택배** | `` |  |  |
| 276 | `0042` | 0px | Level 0 | **일양택배** | `` |  |  |
| 277 | `0043` | 0px | Level 0 | **천일택배** | `` |  |  |
| 278 | `0044` | 0px | Level 0 | **편의점택배** | `` |  |  |
| 279 | `0046` | 0px | Level 0 | **하나로택배** | `` |  |  |
| 280 | `0048` | 0px | Level 0 | **한의사랑택배** | `` |  |  |
| 281 | `0049` | 0px | Level 0 | **합동택배** | `` |  |  |
| 282 | `0050` | 0px | Level 0 | **호남택배** | `` |  |  |
| 283 | `etc` | 0px | Level 0 | **etc** | `` |  |  |
| 284 | `9999` | 0px | Level 0 | **기타택배** | `` |  |  |
| 285 | `rtngRtrvPsbYn` | 15px | Level 1 | **** | `string` | 1 | 반품회수가능여부 [Y, N]
 디폴트:Y |
| 286 | `rtrpNo` | 15px | Level 1 | **** | `string` | 20 | 회수지번호
거래처 API "(일반 Seller용) 판매자 출고지/반품지 등록"을 통하여 등록된 회수지번호를 입력한다. |
| 287 | `ecpnInfo` | 15px | Level 1 | **** | `object` | 4000 | e쿠폰정보
 해당 상품이 e쿠폰인 경우에만 입력한다. |
| 288 | `fbilPrc` | 30px | Level 2 | **** | `number` | 22 | 권면가 |
| 289 | `rtngPsbDvsCd` | 30px | Level 2 | **** | `string` | 20 | 반품가능구분코드 [공통코드 : RTNG_PSB_DVS_CD]
 


공통코드값
공통코드명


WTHN_PRD
사용기간내


EXCD
주문일+7일


ELPS__PRD
사용기간경과 |
| 290 | `WTHN_PRD` | 0px | Level 0 | **사용기간내** | `` |  |  |
| 291 | `EXCD` | 0px | Level 0 | **주문일+7일** | `` |  |  |
| 292 | `ELPS__PRD` | 0px | Level 0 | **사용기간경과** | `` |  |  |
| 293 | `rfndPsbYn` | 30px | Level 2 | **** | `string` | 1 | 환불가능여부 [Y, N]
 디폴트 : Y |
| 294 | `ecpnRfndTypCd` | 30px | Level 2 | **** | `string` | 20 | e쿠폰환불유형코드 [공통코드 : ECPN_RFND_TYP_CD]
 


공통코드값
공통코드명


90
일반_90%, 공통코드 추가속성 - 환불정산율(90%)


100
일반_전액, 공통코드 추가속성 - 환불정산율(100%)


50
특가_50%, 공통코드 추가속성 - 환불정산율(50%)


70
특가_70%, 공통코드 추가속성 - 환불정산율(70%) |
| 295 | `90` | 0px | Level 0 | **일반_90%, 공통코드 추가속성 - 환불정산율(90%)** | `` |  |  |
| 296 | `100` | 0px | Level 0 | **일반_전액, 공통코드 추가속성 - 환불정산율(100%)** | `` |  |  |
| 297 | `50` | 0px | Level 0 | **특가_50%, 공통코드 추가속성 - 환불정산율(50%)** | `` |  |  |
| 298 | `70` | 0px | Level 0 | **특가_70%, 공통코드 추가속성 - 환불정산율(70%)** | `` |  |  |
| 299 | `autoRfndYn` | 30px | Level 2 | **** | `string` | 1 | 자동환불여부 [Y, N] |
| 300 | `useLmtEpn` | 30px | Level 2 | **** | `string` | 4000 | 사용제한설명 |
| 301 | `atntMatrEpn` | 30px | Level 2 | **** | `string` | 4000 | 주의사항설명 |
| 302 | `usePlcEpn` | 30px | Level 2 | **** | `string` | 4000 | 사용장소설명 |
| 303 | `rntlPdInfo` | 15px | Level 1 | **** | `object` | 4000 | 렌탈상품정보
 상품유형이 렌탈일 경우 필수값 |
| 304 | `dutyUsePrd` | 30px | Level 2 | **** | `number` | 22 | 의무사용기간 |
| 305 | `instCst` | 30px | Level 2 | **** | `number` | 22 | 설치비용 |
| 306 | `regCst` | 30px | Level 2 | **** | `number` | 22 | 등록비용 |
| 307 | `cnsmrSlPrc` | 30px | Level 2 | **** | `number` | 22 | 소비자판매가 |
| 308 | `mmRntlCst` | 30px | Level 2 | **** | `number` | 22 | 월렌탈비용 |
| 309 | `vatInclYn` | 30px | Level 2 | **** | `string` | 1 | 부가세포함여부 [Y, N]
 디폴트 : Y |
| 310 | `opngPdInfo` | 15px | Level 1 | **** | `object` |  | 개통형상품정보
 상품유형구분코드가 일반판매_0원상품(GNRL_ZRWON)에 해당하는 개통형상품인 경우 필수입력한다. |
| 311 | `mvCmcoCd` | 30px | Level 2 | **** | `string` | 20 | 이동통신사코드 [공통코드 : MV_CMCO_CD]
 


공통코드값
공통코드명


SKT
SKT


KT
KT


LGT
LGT


CJH
CJ헬로비전


S1
에스원


MLG
미디어로그


KTM
KTM모바일


SKLINK
SK텔링크


RFRBSH
리퍼비쉬


PNPLAY
핀플레이


SLF_SFC
자급제폰 |
| 312 | `SKT` | 0px | Level 0 | **SKT** | `` |  |  |
| 313 | `KT` | 0px | Level 0 | **KT** | `` |  |  |
| 314 | `LGT` | 0px | Level 0 | **LGT** | `` |  |  |
| 315 | `CJH` | 0px | Level 0 | **CJ헬로비전** | `` |  |  |
| 316 | `S1` | 0px | Level 0 | **에스원** | `` |  |  |
| 317 | `MLG` | 0px | Level 0 | **미디어로그** | `` |  |  |
| 318 | `KTM` | 0px | Level 0 | **KTM모바일** | `` |  |  |
| 319 | `SKLINK` | 0px | Level 0 | **SK텔링크** | `` |  |  |
| 320 | `RFRBSH` | 0px | Level 0 | **리퍼비쉬** | `` |  |  |
| 321 | `PNPLAY` | 0px | Level 0 | **핀플레이** | `` |  |  |
| 322 | `SLF_SFC` | 0px | Level 0 | **자급제폰** | `` |  |  |
| 323 | `owhPrc` | 30px | Level 2 | **** | `number` | 22 | 출고가 |
| 324 | `joinAplUrl` | 30px | Level 2 | **** | `string` | 200 | 가입신청서 URL |
| 325 | `sptAmt` | 30px | Level 2 | **** | `number` | 22 | 지원금액 |
| 326 | `adtnSptAmt` | 30px | Level 2 | **** | `number` | 22 | 추가지원금액 |
| 327 | `stkMgtYn` | 15px | Level 1 | **** | `string` | 1 | 재고관리여부 [Y, N] [마트, 슈퍼 제외]
 마트, 슈퍼는 점표별 관리 API를 사용한다.
 'N'인 경우 재고가 999,999,999로 들어간다. 웹재고를 관리하지 않는다.
 Y->N 수정만 가능한다.
 N->Y 수정은 불가하다. |
| 328 | `thdyPdYn` | 14px | Level 1 | **** | `string` | 1 | 명절상품여부 [Y, N]
 Y이고 [마트]일 경우 명절배송처리유형코드를 설정해야 한다. |
| 329 | `thdyDvProcTypCd` | 14px | Level 1 | **△** | `string` | 20 | [마트] 명절배송처리유형코드 [공통코드 : THDY_DV_PROC_TYP_CD]
 명절상품여부 Y이고 마트일 경우 필수값
 


공통코드값
공통코드명


LM_SHOP
명절근거리


LM_DRECT_DPCL
명절 근거리 + 명절택배


LM_SHOP_DPCL
명절택배


LM_ENTP_DPCL
명절업체배송


LM_SHOP_RFRG
명절냉장배송


LM_SHOP_FRZN
명절냉동배송 |
| 330 | `LM_SHOP` | 0px | Level 0 | **명절근거리** | `` |  |  |
| 331 | `LM_DRECT_DPCL` | 0px | Level 0 | **명절 근거리 + 명절택배** | `` |  |  |
| 332 | `LM_SHOP_DPCL` | 0px | Level 0 | **명절택배** | `` |  |  |
| 333 | `LM_ENTP_DPCL` | 0px | Level 0 | **명절업체배송** | `` |  |  |
| 334 | `LM_SHOP_RFRG` | 0px | Level 0 | **명절냉장배송** | `` |  |  |
| 335 | `LM_SHOP_FRZN` | 0px | Level 0 | **명절냉동배송** | `` |  |  |
| 336 | `itmLst` | 15px | Level 1 | **** | `array` |  | 단품목록 |
| 337 | `eitmNo` | 30px | Level 2 | **** | `string` | 30 | 업체단품번호 |
| 338 | `sitmNo` | 30px | Level 2 | **** | `string` | 30 | 판매자단품번호 |
| 339 | `rprtSitmYn` | 30px | Level 2 | **** | `string` | 1 | 대표단품여부 [Y, N]
 - 전체단품 중 1개 설정 가능. |
| 340 | `sortSeq` | 30px | Level 2 | **** | `number` | 10 | 정렬순번 (Front에 노출되는 정렬되는 조건은 아니며 Front 노출 순서 조정 필요 할 경우 optSrtLst 필드로 등록해야 함) |
| 341 | `itmOptLst` | 30px | Level 2 | **** | `array` |  | 단품속성목록
 단품추가시에만 사용하는 항목이다.
 기존 등록된 단품의 옵션,옵션값은 수정이 불가하다. |
| 342 | `optCd` | 45px | Level 3 | **** | `string` | 20 | 옵션코드 [속성모듈 제공 항목]
 기존에 등록된 단품의 옵션명에 해당하는 옵션코드를 입력하여야 한다.
 이관된 상품의 단품 옵션코드가 null인 경우에만 null이 허용된다. |
| 343 | `optNm` | 45px | Level 3 | **** | `string` | 200 | 옵션명 [속성모듈 제공 항목]
 기존에 등록된 단품의 옵션명만 입력가능하다. |
| 344 | `optValCd` | 45px | Level 3 | **** | `string` | 20 | 옵션값코드 [속성모듈 제공 항목]
 입력하고자 하는 옵션값의 옵션값코드가 존재하지 않는 경우에는 옵션값만 입력한다. |
| 345 | `optVal` | 45px | Level 3 | **** | `string` | 4000 | 옵션값 [속성모듈 제공 항목]
 해당 단품의 옵션값을 입력한다. |
| 346 | `dtlsVal` | 45px | Level 3 | **** | `string` | 4000 | 세부값
 세부값을 입력하는 경우
 1. 범위값에 대한 고정값 입력시
 2. 옵션값에 대한 추가 표현 |
| 347 | `itmImgLst` | 30px | Level 2 | **** | `array` |  | 단품이미지목록
 단품당 하나 이상의 이미지를 등록하여야 한다.
 단품당 최대 10개의 이미지를 등록할 수 있다. |
| 348 | `epsrTypCd` | 45px | Level 3 | **** | `string` | 20 | 노출유형코드 [공통코드 : EPSR_TYP_CD]
 


공통코드값
공통코드명


IMG
이미지 |
| 349 | `IMG` | 0px | Level 0 | **이미지** | `` |  |  |
| 350 | `epsrTypDtlCd` | 45px | Level 3 | **** | `string` | 20 | 노출유형상세코드 [공통코드 : EPSR_TYP_DTL_CD]
 


공통코드값
공통코드명


IMG_SQRE
노출유형:이미지 > 정사각형


IMG_LNTH
노출유형:이미지 > 세로형 |
| 351 | `IMG_SQRE` | 0px | Level 0 | **노출유형:이미지 > 정사각형** | `` |  |  |
| 352 | `IMG_LNTH` | 0px | Level 0 | **노출유형:이미지 > 세로형** | `` |  |  |
| 353 | `origImgFileNm` | 45px | Level 3 | **** | `string` | 200 | 원본이미지파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) http://abc.com/12/34/56/78_90.jpg
 (등록가능한 확장자 : jpg, jpeg, png)
 (기존에 등록된 URL과 동일하지만 이미지만 변경 되었을 경우 URL이 변경되어야 정상 반영 될 수 있음. URL에 뒤에 쿼리스트링을 추가하거나 URL 경로 자체가 변경 되야 함.
 Ex. http://abc.com/12/34/56/78_90.jpg?t=20220316) |
| 354 | `rprtImgYn` | 45px | Level 3 | **** | `string` | 1 | 대표이미지여부 [Y, N]
 대표이미지는 단품별 하나만 설정 가능 |
| 355 | `clrchipLst` | 30px | Level 2 | **** | `array` |  | 컬러칩이미지목록
 단품당 1개 등록 가능 리스트 중 첫번째 등록된 파일로 반영된다. |
| 356 | `origImgFileNm` | 45px | Level 3 | **** | `string` | 200 | 원본이미지파일명(경로명)
 파일명을 포함한 다운로드가 가능한 경로를 입력한다.
 ex) http://abc.com/12/34/56/78_90.jpg
 (기존에 등록된 URL과 동일하지만 이미지만 변경 되었을 경우 URL이 변경되어야 정상 반영 될 수 있음. URL에 뒤에 쿼리스트링을 추가하거나 URL 경로 자체가 변경 되야 함.
 Ex. http://abc.com/12/34/56/78_90.jpg?t=20220316) |
| 357 | `pdUtStdInfo` | 30px | Level 2 | **** | `object` | 4000 | 상품단위기준정보 |
| 358 | `pdCapa` | 45px | Level 3 | **** | `number` | 10 | 상품총용량
 기준단위와 기준용량은 표준카테고리 매핑 정보를 따른다.
 ex) 표준카테고리에 기준단위가 ml, 기준용량이 100으로 매핑되어 있는 경우 100ml당 가격이 표시된다. |
| 359 | `stdUtCd` | 45px | Level 3 | **** | `number` | 10 | 기준단위
 상품용량에 대한 기준 단위. 표준카테고리 매핑 정보에 설정된 대표값 또는 추가값을 입력할 수 있다. |
| 360 | `stdCapa` | 45px | Level 3 | **** | `number` | 10 | 기준용량
 표준카테고리 매핑에 설정된 기준단위별 용량을 입력한다. |
| 361 | `slPrc` | 30px | Level 2 | **** | `number` | 22 | 판매가 |
| 362 | `stkQty` | 30px | Level 2 | **** | `number` | 10 | 재고수량
 재고관리여부가 Y인 경우에는 필수값 |
| 363 | `optSrtLst` | 15px | Level 1 | **** | `array` | 5 | 옵션정렬목록
 단품에 적용된 옵션코드의 순서와 해당 옵션코드의 값코드 순서를 지정한다. |
| 364 | `optSeq` | 30px | Level 2 | **O** | `number` | 1 | 옵션순번 |
| 365 | `optNm` | 30px | Level 2 | **O** | `string` | 200 | 옵션명 |
| 366 | `optCd` | 30px | Level 2 | **△** | `string` | 20 | 옵션코드
 단품옵션에 옵션코드를 입력한 경우 필수 |
| 367 | `optValSrtLst` | 30px | Level 2 | **O** | `array` | 500 | 옵션값순번목록 |
| 368 | `optValSeq` | 45px | Level 3 | **O** | `number` | 1 | 옵션값순번 |
| 369 | `optVal` | 45px | Level 3 | **O** | `string` |  | 옵션값 |
| 370 | `optValCd` | 45px | Level 3 | **△** | `string` | 20 | 옵션값코드
 단품옵션에 옵션값코드를 입력한 경우 필수 |
| 371 | `dtlsVal` | 45px | Level 3 | **△** | `string` |  | 세부값
 단품옵션에 세부값을 입력한 경우 필수 |
| 372 | `slrRcPdLst` | 15px | Level 1 | **** | `array` | 4000 | 셀러추천상품목록
 최대 10개까지 등록 가능하다. |
| 373 | `slrRcSpdNo` | 30px | Level 2 | **** | `string` | 30 | 셀러추천판매자상품번호 |
| 374 | `slrRcSitmNo` | 30px | Level 2 | **** | `string` | 30 | 셀러추천판매자단품번호 |
| 375 | `epsrPrirRnkg` | 30px | Level 2 | **** | `number` | 3 | 노출우선순위 |
| 376 | `adtnPdYn` | 14px | Level 1 | **** | `string` | 1 | 추가상품사용여부 [Y, N]
 디폴트:N |
| 377 | `adtnPdInfo` | 14px | Level 1 | **** | `Object` |  | 추가상품정보 |
| 378 | `sortCd` | 30px | Level 2 | **** | `string` | 20 | 추가상품정렬코드 [공통코드 : ADTN_PD_SORT_CD]
 


공통코드값
공통코드명


REGIST_ASC
등록순


NAME_ASC
가나다순


PRICE_ASC
낮은가격순


PRICE_DESC
높은가격순 |
| 379 | `REGIST_ASC` | 0px | Level 0 | **등록순** | `` |  |  |
| 380 | `NAME_ASC` | 0px | Level 0 | **가나다순** | `` |  |  |
| 381 | `PRICE_ASC` | 0px | Level 0 | **낮은가격순** | `` |  |  |
| 382 | `PRICE_DESC` | 0px | Level 0 | **높은가격순** | `` |  |  |
| 383 | `adtnTypeLst` | 30px | Level 2 | **O** | `Array` | 10 | 추가유형목록 |
| 384 | `adtnTypNo` | 44px | Level 3 | **O** | `number` | 30 | 추가유형번호 |
| 385 | `adtnTypNm` | 44px | Level 3 | **** | `string` | 100 | 추가유형명 |
| 386 | `epsrPrirRnkg` | 44px | Level 3 | **** | `number` | 3 | 노출우선순위 |
| 387 | `delYn` | 44px | Level 3 | **** | `string` | 1 | 삭제여부 [Y, N]
 디폴트:N |
| 388 | `adtnPdLst` | 44px | Level 3 | **** | `Array` | 10 | 추가상품목록 |
| 389 | `adtnPdNo` | 60px | Level 4 | **O** | `number` | 30 | 추가상품번호 |
| 390 | `adtnPdNm` | 60px | Level 4 | **** | `string` | 100 | 추가상품명 |
| 391 | `epdNo` | 60px | Level 4 | **** | `String` | 30 | 업체상품번호 |
| 392 | `epsrPrirRnkg` | 60px | Level 4 | **** | `number` | 3 | 노출우선순위 |
| 393 | `slPrc` | 60px | Level 4 | **** | `number` | 10 | 판매가 |
| 394 | `stkQty` | 60px | Level 4 | **** | `number` | 10 | 재고수량 |
| 395 | `useYn` | 60px | Level 4 | **** | `number` | 1 | 사용여부 [Y, N] |
| 396 | `delYn` | 60px | Level 4 | **** | `string` | 1 | 삭제여부 [Y, N]
 디폴트:N |
| 397 | `rtrvTypCd` | 30px | Level 2 | **X** | `string` | 20 | 회수유형코드
 계약유형이 중개일 경우에만 해당.
 


공통코드값
공통코드명


ENTP_RTRV
업체회수


DGNN_RTRV
자동회수 |
| 398 | `ENTP_RTRV` | 0px | Level 0 | **업체회수** | `` |  |  |
| 399 | `DGNN_RTRV` | 0px | Level 0 | **자동회수** | `` |  |  |
