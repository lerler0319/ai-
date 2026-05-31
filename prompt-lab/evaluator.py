"""Core evaluation engine — runs prompts against test cases and scores results."""

import json
import re
from dataclasses import dataclass, field

from providers import BaseProvider, LLMResponse


@dataclass
class EvalScore:
    accuracy: float       # 0–100, 基于关键词匹配和语义简单评估
    format_compliance: float  # 0–100, 是否满足格式要求
    efficiency: float     # 0–100, 基于延迟和 token 消耗
    overall: float        # 0–100, 综合加权

    details: dict = field(default_factory=dict)


def render_prompt(template: str, variables: dict) -> str:
    """用变量填充 prompt 模板。支持 {var} 语法。"""
    result = template
    for key, val in variables.items():
        result = result.replace(f"{{{key}}}", str(val))
    return result


def score_accuracy(output: str, expected: str) -> float:
    """简单的准确率评分：关键词重叠 + 长度合理性"""
    if not expected.strip():
        return 70.0  # 没有期望输出时给基准分

    # 关键词匹配
    expected_words = set(re.findall(r"[\w一-鿿]+", expected.lower()))
    output_words = set(re.findall(r"[\w一-鿿]+", output.lower()))

    if not expected_words:
        return 70.0

    overlap = expected_words & output_words
    keyword_score = len(overlap) / len(expected_words) * 100

    # 长度合理性（输出不应太短）
    len_ratio = min(len(output.split()) / max(len(expected.split()), 1), 2.0)
    len_score = min(len_ratio * 50, 100)

    return round(keyword_score * 0.7 + len_score * 0.3, 1)


def score_format(output: str, expected_format: str | None = None) -> float:
    """评估格式合规性：检查结构化输出元素"""
    score = 100.0

    # 检查是否有明显的截断
    if output.endswith(("...", "等等", "……")) and len(output) < 30:
        score -= 20

    # 检查是否有结构化标记（列表、标题等）
    has_structure = any(marker in output for marker in ["1.", "- ", "•", "**", "##", "|", "```"])
    if not has_structure and len(output) > 200:
        # 长输出没有结构扣分
        score -= 15

    return max(score, 0)


def score_efficiency(latency_ms: float, input_tokens: int, output_tokens: int) -> float:
    """效率评分：延迟越低越好，但不过度惩罚"""
    score = 100.0

    if latency_ms > 5000:
        score -= 30
    elif latency_ms > 2000:
        score -= 15
    elif latency_ms > 1000:
        score -= 5

    # Token 浪费惩罚
    if output_tokens > input_tokens * 3:
        score -= 10

    return max(score, 0)


def compute_score(response: LLMResponse, expected: str) -> EvalScore:
    """综合计算一条结果的评分"""
    if response.error:
        return EvalScore(0, 0, 0, 0, {"error": response.error})

    acc = score_accuracy(response.content, expected)
    fmt = score_format(response.content)
    eff = score_efficiency(response.latency_ms, response.input_tokens, response.output_tokens)

    overall = round(acc * 0.50 + fmt * 0.20 + eff * 0.30, 1)

    return EvalScore(
        accuracy=acc,
        format_compliance=fmt,
        efficiency=eff,
        overall=overall,
        details={
            "output_preview": response.content[:200],
            "latency_ms": response.latency_ms,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        },
    )


def run_single(
    provider: BaseProvider,
    system_prompt: str,
    user_template: str,
    variables: dict,
    expected: str,
) -> tuple[LLMResponse, EvalScore]:
    """运行单次评测：渲染 prompt → 调 LLM → 评分"""
    user_msg = render_prompt(user_template, variables)
    response = provider.generate(system_prompt, user_msg)
    score = compute_score(response, expected)
    return response, score


def run_evaluation(
    provider: BaseProvider,
    prompts: list[dict],
    test_cases: list[dict],
    progress_callback=None,
) -> list[dict]:
    """
    运行完整评测批次。
    prompts: [{"id": 1, "system_prompt": "...", "user_template": "...", "variables": [...]}, ...]
    test_cases: [{"id": 1, "variables_json": "{...}", "expected_output": "...", "name": "..."}, ...]
    返回: [result_dict, ...]
    """
    results = []
    total = len(prompts) * len(test_cases)
    done = 0

    for prompt in prompts:
        for case in test_cases:
            variables = json.loads(case["variables_json"]) if isinstance(case.get("variables_json"), str) else (case.get("variables_json") or {})
            expected = case.get("expected_output", "")

            response, score = run_single(
                provider,
                prompt["system_prompt"],
                prompt["user_template"],
                variables,
                expected,
            )

            results.append({
                "prompt_id": prompt["id"],
                "test_case_id": case["id"],
                "provider_name": provider.name,
                "model": response.model,
                "output": response.content,
                "expected": expected,
                "latency_ms": response.latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "score": score.overall,
                "accuracy": score.accuracy,
                "format_compliance": score.format_compliance,
                "efficiency": score.efficiency,
                "error": response.error,
            })

            done += 1
            if progress_callback:
                progress_callback(done, total)

    return results


def generate_report(results: list[dict]) -> dict:
    """从评测结果生成汇总报告"""
    if not results:
        return {"error": "无数据"}

    # 按 prompt 聚合
    by_prompt: dict[int, list] = {}
    for r in results:
        by_prompt.setdefault(r["prompt_id"], []).append(r)

    summary = []
    for pid, items in by_prompt.items():
        scores = [r["score"] for r in items if r["score"] is not None]
        latencies = [r["latency_ms"] for r in items]
        errors = [r for r in items if r.get("error")]

        summary.append({
            "prompt_id": pid,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 0) if latencies else 0,
            "total_tokens": sum(r["input_tokens"] + r["output_tokens"] for r in items),
            "errors": len(errors),
            "test_count": len(items),
        })

    summary.sort(key=lambda x: x["avg_score"], reverse=True)

    return {
        "by_prompt": summary,
        "total_tests": len(results),
        "winner": summary[0] if summary else None,
    }
