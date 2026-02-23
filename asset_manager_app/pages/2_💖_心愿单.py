import pandas as pd
import streamlit as st

from core import (
    add_wish,
    delete_wish,
    fetch_categories,
    fetch_wishes,
    init_db,
    normalize_user_key,
    update_wish_status,
)

st.set_page_config(page_title="心愿单", page_icon="💖", layout="wide")
init_db()

st.title("💖 心愿单")
st.caption("记录想买的物品，并跟踪优先级与状态")

current_user_key = normalize_user_key(st.session_state.get("current_user_key", "默认用户"))
current_user_name = st.session_state.get("current_user_name", "默认用户")
st.info(f"当前用户：{current_user_name}")

categories = fetch_categories(current_user_key)
cat_options = {f"{c['logo']} {c['name']}": c for c in categories}

with st.expander("➕ 添加心愿", expanded=True):
    with st.form("wish_add_form", clear_on_submit=True):
        name = st.text_input("物品名称", placeholder="例如：iPad mini")
        c1, c2 = st.columns(2)
        cat_label = c1.selectbox("参考分类", ["自定义"] + list(cat_options.keys()))
        target_price = c2.number_input("目标价格(元)", min_value=0.0, step=0.01)

        if cat_label == "自定义":
            c3, c4 = st.columns(2)
            category_name = c3.text_input("自定义种类", placeholder="例如：电子产品")
            category_logo = c4.text_input("自定义Logo", value="💡", max_chars=4)
        else:
            category_name = cat_options[cat_label]["name"]
            category_logo = cat_options[cat_label]["logo"]

        c5, c6 = st.columns(2)
        priority = c5.selectbox("优先级", ["高", "中", "低"], index=1)
        note = c6.text_input("备注", placeholder="例如：等 618 再买")

        submitted = st.form_submit_button("添加心愿")
        if submitted:
            if not name.strip():
                st.error("物品名称不能为空")
            else:
                add_wish(current_user_key, name, category_name, category_logo, target_price, priority, note)
                st.success("已加入心愿单")
                st.rerun()

st.divider()

f1, f2 = st.columns([2, 1])
search_text = f1.text_input("搜索心愿（名称/分类/备注）")
status_filter = f2.selectbox("状态筛选", ["全部", "想买", "已购入", "已放弃"])

wishes = fetch_wishes(current_user_key, search_text=search_text, status=status_filter)

if not wishes:
    st.info("暂无匹配心愿。")
    st.stop()

show_df = pd.DataFrame(
    [
        {
            "物品": w["name"],
            "分类": f"{w['category_logo']} {w['category_name']}",
            "目标价格(元)": round(float(w["target_price"]), 2),
            "优先级": w["priority"],
            "状态": w["status"],
            "创建日期": w["created_date"],
            "备注": w.get("note", ""),
        }
        for w in wishes
    ]
)

st.dataframe(show_df, use_container_width=True)

st.subheader("状态管理 / 删除")
options = {f"#{w['id']} - {w['name']} ({w['status']})": w for w in wishes}
selected_label = st.selectbox("选择一条心愿", list(options.keys()))
selected = options[selected_label]

c1, c2 = st.columns(2)
with c1:
    new_status = st.selectbox("更新状态", ["想买", "已购入", "已放弃"], index=["想买", "已购入", "已放弃"].index(selected["status"]))
    if st.button("保存状态"):
        update_wish_status(current_user_key, selected["id"], new_status)
        st.success("状态已更新")
        st.rerun()

with c2:
    st.warning("删除后不可恢复")
    if st.button("删除该心愿", type="primary"):
        delete_wish(current_user_key, selected["id"])
        st.success("已删除")
        st.rerun()
