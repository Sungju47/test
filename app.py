import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="칼바람 챔피언 대시보드", layout="wide")

# -----------------------------
# 데이터 불러오기
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("champion_master.csv")
    df["champion"] = df["champion"].astype(str)
    return df

df = load_data()

# -----------------------------
# 사이드바: 챔피언 선택
# -----------------------------
st.sidebar.title("⚙️ 필터")
champs = sorted(df["champion"].unique())
champ = st.sidebar.selectbox("챔피언 선택", champs)

# -----------------------------
# 상단 KPI
# -----------------------------
row = df[df["champion"] == champ].iloc[0]

st.title(f"칼바람 — {champ} 통계")
cols = st.columns(6)
cols[0].metric("승률", f"{row.get('winrate',0):.2f}%")
cols[1].metric("픽률", f"{row.get('pickrate',0):.2f}%")
cols[2].metric("게임수", f"{int(row.get('games',0)):,}")
cols[3].metric("KDA", f"{row.get('kda',0):.2f}")
cols[4].metric("DPM", f"{row.get('avg_dpm',0):.0f}")
cols[5].metric("GPM", f"{row.get('avg_gpm',0):.0f}")

if "delta_winrate" in row and not pd.isna(row["delta_winrate"]):
    st.info(f"📈 최근 메타 변화: {row['delta_winrate']:+.2f}%p")

st.divider()

# -----------------------------
# 좌: 추천 빌드 / 우: 페이즈별 DPM
# -----------------------------
left, right = st.columns([1.1, 1])

with left:
    st.subheader("추천 빌드")
    st.markdown(f"**추천 룬**: {row.get('best_rune','—')}")
    st.markdown(f"**추천 스펠**: {row.get('best_spell_combo','—')}")
    st.markdown(f"**시작템**: {row.get('best_start','—')}")
    st.markdown(f"**신발**: {row.get('best_boots','—')}")
    st.markdown(f"**코어3**: {row.get('best_core3','—')}")

    st.subheader("시너지 & 카운터")
    st.markdown(f"**같이하면 좋은 챔피언**: {row.get('synergy_top1','—')} ({row.get('synergy_wr','')})")
    st.markdown(f"**상대하기 어려운 챔피언**: {row.get('enemy_hard_top1','—')} ({row.get('enemy_wr','')})")

with right:
    st.subheader("페이즈별 DPM")
    if any(col in df.columns for col in ["dpm_early","dpm_mid","dpm_late"]):
        plot_df = pd.DataFrame({
            "phase":["0–8분","8–16분","16+분"],
            "dpm":[row.get("dpm_early",None),
                   row.get("dpm_mid",None),
                   row.get("dpm_late",None)]
        })
        fig = px.bar(plot_df, x="phase", y="dpm", text="dpm", title="Phase별 DPM")
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("⚠️ 페이즈별 DPM 데이터 없음")

st.divider()

# -----------------------------
# 챔피언 기본 스탯
# -----------------------------
st.subheader("기본 스탯")
base_cols = [
    ("체력","hp"),("레벨당 체력","hpperlevel"),
    ("마나","mp"),("레벨당 마나","mpperlevel"),
    ("방어력","armor"),("레벨당 방어력","armorperlevel"),
    ("마법저항","spellblock"),("레벨당 마저","spellblockperlevel"),
    ("공격력","attackdamage"),("레벨당 공격력","attackdamageperlevel"),
    ("공속","attackspeed"),("레벨당 공속","attackspeedperlevel"),
    ("이동속도","movespeed"),("사거리","attackrange")
]
cols = st.columns(5)
i=0
for label,key in base_cols:
    if key in df.columns and not pd.isna(row.get(key,np.nan)):
        cols[i%5].metric(label, f"{row[key]:.2f}")
        i+=1

st.divider()

# -----------------------------
# 승률 TOP10 챔피언 그래프 (전체)
# -----------------------------
st.subheader("승률 TOP 10 챔피언")
top10 = df.sort_values("winrate", ascending=False).head(10)
fig = px.bar(top10, x="champion", y="winrate", text="winrate", title="승률 Top10")
fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
st.plotly_chart(fig, use_container_width=True)

st.caption("© 칼바람 분석 대시보드 — 샘플 CSV 기반")
