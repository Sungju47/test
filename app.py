import os, ast, requests
from io import BytesIO
from typing import List
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from PIL import Image
st.set_page_config(page_title="ARAM PS Dashboard", layout="wide")
# ------------------------------------------------------------------
# Data-Dragon 이미지 helpers
# ------------------------------------------------------------------
DDRAGON_VERSION = "14.1.1"            # 리그 패치 버전에 맞춰 갱신
_CHAMP_FIX = {
    "Aurelion Sol":"AurelionSol","Cho'Gath":"Chogath","Dr. Mundo":"DrMundo",
    "Jarvan IV":"JarvanIV","Kai'Sa":"Kaisa","Kha'Zix":"Khazix","Kog'Maw":"KogMaw",
    "LeBlanc":"Leblanc","Lee Sin":"LeeSin","Master Yi":"MasterYi",
    "Miss Fortune":"MissFortune","Nunu & Willump":"Nunu","Rek'Sai":"RekSai",
    "Renata Glasc":"Renata","Tahm Kench":"TahmKench","Twisted Fate":"TwistedFate",
    "Vel'Koz":"Velkoz","Wukong":"MonkeyKing","Xin Zhao":"XinZhao"
}
@st.cache_data(show_spinner=False)
def champion_icon_url(name:str)->str:
    n=_CHAMP_FIX.get(name, name.replace(" ","").replace("'",""))
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{n}.png"
_ITEM_ID={
    "Infinity Edge":"3031","Rabadon's Deathcap":"3089","Void Staff":"3135",
    "Zhonya's Hourglass":"3157","Kraken Slayer":"6672","Galeforce":"6671",
    "Berserker's Greaves":"3006","Ionian Boots of Lucidity":"3158",
    "Plated Steelcaps":"3047","Mercury's Treads":"3111","Boots of Swiftness":"3009",
    "Health Potion":"2003","Control Ward":"2055","Doran's Blade":"1055",
    "Doran's Ring":"1056","Doran's Shield":"1054",
}
def item_icon_url(item:str)->str:
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/item/{_ITEM_ID.get(item,'1001')}.png"
_SPELL_KEY={
    "Flash":"SummonerFlash","Ignite":"SummonerDot","Heal":"SummonerHeal",
    "Barrier":"SummonerBarrier","Exhaust":"SummonerExhaust","Teleport":"SummonerTeleport",
    "Ghost":"SummonerHaste","Cleanse":"SummonerBoost","Smite":"SummonerSmite",
    "Mark":"SummonerSnowball","Snowball":"SummonerSnowball","Clarity":"SummonerMana"
}
def spell_icon_url(spell:str)->str:
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/spell/{_SPELL_KEY.get(spell.strip(),'SummonerFlash')}.png"
@st.cache_data(show_spinner=False)
def load_image(url:str)->Image.Image|None:
    try:
        return Image.open(BytesIO(requests.get(url,timeout=5).content))
    except: return None
# ------------------------------------------------------------------
# CSV 로더
# ------------------------------------------------------------------
CSV_CANDIDATES=[
    "aram_participants_with_full_runes_merged_plus.csv",
    "aram_participants_with_full_runes_merged.csv",
    "aram_participants_with_full_runes.csv",
    "aram_participants_clean_preprocessed.csv",
    "aram_participants_clean_no_dupe_items.csv",
    "aram_participants_with_items.csv",
]
def _discover_csv():
    for f in CSV_CANDIDATES:
        if os.path.exists(f): return f
    return None
def _yes(x): return 1 if str(x).strip().lower() in ("1","true","t","yes") else 0
def _as_list(s):
    if isinstance(s,list): return s
    if not isinstance(s,str) or not s.strip(): return []
    try:
        v=ast.literal_eval(s);
        if isinstance(v,list): return v
    except: pass
    spl="|" if "|" in s else "," if "," in s else None
    return [t.strip() for t in s.split(spl)] if spl else [s]
@st.cache_data(show_spinner=False)
def load_df(buf)->pd.DataFrame:
    df=pd.read_csv(buf)
    df["win_clean"]=df.get("win",0).apply(_yes)
    s1="spell1_name" if "spell1_name" in df else "spell1"
    s2="spell2_name" if "spell2_name" in df else "spell2"
    df["spell_combo"]=(df[s1].astype(str)+" + "+df[s2].astype(str)).str.strip()
    for c in [c for c in df if c.startswith("item")]:
        df[c]=df[c].fillna("").astype(str).str.strip()
    for col in ("team_champs","enemy_champs"):
        if col in df: df[col]=df[col].apply(_as_list)
    df["duration_min"]=pd.to_numeric(df.get("game_end_min"),errors="coerce").fillna(18).clip(6,40)
    df["dpm"]=df.get("damage_total",np.nan)/df["duration_min"].replace(0,np.nan)
    for k in ("kills","deaths","assists"): df[k]=df.get(k,0)
    df["kda"]=(df["kills"]+df["assists"])/df["deaths"].replace(0,np.nan)
    df["kda"]=df["kda"].fillna(df["kills"]+df["assists"])
    return df
# ------------------------------------------------------------------
# 사이드바
# ------------------------------------------------------------------
st.sidebar.header(":gear:  설정")
auto=_discover_csv()
st.sidebar.write(":mag: 자동 검색:", auto if auto else "없음")
up=st.sidebar.file_uploader("CSV 업로드(선택)", type="csv")
df=load_df(up) if up else load_df(auto) if auto else None
if df is None:
    st.error("CSV 파일이 없습니다."); st.stop()
champions=sorted(df["champion"].dropna().unique())
sel=st.sidebar.selectbox(":dart: 챔피언 선택", champions)
# ------------------------------------------------------------------
# 헤더 & 메트릭
# ------------------------------------------------------------------
dfc=df[df["champion"]==sel]
total=df["matchId"].nunique() if "matchId" in df else len(df)
games=len(dfc)
wr=round(dfc["win_clean"].mean()*100,2) if games else 0
pr=round(games/total*100,2) if total else 0
avg_k,avg_d,avg_a=[round(dfc[c].mean(),2) for c in ("kills","deaths","assists")]
avg_dpm=round(dfc["dpm"].mean(),1)
st.title(":trophy: ARAM Analytics")
ic=load_image(champion_icon_url(sel))
mid=st.columns([2,3,2])[1]
with mid:
    if ic: st.image(ic, width=100)
    st.subheader(sel, divider=False)
m1,m2,m3,m4,m5=st.columns(5)
m1.metric("게임 수", games)
m2.metric("승률", f"{wr}%")
m3.metric("픽률", f"{pr}%")
m4.metric("평균 K/D/A", f"{avg_k}/{avg_d}/{avg_a}")
m5.metric("평균 DPM", avg_dpm)
# ------------------------------------------------------------------
tab1,tab2,tab3,tab4=st.tabs([":bar_chart: 게임 분석",":crossed_swords: 아이템 & 스펠",":stopwatch: 타임라인",":clipboard: 상세 데이터"])
with tab1:
    if "first_blood_min" in dfc and dfc["first_blood_min"].notna().any():
        st.metric("퍼블 평균 분", round(dfc["first_blood_min"].mean(),2))
    if "game_end_min" in dfc:
        st.metric("평균 게임 시간", round(dfc["game_end_min"].mean(),2))
with tab2:
    left,right=st.columns(2)
    # 아이템
    with left:
        st.subheader(":shield: 아이템 성과")
        item_cols=[c for c in dfc if c.startswith("item")]
        rec=pd.concat([dfc[["matchId","win_clean",c]].rename(columns={c:"item"}) for c in item_cols])
        g=(rec[rec["item"]!=""]
           .groupby("item").agg(total=("matchId","count"), wins=("win_clean","sum"))
           .assign(win_rate=lambda d:(d.wins/d.total*100).round(2))
           .sort_values(["total","win_rate"],ascending=[False,False]).head(10).reset_index())
        for _,r in g.iterrows():
            c_icon,c_name,c_pick,c_wr=st.columns([1,4,2,2])
            with c_icon: st.image(item_icon_url(str(r.item)), width=32)
            with c_name: st.write(str(r.item))                  # ← str() 캐스팅
            with c_pick: st.write(f"{int(r.total)} 게임")
            with c_wr:   st.write(f"{r.win_rate}%")
            st.divider()
    # 스펠
    with right:
        st.subheader(":sparkles: 스펠 조합")
        sp=(dfc.groupby("spell_combo")
             .agg(games=("matchId","count"), wins=("win_clean","sum"))
             .assign(win_rate=lambda d:(d.wins/d.games*100).round(2))
             .sort_values(["games","win_rate"],ascending=[False,False]).head(8).reset_index())
        for _,r in sp.iterrows():
            s1,s2=[s.strip() for s in str(r.spell_combo).split("+")]
            col_i,col_n,col_v=st.columns([2,3,2])
            with col_i:
                st.image(spell_icon_url(s1), width=28)
                st.image(spell_icon_url(s2), width=28)
            with col_n: st.write(str(r.spell_combo))
            with col_v: st.write(f"{r.win_rate}%\n{int(r.games)}G")
            st.divider()
with tab3:
    if "first_core_item_min" in dfc and dfc["first_core_item_min"].notna().any():
        st.metric("1코어 평균 분", round(dfc["first_core_item_min"].mean(),2))
        fig=px.histogram(dfc,x="first_core_item_min",nbins=24,title="1코어 시점")
        fig.update_layout(plot_bgcolor="#1E2328",paper_bgcolor="#1E2328",font_color="#F0E6D2")
        st.plotly_chart(fig, use_container_width=True)
with tab4:
    st.dataframe(dfc.drop(columns=["team_champs","enemy_champs"],errors="ignore"),
                 use_container_width=True)
st.caption(f"Data-Dragon v{DDRAGON_VERSION} · {len(champions)}챔프 · {total}경기")
