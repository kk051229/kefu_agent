import streamlit as st
import main

import Memory
import main

st.title("客服小助手")

# ① 行李柜里的「用户 → 管家」通讯录（只建一次）
if "memories" not in st.session_state:
    st.session_state.memories = {}

user_id = st.text_input("你是谁？(输入用户编号，比如 u001)", value="u001")

if user_id:
    # ② 这个用户还没有管家？给他建一个（文件按编号分家）
    if user_id not in st.session_state.memories:
        m = Memory.Memory(path=f"memory_{user_id}.json")      # 填空：路径长什么样？
        m.load()                          # 填空：启动读盘
        st.session_state.memories[user_id] = m

    # ③ 换管家：让 main 的大脑用「这个用户」的管家
    main.memory = st.session_state.memories[user_id]

    # ④ 画历史（和以前一样，但用当前管家的记忆）
    for msg in main.memory.messages:
        if msg["role"] in ("user", "assistant"):
            st.chat_message(msg["role"]).write(msg["content"])

    # ⑤ 聊天（老代码照旧）
    q = st.chat_input("有什么可以帮您？")
    if q:
        st.chat_message("user").write(q)
        reply = main.answer(main.memory.messages, q)
        st.chat_message("assistant").write(reply)
