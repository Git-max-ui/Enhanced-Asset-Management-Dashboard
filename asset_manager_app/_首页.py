from datetime import date, datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from core import (
    add_asset,
    add_search_history,
    add_category,
    build_display_rows,
    build_tag_cloud_data,
    calculate_health_scores,
    delete_asset,
    delete_category,
    fetch_all_assets_by_user,
    fetch_assets,
    fetch_categories,
    fetch_recent_assets,
    fetch_search_history,
    fetch_warning_assets,
    get_all_tags,
    get_search_suggestions,
    init_db,
    normalize_user_key,
    recommend_category,
    update_asset,
)

init_db()
st.set_page_config(page_title="资产管理 App", page_icon="📦", layout="wide")

st.markdown(
    """
    <style>
    .metric-card {
      background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(129,140,248,0.15));
      border: 1px solid rgba(148,163,184,0.2);
      border-radius: 16px;
      padding: 16px;
      min-height: 130px;
    }
    .metric-title {font-size: 0.95rem; color: #cbd5e1;}
    .metric-value {font-size: 2rem; font-weight: 700; color: #f8fafc; margin-top: 6px;}
    .metric-sub {font-size: 0.9rem; color: #94a3b8; margin-top: 8px;}
    .ok {color: #22c55e;}
    .warn {color: #f59e0b;}
    .down {color: #ef4444;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💼 Enhanced Asset Management Dashboard")
st.caption("暗色卡片式布局 · 智能分类标签 · 高级可视化分析")

if "current_user_key" not in st.session_state:
    st.session_state.current_user_key = normalize_user_key("默认用户")
if "current_user_name" not in st.session_state:
    st.session_state.current_user_name = "默认用户"

with st.sidebar:
    st.subheader("👤 用户")
    user_name_input = st.text_input("当前用户名", value=st.session_state.current_user_name)
    if st.button("切换用户"):
        st.session_state.current_user_name = user_name_input.strip() or "默认用户"
        st.session_state.current_user_key = normalize_user_key(st.session_state.current_user_name)
        st.success(f"已切换到：{st.session_state.current_user_name}")
        st.rerun()

current_user_key = st.session_state.current_user_key
current_user_name = st.session_state.current_user_name
st.info(f"当前用户：{current_user_name}")

ADD_FORM_KEYS = [
    "add_name",
    "add_price",
    "add_use_custom",
    "add_purchase_date",
    "add_custom_category_name",
    "add_custom_logo",
    "add_tags",
    "add_frequency_tag",
    "add_asset_status",
    "add_maintenance_enabled",
    "add_maintenance_date",
    "add_selected_category",
]

if st.session_state.pop("reset_add_form", False):
    for key in ADD_FORM_KEYS:
        st.session_state.pop(key, None)
    st.session_state["open_add_asset"] = False

categories = fetch_categories(current_user_key)
category_labels = {c["id"]: f"{c['logo']} {c['name']}" for c in categories}
all_rows = fetch_all_assets_by_user(current_user_key)
warning_rows = fetch_warning_assets(current_user_key, days=30)


def _month_sum(rows, dt: date) -> float:
    return sum(
        float(r["price"])
        for r in rows
        if datetime.strptime(r["purchase_date"], "%Y-%m-%d").date().year == dt.year
        and datetime.strptime(r["purchase_date"], "%Y-%m-%d").date().month == dt.month
    )


today = date.today()
if today.month == 1:
    prev_month_date = date(today.year - 1, 12, 1)
else:
    prev_month_date = date(today.year, today.month - 1, 1)

total_value = sum(float(r["price"]) for r in all_rows)
asset_count = len(all_rows)
category_count = len({r.get("category_name", "未分类") for r in all_rows})
current_month_value = _month_sum(all_rows, today)
prev_month_value = _month_sum(all_rows, prev_month_date)

if prev_month_value > 0:
    delta_pct = (current_month_value - prev_month_value) / prev_month_value * 100
elif current_month_value > 0:
    delta_pct = 100.0
else:
    delta_pct = 0.0

arrow = "↑" if delta_pct >= 0 else "↓"
delta_cls = "ok" if delta_pct >= 0 else "down"

metrics_cols = st.columns(3)
with metrics_cols[0]:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-title">💰 总资产价值</div>
          <div class="metric-value">¥{total_value:,.2f}</div>
          <div class="metric-sub {delta_cls}">{arrow} 月度变化 {abs(delta_pct):.2f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with metrics_cols[1]:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-title">📊 资产总数</div>
          <div class="metric-value">{asset_count}</div>
          <div class="metric-sub">覆盖 {category_count} 个分类</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with metrics_cols[2]:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-title">⚠️ 预警项目数</div>
          <div class="metric-value">{len(warning_rows)}</div>
          <div class="metric-sub warn">未来30天即将到期/需保养</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

mid_left, mid_right = st.columns(2)
with mid_left:
    st.subheader("资产分布环形图")
    if all_rows:
        df_all = pd.DataFrame(all_rows)
        by_cat = df_all.groupby("category_name", as_index=False)["price"].sum()
        fig_donut = px.pie(by_cat, names="category_name", values="price", hole=0.55, title="分类资产价值占比")
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("暂无数据")

with mid_right:
    st.subheader("快速操作")
    qa1, qa2, qa3 = st.columns(3)
    if qa1.button("添加资产", use_container_width=True):
        st.session_state["open_add_asset"] = True

    if all_rows:
        export_df = pd.DataFrame(build_display_rows(all_rows)[0])
        out = BytesIO()
        export_df.to_excel(out, index=False)
        qa2.download_button(
            "导出数据",
            data=out.getvalue(),
            file_name="assets_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        qa2.button("导出数据", disabled=True, use_container_width=True)

    report_text = (
        f"资产报告（{current_user_name}）\n"
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"总资产价值：¥{total_value:,.2f}\n"
        f"资产总数：{asset_count}\n"
        f"预警项目数：{len(warning_rows)}\n"
        f"月度变化：{arrow}{abs(delta_pct):.2f}%\n"
    )
    qa3.download_button(
        "生成报告",
        data=report_text.encode("utf-8"),
        file_name="asset_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.divider()

with st.expander("🏷️ 分类设置（内置常用类型 + 自定义）", expanded=False):
    st.write("已内置：手机、平板、电脑、耳机、衣服、鞋子、包、书、键盘、鼠标")
    st.dataframe(
        pd.DataFrame(
            [{"分类": c["name"], "Logo": c["logo"]} for c in categories]
        ),
        use_container_width=True,
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    new_cat_name = c1.text_input("新增分类名称", placeholder="例如：相机")
    new_cat_logo = c2.text_input("Logo", value="📦", max_chars=4)
    if c3.button("新增分类"):
        if not new_cat_name.strip():
            st.error("分类名称不能为空")
        else:
            add_category(current_user_key, new_cat_name, new_cat_logo)
            st.success("分类已新增")
            st.rerun()

    del_options = {f"#{c['id']} {c['logo']} {c['name']}": c["id"] for c in categories}
    if del_options:
        sel = st.selectbox("删除分类", list(del_options.keys()))
        if st.button("删除所选分类"):
            delete_category(current_user_key, del_options[sel])
            st.success("分类已删除（已有资产会保留原分类文本）")
            st.rerun()

with st.expander("➕ 添加物品", expanded=st.session_state.get("open_add_asset", True)):
    c1, c2 = st.columns(2)
    name = c1.text_input("名称", placeholder="例如：MacBook Pro", key="add_name")
    price = c2.number_input("价格(元)", min_value=0.0, step=0.01, key="add_price")

    recommendation = recommend_category(name, categories)
    if recommendation is not None:
        rc1, rc2 = st.columns([3, 1])
        rc1.info(f"智能推荐分类：{recommendation['logo']} {recommendation['name']}")
        if rc2.button("使用推荐", key="use_recommendation"):
            st.session_state["add_use_custom"] = False
            st.session_state["add_selected_category"] = recommendation["id"]
            st.rerun()

    c3, c4 = st.columns(2)
    use_custom = c3.checkbox("使用自定义种类", key="add_use_custom")
    purchase_date = c4.date_input("购入日期", value=date.today(), key="add_purchase_date")

    c7, c8, c9 = st.columns(3)
    frequency_tag = c7.selectbox("使用频率", ["日常", "偶尔", "稀有"], key="add_frequency_tag")
    status_tag = c8.selectbox("资产状态", ["使用中", "已处置"], key="add_asset_status")
    maintenance_enabled = c9.checkbox("设置保养/到期日", key="add_maintenance_enabled")
    maintenance_date = None
    if maintenance_enabled:
        maintenance_date = st.date_input("保养/到期日", value=date.today(), key="add_maintenance_date")

    tags_input = st.text_input("自定义标签（逗号分隔）", placeholder="#工作必需,#投资品", key="add_tags")

    selected_category_id = None
    custom_category_name = ""
    custom_logo = "📦"

    if use_custom:
        c5, c6 = st.columns(2)
        custom_category_name = c5.text_input("自定义种类", placeholder="例如：收藏", key="add_custom_category_name")
        custom_logo = c6.text_input("自定义Logo", value="📦", max_chars=4, key="add_custom_logo")
    else:
        category_options = list(category_labels.keys())
        if category_options:
            selected_category_id = st.selectbox(
                "选择种类",
                options=category_options,
                format_func=lambda x: category_labels[x],
                key="add_selected_category",
            )
        else:
            st.warning("当前没有可选种类，请先在上方“分类设置”里添加种类，或勾选“使用自定义种类”。")

    add_submit = st.button("添加", key="add_submit_btn")
    if add_submit:
        if not name.strip():
            st.error("名称不能为空")
        elif price <= 0:
            st.error("价格需大于 0")
        elif use_custom and not custom_category_name.strip():
            st.error("自定义种类不能为空")
        elif not use_custom and selected_category_id is None:
            st.toast("请先添加并选择种类", icon="⚠️")
            st.error("未选择种类，无法添加物品。请先添加种类后再提交。")
        else:
            add_asset(
                user_key=current_user_key,
                name=name,
                category_id=selected_category_id,
                custom_category_name=custom_category_name,
                custom_logo=custom_logo,
                price=price,
                purchase_date=purchase_date,
                frequency_tag=frequency_tag,
                custom_tags=tags_input,
                maintenance_date=maintenance_date,
                asset_status=status_tag,
            )
            st.success("添加成功")
            st.session_state["reset_add_form"] = True
            st.rerun()

st.subheader("📋 物品列表")
f1, f2, f3 = st.columns([2, 1, 1])
search_text = f1.text_input("智能搜索（名称/分类/标签）", key="search_text")
all_category_names = sorted({c["name"] for c in categories})
for r in all_rows:
    all_category_names.append(r.get("category_name", "未分类"))
category_filter = f2.selectbox("分类筛选", ["全部"] + sorted(set(all_category_names)))
price_tag_filter = f3.selectbox("价格标签", ["全部", "低", "中", "高"])

tag_candidates = get_all_tags(all_rows)
adv1, adv2, adv3 = st.columns([1, 1, 2])
tag_filter = adv1.selectbox("标签筛选", ["全部"] + tag_candidates)
enable_start = adv2.checkbox("启用起始日期", key="enable_start_date")
enable_end = adv3.checkbox("启用结束日期", key="enable_end_date")
start_date = adv2.date_input("起始日期", value=date.today(), key="start_date") if enable_start else None
end_date = adv3.date_input("结束日期", value=date.today(), key="end_date") if enable_end else None

effective_search = search_text.strip()
if effective_search:
    add_search_history(current_user_key, effective_search)

suggestions = get_search_suggestions(current_user_key, effective_search) if effective_search else []
if suggestions:
    st.caption("搜索建议：" + " / ".join(suggestions))

history = fetch_search_history(current_user_key)
if history:
    history_pick = st.selectbox("最近搜索（10条）", [""] + history)
    if history_pick and not effective_search:
        effective_search = history_pick

rows = fetch_assets(
    current_user_key,
    search_text=effective_search,
    category_name=category_filter,
    tag_filter=tag_filter,
    price_tag_filter=price_tag_filter,
    start_date=start_date,
    end_date=end_date,
)
display_rows, total_price, total_daily_price = build_display_rows(rows)

if display_rows:
    df_show = pd.DataFrame(display_rows)
    st.dataframe(df_show, use_container_width=True)

    output = BytesIO()
    df_show.to_excel(output, index=False)
    st.download_button(
        label="⬇️ 导出为 Excel",
        data=output.getvalue(),
        file_name="assets_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("暂无匹配物品。")

tag_cloud_data = build_tag_cloud_data(rows)
if tag_cloud_data:
    st.subheader("🏷️ 标签云")
    df_tag = pd.DataFrame(tag_cloud_data)
    fig_tag = px.bar(df_tag, x="标签", y="数量", color="数量", title="标签热度")
    st.plotly_chart(fig_tag, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.metric("当前筛选总价格", f"¥{total_price:,.2f}")
with col_b:
    st.metric("当前筛选总日均价格", f"¥{total_daily_price:,.2f}/天")

health_scores = calculate_health_scores(rows)
st.metric("整体资产健康度", f"{health_scores['整体健康度']:.1f}/100")

bottom_left, bottom_right = st.columns(2)
with bottom_left:
    st.subheader("🕒 最近添加资产（5条）")
    recent_rows = fetch_recent_assets(current_user_key, limit=5)
    if recent_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "名称": r["name"],
                        "分类": f"{r.get('category_logo','📦')} {r.get('category_name','未分类')}",
                        "价格": float(r["price"]),
                        "购入日期": r["purchase_date"],
                    }
                    for r in recent_rows
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("暂无最近资产")

with bottom_right:
    st.subheader("⚠️ 即将到期/预警提醒")
    if warning_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "名称": r["name"],
                        "分类": r.get("category_name", "未分类"),
                        "保养/到期日": r.get("maintenance_date"),
                        "状态": r.get("asset_status", "使用中"),
                    }
                    for r in warning_rows
                ]
            ),
            use_container_width=True,
        )
    else:
        st.success("暂无预警项目")

st.divider()
st.subheader("✏️ 修改 / 🗑️ 删除")

if all_rows:
    options = {
        f"#{r['id']} - {r['name']} ({r.get('category_logo', '📦')} {r.get('category_name', '未分类')})": r
        for r in all_rows
    }
    selected_label = st.selectbox("选择物品", list(options.keys()))
    selected = options[selected_label]

    default_date = datetime.strptime(selected["purchase_date"], "%Y-%m-%d").date()

    edit_col, delete_col = st.columns(2)

    with edit_col:
        with st.form("edit_form"):
            new_name = st.text_input("名称", value=selected["name"])
            new_price = st.number_input("价格(元)", min_value=0.0, step=0.01, value=float(selected["price"]))
            new_date = st.date_input("购入日期", value=default_date)
            new_freq = st.selectbox("使用频率", ["日常", "偶尔", "稀有"], index=["日常", "偶尔", "稀有"].index(selected.get("frequency_tag", "日常")))
            new_status = st.selectbox("资产状态", ["使用中", "已处置"], index=["使用中", "已处置"].index(selected.get("asset_status", "使用中")))
            new_tags = st.text_input("标签", value=selected.get("custom_tags", ""))
            edit_enable_maintenance = st.checkbox("设置保养/到期日", value=bool(selected.get("maintenance_date")))
            edit_maintenance_date = None
            if edit_enable_maintenance:
                init_maintenance = date.today()
                if selected.get("maintenance_date"):
                    init_maintenance = datetime.strptime(selected["maintenance_date"], "%Y-%m-%d").date()
                edit_maintenance_date = st.date_input("保养/到期日", value=init_maintenance)

            use_custom_edit = st.checkbox("使用自定义种类", value=selected.get("category_id") is None)
            edit_category_id = None
            edit_custom_name = ""
            edit_custom_logo = selected.get("category_logo", "📦")

            if use_custom_edit:
                c5, c6 = st.columns(2)
                edit_custom_name = c5.text_input("自定义种类", value=selected.get("category_name", "未分类"))
                edit_custom_logo = c6.text_input("自定义Logo", value=selected.get("category_logo", "📦"), max_chars=4)
            else:
                cat_ids = list(category_labels.keys())
                if cat_ids:
                    default_idx = 0
                    if selected.get("category_id") in cat_ids:
                        default_idx = cat_ids.index(selected.get("category_id"))
                    edit_category_id = st.selectbox(
                        "选择种类",
                        options=cat_ids,
                        index=default_idx,
                        format_func=lambda x: category_labels[x],
                    )
                else:
                    st.warning("当前无可选种类，请先新增种类，或改为“使用自定义种类”。")

            edit_submit = st.form_submit_button("保存修改")
            if edit_submit:
                if not new_name.strip():
                    st.error("名称不能为空")
                elif use_custom_edit and not edit_custom_name.strip():
                    st.error("自定义种类不能为空")
                elif not use_custom_edit and edit_category_id is None:
                    st.toast("请先添加并选择种类", icon="⚠️")
                    st.error("未选择种类，无法保存修改。")
                else:
                    update_asset(
                        user_key=current_user_key,
                        asset_id=selected["id"],
                        name=new_name,
                        category_id=edit_category_id,
                        custom_category_name=edit_custom_name,
                        custom_logo=edit_custom_logo,
                        price=new_price,
                        purchase_date=new_date,
                        frequency_tag=new_freq,
                        custom_tags=new_tags,
                        maintenance_date=edit_maintenance_date,
                        asset_status=new_status,
                    )
                    st.success("修改成功")
                    st.rerun()

    with delete_col:
        st.warning("删除后不可恢复")
        if st.button("删除当前物品", type="primary"):
            delete_asset(current_user_key, selected["id"])
            st.success("删除成功")
            st.rerun()
else:
    st.info("没有可修改或删除的物品。")
