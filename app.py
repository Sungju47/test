import streamlit as st
import pandas as pd

# -------------------------------
# CSV 로드
# -------------------------------
file_path = "C:/Users/cjswo/OneDrive/바탕 화면/새 폴더 (2)/aram_participants_with_icons_superlight.csv"
df = pd.read_csv(file_path)

# -------------------------------
# 사이드바: 챔피언 선택
# -------------------------------
champions = sorted(df['champion'].dropna().unique())
sel_champ = st.sidebar.selectbox("챔피언 선택", champions)

# -------------------------------
# 선택 챔피언 필터링
# -------------------------------
dfc = df[df['champion'] == sel_champ]

st.title(f"ARAM Dashboard — {sel_champ}")

# -------------------------------
# 메트릭
# -------------------------------
games = len(dfc)
winrate = round(dfc['win'].mean() * 100, 2) if games else 0
avg_k = round(dfc['kills'].mean(), 2)
avg_d = round(dfc['deaths'].mean(), 2)
avg_a = round(dfc['assists'].mean(), 2)

c1, c2, c3 = st.columns(3)
c1.metric("게임 수", games)
c2.metric("승률(%)", winrate)
c3.metric("평균 K/D/A", f"{avg_k}/{avg_d}/{avg_a}")

# -------------------------------
# 추천 아이템
# -------------------------------
st.subheader("추천 아이템 (Top 5)")
item_cols = [col for col in dfc.columns if col.startswith("item") and col.endswith("_name")]

# 아이템별 게임 수와 승률 계산
items_list = []
for col in item_cols:
    temp = dfc[[col, 'win']].rename(columns={col: 'item'})
    temp = temp[temp['item'] != ""]
    items_list.append(temp)
items_df = pd.concat(items_list)

top_items = (items_df.groupby('item')
             .agg(total=('item','count'), wins=('win','sum'))
             .assign(win_rate=lambda x: (x.wins / x.total * 100).round(2))
             .sort_values(['total', 'win_rate'], ascending=[False, False])
             .head(5)
             .reset_index())

for _, row in top_items.iterrows():
    icon_col = row['item'].replace(" ", "_").lower() + "_icon"
    # 아이콘 URL 컬럼 찾기
    icon_cols = [c for c in dfc.columns if c.startswith(row['item'].split()[0].lower()) and c.endswith("_icon")]
    icon_url = dfc[icon_cols[0]].dropna().iloc[0] if icon_cols else None
    st.image(icon_url, width=50, caption=f"{row['item']} — {int(row['total'])}G / {row['win_rate']}%")

# -------------------------------
# 추천 스펠
# -------------------------------
st.subheader("추천 스펠 조합 (Top 5)")
if 'spell1_name' in dfc.columns and 'spell2_name' in dfc.columns:
    dfc['spell_combo'] = dfc['spell1_name'] + " + " + dfc['spell2_name']
    spells = (dfc.groupby('spell_combo')
              .agg(total=('spell_combo','count'), wins=('win','sum'))
              .assign(win_rate=lambda x: (x.wins / x.total * 100).round(2))
              .sort_values(['total','win_rate'], ascending=[False, False])
              .head(5)
              .reset_index())
    for _, row in spells.iterrows():
        spell1 = dfc[dfc['spell1_name'].notna()]['spell1_name'].iloc[0]
        spell2 = dfc[dfc['spell2_name'].notna()]['spell2_name'].iloc[0]
        st.write(f"{row['spell_combo']} — {int(row['total'])}G / {row['win_rate']}%")
