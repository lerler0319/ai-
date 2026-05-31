"""SQLite database layer for Prompt Lab."""

import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "promptlab.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            system_prompt TEXT NOT NULL DEFAULT '',
            user_template TEXT NOT NULL DEFAULT '{input}',
            variables TEXT NOT NULL DEFAULT '["input"]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            variables_json TEXT NOT NULL DEFAULT '{}',
            expected_output TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            prompt_ids TEXT NOT NULL,
            test_case_ids TEXT NOT NULL,
            provider_config TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS eval_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
            prompt_id INTEGER NOT NULL,
            test_case_id INTEGER NOT NULL,
            provider_name TEXT NOT NULL,
            model TEXT NOT NULL,
            output TEXT NOT NULL DEFAULT '',
            expected TEXT NOT NULL DEFAULT '',
            latency_ms REAL NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            score REAL,
            accuracy REAL,
            format_compliance REAL,
            efficiency REAL,
            error TEXT
        );
    """)
    conn.commit()
    conn.close()


# ── Prompts CRUD ────────────────────────────────────────────

def list_prompts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM prompts ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_prompt(pid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_prompt(name: str, system_prompt: str, user_template: str, variables: list[str]):
    conn = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO prompts (name, system_prompt, user_template, variables, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (name, system_prompt, user_template, json.dumps(variables), now, now),
    )
    conn.commit()
    conn.close()


def update_prompt(pid: int, name: str, system_prompt: str, user_template: str, variables: list[str]):
    conn = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE prompts SET name=?, system_prompt=?, user_template=?, variables=?, updated_at=? WHERE id=?",
        (name, system_prompt, user_template, json.dumps(variables), now, pid),
    )
    conn.commit()
    conn.close()


def delete_prompt(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM prompts WHERE id=?", (pid,))
    conn.commit()
    conn.close()


# ── Test Cases CRUD ─────────────────────────────────────────

def list_test_cases():
    conn = get_db()
    rows = conn.execute("SELECT * FROM test_cases ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_test_case(name: str, variables: dict, expected: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO test_cases (name, variables_json, expected_output) VALUES (?,?,?)",
        (name, json.dumps(variables), expected),
    )
    conn.commit()
    conn.close()


def get_test_case(tid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM test_cases WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_test_case(tid: int):
    conn = get_db()
    conn.execute("DELETE FROM test_cases WHERE id=?", (tid,))
    conn.commit()
    conn.close()


# ── Evaluations ─────────────────────────────────────────────

def create_evaluation(name: str, prompt_ids: list[int], test_case_ids: list[int], provider_config: dict) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO evaluations (name, prompt_ids, test_case_ids, provider_config, status) VALUES (?,?,?,?,?)",
        (name, json.dumps(prompt_ids), json.dumps(test_case_ids), json.dumps(provider_config), "pending"),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def update_eval_status(eid: int, status: str):
    conn = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if status == "completed" else None
    if now:
        conn.execute("UPDATE evaluations SET status=?, completed_at=? WHERE id=?", (status, now, eid))
    else:
        conn.execute("UPDATE evaluations SET status=? WHERE id=?", (status, eid))
    conn.commit()
    conn.close()


def save_eval_result(eid: int, pid: int, tid: int, provider_name: str, model: str, output: str, expected: str, latency: float, in_tok: int, out_tok: int, score: float | None, accuracy: float | None, format_compliance: float | None, efficiency: float | None, error: str | None):
    conn = get_db()
    conn.execute(
        "INSERT INTO eval_results (evaluation_id, prompt_id, test_case_id, provider_name, model, output, expected, latency_ms, input_tokens, output_tokens, score, accuracy, format_compliance, efficiency, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, pid, tid, provider_name, model, output, expected, latency, in_tok, out_tok, score, accuracy, format_compliance, efficiency, error),
    )
    conn.commit()
    conn.close()


def list_evaluations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM evaluations ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_evaluation(eid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM evaluations WHERE id=?", (eid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_eval_results(eid: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT r.*, p.name as prompt_name, t.name as test_case_name "
        "FROM eval_results r "
        "LEFT JOIN prompts p ON r.prompt_id = p.id "
        "LEFT JOIN test_cases t ON r.test_case_id = t.id "
        "WHERE r.evaluation_id=? ORDER BY r.prompt_id, r.test_case_id",
        (eid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_evaluation(eid: int):
    conn = get_db()
    conn.execute("DELETE FROM evaluations WHERE id=?", (eid,))
    conn.commit()
    conn.close()


# ── Stats ───────────────────────────────────────────────────

def get_stats():
    conn = get_db()
    prompts = conn.execute("SELECT COUNT(*) as n FROM prompts").fetchone()["n"]
    cases = conn.execute("SELECT COUNT(*) as n FROM test_cases").fetchone()["n"]
    evals = conn.execute("SELECT COUNT(*) as n FROM evaluations").fetchone()["n"]
    conn.close()
    return {"prompts": prompts, "test_cases": cases, "evaluations": evals}
