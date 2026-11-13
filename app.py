import streamlit as st
import auth
import graph

import Memory

st.title("客服小助手")

# ① 行李柜里的「用户 → 管家」通讯录（只建一次）
if "memories" not in st.session_state:
    st.session_state.memories = {}
if "user_id" not in st.session_state:
    st.session_state.user_id = None          # 没登录就是 None

# ② 没登录 → 只画登录框，画完就停（走不到下面的聊天代码）
if st.session_state.user_id is None:
    st.subheader("请先登录")
    with st.form("登录"):
        user_id = st.text_input("用户编号", value="u001")
        password = st.text_input("密码", type="password")
        提交 = st.form_submit_button("登录")
    if 提交:
        try:
            auth.登录(user_id.strip(), password)     # 密码不对会抛 登录失败
        except auth.登录失败 as e:
            st.error(str(e))
        else:
            st.session_state.user_id = user_id.strip()
            st.rerun()                              # 刷新这一页，这时候 user_id 有值了
    st.caption("演示账号：u001 / u002，密码 123456（新账号用 POST /register 注册）")
    st.stop()

user_id = st.session_state.user_id

with st.sidebar:
    st.write(f"已登录：**{user_id}**")
    if st.button("退出登录"):
        st.session_state.user_id = None
        st.session_state.memories = {}          # 顺手把管家通讯录也清空
        st.rerun()

# ③ 这个用户还没有管家？给他建一个（文件按编号分家）
if user_id not in st.session_state.memories:
    m = Memory.Memory(path=f"memory_{user_id}.json", user_id=user_id)
    m.load()                                    # 启动读盘
    st.session_state.memories[user_id] = m

# ④ 拿出这个用户的管家（不再写全局 main.memory：多个人同时用也不会串号）
管家 = st.session_state.memories[user_id]

# ⑤ 画历史
for msg in 管家.messages:
    if msg["role"] in ("user", "assistant"):
        st.chat_message(msg["role"]).write(msg["content"])

# ⑥ 聊天（走 LangGraph 版大脑）
q = st.chat_input("有什么可以帮您？")
if q:
    st.chat_message("user").write(q)
    reply = graph.answer(管家, q)
    st.chat_message("assistant").write(reply)
