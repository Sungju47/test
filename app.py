import os, pandas as pd, numpy as np, streamlit as st
from io import BytesIO
import requests, re, unicodedata
import plotly.express as px

st.set_page_config(page_title="ARAM Dashboard", layout="wide")

# -------------------- Data Dragon 헬퍼 --------------------
@st.cache_data(show_spinner=False, ttl=86400)
def ddragon_version():
    return requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5).json()[0]

@st.cache_data(show_spinner=False, ttl=86400)
def load_dd_maps(ver:str):
    champs = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json", timeout=5).json()["data"]
    def norm(s): return unicodedata.normalize("NFKD", s).replace(" ", "").replace("'", "").replace(".", "").replace("&","").replace(":","")
    champ_name2file = { c["name"]: c["id"]+".png" for c in champs.values() }
    champ_alias = { norm(c["name"]).lower(): c["id"]+".png" for c in champs.values() }
    
    items = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/item.json", timeout=5).json()["data"]
    item_name2id = { v["name"]: k for k,v in items.items() }
    
    spells = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/summoner.json", timeout=5).json()["data"]
    spell_name2key = { v["name"]: v["id"] for v in spells.values() }
    
    return {"champ_name2file": champ_name2file, "champ_alias": champ_alias,
            "item_name2id": item_name2id, "spell_name2key": spell_name2key}

DDRAGON_VERSION = ddragon_version()
DD = load_dd_maps(DDRAGON_VERSION)

def champion_icon_url(name:str)->str:
    key = DD["champ_name2file"].get(name)
    if not key:
        n = re.sub(r"[ '&.:]", "", name).lower()
        key = DD["champ_alias"].get(n)
    if not key:
        key = re.sub(r"[ '&.:]", "", name)
        key = key[0].upper() + key[1:] + ".png"
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{key}"

def item_icon_url(name:str)->str:
    iid = DD["item_name2id"].get(name, "1001")
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/item/{iid}.png"

def spell_icon_url(name:str)->str:
    skey = DD["spell_name2key"].get(name.strip(), "SummonerFlash")
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/spell/{skey}.png"

# -------------------- CSV 로드 --------------------
CSV_CANDIDATES = [
    "aram_participants_with_icons_superlight.csv",
    "aram_participants_with_items.csv",
]
def _discover_csv():
    for f in CSV_CANDIDATES:
        if os.path.exists(f): return f
    return None

uploaded = st.sidebar.file_uploader("CSV 업로드", type="csv")
auto_path = _discover_csv()
df = pd.read_csv(uploaded) if uploaded else pd.read_csv(auto_path) if auto_path else None

if df is None:
    st.error("CSV 파일이 없습니다.")
    st.stop()

# -------------------- 챔피언 선택 --------------------
champions = sorted(df["champion"].dropna().unique())
sel = st.sidebar.selectbox("챔피언 선택", champions)
dfc = df[df["champion"]==sel]

# -------------------- 기본 메트릭 --------------------
games = len(dfc)
wr = round(dfc["win"].mean()*100,2) if games else 0
st.title(f"ARAM Dashboard - {sel}")
st.image(champion_icon_url(sel), width=100)
st.metric("게임 수", games)
st.metric("승률", f"{wr}%")

# -------------------- 아이템 추천 --------------------
st.subheader("추천 아이템")
item_cols = [c for c in dfc if "item" in c and "_name" in c]
rec = pd.concat([dfc[["win",c]].rename(columns={c:"item"}) for c in item_cols])
rec = rec[rec["item"]!=""]
g = rec.groupby("item").agg(total=("item","count"), wins=("win","sum")).assign(win_rate=lambda d:(d.wins/d.total*100)).sort_values(["total","win_rate"],ascending=[False,False]).head(5).reset_index()

for _, r in g.iterrows():
    col1, col2, col3 = st.columns([1,3,1])
    col1.image(item_icon_url(r.item), width=32)
    col2.write(r.item)
    col3.write(f"{int(r.total)}G / {round(r.win_rate,1)}%")

# -------------------- 스펠 추천 --------------------
st.subheader("추천 스펠")
dfc["spell_combo"] = dfc["spell1_name"].astype(str) + " + " + dfc["spell2_name"].astype(str)
sp = dfc.groupby("spell_combo").agg(games=("spell_combo","count"), wins=("win","sum")).assign(win_rate=lambda d:(d.wins/d.games*100)).sort_values(["games","win_rate"],ascending=[False,False]).head(5).reset_index()

for _, r in sp.iterrows():
    s1, s2 = r.spell_combo.split(" + ")
    col1, col2, col3 = st.columns([1,3,1])
    col1.image(spell_icon_url(s1), width=28)
    col1.image(spell_icon_url(s2), width=28)
    col2.write(r.spell_combo)
    col3.write(f"{r.games}G / {round(r.win_rate,1)}%")

# -------------------- DPM 그래프 --------------------
if "damage_total" in dfc and "duration_min" in dfc:
    dfc["dpm"] = dfc["damage_total"] / dfc["duration_min"].replace(0,np.nan)
    fig = px.histogram(dfc, x="dpm", nbins=20, title="DPM 분포")
    st.plotly_chart(fig, use_container_width=True)
