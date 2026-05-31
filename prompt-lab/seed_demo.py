"""Seed demo data for HR presentation."""
import json
import sys
sys.path.insert(0, ".")

import database as db
from providers import MockProvider
from evaluator import run_evaluation

db.init_db()

# ── 清理旧数据 ──
for e in db.list_evaluations():
    db.delete_evaluation(e["id"])

# ══════════════════════════════════════════════════════════════
# 3 个提示词：同一客服场景，质量从低到高
# ══════════════════════════════════════════════════════════════

# 版本 A：最简单的 prompt（测试它会不会很差）
db.save_prompt(
    "版本A-基础指令",
    "You are a customer service assistant.",
    "回答用户问题：{input}",
    ["input"],
)

# 版本 B：加了角色和规则（中等质量）
db.save_prompt(
    "版本B-角色扮演",
    "你是一个专业的电商客服专员。请用礼貌、亲切的语气回复用户。回答尽量简洁，不超过200字。如果遇到投诉，先道歉再提供解决方案。",
    "用户说：{input}\n\n请回复：",
    ["input"],
)

# 版本 C：最佳实践 prompt（结构化 + Few-shot + 约束）
db.save_prompt(
    "版本C-结构化最佳实践",
    """你是一位资深电商客服专家，有10年经验。回复时必须遵守以下规则：

1. 先共情用户感受
2. 清晰回答核心问题（用列表形式，不超过3点）
3. 最后给出下一步建议

**语气要求**：温暖但专业，不要过度道歉。

**格式要求**：每段之间空一行，重点内容用 **加粗** 标记。""",
    "## 用户问题\n{input}\n\n## 回复要求\n请按上述规则生成回复，控制在200字以内。",
    ["input"],
)

# ══════════════════════════════════════════════════════════════
# 5 个测试用例：覆盖常见客服场景
# ══════════════════════════════════════════════════════════════

test_cases = [
    {
        "name": "简单商品咨询",
        "vars": {"input": "请问这款蓝牙耳机的续航时间是多久？"},
        "expected": "这款蓝牙耳机单次续航约8小时，配合充电盒可达32小时。具体参数可查看商品详情页哦。",
    },
    {
        "name": "物流查询",
        "vars": {"input": "我3天前下的单，怎么还没到？订单号#2024001"},
        "expected": "非常抱歉让您久等了。已为您查询，订单#2024001预计明天送达。物流延迟给您带来不便，我们已催促快递优先配送。",
    },
    {
        "name": "退换货咨询",
        "vars": {"input": "买的衣服尺码不合适，可以换吗？已经拆了吊牌。"},
        "expected": "您好，已拆吊牌不影响退换货。请在订单页面提交换货申请，选择合适尺码，我们收到退回商品后48小时内为您发出新品。",
    },
    {
        "name": "商品质量问题投诉",
        "vars": {"input": "收到的手机屏幕有划痕！新买的就这样，太失望了！"},
        "expected": "非常抱歉给您带来不好的体验！我们已为您安排：1. 立即补发一台全新手机，无需退回瑕疵品；2. 赠送50元店铺优惠券。请将瑕疵照片发送给我们，以便内部追责。",
    },
    {
        "name": "优惠券使用问题",
        "vars": {"input": "结算时输入优惠码显示已过期，但我昨天才领的？"},
        "expected": "抱歉给您带来困扰。请您提供优惠码信息，我帮您核实。如确实在有效期内，我们会手动为您补差价。",
    },
]

for tc in test_cases:
    db.save_test_case(tc["name"], tc["vars"], tc["expected"])

# ══════════════════════════════════════════════════════════════
# 运行一次 Mock 评测，产出结果数据
# ══════════════════════════════════════════════════════════════

prompts = db.list_prompts()
cases = db.list_test_cases()

provider = MockProvider("mock-v1")
eid = db.create_evaluation(
    "客服提示词对比评测 (演示)",
    [p["id"] for p in prompts],
    [c["id"] for c in cases],
    {"type": "mock", "model": "mock-v1"},
)
db.update_eval_status(eid, "running")

print(f"评测ID: {eid}, {len(prompts)} prompts × {len(cases)} cases = {len(prompts)*len(cases)} runs")

results = run_evaluation(provider, prompts, cases)

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

# 打印摘要
from evaluator import generate_report
report = generate_report(results)
print("\n=== 评测结果摘要 ===")
for item in report["by_prompt"]:
    p = db.get_prompt(item["prompt_id"])
    print(f"  {p['name']}: 平均分={item['avg_score']}, 延迟={item['avg_latency_ms']:.0f}ms")

print(f"\n评测完成！{len(results)} 条结果已入库。")
