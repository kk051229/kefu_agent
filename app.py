import streamlit as st
import main

st.title("乐乐客服助手")

# ① 第一次打开网页时，让大脑读盘（想起以前的事）
if "started" not in st.session_state:
    main.memory.load()          # 填空 1：读盘的方法叫什么？
    st.session_state.started = True

# ② 把历史对话画成气泡
for msg in main.memory.messages:
    if msg["role"] in ("user", "assistant"):
        st.chat_message(msg["role"]).write(msg["content"])   # 填空 2/3：用消息的什么字段？

# ③ 聊天框 + 调大脑
q = st.chat_input("臭乐乐,你又有啥事找我")
if q:
    st.chat_message("user").write(q)
    reply = main.answer(main.memory.messages, q)
    st.chat_message("assistant").write(reply)
