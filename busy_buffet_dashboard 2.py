"""
Busy Buffet Analysis Dashboard
Hotel Amber 85 — Breakfast Buffet
Run with: streamlit run busy_buffet_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Busy Buffet Analysis — Hotel Amber 85",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── COLOUR PALETTE ─────────────────────────────────────────────────────────────
C_BLUE   = "#378ADD"
C_ORANGE = "#D85A30"
C_RED    = "#E24B4A"
C_GREEN  = "#3B6D11"
C_AMBER  = "#BA7517"
C_LIGHT_BLUE = "#B5D4F4"
C_LIGHT_GREEN = "#C0DD97"

DAY_ORDER = ["Mon Jan 13", "Tue Jan 14", "Wed Jan 15", "Fri Jan 17", "Sat Jan 18"]
DAY_COLORS = {
    "Mon Jan 13": C_GREEN,
    "Tue Jan 14": C_ORANGE,
    "Wed Jan 15": C_RED,
    "Fri Jan 17": C_GREEN,
    "Sat Jan 18": C_GREEN,
}

# ── DATA LOADING & CLEANING ────────────────────────────────────────────────────
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    sheet_map = {
        "133": "Mon Jan 13",
        "143": "Tue Jan 14",
        "153": "Wed Jan 15",
        "173": "Fri Jan 17",
        "183": "Sat Jan 18",
    }
    all_sheets = pd.read_excel(path, sheet_name=None)
    frames = []
    for sheet_name, df in all_sheets.items():
        cols = ["service_no.", "pax", "queue_start", "queue_end",
                "table_no.", "meal_start", "meal_end", "Guest_type"]
        df = df[cols].copy()
        df["day"] = sheet_map[sheet_name]
        frames.append(df)

    full = pd.concat(frames, ignore_index=True)

    # ── FIXES ──────────────────────────────────────────────────────────────────
    # Sat Jan 18 svc 62: swapped meal times
    m62 = (full["day"] == "Sat Jan 18") & (full["service_no."] == 62)
    full.loc[m62, ["meal_start", "meal_end"]] = \
        full.loc[m62, ["meal_end", "meal_start"]].values

    # Sat Jan 18 svc 5: 02:29 → 07:29
    m5 = (full["day"] == "Sat Jan 18") & (full["service_no."] == 5)
    full.loc[m5, "meal_start"] = "07:29:00"

    # Drop rows where pax=0/NaN AND no meal recorded
    drop = ((full["pax"] == 0) | full["pax"].isna()) & full["meal_start"].isna()
    full = full[~drop].copy()

    # pax=0 but has meal → treat pax as unknown
    full.loc[full["pax"] == 0, "pax"] = np.nan

    # ── TIME CONVERSION ────────────────────────────────────────────────────────
    def to_td(col):
        return pd.to_timedelta(
            col.astype(str).where(col.notna(), None), errors="coerce"
        )

    full["qs"] = to_td(full["queue_start"])
    full["qe"] = to_td(full["queue_end"])
    full["ms"] = to_td(full["meal_start"])
    full["me"] = to_td(full["meal_end"])

    full["meal_dur"]   = (full["me"] - full["ms"]).dt.total_seconds() / 60
    full["queue_wait"] = (full["qe"] - full["qs"]).dt.total_seconds() / 60

    full["has_queue"]   = full["qs"].notna()
    full["has_meal"]    = full["ms"].notna()
    full["is_walkaway"] = full["has_queue"] & ~full["has_meal"]

    return full


# ── HELPERS ────────────────────────────────────────────────────────────────────
def metric_row(cols_data: list):
    """Render a row of st.metric cards. cols_data = [(label, value, delta), ...]"""
    cols = st.columns(len(cols_data))
    for col, (label, value, delta) in zip(cols, cols_data):
        col.metric(label, value, delta)


def fig_layout(fig, height=380):
    fig.update_layout(
        height=height,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor="rgba(0,0,0,0.1)")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.07)", linecolor="rgba(0,0,0,0)")
    return fig


def insight_box(text: str, colour: str = C_BLUE):
    st.markdown(
        f"""<div style="
            background:rgba(55,138,221,0.07);
            border-left:4px solid {colour};
            border-radius:6px;
            padding:12px 16px;
            font-size:14px;
            line-height:1.7;
            margin-top:10px;
        ">{text}</div>""",
        unsafe_allow_html=True,
    )


def verdict_badge(text: str, colour: str, bg: str):
    st.markdown(
        f"""<span style="
            background:{bg};color:{colour};
            font-size:12px;font-weight:600;
            padding:4px 14px;border-radius:20px;
            display:inline-block;margin-bottom:8px;
        ">{text}</span>""",
        unsafe_allow_html=True,
    )


def explain_box(text: str):
    st.markdown(
        f"""<div style="
            background:rgba(0,0,0,0.04);
            border-radius:8px;
            padding:12px 16px;
            font-size:13px;
            color:#555;
            line-height:1.7;
            margin-bottom:14px;
        ">{text}</div>""",
        unsafe_allow_html=True,
    )


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    # ── SIDEBAR ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("🍳 Busy Buffet")
        st.caption("Hotel Amber 85 — Breakfast Analysis")
        st.divider()

        uploaded = st.file_uploader(
            "Upload dataset (.xlsx)", type=["xlsx"]
        )
        st.divider()

        page = st.radio(
            "Navigate",
            [
                "📊 Overview",
                "S1 — Queue Pain",
                "S2 — Busy Every Day?",
                "S3 — Walk-ins Sit Long",
                "A1 — Reduce Seating Time",
                "A2 — Raise Price Daily",
                "A3 — Queue Skip",
                "✅ Task 3 — Best Solution",
            ],
        )
        st.divider()
        st.caption("Task 1: Prove/disprove staff comments\nTask 2: Disprove proposed actions\nTask 3: Best solution")

    if uploaded is None:
        st.info("👈 Upload the buffet dataset Excel file in the sidebar to begin.")
        st.stop()

    df = load_data(uploaded)
    meal = df[df["has_meal"] & df["meal_dur"].notna() & (df["meal_dur"] > 0)].copy()

    # Day-level summary
    day_stats = (
        df.groupby("day")
        .agg(
            groups=("service_no.", "count"),
            total_pax=("pax", "sum"),
            queued_groups=("has_queue", "sum"),
            walkaways=("is_walkaway", "sum"),
        )
        .reindex(DAY_ORDER)
    )

    # ══════════════════════════════════════════════════════════════════════════
    # OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    if page == "📊 Overview":
        st.title("📊 Busy Buffet — Full Analysis Overview")
        st.markdown(
            "Hotel Amber 85 promoted an all-you-can-eat breakfast buffet on TikTok "
            "and experienced a sudden surge in walk-in guests. This dashboard analyses "
            "**5 days of service data** to evaluate staff comments and proposed solutions."
        )
        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total guest groups", f"{len(df):,}")
        col2.metric("Total pax", f"{int(df['pax'].sum()):,}")
        col3.metric("Groups who queued", f"{df['has_queue'].sum()}")
        col4.metric("Walk-aways", f"{df['is_walkaway'].sum()}")

        st.divider()
        st.subheader("Daily at a glance")

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Total pax by day", "Queue volume by day"),
        )
        colors = [DAY_COLORS[d] for d in DAY_ORDER]
        fig.add_trace(
            go.Bar(
                x=DAY_ORDER, y=day_stats["total_pax"].values,
                marker_color=colors, name="Pax", showlegend=False,
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=DAY_ORDER, y=day_stats["queued_groups"].values,
                marker_color=colors, name="Queued", showlegend=False,
            ),
            row=1, col=2,
        )
        fig_layout(fig, height=340)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Summary of findings")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Statement verdicts**")
            st.markdown("🟡 S1 — Queue pain: **Partially True**")
            st.markdown("🔴 S2 — Busy every day: **False**")
            st.markdown("🟢 S3 — Walk-ins sit long: **True**")
        with c2:
            st.markdown("**Action verdicts**")
            st.markdown("❌ A1 — Reduce seating time: **Won't Work**")
            st.markdown("❌ A2 — Raise price all days: **Won't Work**")
            st.markdown("❌ A3 — Queue skip: **Won't Work**")
        with c3:
            st.markdown("**Root cause**")
            st.markdown(
                "Mid-week demand spike (Tue/Wed) from TikTok promo, "
                "combined with walk-in guests staying 66% longer than "
                "in-house guests, collapsing table turnover."
            )

    # ══════════════════════════════════════════════════════════════════════════
    # STATEMENT 1
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "S1 — Queue Pain":
        verdict_badge("PARTIALLY TRUE", "#854F0B", "#FAEEDA")
        st.title("Statement 1 — Queue pain is real, but not every day")
        st.markdown(
            """*"In-house customers are unhappy that they have to wait for a table. """
            """Walk-in customers are also unhappy, when they queue up for a long time """
            """and leave the queue because they don't want to wait any longer."*"""
        )
        explain_box(
            "<b>What we're testing:</b> Do in-house guests have to queue? "
            "Do walk-in guests abandon the queue? We split queue_start/queue_end data "
            "by Guest_type and identify walk-aways (has queue but no meal_start)."
        )

        stayed = df[df["has_queue"] & df["has_meal"]]
        wa     = df[df["is_walkaway"]]
        ih     = df[df["Guest_type"] == "In house"]
        wi     = df[df["Guest_type"] == "Walk in"]

        metric_row([
            ("In-house who queued", f"{ih['has_queue'].sum()} / {ih['has_meal'].sum()} groups", None),
            ("In-house walk-aways", str(int((ih["is_walkaway"]).sum())), "avg 24 min wait"),
            ("Walk-in walk-aways", str(int((wi["is_walkaway"]).sum())), "avg 35 min wait"),
            ("Overall avg queue wait", "34 min", "for those who stayed"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Avg wait time by guest type & outcome")
            cats  = ["In-house\nstayed", "In-house\nwalk-away", "Walk-in\nstayed", "Walk-in\nwalk-away"]
            waits = [
                stayed[stayed["Guest_type"] == "In house"]["queue_wait"].mean(),
                wa[wa["Guest_type"] == "In house"]["queue_wait"].mean(),
                stayed[stayed["Guest_type"] == "Walk in"]["queue_wait"].mean(),
                wa[wa["Guest_type"] == "Walk in"]["queue_wait"].mean(),
            ]
            bar_colors = [C_BLUE, C_RED, C_ORANGE, C_RED]
            fig = go.Figure(go.Bar(
                x=cats, y=[round(w, 1) for w in waits],
                marker_color=bar_colors,
                text=[f"{w:.0f} min" for w in waits],
                textposition="outside",
            ))
            fig.update_layout(yaxis_title="Minutes waiting", showlegend=False)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("Queuing volume by day")
            q_by_day = df[df["has_queue"]].groupby("day").size().reindex(DAY_ORDER, fill_value=0)
            fig = go.Figure(go.Bar(
                x=DAY_ORDER,
                y=q_by_day.values,
                marker_color=[DAY_COLORS[d] for d in DAY_ORDER],
                text=q_by_day.values,
                textposition="outside",
            ))
            fig.update_layout(yaxis_title="Groups queued", showlegend=False)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Verdict:</b> The staff comment is <b>partially true</b>. "
            "Queuing pain IS real — 28–39 min average waits, and 9 groups abandoned entirely. "
            "But it only happened on <b>Tuesday and Wednesday</b>. On Mon, Fri, and Sat, "
            "zero groups had to queue. The statement overgeneralises a mid-week problem "
            "as an everyday problem.",
            C_AMBER,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STATEMENT 2
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "S2 — Busy Every Day?":
        verdict_badge("FALSE", "#A32D2D", "#FCEBEB")
        st.title("Statement 2 — Not busy every day")
        st.markdown(
            """*"We are very busy every day of the week. If it's going to be this busy """
            """every week I think it's impossible to sustain this business. This buffet """
            """business is not possible for this hotel."*"""
        )
        explain_box(
            "<b>What we're testing:</b> We count total pax and queued groups per day. "
            "If it were truly 'busy every day,' we'd expect queuing and high pax on all 5 days."
        )

        metric_row([
            ("Busiest day — Wed", "166 pax", "49 groups queued"),
            ("Quietest day — Mon", "102 pax", "0 groups queued"),
            ("Days with zero queuing", "3 of 5", "Mon, Fri, Sat"),
            ("Walk-aways all week", "9 total", "8 happened on Wed alone"),
        ])
        st.divider()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=DAY_ORDER,
                y=day_stats["total_pax"].values,
                name="Total pax",
                marker_color=[DAY_COLORS[d] for d in DAY_ORDER],
                text=day_stats["total_pax"].astype(int).values,
                textposition="outside",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=DAY_ORDER,
                y=day_stats["queued_groups"].values,
                name="Groups queued",
                mode="lines+markers",
                line=dict(color=C_RED, width=2.5),
                marker=dict(size=9, color=C_RED),
            ),
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Total pax", secondary_y=False)
        fig.update_yaxes(title_text="Groups queued", secondary_y=True, showgrid=False)
        fig_layout(fig, height=400)
        st.plotly_chart(fig, use_container_width=True)

        insight_box(
            "<b>Verdict: False.</b> 3 out of 5 days had <b>zero queuing</b> at all. "
            "The congestion is a Tue/Wed phenomenon — likely driven by the TikTok promotion "
            "reaching its peak audience mid-week. Mon, Fri, and Sat are running smoothly. "
            "The business is not uniformly unsustainable — it has a specific, fixable "
            "problem on 2 days.",
            C_RED,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STATEMENT 3
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "S3 — Walk-ins Sit Long":
        verdict_badge("TRUE", "#3B6D11", "#EAF3DE")
        st.title("Statement 3 — Walk-ins stay significantly longer")
        st.markdown(
            """*"Walk-in customers sit the whole day. It's very difficult to find seats """
            """for in-house customers. We don't have enough tables so when one customer """
            """sits for a long time it makes the queue very long."*"""
        )
        explain_box(
            "<b>What we're testing:</b> We compute meal_duration = meal_end − meal_start "
            "for every group, then compare the distribution between In-house and Walk-in guests. "
            "Longer average duration = tables occupied longer = fewer available seats = longer queue."
        )

        ih_dur = meal[meal["Guest_type"] == "In house"]["meal_dur"]
        wi_dur = meal[meal["Guest_type"] == "Walk in"]["meal_dur"]

        metric_row([
            ("Walk-in avg meal", f"{wi_dur.mean():.0f} min", f"median: {wi_dur.median():.0f} min"),
            ("In-house avg meal", f"{ih_dur.mean():.0f} min", f"median: {ih_dur.median():.0f} min"),
            ("Walk-ins over 2 hrs", str((wi_dur > 120).sum()), "11% of walk-in groups"),
            ("In-house over 2 hrs", str((ih_dur > 120).sum()), "3% of in-house groups"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Meal duration distribution")
            bins   = [0, 30, 60, 90, 120, 180, 300]
            labels = ["<30", "30–60", "60–90", "90–120", "120–180", "180+"]
            ih_cut = pd.cut(ih_dur, bins=bins, labels=labels).value_counts().sort_index()
            wi_cut = pd.cut(wi_dur, bins=bins, labels=labels).value_counts().sort_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(name="In house", x=labels, y=ih_cut.values, marker_color=C_BLUE))
            fig.add_trace(go.Bar(name="Walk in",  x=labels, y=wi_cut.values, marker_color=C_ORANGE))
            fig.update_layout(barmode="group", yaxis_title="Number of groups")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("Box plot — meal duration spread")
            fig = go.Figure()
            for gt, col in [("In house", C_BLUE), ("Walk in", C_ORANGE)]:
                sub = meal[meal["Guest_type"] == gt]["meal_dur"]
                fig.add_trace(go.Box(
                    y=sub, name=gt, marker_color=col,
                    boxmean=True, line_width=1.5,
                ))
            fig.update_layout(yaxis_title="Meal duration (min)", showlegend=True)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Verdict: True.</b> Walk-in guests stay <b>66% longer</b> on average than "
            "in-house guests (73 vs 44 min). The 5-hour seating promotion directly encourages "
            "this. On the busiest days (Tue/Wed), 32 walk-in groups stayed over 90 minutes — "
            "blocking tables and directly causing the queue to build up. "
            "This is the <b>root cause</b> of the whole problem.",
            C_GREEN,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION 1
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "A1 — Reduce Seating Time":
        verdict_badge("WON'T WORK", "#A32D2D", "#FCEBEB")
        st.title("Action 1 — Reduce seating time (5 hr → less)")
        st.markdown(
            "*Management idea: If we limit how long guests can sit, tables will turn "
            "over faster and the queue will shrink.*"
        )
        explain_box(
            "<b>Why this seems logical:</b> Shorter seating cap → faster table turnover → "
            "more seats available → shorter queue.<br><br>"
            "<b>Why the data says otherwise:</b> We check how many guests are actually "
            "<em>using</em> the 5-hour allowance. If almost nobody stays near 5 hours, "
            "reducing the cap changes nothing in practice."
        )

        metric_row([
            ("Max actual stay", "225 min (3h 45m)", "nobody reached 5 hours"),
            ("Staying over 3 hrs", "0.9%", "only 3 of 349 groups"),
            ("Staying over 2 hrs", "7.2%", "25 groups total"),
            ("Walk-in avg stay", "73 min", "well below any cap"),
        ])
        st.divider()

        bins   = [0, 30, 60, 90, 120, 180, 300]
        labels = ["<30", "30–60", "60–90", "90–120", "120–180", "180+"]
        all_cut = pd.cut(meal["meal_dur"], bins=bins, labels=labels).value_counts().sort_index()
        total   = all_cut.sum()
        cum_pct = (all_cut.cumsum() / total * 100).values

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Guest count by meal duration bracket")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=labels, y=all_cut.values,
                marker_color=C_LIGHT_BLUE, name="Groups",
                text=all_cut.values, textposition="outside",
            ))
            fig.update_layout(yaxis_title="Number of groups", showlegend=False)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("Cumulative % of guests gone by each bracket")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=labels, y=[round(v, 1) for v in cum_pct],
                mode="lines+markers",
                line=dict(color=C_BLUE, width=2.5),
                marker=dict(size=9),
                fill="tozeroy", fillcolor="rgba(55,138,221,0.1)",
                name="Cumulative %",
                text=[f"{v:.0f}%" for v in cum_pct],
                textposition="top center",
            ))
            fig.add_hline(y=99, line_dash="dot", line_color=C_RED,
                          annotation_text="99% of guests gone by 180 min")
            fig.update_layout(yaxis_title="Cumulative % of guests left", yaxis_range=[0, 110])
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Why it won't work:</b> <b>Nobody is using the 5-hour allowance.</b> "
            "The longest anyone actually stayed was 3h 45min — one outlier. "
            "99% of guests leave within 3 hours on their own. "
            "Reducing the cap from 5 hours to 3 hours (or even 2 hours) would not change "
            "actual behaviour at all. The cap is not the binding constraint — the real problem "
            "is the <b>volume of guests arriving at the same time on Tue/Wed</b>, "
            "not how long they each sit.",
            C_RED,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION 2
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "A2 — Raise Price Daily":
        verdict_badge("WON'T WORK", "#A32D2D", "#FCEBEB")
        st.title("Action 2 — Raise price to 259฿ every day")
        st.markdown(
            "*Management idea: Higher price every day will reduce total demand "
            "and make the buffet manageable.*"
        )
        explain_box(
            "<b>Why this seems logical:</b> Higher price → fewer guests → less congestion. "
            "Simple supply-and-demand thinking.<br><br>"
            "<b>Why the data says otherwise:</b> The problem only exists on 2 days. "
            "Raising prices on all 5 days punishes guests on the 3 days that are working fine "
            "— risking good revenue without fixing the actual spike days."
        )

        good_days = ["Mon Jan 13", "Fri Jan 17", "Sat Jan 18"]
        bad_days  = ["Tue Jan 14", "Wed Jan 15"]
        good_pax  = day_stats.loc[good_days, "total_pax"].sum()
        rev_at_risk = good_pax * 0.20 * 159

        metric_row([
            ("Problem days", "2 of 5", "Tue & Wed only"),
            ("Fine days (no queue)", "3 of 5", "Mon, Fri, Sat"),
            ("Revenue at risk (est.)", f"฿{rev_at_risk:,.0f}", "if fine days lose 20% pax"),
            ("Tue+Wed avg pax", "160", "vs Mon/Fri/Sat avg 114"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Queue problems concentrated on 2 days only")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=DAY_ORDER,
                y=day_stats["total_pax"].values,
                name="Total pax",
                marker_color=[C_RED if d in bad_days else C_LIGHT_GREEN for d in DAY_ORDER],
                text=[f"{int(v)} pax" for v in day_stats["total_pax"].values],
                textposition="outside",
            ))
            fig.add_trace(go.Bar(
                x=DAY_ORDER,
                y=day_stats["queued_groups"].values,
                name="Groups queued",
                marker_color=[C_ORANGE if d in bad_days else "rgba(0,0,0,0.05)" for d in DAY_ORDER],
                text=[f"{int(v)} queued" if v > 0 else "" for v in day_stats["queued_groups"].values],
                textposition="inside",
            ))
            fig.update_layout(barmode="overlay", yaxis_title="Count")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("Raising price all days: who gets hurt?")
            days_label  = ["Mon\n(fine)", "Tue\n(problem)", "Wed\n(problem)", "Fri\n(fine)", "Sat\n(fine)"]
            current_rev = [
                102 * 159, 154 * 159, 166 * 159, 118 * 159, 122 * 199
            ]
            raise_all   = [
                102 * 0.8 * 259, 154 * 0.8 * 259, 166 * 0.8 * 259,
                118 * 0.8 * 259, 122 * 0.8 * 259,
            ]
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Current revenue",
                                 x=days_label, y=current_rev, marker_color=C_LIGHT_BLUE))
            fig.add_trace(go.Bar(name="After blanket raise (−20% pax)",
                                 x=days_label, y=raise_all, marker_color=C_RED))
            fig.update_layout(barmode="group", yaxis_title="Est. daily revenue (฿)")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Why it won't work:</b> Raising prices <b>every day</b> is a blunt instrument "
            "aimed at a precise problem. Mon, Fri, and Sat are already running well — "
            "raising prices there risks losing good-day guests and revenue for no benefit. "
            "Meanwhile, the TikTok crowd driving the Tue/Wed spike may be price-insensitive "
            "and still come regardless. You'd be hurting the days that don't need fixing "
            "while potentially not fixing the days that do.",
            C_RED,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION 3
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "A3 — Queue Skip":
        verdict_badge("WON'T WORK", "#A32D2D", "#FCEBEB")
        st.title("Action 3 — Queue skipping for in-house guests")
        st.markdown(
            "*Management idea: Let in-house hotel guests skip the queue so they "
            "don't feel frustrated waiting behind walk-in guests.*"
        )
        explain_box(
            "<b>Why this seems logical:</b> In-house guests are paying hotel guests — "
            "they deserve priority. If they can skip, their frustration goes away.<br><br>"
            "<b>Why the data says otherwise:</b> Queue skipping doesn't reduce the total "
            "number of people waiting or create any new tables. It only reorders who waits. "
            "The underlying capacity problem remains completely unchanged."
        )

        wed = df[df["day"] == "Wed Jan 15"]
        metric_row([
            ("Wed total queued", "49", "groups waiting on worst day"),
            ("In-house queued Wed", "17", "avg 30 min wait"),
            ("Walk-in queued Wed", "32", "avg 48 min wait"),
            ("New tables created by skipping", "0", "no capacity added"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Queue composition on Wednesday (worst day)")
            ih_q = int(wed[wed["has_queue"] & (wed["Guest_type"] == "In house") & ~wed["is_walkaway"]].shape[0])
            wi_q = int(wed[wed["has_queue"] & (wed["Guest_type"] == "Walk in") & ~wed["is_walkaway"]].shape[0])
            wa_n = int(wed[wed["is_walkaway"]].shape[0])
            fig = go.Figure(go.Bar(
                x=["In-house\nqueued", "Walk-in\nqueued", "Walk-aways"],
                y=[ih_q, wi_q, wa_n],
                marker_color=[C_BLUE, C_ORANGE, C_RED],
                text=[ih_q, wi_q, wa_n], textposition="outside",
            ))
            fig.update_layout(yaxis_title="Number of groups", showlegend=False)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("What queue skip actually changes")
            categories = ["Total groups\nin queue", "Tables\ncreated", "Total wait\ntime saved"]
            before = [49, 0, 0]
            after  = [49, 0, 0]
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Before skip policy", x=categories, y=before,
                                 marker_color=C_LIGHT_BLUE))
            fig.add_trace(go.Bar(name="After skip policy",  x=categories, y=after,
                                 marker_color=C_ORANGE))
            fig.update_layout(barmode="group", yaxis_title="Value",
                              annotations=[dict(x=0, y=52, text="Still 49!", showarrow=False,
                                               font=dict(color=C_RED, size=13))])
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Why it won't work:</b> On the worst day (Wed), 49 groups were queuing. "
            "If in-house guests skip, those <b>same 49 groups still wait</b> — walk-in guests "
            "just wait even longer (their avg was already 48 min). "
            "This makes walk-in frustration worse, increases walk-aways, and loses walk-in revenue. "
            "In-house guests may feel slightly better, but the "
            "<b>root problem — too many guests, not enough table turnover — is completely untouched.</b> "
            "It's cosmetic, not a fix.",
            C_RED,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # TASK 3 — BEST SOLUTION
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "✅ Task 3 — Best Solution":
        verdict_badge("RECOMMENDED SOLUTION", "#185FA5", "#E6F1FB")
        st.title("Task 3 — Dynamic pricing: target the problem days, not all days")
        explain_box(
            "<b>The insight:</b> The problem is a mid-week demand spike on Tue & Wed. "
            "Mon, Fri, Sat run fine. The solution should target <b>only the problem days</b> "
            "with higher pricing — smoothing demand across the week rather than suppressing "
            "it everywhere."
        )

        st.subheader("The proposal: keep 159฿ on good days, raise to 259฿ on Tue & Wed only")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Current vs projected pax after dynamic pricing**")
            proj_pax = [102, round(154 * 0.8), round(166 * 0.8), 118, 122]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Current pax",
                x=DAY_ORDER, y=day_stats["total_pax"].astype(int).values,
                marker_color=C_LIGHT_BLUE, opacity=0.8,
            ))
            fig.add_trace(go.Bar(
                name="Projected pax (dynamic price)",
                x=DAY_ORDER, y=proj_pax,
                marker_color=[C_GREEN if i not in [1, 2] else C_AMBER
                              for i in range(5)],
            ))
            fig.update_layout(barmode="group", yaxis_title="Pax")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.markdown("**Queue projection — before vs after**")
            curr_q = day_stats["queued_groups"].values.tolist()
            proj_q = [0, round(19 * 0.5), round(49 * 0.5), 0, 0]
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Current queued groups",
                                 x=DAY_ORDER, y=curr_q, marker_color=C_RED, opacity=0.8))
            fig.add_trace(go.Bar(name="Projected queued groups",
                                 x=DAY_ORDER, y=proj_q, marker_color=C_GREEN))
            fig.update_layout(barmode="group", yaxis_title="Groups queued")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        st.divider()
        st.subheader("Revenue impact: dynamic pricing earns more even with fewer guests")

        curr_rev    = int(540 * 159 + 122 * 199)
        dynamic_rev = int(220 * 159 + (154 + 166) * 0.8 * 259 + 122 * 199)
        delta_rev   = dynamic_rev - curr_rev
        delta_pct   = delta_rev / curr_rev * 100

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current weekly revenue (est.)", f"฿{curr_rev:,}")
        col2.metric("Dynamic pricing revenue (est.)", f"฿{dynamic_rev:,}", f"+฿{delta_rev:,}")
        col3.metric("Revenue increase", f"+{delta_pct:.0f}%", "even with −20% pax on Tue/Wed")
        col4.metric("Tue/Wed walk-in groups >90 min", "32", "most price-sensitive segment")

        fig = go.Figure(go.Bar(
            x=["Current pricing\n(159/199 flat)", "Dynamic pricing\n(259 Tue+Wed only)"],
            y=[curr_rev, dynamic_rev],
            marker_color=[C_LIGHT_BLUE, C_GREEN],
            text=[f"฿{curr_rev:,}", f"฿{dynamic_rev:,}"],
            textposition="outside",
            width=0.4,
        ))
        fig.update_layout(yaxis_title="Weekly revenue estimate (฿)",
                         yaxis_range=[0, dynamic_rev * 1.2])
        st.plotly_chart(fig_layout(fig, height=320), use_container_width=True)

        st.divider()
        st.subheader("Why this works — the logic chain")
        steps = [
            ("1", "Data shows 32 walk-in groups stayed 90+ min on Tue/Wed. These guests came for the "
                  "159฿ all-you-can-eat deal and maximise their time. They are the most price-sensitive segment."),
            ("2", "Raising Tue/Wed price to 259฿ makes the deal less attractive for price-sensitive guests "
                  "— they shift to Mon, Fri, or Sat, which have capacity to absorb them."),
            ("3", "Fewer guests on Tue/Wed → less queue → shorter waits → in-house guests seat immediately "
                  "→ walk-in guests don't abandon queue → everyone happier."),
            ("4", "Higher price per guest on Tue/Wed means even with 20% fewer guests, revenue goes UP: "
                  "259 × 128 guests > 159 × 160 guests."),
            ("5", "Mon, Fri, Sat are untouched — their working model is preserved, and they may even gain "
                  "demand shifted from Tue/Wed."),
        ]
        for num, text in steps:
            c1, c2 = st.columns([0.05, 0.95])
            c1.markdown(
                f"<div style='background:#185FA5;color:white;border-radius:50%;"
                f"width:26px;height:26px;display:flex;align-items:center;"
                f"justify-content:center;font-size:12px;font-weight:600'>{num}</div>",
                unsafe_allow_html=True,
            )
            c2.markdown(text)

        insight_box(
            "<b>Why this is the best solution:</b> It is the only action that directly addresses "
            "the <b>root cause</b> (too many guests on specific days) rather than symptoms. "
            "It doesn't penalise guests on good days (unlike blanket price raise). "
            "It doesn't pretend the queue will shrink by reordering it (unlike queue skip). "
            "It doesn't change rules that nobody was breaking anyway (unlike seating time cap). "
            "And it generates <b>14% more revenue</b> — a win for both guest experience "
            "and business sustainability.",
            C_GREEN,
        )


if __name__ == "__main__":
    main()
