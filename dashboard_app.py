"""
Day 13 AI Observability Dashboard
==================================
Streamlit dashboard đọc data/logs.jsonl và hiển thị 6 panel
theo contract config/dashboard.yaml.

Chạy:  streamlit run dashboard_app.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOG_PATH = Path("data/logs.jsonl")
DASHBOARD_CONFIG = Path("config/dashboard.yaml")
SLO_CONFIG = Path("config/slo.yaml")


def load_logs() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def load_dashboard_yaml() -> dict:
    return yaml.safe_load(DASHBOARD_CONFIG.read_text(encoding="utf-8"))


def load_slo_yaml() -> dict:
    return yaml.safe_load(SLO_CONFIG.read_text(encoding="utf-8"))


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="Day 13 AI Observability",
        page_icon="📊",
        layout="wide",
    )

    # Custom CSS for premium look
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p { color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .slo-pass { color: #a6e3a1; font-weight: bold; }
    .slo-fail { color: #f38ba8; font-weight: bold; }
    .panel-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #cdd6f4;
        margin-bottom: 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #45475a;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Day 13 AI Observability Dashboard</h1>
        <p>Real-time monitoring • 6 panels • data/logs.jsonl</p>
    </div>
    """, unsafe_allow_html=True)

    # Load data
    logs = load_logs()
    if not logs:
        st.error("⚠️ Không tìm thấy data/logs.jsonl hoặc file rỗng. Chạy API và load test trước.")
        return

    dashboard_cfg = load_dashboard_yaml()["dashboard"]
    slo_cfg = load_slo_yaml()

    # Filter events
    response_sent = [r for r in logs if r.get("event") == "response_sent"]
    request_received = [r for r in logs if r.get("event") == "request_received"]
    request_failed = [r for r in logs if r.get("event") == "request_failed"]

    # Sidebar info
    with st.sidebar:
        st.markdown("### ⚙️ Dashboard Config")
        st.markdown(f"**Time range:** {dashboard_cfg['time_range_minutes']} phút")
        st.markdown(f"**Refresh:** {dashboard_cfg['refresh_seconds']}s")
        st.markdown(f"**Total logs:** {len(logs)}")
        st.markdown(f"**response_sent:** {len(response_sent)}")
        st.markdown(f"**request_received:** {len(request_received)}")
        st.markdown(f"**request_failed:** {len(request_failed)}")
        st.divider()
        st.markdown("### 📋 SLO Targets")
        for sli_name, sli in slo_cfg.get("slis", {}).items():
            st.markdown(f"- **{sli_name}**: {sli['objective']} (target {sli['target']}%)")

    # ===================================================================
    # ROW 1: Latency | Traffic | Errors
    # ===================================================================
    col1, col2, col3 = st.columns(3)

    # --- Panel 1: Latency Percentiles ---
    with col1:
        st.markdown('<div class="panel-title">⏱️ Latency Percentiles (ms)</div>', unsafe_allow_html=True)
        latencies = [r.get("latency_ms", 0) for r in response_sent if r.get("latency_ms") is not None]
        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        p99 = percentile(latencies, 99)
        threshold = 3000  # from dashboard.yaml

        c1, c2, c3 = st.columns(3)
        c1.metric("P50", f"{p50:.0f} ms")
        c2.metric("P95", f"{p95:.0f} ms")
        c3.metric("P99", f"{p99:.0f} ms")

        slo_status = "✅ PASS" if p95 <= threshold else "❌ FAIL"
        slo_color = "slo-pass" if p95 <= threshold else "slo-fail"
        st.markdown(f'SLO: P95 ≤ {threshold}ms → <span class="{slo_color}">{slo_status} ({p95:.0f}ms)</span>', unsafe_allow_html=True)

        # Time series
        if latencies:
            ts_data = []
            for r in response_sent:
                if r.get("latency_ms") is not None and r.get("ts"):
                    ts_data.append({"time": r["ts"][:19], "latency_ms": r["latency_ms"]})
            if ts_data:
                st.line_chart(
                    data={d["time"]: d["latency_ms"] for d in ts_data},
                    use_container_width=True,
                    height=200,
                )

    # --- Panel 2: Traffic ---
    with col2:
        st.markdown('<div class="panel-title">📈 Request Traffic</div>', unsafe_allow_html=True)
        total_requests = len(request_received)

        # Group by minute
        minute_counts: dict[str, int] = {}
        for r in request_received:
            ts = r.get("ts", "")[:16]  # truncate to minute
            minute_counts[ts] = minute_counts.get(ts, 0) + 1

        rate_per_min = total_requests / max(1, len(minute_counts))
        threshold_traffic = 1  # from dashboard.yaml

        st.metric("Total Requests", total_requests)
        st.metric("Avg Rate", f"{rate_per_min:.1f} req/min")

        slo_status = "✅ PASS" if rate_per_min >= threshold_traffic else "❌ FAIL"
        slo_color = "slo-pass" if rate_per_min >= threshold_traffic else "slo-fail"
        st.markdown(f'Threshold: rate ≥ {threshold_traffic} req/min → <span class="{slo_color}">{slo_status}</span>', unsafe_allow_html=True)

        if minute_counts:
            st.bar_chart(minute_counts, use_container_width=True, height=200)

    # --- Panel 3: Error Rate & Breakdown ---
    with col3:
        st.markdown('<div class="panel-title">🚨 Error Rate & Breakdown</div>', unsafe_allow_html=True)
        total_req = len(request_received)
        total_err = len(request_failed)
        error_rate = (total_err / total_req * 100) if total_req > 0 else 0.0
        threshold_err = 2.0  # from dashboard.yaml

        st.metric("Error Rate", f"{error_rate:.2f}%")
        st.metric("Total Errors", total_err)

        slo_status = "✅ PASS" if error_rate <= threshold_err else "❌ FAIL"
        slo_color = "slo-pass" if error_rate <= threshold_err else "slo-fail"
        st.markdown(f'SLO: error rate ≤ {threshold_err}% → <span class="{slo_color}">{slo_status}</span>', unsafe_allow_html=True)

        # Breakdown by error_type
        error_breakdown: dict[str, int] = {}
        for r in request_failed:
            et = r.get("error_type", "unknown")
            error_breakdown[et] = error_breakdown.get(et, 0) + 1

        if error_breakdown:
            st.bar_chart(error_breakdown, use_container_width=True, height=200)
        else:
            st.info("No errors detected ✅")

    # ===================================================================
    # ROW 2: Cost | Tokens | Quality
    # ===================================================================
    col4, col5, col6 = st.columns(3)

    # --- Panel 4: Cost Over Time ---
    with col4:
        st.markdown('<div class="panel-title">💰 Cost Over Time (USD)</div>', unsafe_allow_html=True)
        costs = [r.get("cost_usd", 0) for r in response_sent if r.get("cost_usd") is not None]
        total_cost = sum(costs)
        threshold_cost = 2.5  # from dashboard.yaml

        st.metric("Total Cost", f"${total_cost:.4f}")

        # Cost by minute
        cost_by_min: dict[str, float] = {}
        for r in response_sent:
            if r.get("cost_usd") is not None and r.get("ts"):
                ts = r["ts"][:16]
                cost_by_min[ts] = cost_by_min.get(ts, 0) + r["cost_usd"]

        slo_status = "✅ PASS" if total_cost <= threshold_cost else "❌ FAIL"
        slo_color = "slo-pass" if total_cost <= threshold_cost else "slo-fail"
        st.markdown(f'SLO: total ≤ ${threshold_cost} → <span class="{slo_color}">{slo_status} (${total_cost:.4f})</span>', unsafe_allow_html=True)

        if cost_by_min:
            st.bar_chart(cost_by_min, use_container_width=True, height=200)

    # --- Panel 5: Tokens ---
    with col5:
        st.markdown('<div class="panel-title">🔢 Input & Output Tokens</div>', unsafe_allow_html=True)
        tokens_in = sum(r.get("tokens_in", 0) for r in response_sent if r.get("tokens_in") is not None)
        tokens_out = sum(r.get("tokens_out", 0) for r in response_sent if r.get("tokens_out") is not None)
        total_tokens = tokens_in + tokens_out
        threshold_tokens = 50000  # from dashboard.yaml

        c1, c2 = st.columns(2)
        c1.metric("Tokens In", f"{tokens_in:,}")
        c2.metric("Tokens Out", f"{tokens_out:,}")

        st.metric("Total", f"{total_tokens:,}")

        slo_status = "✅ PASS" if total_tokens <= threshold_tokens else "❌ FAIL"
        slo_color = "slo-pass" if total_tokens <= threshold_tokens else "slo-fail"
        st.markdown(f'Threshold: total ≤ {threshold_tokens:,} → <span class="{slo_color}">{slo_status}</span>', unsafe_allow_html=True)

        # Token breakdown chart
        st.bar_chart({"tokens_in": tokens_in, "tokens_out": tokens_out}, use_container_width=True, height=200)

    # --- Panel 6: Quality Proxy ---
    with col6:
        st.markdown('<div class="panel-title">⭐ Quality Proxy (0–1)</div>', unsafe_allow_html=True)
        quality_scores = [r.get("quality_score", 0) for r in response_sent if r.get("quality_score") is not None]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        threshold_quality = 0.75  # from dashboard.yaml

        st.metric("Mean Quality", f"{avg_quality:.3f}")

        slo_status = "✅ PASS" if avg_quality >= threshold_quality else "❌ FAIL"
        slo_color = "slo-pass" if avg_quality >= threshold_quality else "slo-fail"
        st.markdown(f'SLO: mean ≥ {threshold_quality} → <span class="{slo_color}">{slo_status} ({avg_quality:.3f})</span>', unsafe_allow_html=True)

        # Quality over time
        if quality_scores:
            q_data = {}
            for r in response_sent:
                if r.get("quality_score") is not None and r.get("ts"):
                    q_data[r["ts"][:19]] = r["quality_score"]
            if q_data:
                st.line_chart(q_data, use_container_width=True, height=200)

    # ===================================================================
    # Footer: Log detail table
    # ===================================================================
    st.divider()
    with st.expander("📝 Recent Log Records (last 20)"):
        recent = logs[-20:]
        display_cols = ["ts", "level", "event", "correlation_id", "feature",
                        "latency_ms", "tokens_in", "tokens_out", "cost_usd",
                        "quality_score", "error_type"]
        table_data = []
        for r in recent:
            row = {col: r.get(col, "") for col in display_cols}
            table_data.append(row)
        st.table(table_data)


if __name__ == "__main__":
    main()
