import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import (
    build_display_rows,
    calculate_health_scores,
    calculate_retention_rate,
    fetch_all_assets_by_user,
    fetch_wishes,
    init_db,
    normalize_user_key,
)

st.set_page_config(page_title="统计分析", page_icon="📊", layout="wide")
init_db()

st.title("📊 多维统计分析")
st.caption("高级交互图表：趋势/热力图/漏斗/雷达，支持鼠标悬停实时查看")

current_user_key = normalize_user_key(st.session_state.get("current_user_key", "默认用户"))
current_user_name = st.session_state.get("current_user_name", "默认用户")
st.info(f"当前用户：{current_user_name}")

rows = fetch_all_assets_by_user(current_user_key)
wishes = fetch_wishes(current_user_key)
if not rows:
    st.info("暂无资产数据，请先在首页添加物品。")
    st.stop()

display_rows, total_price, total_daily_price = build_display_rows(rows)
df = pd.DataFrame(display_rows)

df_raw = pd.DataFrame(rows)
df_raw["purchase_date"] = pd.to_datetime(df_raw["purchase_date"])
df_raw["month"] = df_raw["purchase_date"].dt.to_period("M").astype(str)
df_raw["date"] = df_raw["purchase_date"].dt.date

df["购入日期"] = pd.to_datetime(df["购入日期"])

retention_rates = [
    calculate_retention_rate(float(r["price"]), int((pd.Timestamp.today().date() - pd.to_datetime(r["purchase_date"]).date()).days + 1))
    for r in rows
]
avg_retention = sum(retention_rates) / len(retention_rates) if retention_rates else 0

c1, c2, c3 = st.columns(3)
c1.metric("资产数量", len(df))
c2.metric("总价格", f"¥{total_price:,.2f}")
c3.metric("平均保值率", f"{avg_retention:.2f}%")

st.metric("总日均价格", f"¥{total_daily_price:,.2f}/天")

st.subheader("Chart 1 · 资产价值趋势")
trend = (
    df_raw.groupby(["month", "category_name"], as_index=False)["price"]
    .sum()
    .sort_values("month")
)
fig_trend = px.line(
    trend,
    x="month",
    y="price",
    color="category_name",
    markers=True,
    title="按分类的月度资产价值趋势",
)
fig_trend.update_layout(hovermode="x unified", xaxis_title="时间（月）", yaxis_title="资产价值")
st.plotly_chart(fig_trend, use_container_width=True)

st.subheader("Chart 2 · 消费时间热力图（过去12个月）")
end_day = pd.Timestamp.today().normalize()
start_day = end_day - pd.DateOffset(months=12)
df_12m = df_raw[df_raw["purchase_date"] >= start_day].copy()

if not df_12m.empty:
    daily_spend = (
        df_12m.assign(date=df_12m["purchase_date"].dt.date)
        .groupby("date", as_index=False)
        .agg(amount=("price", "sum"))
    )
    daily_spend["date"] = pd.to_datetime(daily_spend["date"])
    day_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    daily_spend["weekday"] = daily_spend["date"].dt.weekday.map(day_map)
    daily_spend["week"] = daily_spend["date"].dt.isocalendar().week.astype(int)

    heat = daily_spend.pivot_table(index="weekday", columns="week", values="amount", aggfunc="sum", fill_value=0)
    ordered_weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    heat = heat.reindex([d for d in ordered_weekdays if d in heat.index])

    fig_heat = px.imshow(
        heat,
        aspect="auto",
        color_continuous_scale="Turbo",
        title="日历热力图（颜色越深表示购买金额越高）",
        labels={"x": "周序号", "y": "星期", "color": "金额"},
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    selected_day = st.date_input("查看指定日期购买详情", value=end_day.date(), key="heatmap_selected_day")
    day_items = df_raw[df_raw["date"] == selected_day]
    if not day_items.empty:
        st.dataframe(
            day_items[["name", "category_name", "price", "purchase_date"]]
            .rename(columns={"name": "名称", "category_name": "分类", "price": "价格", "purchase_date": "购入日期"}),
            use_container_width=True,
        )
    else:
        st.caption("该日期无购买记录")
else:
    st.info("过去12个月暂无购买数据")

st.subheader("Chart 3 · 心愿单转化漏斗")
wish_count = sum(1 for w in wishes if w.get("status") == "想买")
bought_count = sum(1 for w in wishes if w.get("status") == "已购入")
in_use_count = sum(1 for r in rows if r.get("asset_status", "使用中") == "使用中")
disposed_count = sum(1 for r in rows if r.get("asset_status", "使用中") == "已处置")

funnel_df = pd.DataFrame(
    {
        "阶段": ["心愿单", "已购买", "使用中", "已处置"],
        "数量": [wish_count, bought_count, in_use_count, disposed_count],
    }
)
fig_funnel = px.funnel(funnel_df, x="数量", y="阶段", title="资产生命周期漏斗")
st.plotly_chart(fig_funnel, use_container_width=True)

if wish_count > 0:
    purchase_rate = bought_count / wish_count * 100
else:
    purchase_rate = 0
st.caption(f"心愿单→已购买 转化率：{purchase_rate:.2f}%")

st.subheader("Chart 4 · 资产健康度雷达图")
scores = calculate_health_scores(rows)
radar_dims = ["保值率", "使用频率", "维护状态", "必要性", "流动性"]
radar_vals = [scores[d] for d in radar_dims]

fig_radar = go.Figure()
fig_radar.add_trace(
    go.Scatterpolar(
        r=radar_vals + [radar_vals[0]],
        theta=radar_dims + [radar_dims[0]],
        fill="toself",
        name="健康评分",
    )
)
fig_radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    showlegend=False,
    title=f"整体健康度：{scores['整体健康度']:.2f}/100",
)
st.plotly_chart(fig_radar, use_container_width=True)

st.subheader("明细数据")
st.dataframe(df, use_container_width=True)
