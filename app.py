# app.py
# ---------------------------------------------------------
# ARAM PS Dashboard (Upload-based)
# - CSV 업로드 / 자동탐색 지원
# - Data Dragon 에서 챔피언/아이템/스펠/룬 아이콘 자동 매핑
# - 표는 유지, "최고 추천" 아이템/룬은 배지로 요약 표시
# ---------------------------------------------------------
import os, ast, re, unicodedata, requests
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="ARAM PS Dashboard", layout="wide")

# =========================
# Data Dragon helpers
# =========================
@st.cache_data(show_spinner=False, ttl=86400)
def ddragon_version() -> str:
    return requests.get(
        "https://ddragon.leagueoflegends.com/api/versions.json",
        timeout=8
    ).json()[0]

@st.cache_data(show_spinner=False, ttl=86400)
def load_dd_maps(ver: str) -> Dict[str, Dict[str, str]]:
    # Champion
    champs = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json",
        timeout=8
    ).json()["data"]

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        s = s.replace(" ", "").replace("'", "").replace(".", "")
        s = s.replace("&", "").replace(":", "")
        return s

    champ_name2file = { c["name"]: c["id"] + ".png" for c in champs.values() }
    champ_alias      = { norm(c["name"]).lower(): c["id"] + ".png" for c in champs.values() }

    # Items
    items = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/item.json",
        timeout=8
    ).json()["data"]
    item_name2id = { v["name"]: k for k, v in items.items() }  # "Infinity Edge" → "3031"

    # Spells
    spells = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/summoner.json",
        timeout=8
    ).json()["data"]
    spell_name2key = { v["name"]: v["id"] for v in spells.values() }  # "Flash" → "SummonerFlash"

    # Runes (Reforged)
    runes = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/runesReforged.json",
        timeout=8
    ).json()
    # 트리(메인/보조) 아이콘: "perk-images/Styles/<Tree>/<Tree>.png"
    rune_tree_name2icon = {}
    rune_name2icon = {}
    for tree in runes:
        rune_tree_name2icon[tree["name"]] = tree["icon"]  # e.g. "perk-images/Styles/Precision/Precision.png"
        for slot in tree.get("slots", []):
            for r in slot.get("runes", []):
                rune_name2icon[r["name"]] = r["icon"]       # e.g. "perk-images/Styles/Precision/PressTheAttack/PressTheAttack.png"

    return {
        "champ_name2file":   champ_name2file,
        "champ_alias":       champ_alias,
        "item_name2id":      item_name2id,
        "spell_name2key":    spell_name2key,
        "rune_tree_name2icon": rune_tree_name2icon,
        "rune_name2icon":      rune_name2icon,
    }

DDRAGON_VERSION = ddragon_version()
DD = load_dd_maps(DDRAGON_VERSION)

def champion_icon_url(name: str) -> str:
    key = DD["champ_name2file"].get(name)
    if not key:
        n = re.sub(r"[ '&.:]", "", name).lower()
        key = DD["champ_alias"].get(n)
    if not key:
        # 최후 추정
        key = re.sub(r"[ '&.:]", "", name)
        key = key[:1].upper() + key[1:]
        key += ".png"
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{key}"

def item_icon_url_by_name(item_name: str) -> str:
    iid = DD["item_name2id"].get(item_name, "1001")  # fallback: Boots
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/item/{iid}.png"

def item_icon_url_by_id(item_id: str) -> str:
    iid = str(item_id).strip()
    if not iid.isdigit():
        iid = "1001"
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/item/{iid}.png"

def spell_icon_url(spell_name: str) -> str:
    skey = DD["spell_name2key"].get(spell_name.strip(), "SummonerFlash")
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/spell/{skey}.png"

def rune_tree_icon_url(tree_name: str) -> str:
    icon_path = DD["rune_tree_name2icon"].get(tree_name)
    if not icon_path:
        # fallback: Precision
        icon_path = "perk-images/Styles/Precision/Precision.png"
    return f"https://ddragon.leagueoflegends.com/cdn/img/{icon_path}"

# =========================
# CSV 로드/전처리
# =========================
CSV_CANDIDATES = [
    "aram_participants_with_full_runes_merged_plus.csv",
    "aram_participants_with_full_runes_merged.csv",
    "aram_participants_with_full_runes.csv",
    "aram_participants_clean_preprocessed.csv",
    "aram_participants_clean_no_dupe_items.csv",
    "aram_participants_with_items.csv",
]

def _discover_csv() -> Optional[str]:
    for f in CSV_CANDIDATES:
        if os.path.exists(f):
            return f
    return None

def _yes(x) -> int:
    return 1 if str(x).strip().lower() in ("1", "true", "t", "yes") else 0

def _as_list(s):
    if isinstance(s, list):
        return s
    if not isinstance(s, str) or not s.strip():
        return []
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return v
    except Exception:
        pass
    spl = "|" if "|" in s else "," if "," in s else None
    return [t.strip() for t in s.split(spl)] if spl else [s]

@st.cache_data(show_spinner=False)
def load_df(buf) -> pd.DataFrame:
    df = pd.read_csv(buf)

    # 기본 파생
    df["win_clean"] = df.get("win", 0).apply(_yes)

    # 스펠 콤보
    s1 = "spell1_name" if "spell1_name" in df.columns else ("spell1" if "spell1" in df.columns else None)
    s2 = "spell2_name" if "spell2_name" in df.columns else ("spell2" if "spell2" in df.columns else None)
    df["spell_combo"] = ""
    if s1 and s2:
        df["spell_combo"] = (df[s1].astype(str).str.strip() + " + " + df[s2].astype(str).str.strip()).str.strip()

    # 아이템 문자열/ID 정리
    for c in [c for c in df.columns if c.startswith("item")]:
        df[c] = df[c].fillna("").astype(str).str.strip()

    # 팀/상대
    for col in ("team_champs", "enemy_champs"):
        if col in df.columns:
            df[col] = df[col].apply(_as_list)

    # 시간/지표
    df["duration_min"] = pd.to_numeric(df.get("game_end_min"), errors="coerce").fillna(18).clip(6, 40)
    df["dpm"] = df.get("damage_total", np.nan) / df["duration_min"].replace(0, np.nan)
    for k in ("kills", "deaths", "assists"):
        df[k] = pd.to_numeric(df.get(k, 0), errors="coerce").fillna(0)
    df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].replace(0, np.nan)
    df["kda"] = df["kda"].fillna(df["kills"] + df["assists"])

    return df

# =========================
# UI — 입력부
# =========================
st.sidebar.header("데이터")
auto_path = _discover_csv()
st.sidebar.write("자동 검색:", auto_path if auto_path else "없음")
uploaded = st.sidebar.file_uploader("CSV 업로드(권장)", type=["csv"])

df = load_df(uploaded) if uploaded else (load_df(auto_path) if auto_path else None)
if df is None or "champion" not in df.columns:
    st.error("CSV를 업로드하거나 레포 루트에 CSV를 두세요. (champion 컬럼 필요)")
    st.stop()

champions = sorted(df["champion"].dropna().unique().tolist())
sel_champ = st.sidebar.selectbox("챔피언 선택", champions)

# =========================
# 상단 헤더/요약
# =========================
dfc = df[df["champion"] == sel_champ].copy()
total_matches = df["matchId"].nunique() if "matchId" in df.columns else len(df)
games = len(dfc)
wr = round(dfc["win_clean"].mean() * 100, 2) if games else 0.0
pr = round(games / total_matches * 100, 2) if total_matches else 0.0
avg_k = round(dfc["kills"].mean(), 2) if games else 0
avg_d = round(dfc["deaths"].mean(), 2) if games else 0
avg_a = round(dfc["assists"].mean(), 2) if games else 0
avg_dpm = round(dfc["dpm"].mean(), 1) if games else 0

st.title("ARAM PS Dashboard")
cL, cM = st.columns([1, 5])
with cL:
    st.image(champion_icon_url(sel_champ), width=96)
with cM:
    st.subheader(sel_champ)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("게임 수", games)
m2.metric("승률(%)", wr)
m3.metric("픽률(%)", pr)
m4.metric("평균 K/D/A", f"{avg_k}/{avg_d}/{avg_a}")
m5.metric("평균 DPM", avg_dpm)

# =========================
# 추천 배지 (아이템/룬) — 판수 우선, 동률 시 승률
# =========================
def build_item_long(sub: pd.DataFrame) -> pd.DataFrame:
    """item*_name(또는 item*)와 item*_id가 동시에 있을 때 둘 다 녹여서 한 표로 합치기"""
    name_cols = [c for c in sub.columns if c.startswith("item") and c.endswith("_name")]
    id_cols   = [c for c in sub.columns if c.startswith("item") and c.endswith("_id")]
    bare_cols = [c for c in sub.columns if c.startswith("item") and not c.endswith("_name") and not c.endswith("_id")]

    rec = []

    # (name,id) 페어 우선
    # item0_name ↔ item0_id 식으로 짝맞추기
    name_base = { c[:-5]: c for c in name_cols }  # "item0": "item0_name"
    id_base   = { c[:-3]: c for c in id_cols }    # "item0": "item0_id"

    bases = sorted(set(list(name_base.keys()) + list(id_base.keys())))
    for base in bases:
        ncol = name_base.get(base)
        icol = id_base.get(base)
        cols = ["matchId", "win_clean"]
        if ncol: cols.append(ncol)
        if icol: cols.append(icol)
        tmp = sub[cols].copy()
        tmp = tmp.rename(columns={ncol: "item_name", icol: "item_id"})
        rec.append(tmp)

    # bare (item0, item1 ...)
    for c in bare_cols:
        tmp = sub[["matchId", "win_clean", c]].rename(columns={c: "item_name"})
        tmp["item_id"] = ""
        rec.append(tmp)

    if not rec:
        return pd.DataFrame(columns=["matchId","win_clean","item_name","item_id"])

    u = pd.concat(rec, ignore_index=True)
    u["item_name"] = u["item_name"].fillna("").astype(str).str.strip()
    u["item_id"]   = u["item_id"].fillna("").astype(str).str.strip()
    u = u[(u["item_name"] != "") | (u["item_id"] != "")]
    return u

def top_item_row(sub: pd.DataFrame) -> Optional[pd.Series]:
    u = build_item_long(sub)
    if u.empty: return None
    g = (
        u.assign(key=u["item_name"].replace("", np.nan).fillna(u["item_id"]))
         .groupby("key")
         .agg(
             games=("matchId","count"),
             wins =("win_clean","sum"),
             item_name=("item_name", lambda s: s.replace("", np.nan).dropna().mode().iloc[0] if s.replace("", np.nan).dropna().size else ""),
             item_id  =("item_id",   lambda s: s.replace("", np.nan).dropna().mode().iloc[0] if s.replace("", np.nan).dropna().size else "")
         )
         .reset_index(drop=True)
    )
    g["win_rate"] = (g["wins"]/g["games"]*100).round(2)
    g = g.sort_values(["games","win_rate"], ascending=[False, False]).reset_index(drop=True)
    return g.iloc[0]

def top_rune_pair(sub: pd.DataFrame) -> Optional[Tuple[str,str,int,float]]:
    # rune_core / rune_sub 이름 기반
    if "rune_core" not in sub.columns or "rune_sub" not in sub.columns:
        return None
    grp = (
        sub.groupby(["rune_core","rune_sub"])
           .agg(games=("matchId","count"), wins=("win_clean","sum"))
           .reset_index()
    )
    if grp.empty: return None
    grp["win_rate"] = (grp["wins"]/grp["games"]*100).round(2)
    grp = grp.sort_values(["games","win_rate"], ascending=[False, False]).reset_index(drop=True)
    r = grp.iloc[0]
    return str(r["rune_core"]), str(r["rune_sub"]), int(r["games"]), float(r["win_rate"])

st.subheader("추천 (판수 우선, 동률 시 승률)")

bc1, bc2 = st.columns(2)

with bc1:
    st.markdown("**아이템 추천**")
    ti = top_item_row(dfc)
    if ti is None:
        st.info("아이템 데이터가 없습니다.")
    else:
        # 아이콘 URL: id가 있으면 id로, 없으면 이름으로
        icon_url = item_icon_url_by_id(ti["item_id"]) if str(ti["item_id"]).strip() else item_icon_url_by_name(ti["item_name"])
        with st.columns([1,4,2,2])[0]:
            st.image(icon_url, width=48)
        st.write(f"{ti['item_name'] or ti['item_id']}")
        st.caption(f"{int(ti['games'])} 게임 · 승률 {ti['win_rate']}%")

with bc2:
    st.markdown("**룬(메인/보조) 추천**")
    tr = top_rune_pair(dfc)
    if tr is None:
        st.info("룬 데이터가 없습니다.")
    else:
        core, sub, rg, rwr = tr
        colI, colT = st.columns([2,5])
        with colI:
            st.image(rune_tree_icon_url(core), width=44)
            st.image(rune_tree_icon_url(sub),  width=44)
        with colT:
            st.write(f"{core} / {sub}")
            st.caption(f"{rg} 게임 · 승률 {round(rwr,2)}%")

st.markdown("---")

# =========================
# 탭
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["게임 분석", "아이템 & 스펠", "타임라인", "상세 데이터"])

with tab1:
    c1, c2, c3 = st.columns(3)
    if "first_blood_min" in dfc.columns and dfc["first_blood_min"].notna().any():
        c1.metric("퍼블 평균(분)", round(dfc["first_blood_min"].mean(), 2))
    if "game_end_min" in dfc.columns and dfc["game_end_min"].notna().any():
        c2.metric("평균 게임시간(분)", round(dfc["game_end_min"].mean(), 2))
    if "gold_spike_min" in dfc.columns and dfc["gold_spike_min"].notna().any():
        fig = px.histogram(dfc, x="gold_spike_min", nbins=20, title="골드 스파이크 시각 분포(분)")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    left, right = st.columns(2)

    # 아이템 표 (슬롯 무시 합산)
    with left:
        st.subheader("아이템 성과 (Top 20)")
        u = build_item_long(dfc)
        if u.empty:
            st.info("아이템 데이터가 없습니다.")
        else:
            g = (
                u[u["item_name"].astype(str) + u["item_id"].astype(str) != ""]
                .assign(key=u["item_name"].replace("", np.nan).fillna(u["item_id"]))
                .groupby("key")
                .agg(
                    total=("matchId", "count"),
                    wins =("win_clean","sum"),
                    item_name=("item_name", lambda s: s.replace("", np.nan).dropna().mode().iloc[0] if s.replace("", np.nan).dropna().size else ""),
                    item_id  =("item_id",   lambda s: s.replace("", np.nan).dropna().mode().iloc[0] if s.replace("", np.nan).dropna().size else "")
                )
                .reset_index(drop=True)
            )
            g["win_rate"] = (g["wins"]/g["total"]*100).round(2)
            g = g.sort_values(["total","win_rate"], ascending=[False, False]).head(20)

            # 리스트형 표 + 아이콘
            for _, r in g.iterrows():
                ci, cn, cp, cw = st.columns([1, 5, 2, 2])
                icon = item_icon_url_by_id(r["item_id"]) if str(r["item_id"]).strip() else item_icon_url_by_name(r["item_name"])
                with ci: st.image(icon, width=28)
                with cn: st.write(str(r["item_name"] or r["item_id"]))
                with cp: st.write(f"{int(r['total'])} 게임")
                with cw: st.write(f"{r['win_rate']}%")
                st.divider()

    # 스펠 표
    with right:
        st.subheader("스펠 조합 (Top 10)")
        if "spell_combo" not in dfc.columns or not dfc["spell_combo"].str.strip().any():
            st.info("스펠 데이터가 없습니다.")
        else:
            sp = (
                dfc.groupby("spell_combo")
                   .agg(games=("matchId","count"), wins=("win_clean","sum"))
                   .reset_index()
            )
            sp["win_rate"] = (sp["wins"]/sp["games"]*100).round(2)
            sp = sp.sort_values(["games","win_rate"], ascending=[False, False]).head(10)
            for _, r in sp.iterrows():
                s1, s2 = [x.strip() for x in str(r["spell_combo"]).split("+", 1)]
                ci, cn, cv = st.columns([2, 5, 2])
                with ci:
                    st.image(spell_icon_url(s1), width=26)
                    st.image(spell_icon_url(s2), width=26)
                with cn: st.write(r["spell_combo"])
                with cv: st.write(f"{r['win_rate']}% · {int(r['games'])}G")
                st.divider()

with tab3:
    st.subheader("코어 아이템 구매 타이밍")
    a, b = st.columns(2)
    if "first_core_item_min" in dfc.columns and dfc["first_core_item_min"].notna().any():
        a.metric("1코어 평균 분", round(dfc["first_core_item_min"].mean(), 2))
        fig = px.histogram(dfc.dropna(subset=["first_core_item_min"]), x="first_core_item_min", nbins=24, title="1코어 시점")
        st.plotly_chart(fig, use_container_width=True)
    if "second_core_item_min" in dfc.columns and dfc["second_core_item_min"].notna().any():
        b.metric("2코어 평균 분", round(dfc["second_core_item_min"].mean(), 2))
        fig = px.histogram(dfc.dropna(subset=["second_core_item_min"]), x="second_core_item_min", nbins=24, title="2코어 시점")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.dataframe(
        dfc.drop(columns=["team_champs","enemy_champs"], errors="ignore"),
        use_container_width=True
    )

st.caption(f"Data-Dragon v{DDRAGON_VERSION} · {len(champions)} champs · {total_matches} matches")
