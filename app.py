import streamlit as st
import pandas as pd
import requests, io
from PIL import Image

st.set_page_config(page_title="ARAM PS Dashboard", layout="wide")

# ----------------------------
# CSV 로딩
# ----------------------------
CSV_CANDIDATES = [
    "aram_participants_with_icons_superlight.csv",
    "aram_participants_with_full_runes_merged_plus.csv",
]

def load_csv(buf):
    try:
        df = pd.read_csv(buf)
        # 최소 컬럼 체크
        if "champion" not in df.columns:
            st.error("CSV에 'champion' 컬럼이 없습니다.")
            return None
        return df
    except Exception as e:
        st.error(f"CSV 로딩 실패: {e}")
        return None

def discover_local_csv():
    for f in CSV_CANDIDATES:
        if os.path.exists(f):
            return f
    return None

def load_from_github(user, repo, branch="main", filename=None):
    if not filename: return None
    url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{filename}"
    try:
        s = requests.get(url, timeout=5).content
        return pd.read_csv(io.StringIO(s.decode("utf-8")))
    except Exception as e:
        st.warning(f"GitHub CSV 로딩 실패: {e}")
        return None

# 사이드바
st.sidebar.header("CSV 선택")
uploaded = st.sidebar.file_uploader("CSV 업로드", type="csv")
auto_csv = discover_local_csv()
st.sidebar.write("자동 탐색:", auto_csv if auto_csv else "없음")
gh_user = st.sidebar.text_input("GitHub 유저")
gh_repo = st.sidebar.text_input("GitHub 리포지토리")
gh_file = st.sidebar.text_input("CSV 파일명")

# 우선순위: 업로드 > 로컬 > GitHub
df = None
if uploaded:
    df = load_csv(uploaded)
elif auto_csv:
    df = load_csv(auto_csv)
elif gh_user and gh_repo and gh_file:
    df = load_from_github(gh_user, gh_repo, filename=gh_file)

if df is None:
    st.stop()

# ----------------------------
# Data Dragon 버전 & 이미지 helpers
# ----------------------------
DDRAGON_VERSION = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()[0]

def champion_icon_url(name:str):
    n = name.replace(" ","").replace("'","")
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{n}.png"

def item_icon_url(item:str, default_id="1001"):
    # CSV에는 item 컬럼 이름이 이미 아이템명
    # Data Dragon 아이템 ID 매핑이 필요하면 여기서 dict 확장 가능
    item_id_map = {
        "Infinity Edge":"3031","Rabadon's Deathcap":"3089","Kraken Slayer":"6672",
        "Galeforce":"6671","Berserker's Greaves":"3006",
        "Plated Steelcaps":"3047","Mercury's Treads":"3111","Boots of Swiftness":"3009",
    }
    iid = item_id_map.get(item, default_id)
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/item/{iid}.png"

def spell_icon_url(spell:str):
    spell_map = {
        "Flash":"SummonerFlash","Ignite":"SummonerDot","Heal":"SummonerHeal",
        "Barrier":"SummonerBarrier","Exhaust":"SummonerExhaust","Teleport":"SummonerTeleport",
    }
    key = spell_map.get(spell.strip(), "SummonerFlash")
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/spell/{key}.png"

# ----------------------------
# 챔피언 선택
# ----------------------------
champions = sorted(df["champion"].dropna().unique())
sel = st.sidebar.selectbox("챔피언 선택", champions)
dfc = df[df["champion"]==sel]

st.title(f"ARAM Dashboard - {sel}")
# 챔피언 아이콘
st.image(champion_icon_url(sel), width=100)

# ----------------------------
# 아이템/스펠 요약
# ----------------------------
st.subheader("아이템/스펠 추천")
item_cols = [c for c in dfc if c.startswith("item") and "name" in c]
for c in item_cols:
    g = dfc[c].value_counts().head(5)
    st.write(f"**{c}**")
    for item, cnt in g.items():
        st.image(item_icon_url(item), width=32)
        st.write(f"{item} ({cnt}게임)")

spell_cols = [c for c in dfc if c.startswith("spell")]
for c in spell_cols:
    g = dfc[c].value_counts().head(3)
    st.write(f"**{c}**")
    for spell, cnt in g.items():
        st.image(spell_icon_url(spell), width=28)
        st.write(f"{spell} ({cnt}게임)")
