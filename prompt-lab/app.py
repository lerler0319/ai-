"""Prompt Lab — AI 提示词 A/B 测试平台"""

import json
import os
import sys
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 确保能找到同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from evaluator import generate_report, run_evaluation
from providers import create_provider

# ── Page config ─────────────────────────────────────────────

st.set_page_config(
    page_title="Prompt Lab",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init DB ─────────────────────────────────────────────────

db.init_db()

# ── Sidebar ─────────────────────────────────────────────────

with st.sidebar:
    st.title("🧪 Prompt Lab")
    st.caption("AI 提示词 A/B 测试平台")

    stats = db.get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Prompts", stats["prompts"])
    col2.metric("测试用例", stats["test_cases"])
    col3.metric("评测", stats["evaluations"])

    st.divider()
    page = st.radio(
        "导航",
        ["📊 仪表盘", "📝 提示词管理", "🧪 测试用例", "🚀 运行评测", "📈 评测结果"],
        label_visibility="collapsed",
    )

# ── Helper ──────────────────────────────────────────────────

def render_variable_inputs(variables: list[str], prefix: str = "") -> dict:
    """渲染变量输入框，返回 {var: value} 字典"""
    vals = {}
    for var in variables:
        key = f"{prefix}_{var}"
        vals[var] = st.text_input(f"`{{{var}}}`", key=key)
    return vals


# ═══════════════════════════════════════════════════════════════
# 仪表盘
# ═══════════════════════════════════════════════════════════════

if page == "📊 仪表盘":
    st.title("📊 仪表盘")

    # 统计卡片
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📝 提示词", stats["prompts"])
    c2.metric("🧪 测试用例", stats["test_cases"])
    c3.metric("🚀 评测次数", stats["evaluations"])

    prompts = db.list_prompts()
    test_cases = db.list_test_cases()
    c4.metric("💡 可运行组合", len(prompts) * len(test_cases))

    # 最近评测
    st.subheader("最近评测")
    evals = db.list_evaluations()
    if evals:
        for e in evals[:5]:
            status_icon = "✅" if e["status"] == "completed" else "⏳"
            st.write(f"{status_icon} **{e['name']}** — {e['created_at']} — {e['status']}")
    else:
        st.info("还没有评测记录，去「运行评测」开始第一次测试吧！")

    # 快速开始引导
    st.divider()
    st.subheader("🚀 快速开始")
    st.markdown("""
    1. **添加提示词** → 在「提示词管理」创建你要测试的 prompt 版本
    2. **添加测试用例** → 在「测试用例」添加输入和期望输出
    3. **运行评测** → 选择提示词、测试用例、模型，一键跑分
    4. **查看结果** → 在「评测结果」查看对比报告和可视化图表
    """)

# ═══════════════════════════════════════════════════════════════
# 提示词管理
# ═══════════════════════════════════════════════════════════════

elif page == "📝 提示词管理":
    st.title("📝 提示词管理")

    tab_new, tab_list = st.tabs(["➕ 新建", "📋 列表"])

    with tab_new:
        st.subheader("新建提示词")

        name = st.text_input("名称（方便识别）", key="prompt_name")
        system_prompt = st.text_area(
            "System Prompt",
            height=150,
            placeholder="你是一个专业的客服助手，擅长用简洁的语言解答用户问题...",
            key="prompt_system",
        )
        user_template = st.text_area(
            "User Message 模板",
            height=100,
            value="{input}",
            placeholder="使用 {变量名} 作为占位符，如：请翻译以下内容为{target_lang}：{input}",
            help="用 {变量名} 作为占位符，运行时会被测试用例中的变量值替换",
            key="prompt_template",
        )

        # 自动提取模板中的变量
        import re
        detected_vars = re.findall(r"\{(\w+)\}", user_template)
        variables_str = st.text_input(
            "变量列表（逗号分隔，自动从模板提取）",
            value=", ".join(detected_vars) if detected_vars else "input",
            key="prompt_vars",
        )

        if st.button("💾 保存提示词", use_container_width=True):
            if not name.strip():
                st.error("名称不能为空")
            else:
                vars_list = [v.strip() for v in variables_str.split(",") if v.strip()]
                db.save_prompt(name.strip(), system_prompt, user_template, vars_list)
                st.success(f"已保存「{name}」")
                st.rerun()

    with tab_list:
        prompts = db.list_prompts()
        if not prompts:
            st.info("还没有提示词，先去新建一个吧")
        else:
            for p in prompts:
                with st.expander(f"📝 {p['name']} — ID:{p['id']} — {p['updated_at'][:16]}"):
                    st.caption("**System Prompt**")
                    st.text(p["system_prompt"][:500] + ("..." if len(p["system_prompt"]) > 500 else ""))
                    st.caption("**User Template**")
                    st.code(p["user_template"])
                    st.caption(f"变量: {p['variables']}")

                    col_btn1, col_btn2 = st.columns(2)
                    if col_btn1.button("🗑 删除", key=f"del_p_{p['id']}"):
                        db.delete_prompt(p["id"])
                        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

elif page == "🧪 测试用例":
    st.title("🧪 测试用例")

    tab_new, tab_list = st.tabs(["➕ 新建", "📋 列表"])

    with tab_new:
        st.subheader("新建测试用例")

        prompts = db.list_prompts()
        if prompts:
            # 从已有 prompt 继承变量结构
            ref_prompt = st.selectbox(
                "基于哪个提示词创建？（用于自动匹配变量）",
                options=[p["name"] for p in prompts],
                key="tc_ref_prompt",
            )
            ref = next((p for p in prompts if p["name"] == ref_prompt), prompts[0])
            variables_def = json.loads(ref["variables"]) if isinstance(ref["variables"], str) else ref["variables"]

            st.caption(f"变量（来自「{ref_prompt}」）:")
            var_values = render_variable_inputs(variables_def, prefix="tc")
        else:
            st.warning("请先创建提示词，才能定义对应的测试变量")
            var_values = {"input": st.text_area("输入内容", key="tc_input_fallback")}

        name = st.text_input("用例名称", placeholder="如：简单问候测试", key="tc_name")
        expected = st.text_area(
            "期望输出（可选）",
            height=100,
            placeholder="期望模型输出的参考内容，留空则不做准确率对比",
            key="tc_expected",
        )

        if st.button("💾 保存测试用例", use_container_width=True):
            if not name.strip():
                st.error("名称不能为空")
            elif not var_values:
                st.error("至少需要一个变量值")
            else:
                db.save_test_case(name.strip(), var_values, expected)
                st.success(f"已保存测试用例「{name}」")
                st.rerun()

    with tab_list:
        cases = db.list_test_cases()
        if not cases:
            st.info("还没有测试用例")
        else:
            for c in cases:
                with st.expander(f"🧪 {c['name']} — ID:{c['id']}"):
                    st.caption("**变量值**")
                    st.json(json.loads(c["variables_json"]) if isinstance(c["variables_json"], str) else c["variables_json"])
                    if c["expected_output"]:
                        st.caption("**期望输出**")
                        st.text(c["expected_output"][:300])

                    if st.button("🗑 删除", key=f"del_tc_{c['id']}"):
                        db.delete_test_case(c["id"])
                        st.rerun()

# ═══════════════════════════════════════════════════════════════
# 运行评测
# ═══════════════════════════════════════════════════════════════

elif page == "🚀 运行评测":
    st.title("🚀 运行评测")

    prompts = db.list_prompts()
    test_cases = db.list_test_cases()

    if not prompts or not test_cases:
        st.warning("需要至少 1 个提示词和 1 个测试用例才能运行评测")
        st.stop()

    # 配置区
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("1. 选择提示词")
        selected_prompts = []
        for p in prompts:
            if st.checkbox(f"📝 {p['name']} (ID:{p['id']})", value=True, key=f"sp_{p['id']}"):
                selected_prompts.append(p)

    with col_right:
        st.subheader("2. 选择测试用例")
        selected_cases = []
        for c in test_cases:
            if st.checkbox(f"🧪 {c['name']} (ID:{c['id']})", value=True, key=f"sc_{c['id']}"):
                selected_cases.append(c)

    st.divider()
    st.subheader("3. 配置模型")

    col_p1, col_p2, col_p3 = st.columns(3)

    with col_p1:
        provider_type = st.selectbox(
            "模型供应商",
            ["mock", "anthropic", "openai", "deepseek"],
            format_func=lambda x: {
                "mock": "🖥 Mock（无需 API Key）",
                "anthropic": "🔮 Anthropic Claude",
                "openai": "🤖 OpenAI GPT",
                "deepseek": "🐋 DeepSeek",
            }[x],
        )

    with col_p2:
        model_map = {
            "mock": ["mock-v1"],
            "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-7"],
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        }
        model = st.selectbox("模型", model_map[provider_type])

    with col_p3:
        eval_name = st.text_input("评测名称", value=f"评测 {time.strftime('%m-%d %H:%M')}")

    st.divider()

    # 运行前摘要
    total_runs = len(selected_prompts) * len(selected_cases)
    st.info(f"📊 将运行 **{len(selected_prompts)}** 个提示词 × **{len(selected_cases)}** 个测试用例 = **{total_runs}** 次 API 调用")

    if provider_type != "mock":
        key_var = "ANTHROPIC_API_KEY" if provider_type == "anthropic" else "OPENAI_API_KEY"
        if not os.getenv(key_var):
            st.warning(f"⚠ 未检测到 `{key_var}` 环境变量，请在 .env 文件中配置，或切换到 Mock 模式演示")

    if st.button("🔥 开始评测", use_container_width=True, type="primary"):
        if not selected_prompts:
            st.error("请至少选择一个提示词")
        elif not selected_cases:
            st.error("请至少选择一个测试用例")
        elif not eval_name.strip():
            st.error("请输入评测名称")
        else:
            prompt_ids = [p["id"] for p in selected_prompts]
            case_ids = [c["id"] for c in selected_cases]

            provider_config = {"type": provider_type, "model": model}
            eid = db.create_evaluation(eval_name, prompt_ids, case_ids, provider_config)
            db.update_eval_status(eid, "running")

            try:
                provider = create_provider(provider_type, model)

                progress_bar = st.progress(0, text="准备中...")
                status_text = st.empty()

                def update_progress(done: int, total: int):
                    progress_bar.progress(done / total, text=f"评测中... {done}/{total}")
                    status_text.text(f"已完成 {done}/{total}")

                results = run_evaluation(provider, selected_prompts, selected_cases, update_progress)

                # 保存结果到数据库
                for r in results:
                    db.save_eval_result(
                        eid, r["prompt_id"], r["test_case_id"],
                        r["provider_name"], r["model"],
                        r["output"], r["expected"],
                        r["latency_ms"], r["input_tokens"], r["output_tokens"],
                        r["score"], r["accuracy"], r["format_compliance"], r["efficiency"],
                        r.get("error"),
                    )

                db.update_eval_status(eid, "completed")
                progress_bar.progress(1.0, text="✅ 评测完成！")
                status_text.empty()

                st.success(f"评测完成！共 {len(results)} 条结果")
                st.balloons()

            except Exception as ex:
                db.update_eval_status(eid, "failed")
                st.error(f"评测失败: {ex}")
                import traceback
                st.code(traceback.format_exc())

# ═══════════════════════════════════════════════════════════════
# 评测结果
# ═══════════════════════════════════════════════════════════════

elif page == "📈 评测结果":
    st.title("📈 评测结果")

    evals = db.list_evaluations()

    if not evals:
        st.info("还没有评测记录，先去「运行评测」吧！")
        st.stop()

    selected_eval = st.selectbox(
        "选择评测",
        options=[f"ID:{e['id']} — {e['name']} ({e['status']} @ {e['created_at'][:16]})" for e in evals],
        key="eval_select",
    )

    if selected_eval:
        eid = int(selected_eval.split("—")[0].replace("ID:", "").strip())
        eval_info = db.get_evaluation(eid)
        results = db.get_eval_results(eid)

        if not results:
            st.warning("该评测没有结果数据")
            st.stop()

        # 评测元信息
        provider_cfg = json.loads(eval_info["provider_config"]) if isinstance(eval_info["provider_config"], str) else eval_info["provider_config"]
        st.caption(f"模型: {provider_cfg.get('type', '?')}/{provider_cfg.get('model', '?')} | 状态: {eval_info['status']} | 时间: {eval_info['created_at']}")

        # 生成报告
        report = generate_report(results)

        # ── 排名卡片 ──
        st.subheader("🏆 Prompt 排名")
        if report.get("by_prompt"):
            cols = st.columns(len(report["by_prompt"]))
            for i, item in enumerate(report["by_prompt"]):
                prompt_info = db.get_prompt(item["prompt_id"])
                prompt_name = prompt_info["name"] if prompt_info else f"ID:{item['prompt_id']}"
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                cols[i].metric(
                    f"{medal} {prompt_name}",
                    f"{item['avg_score']}分",
                    delta=f"{item['avg_latency_ms']:.0f}ms 平均延迟",
                )

        # ── 图表 ──
        st.divider()
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("📊 平均分数对比")
            chart_data = []
            for item in report["by_prompt"]:
                prompt_info = db.get_prompt(item["prompt_id"])
                name = prompt_info["name"] if prompt_info else f"ID:{item['prompt_id']}"
                chart_data.append({"Prompt": name, "平均分": item["avg_score"]})
            if chart_data:
                df = pd.DataFrame(chart_data)
                fig = px.bar(df, x="Prompt", y="平均分", color="平均分",
                             color_continuous_scale="Blues", text_auto=True)
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.subheader("⏱ 平均延迟 (ms)")
            chart_data2 = []
            for item in report["by_prompt"]:
                prompt_info = db.get_prompt(item["prompt_id"])
                name = prompt_info["name"] if prompt_info else f"ID:{item['prompt_id']}"
                chart_data2.append({"Prompt": name, "延迟(ms)": item["avg_latency_ms"]})
            if chart_data2:
                df2 = pd.DataFrame(chart_data2)
                fig2 = px.bar(df2, x="Prompt", y="延迟(ms)", color="延迟(ms)",
                              color_continuous_scale="Reds", text_auto=True)
                fig2.update_traces(textposition="outside")
                st.plotly_chart(fig2, use_container_width=True)

        # ── 详细结果表 ──
        st.divider()
        st.subheader("📋 详细结果")

        # 构建表格数据
        table_rows = []
        for r in results:
            prompt_info = db.get_prompt(r["prompt_id"])
            case_info = db.get_test_case(r["test_case_id"])
            table_rows.append({
                "Prompt": prompt_info["name"] if prompt_info else f"ID:{r['prompt_id']}",
                "测试用例": case_info["name"] if case_info else f"ID:{r['test_case_id']}",
                "输出": r["output"][:100] + ("..." if len(r.get("output", "") or "") > 100 else ""),
                "综合分": r["score"],
                "准确率": r.get("accuracy", "—"),
                "格式": r.get("format_compliance", "—"),
                "效率": r.get("efficiency", "—"),
                "延迟(ms)": r["latency_ms"],
                "错误": r.get("error") or "",
            })

        df_table = pd.DataFrame(table_rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        # ── 单条结果展开 ──
        st.divider()
        st.subheader("🔍 展开查看输出")

        for r in results:
            prompt_info = db.get_prompt(r["prompt_id"])
            case_info = db.get_test_case(r["test_case_id"])
            pname = prompt_info["name"] if prompt_info else f"ID:{r['prompt_id']}"
            cname = case_info["name"] if case_info else f"ID:{r['test_case_id']}"

            with st.expander(f"{pname} × {cname} — {r['score']}分"):
                if r.get("error"):
                    st.error(r["error"])
                st.text_area("模型输出", value=r["output"] or "", height=200, disabled=True)
                if r.get("expected"):
                    st.text_area("期望输出", value=r["expected"] or "", height=100, disabled=True)
                st.caption(f"延迟: {r['latency_ms']:.0f}ms | Input: {r['input_tokens']}t | Output: {r['output_tokens']}t")

        # 删除评测
        if st.button("🗑 删除此评测", type="secondary"):
            db.delete_evaluation(eid)
            st.rerun()

# ── Footer ───────────────────────────────────────────────────

st.sidebar.divider()
st.sidebar.caption("Prompt Lab v1.0 — 你的 AI 提示词工程工具箱")
st.sidebar.caption("支持 Mock / Anthropic / OpenAI / DeepSeek")
