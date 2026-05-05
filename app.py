import sys
import os
sys.path.insert(0, "backend")

import streamlit as st
import pandas as pd


from core.ai_service import AIService
from core.prompts import INSIGHT_GENERATOR, CALENDAR_PARSE, RAG_ENHANCE
from core.database import init_db, add_record, get_records_by_type, _now
from core.database import add_message, get_messages_by_conversation,add_task
from core.feishu_api import FeishuClient
from core.rag_engine import RAGEngine
from core.agent import Agent, ToolCallingAgent
from core.enhanced_analytics import AnomalyDetector, PatternRecognizer, CorrelationAnalyzer, LearningTracker

# ---------- 页面设置 ----------
st.set_page_config(
    page_title="Kiyo - Your AI  Companion",
    page_icon="🌿",
    layout="centered"
)

# init
if "ai" not in st.session_state:
    st.session_state.ai = AIService()

if "rag" not in st.session_state:
    st.session_state.rag = RAGEngine()

if "conv_id" not in st.session_state:
    st.session_state.conv_id = 1

if "messages" not in st.session_state:
    db_msgs = get_messages_by_conversation(st.session_state.conv_id)
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"] } for m in db_msgs
    
    ]
if "active_panel" not in st.session_state:
    st.session_state.active_panel = None

if "agent" not in st.session_state:
    st.session_state.agent = Agent()

if "tool_agent" not in st.session_state:
    st.session_state.tool_agent = ToolCallingAgent()

# CSS
st.markdown("""
<style>
    /* 整体内容区域向右平移，减少右侧空白 */
    .block-container {
        padding-left: 4rem !important;
        padding-right: 0.5rem !important;
        max-width: 900px;
    }

    /* 导航按钮样式 */
    div[data-testid="stHorizontalBlock"] button {
        border-radius: 12px;
        background-color: #EDD7AD;
        color: #474340;
        border: 1px solid rgba(0,0,0,0.05);
        transition: all 0.2s ease;
        font-size: 14px;
        padding: 8px 0;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background-color: #B09E84;
        color: #EDD7AD;
    }

    /* Kiyo 头像圆形框 */
    .kiyo-avatar {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background-color: #B09E84;
        color: #EDD7AD;
        font-size: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 16px auto;
    }
    /* 输入框聚焦时边框颜色改成 #10319F */
        [data-testid="stChatInput"] textarea:focus {
        border-color: #10319F !important;
        box-shadow: 0 0 0 1px #10319F !important;
        outline: none !important;
    }
    input:focus, textarea:focus {
        border-color: #10319F !important;
        outline: none !important;
    }
    .insight-card {
        background: #FFFFFF;
        border-radius: 14px;
        padding: 20px;
        border: 1px solid rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

# top 
cols = st.columns([1, 1, 1, 1, 1, 1])  # 去掉右侧空白列
with cols[0]:
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.active_panel = "chat"
with cols[1]:
    if st.button("🍽️ Record", use_container_width=True):
        st.session_state.active_panel = "record"
with cols[2]:
    if st.button("📊 Dashboard", use_container_width=True):
        st.session_state.active_panel = "dashboard"
with cols[3]:
    if st.button("📝 Learn", use_container_width=True):
        st.session_state.active_panel = "learning"
with cols[4]:
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.active_panel = "settings"
with cols[5]:
    if st.button("📅 Calendar", use_container_width=True):
        st.session_state.active_panel = "calendar"

                 
st.divider()

# active panel
if st.session_state.active_panel == "record":
    st.subheader("🍽️ Record Your Moment")
    with st.form("record_form"):
        record_type = st.selectbox("Type", ["meal", "emotion", "energy", "note"])
        content = st.text_area("What's on your mind?")
        score = st.slider("Rating (1-5)", 1, 5, 3)

        if st.form_submit_button("Save"):
            rid = add_record(record_type, content, score)

            # AI analysis
            from core.ai_service import AIService
            ai = AIService()

            analysis = st.session_state.ai.analyze_record(content)
            if analysis:
                emotion = analysis.get("emotion", "unknown")
                summary = analysis.get("summary", "")
                st.info(f"💡 {summary} (Mood: {emotion})")

            st.success("Saved!")

            try:
                import json
                feishu = FeishuClient()
                                # 根据记录类型选择卡片样式
                card_theme_map = {
                    "meal": {"color": "orange", "emoji": "🍽️", "label": "饮食记录"},
                    "emotion": {"color": "purple", "emoji": "💭", "label": "情绪记录"},
                    "energy": {"color": "yellow", "emoji": "⚡", "label": "能量记录"},
                    "note": {"color": "blue", "emoji": "📝", "label": "笔记记录"},
                }
                theme = card_theme_map.get(record_type, {"color": "blue", "emoji": "📌", "label": "新记录"})
                
                # 构建评分星星
                stars = "★" * score + "☆" * (5 - score)
                
                import datetime
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                
                card_content = json.dumps({
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": f"{theme['emoji']} Kiyo {theme['label']}"},
                        "template": theme["color"]
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**类型**:{theme['emoji']} {record_type}\n**评分**:{stars} ({score}/5)"
                            }
                        },
                        {"tag": "hr"},
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"💬 {content[:150]}{'...' if len(content) > 150 else ''}"
                            }
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {"tag": "plain_text", "content": f"🕐 {now_str}  ·  来自你的 Kiyo 学习伴侣"}
                            ]
                        }
                    ]
                })
                
                feishu_open_id = os.getenv("FEISHU_OPEN_ID", "")
                if feishu_open_id:
                    feishu.send_message(
                        receive_id=feishu_open_id,
                        content=card_content,
                        receive_id_type="open_id"
                    )
                    st.caption("✅ 飞书卡片已发送")
                else:
                    st.caption("⚠️ 飞书通知跳过：未配置 FEISHU_OPEN_ID")
            except Exception as e:
                st.caption(f"⚠️ 飞书通知异常：{e}")

    st.subheader("Recent Records")
    records = get_records_by_type(record_type, 10)
    for r in records:
        st.caption(f"{r['created_at']} | Score: {r['score']}")
        st.write(r['content'])
        st.divider()

elif st.session_state.active_panel == "dashboard":
    st.subheader("📊 Your Dashboard")
    from core.analytics import Analytics

    stats = Analytics.weekly_summary()
    for s in stats:
        st.metric(f"This Week {s['type']}", f"{s['count']} times", f"Avg {s['avg_score']}")

    st.markdown("---")
    st.subheader("📈 Mood Trend (7 Days)")
    mood = Analytics.mood_trend_for_chart()
    if mood and mood.get("dates"):
        chart_data = pd.DataFrame({"date": mood["dates"], "mood": mood["scores"]})
        st.line_chart(chart_data.set_index("date"))

    st.subheader("🍽️ Meal Frequency (7 Days)")
    meal = Analytics.meal_freq_for_chart()
    if meal and meal.get("dates"):
        meal_data = pd.DataFrame({"date": meal["dates"], "meal": meal["counts"]})
        st.bar_chart(meal_data.set_index("date"))
    
    st.markdown("---")
    st.subheader("🔮 AI 洞察")

    if st.button("✨ 生成本周洞察"):
        with st.spinner("kiyo 正在分析你的数据 "):
            from core.analytics import Analytics
            records = Analytics.get_weekly_records()

            if not records:
                st.warning("本周还没有记录，先记录一些内容吧~")
            else:
                records_text = ""
                for r in records:
                    emoji = {"meal":"🍽️","emotion":"💭","energy":"⚡","note":"📝"}.get(r["type"],"📌")
                    records_text += f"- {emoji} [{r['type']}] {r['content']} (评分:{r['score']}/5, 时间:{r['time']})\n"

                stats = Analytics.weekly_summary()
                stats_text = "\n".join([f"- {s['type']}: {s['count']}次, 均分{s['avg_score']}/5" for s in stats])

                # Prompt!
                insight_prompt = INSIGHT_GENERATOR(records_text, stats_text)
                insight = st.session_state.ai.chat(insight_prompt)

                st.success("本周洞察已生成 ✨")
                st.markdown(f"""
                <div style="background:#FFF2DF; border-radius:14px; padding:20px; border:1px solid rgba(0,0,0,0.04);">
                    <p style="color:#474340; font-size:15px; line-height:1.8; white-space:pre-wrap;">{insight}</p>
                </div>
                """, unsafe_allow_html=True)

                from core.database import add_memory
                add_memory(topic_id=1, content=f"[本周洞察] {insight[:200]}", source="auto")

    st.markdown("---")
    st.subheader("🚨 异常检测")

    if st.button("🔍 检测评分异常"):
        with st.spinner("分析中..."):
            anomalies = AnomalyDetector.detect_score_anomalies("emotion", days=30)
            if anomalies:
                st.warning(f"发现 {len(anomalies)} 个异常点")
                for a in anomalies[:5]:
                    st.caption(f"{a['created_at'][:10]} | 评分: {a['score']} (Z-score: {a['z_score']})")
            else:
                st.success("未发现明显异常")

    st.subheader("📅 周模式")
    pattern = PatternRecognizer.find_weekly_pattern("emotion")
    if pattern:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        scores = [pattern[d]["avg_score"] for d in days]
        counts = [pattern[d]["count"] for d in days]

        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(pd.DataFrame({"评分": scores}, index=days))
        with col2:
            st.bar_chart(pd.DataFrame({"记录数": counts}, index=days))

    st.subheader("🔗 相关性分析")
    corr = CorrelationAnalyzer.analyze_correlation(days=30)
    for name, data in corr.items():
        label = name.replace("_", " vs ").title()
        st.caption(f"{label}: {data['coefficient']} ({data['interpretation']})")



elif st.session_state.active_panel == "learning":
    st.subheader("📝 Learning Plan")
    idea = st.text_input("What do you want to learn?", placeholder="e.g., system architecture design")
    if st.button("✨ AI Break It Down"):
        with st.spinner("Kiyo is planning..."):
            tasks = st.session_state.ai.generate_learning_plan(idea)
            if not tasks:
                st.warning("AI 没有返回任务，请换个方式描述你的学习目标试试。")
            else:
                count = 0
                for t in tasks:

                    if not isinstance(t, dict):
                        continue
                    name = t.get('name') or t.get('title', 'Untitled')
                    desc = t.get('description', '')
                    mins = t.get('estimated_minutes') or t.get('duration', 25)
                    try:
                        mins = int(float(mins))
                    except:
                        mins = 25
                    add_task(name=name, description=desc, estimated_minutes=mins)
                    st.markdown(f"**✅ {count+1}. {name}** — {desc} ({mins} min)")
                    count += 1
                st.success(f"Created {count} tasks!")

elif st.session_state.active_panel == "settings":
    st.subheader("⚙️ Settings")
    st.text_input("Doubao API Key", type="password")
    st.number_input("Default Learning Duration (min)", 5, 120, 25)
    st.button("Save Settings")

    st.markdown("---")
    st.subheader("📂 Knowledge Base Management")

    if st.button("📊 Dase status Check"):
        stats = st.session_state.rag.get_collection_stats()
        st.info(f"Number of knowledge base entries:{stats['count']}")

    uploaded_file = st.file_uploader(
        "Update documents to knowledge base(PDF/MD/TXT)",
        type=["pdf", "md", "txt"]
    )

    if uploaded_file:
        st.info(f"Processing: {uploaded_file.name}...")

        import tempfile
        import os

        suffix = f".{uploaded_file.name.split('.')[-1]}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix)as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            if uploaded_file.name.endswith(".pdf"):
                st.session_state.rag.add_pdf(tmp_path)
                st.success(f"✅ PDF Added !: {uploaded_file.name}")

            else:
                # md/txt
                with open(tmp_path, "r", encoding="utf-8")as f:
                    text = f.read()
                st.session_state.rag.add_text(
                    text,
                    metadata={"source": uploaded_file.name, "type": "file"}
                )
                st.success(f"TXT added!: {uploaded_file.name}")

        except Exception as e:
            st.error(f"❌ Processing Failed: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    st.markdown("---")
    st.subheader("🧠 学习档案 & 记忆")

    if st.button("📋 查看全部记忆"):
        from core.database import get_all_memories
        memories = get_all_memories()
        if not memories:
            st.info("暂无记忆记录。Kiyo 会在对话和洞察生成中自动为你记录。")
        else:
            for m in memories[: 20]:
                source_tag = "🤖 自动" if m.get('source') == 'auto' else "✍️ 手动"
                with st.expander(f"{source_tag} | {m['created_at']}"):
                    st.write(m['content'])

    st.markdown("---")
    st.subheader("🧠 技能树进度")

    progress = LearningTracker.get_skill_progress()
    for category, data in progress.items():
        st.markdown(f"**{category}** ({data['completed']}/{data['total']})")

        cols = st.columns(len(data["skills"]) if data["skills"] else 1)
        for i, skill in enumerate(data.get("skills", [])):
            with cols[i % len(cols)]:
                icon = "✅" if skill["completed"] else "⬜"
                st.caption(f"{icon} {skill['name']}")

    st.markdown("---")
    st.subheader("🏆 成就系统")

    achievements = LearningTracker.get_achievements()
    for ach in achievements:
        icon = ach["icon"]
        status = "✅" if ach["unlocked"] else "🔒"
        st.markdown(f"{icon} {ach['name']} {status}")
        st.caption(f"_{ach['description']}_")

elif st.session_state.active_panel == "calendar":
    st.subheader("📅 日程助手")
    
    with st.form("calendar_form"):
        event_text = st.text_area(
            "告诉我你想安排什么？",
            placeholder="例如:明天下午3点复习系统架构,2小时",
            height=80
        )
        submitted = st.form_submit_button("✨ 创建日程")
    
    if submitted and event_text.strip():
        with st.spinner("Kiyo 正在为你安排..."):
            import json
            parse_prompt = CALENDAR_PARSE(event_text)
            result = st.session_state.ai.chat(parse_prompt)
            
            try:
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    event_data = json.loads(json_match.group())
                    
                    title = event_data.get("title", "未命名事件")
                    date = event_data.get("date") or "2026-04-30"
                    time = event_data.get("time") or "09:00"
                    duration = event_data.get("duration_minutes") or 60
                    
                    start_time = f"{date}T{time}:00"
                    from datetime import datetime, timedelta
                    start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
                    end_dt = start_dt + timedelta(minutes=int(duration))
                    end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
                    
                    try:
                        feishu = FeishuClient()
                        response = feishu.create_calendar_event(
                            summary=title,
                            start_time=start_time,
                            end_time=end_time
                        )
                        
                        if response and response.get("code") == 0:
                            st.success(f"✅ 已创建日程：{title}")
                            st.info(f"📅 {date} {time} | ⏱️ {duration} 分钟")
                            try:
                                feishu_open_id = os.getenv("FEISHU_OPEN_ID", "")
                                if feishu_open_id:
                                    feishu.send_message(
                                        receive_id=feishu_open_id,
                                        content=f"📅 新日程：{title}\n⏰ {date} {time}\n⏱️ {duration}分钟",
                                        receive_id_type="open_id"
                                    )
                            except:
                                pass
                        else:
                            st.warning("⚠️ 飞书日历创建失败，请检查权限配置")
                            st.caption(f"调试信息：{response}")
                    
                    except Exception as e:
                        st.success(f"✅ 已解析日程：{title}")
                        st.info(f"📅 {date} {time} | ⏱️ {duration} 分钟")
                        st.caption("⚠️ 飞书日历同步跳过，请检查网络或权限")
                
                else:
                    st.warning("未能解析日程信息，请换个方式描述")
                    st.caption(f"AI 返回：{result[:200]}")
            
            except Exception as e:
                st.error(f"解析失败：{e}")
                st.caption(f"AI 返回：{result[:200]}")

elif st.session_state.active_panel == "voice":
    st.subheader("🎙️ Voice input")
    st.caption("请点击下方麦克风按钮开始说话,Kiyo在听...")

    audio_value = st.audio_input("点击录音")
    if audio_value:
        st.audio(audio_value)
        st.info("正在识别你的语音...")

        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_value.read())
            tmp_path = tmp.name

        recognized_text = "(语音模块待接入...)"
        if recognized_text:
            st.success(f"识别结果: {recognized_text}")

            from core.ai_service import AIService
            ai = AIService()
            analysis = ai.analyze_record(recognized_text)
            if analysis:
                st.info(f"💡 AI 分析：{analysis.get('summary', '')} (情绪: {analysis.get('emotion', 'unknown')})")


else:
    if not st.session_state.messages:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='kiyo-avatar'>🌿</div>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center; color:#474340;'>Welcome back, Celandine</h1>", unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        card_cols = st.columns(5, gap="small")
        with card_cols[0]:
            if st.button("📖\nContinue", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Let's continue where I left off."})
                st.rerun()
        with card_cols[1]:
            if st.button("✨\nNew Topic", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "I want to learn something new."})
                st.rerun()
        with card_cols[2]:
            if st.button("🎯\nMake Plan", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Help me create a study plan."})
                st.rerun()
        with card_cols[3]:
            if st.button("📝\nQuiz Me", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Give me a practice question."})
                st.rerun()
        with card_cols[4]:
            if st.button("🧭\nStyle Quiz", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Let's do a learning style quiz."})
                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    use_agent = st.checkbox("🤖 启用多步推理模式", value=False)

    user_input = st.chat_input("Message @ attach file")
    if user_input:

        with st.chat_message("user", avatar="🧑‍💻"):
            st.write(user_input)
        add_message(st.session_state.conv_id, "user", user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        contexts = st.session_state.rag.query(user_input)
        context_text = "\n---\n".join(contexts) if contexts else ""

        if context_text:
            enhanced_input = RAG_ENHANCE(context_text, user_input)
        else:
            enhanced_input = user_input

        with st.chat_message("assistant", avatar="🌿"):
            with st.spinner("Kiyo is thinking..."):
                if use_agent:
                    reply = st.session_state.agent.think(user_input)
                    thoughts = st.session_state.agent.get_thought_chain()
                    
                    if thoughts and len(thoughts) > 1:
                        with st.expander("🧠 思考过程"):
                            for t in thoughts:
                                st.markdown(f"**Step {t['step']}**: {t.get('response', '')[:200]}...")
                else:
                    reply = st.session_state.ai.chat(enhanced_input)
                st.write(reply)

        add_message(st.session_state.conv_id, "assistant", reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
