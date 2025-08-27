import os, ast, requests, unicodedata
from io import BytesIO
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from PIL import Image

st.set_page_config(page_title="ARAM PS Dashboard", layout="wide")

# ---------------------------
# Data Dragon
# ---------------------------
@st.cache_data(ttl=86400)
def get_latest_dd_version() -> str:
    return requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5).json()[0]

@st.cache_data(ttl=86400)
def load_dd_data(dd_version: str):
    # 챔피언
    champs = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{dd_version}/data/en_US/champion.json", timeout=5).json()["data"]
    champ_name2file = {c["name"]: c["id"] + ".png" for c in champs.values()}
    champ_alias = {"".join(c for c in unicodedata.normalize("NFKD", c["name"]) if c.isalnum()).lower(): c["id"] + ".png" for c in champs.values()}

    # 아이템
    items = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{dd_version}/data/en_US/item.json", timeout=5).json()["data"]
    item_name2id = {v["name"]: k for k, v in items.items()}

    # 스펠
    spells = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{dd_version}/data/en_US/summoner.json", timeout=5).json()["data"]
    spell_name2key = {v["name"]: v["id"] for v in spells.values()}

    return {
        "champ_name2file": champ_name2file,
        "champ_alias": champ_alias,
        "item_name2id": item_name2id,
        "spell_name2key": spell_name2key
    }

DD_VERSION = get_latest_dd_version()
DD = load_dd_data(DD_VERSION)

def champion_icon_url(name: str) -> str:
    key = DD["champ_name2file"].get(name)
    if not key:
        norm_name = "".join(c for c in unicodedata.normalize("NFKD", name) if c.isalnum()).lower()
        key = DD["champ_alias"].get(norm_name)
    if not key:
        key = "".join(word.capitalize() for word in name.replace("'", "").split()) + ".png"
    return f"https://ddragon.leagueoflegends.com/cdn/{DD_VERSION}/img/champion/{key}"

def item_icon_url(item: str) -> str:
    iid = DD["item_name2id"].get(item)
    if not iid:
        iid = "1001"  # 기본 아이템 fallback
    return f"https://ddragon.leagueoflegends.com/cdn/{DD_VERSION}/img/item/{iid}.png"

def spell_icon_url(spell: str) -> str:
    key = DD["spell_name2key"].get(spell.strip())
    if not key:
        key = "SummonerFlash"
    return f"https://ddragon.leagueoflegends.com/cdn/{DD_VERSION}/img/spell/{key}.png"

# ---------------------------
# CSV 로드
# ---------------------------
CSV_CANDIDATES = [
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
    try: v = ast.literal_eval(s); return v if isinstance(v,list) else [s]
    except: return [s]

@st.cache_data
def load_df(buf):
    df = pd.read_csv(buf)
    df["win_clean"] = df.get("win",0).apply(_yes)
    df["duration_min"] = pd.to_numeric(df.get("game_end_min"), errors="coerce").fillna(18).clip(6,40)
    df["dpm"] = df.get("damage_total", np.nan)/df["duration_min"].replace(0,np.nan)
    for k in ("kills","deaths","assists"): df[k]=df.get(k,0)
    df["kda"] = (df["kills"]+df["assists"])/df["deaths"].replace(0,np.nan)
    df["kda"] = df["kda"].fillna(df["kills"]+df["assists"])
    # spell_combo
    s1,s2 = "spell1_name" if "spell1_name" in df else "spell1", "spell2_name" if "spell2_name" in df else "spell2"
    df["spell_combo"] = df[s1].astype(str) + " + " + df[s2].astype(str)
    return df

# ---------------------------
# Streamlit UI
# ---------------------------
st.sidebar.header(":gear: 설정")
auto_path = _discover_csv()
uploaded = st.sidebar.file_uploader("CSV 업로드(선택)", type="csv")
df = load_df(uploaded) if uploaded else (load_df(auto_path) if auto_path else None)
if df is None: st.error("CSV 없음"); st.stop()

champions = sorted(df["champion"].dropna().unique())
sel = st.sidebar.selectbox(":dart: 챔피언 선택", champions)
dfc = df[df["champion"]==sel]

# ---------------------------
# 추천 아이템 / 스펠 (1개씩)
# ---------------------------
item_cols = [c for c in dfc if c.startswith("item")]
rec = pd.concat([dfc[["matchId","win_clean",c]].rename(columns={c:"item"}) for c in item_cols])
rec = rec[rec["item"]!=""]
item_stats = rec.groupby("item").agg(total=("matchId","count"), wins=("win_clean","sum")).assign(win_rate=lambda d:(d.wins/d.total*100).round(2))
top_item = item_stats.sort_values(["total","win_rate"], ascending=[False,False]).iloc[0]

spell_stats = dfc.groupby("spell_combo").agg(total=("matchId","count"), wins=("win_clean","sum")).assign(win_rate=lambda d:(d.wins/d.total*100).round(2))
top_spell = spell_stats.sort_values(["total","win_rate"], ascending=[False,False]).iloc[0]
s1,s2 = [s.strip() for s in top_spell.name.split("+")]

# ---------------------------
# Streamlit 레이아웃
# ---------------------------
st.title(f"ARAM Dashboard — {sel}")

c1,c2 = st.columns(2)
with c1:
    st.subheader("추천 아이템")
    st.image(item_icon_url(top_item.name), width=64)
    st.caption(f"{top_item.name} — {top_item.win_rate}% 승률, {top_item.total}게임")
with c2:
    st.subheader("추천 스펠 조합")
    st.image(spell_icon_url(s1), width=48)
    st.image(spell_icon_url(s2), width=48)
    st.caption(f"{top_spell.name} — {top_spell.win_rate}% 승률, {top_spell.total}게임")
