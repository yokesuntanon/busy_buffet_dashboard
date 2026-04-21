"""
Breakfast Buffet Analysis Dashboard
Hotel Amber 85 - Breakfast Buffet
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# PAGE CONFIG
st.set_page_config(
    page_title="Breakfast Buffet Analysis: Hotel Amber 85",
    layout="wide",
    initial_sidebar_state="expanded",
)

# COLOUR PALETTE
C_BLUE   = "#65BCB5"
C_ORANGE = "#ED802A"
C_RED    = "#A6171C"
C_GREEN  = "#A4CF4A"
C_AMBER  = "#BA7517"
C_LIGHT_BLUE = "#B5D4F4"
C_LIGHT_GREEN = "#BAD797"

DAY_ORDER = ["Fri, Mar 13", "Sat, Mar 14", "Sun, Mar 15", "Tue, Mar 17", "Wed, Mar 18"]
DAY_COLORS = {
    "Fri, Mar 13": C_BLUE,
    "Sat, Mar 14": C_ORANGE,
    "Sun, Mar 15": C_RED,
    "Tue, Mar 17": C_BLUE,
    "Wed, Mar 18": C_BLUE,
}

# DATA LOADING & CLEANING
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    sheet_map = {
        "133": "Fri, Mar 13",
        "143": "Sat, Mar 14",
        "153": "Sun, Mar 15",
        "173": "Tue, Mar 17",
        "183": "Wed, Mar 18",
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

    # FIXES 
    # Mar 18 svc 62: swapped meal times
    m62 = (full["day"] == "Wed, Mar 18") & (full["service_no."] == 62)
    full.loc[m62, ["meal_start", "meal_end"]] = \
        full.loc[m62, ["meal_end", "meal_start"]].values

    # Mar 18 svc 5: 02:29 → 07:29
    m5 = (full["day"] == "Wed, Jan 18") & (full["service_no."] == 5)
    full.loc[m5, "meal_start"] = "07:29:00"

    # Drop rows where pax=0/NaN AND no meal recorded
    drop = ((full["pax"] == 0) | full["pax"].isna()) & full["meal_start"].isna()
    full = full[~drop].copy()

    # pax=0 but has meal → treat pax as unknown
    full.loc[full["pax"] == 0, "pax"] = np.nan

    # TIME CONVERSION
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


# HELPERS
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


# MAIN
def main():
    # SIDEBAR
    with st.sidebar:
        st.title("Breakfast Buffet")
        st.caption("Hotel Amber 85: Breakfast Analysis")
        st.divider()

        uploaded = st.file_uploader(
            "Upload dataset (.xlsx)", type=["xlsx"]
        )
        st.divider()

        page = st.radio(
            "Topics",
            [
                "Overview",
                "S1: Long Waiting Times",
                "S2: Capacity Overload",
                "S3: Low Table Turnover",
                "Action 1: Reduce seating time",
                "Action 2: Raise price",
                "Action 3: Queue skip",
                "Recommended Solution",
            ],
        )
        st.divider()
        st.caption("Atmind Group")

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
            total_pax_in_house=("pax", "sum"),
            total_pax_walk_ins=("pax", "sum"),
        )
        .reindex(DAY_ORDER)
    )

    # OVERVIEW

    if page == "Overview":
        st.title("Breakfast Buffet — Analysis Overview")
        st.markdown(
            "Hotel Amber 85 promoted a breakfast buffet on TikTok "
            "and experienced a sudden surge in walk-in guests. This dashboard analyses "
            "5 days of service data to evaluate staff comments and proposed solutions."
        )
        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total guest groups", f"{len(df):,}")
        col2.metric("Total pax", f"{int(df['pax'].sum()):,}")
        col3.metric("Groups who queued", f"{df['has_queue'].sum()}")
        col4.metric("Walk-aways", f"{df['is_walkaway'].sum()}")

        st.divider()
        st.subheader("Daily Summary")
    
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

        pax_by_type = (
            df.groupby(["day", "Guest_type"])["pax"]
            .sum()
            .reindex(pd.MultiIndex.from_product(
                [DAY_ORDER, ["In house", "Walk in"]],
                names=["day", "Guest_type"]))
            .fillna(0)
            .reset_index()
        )
        ih_pax = pax_by_type[pax_by_type["Guest_type"] == "In house"]["pax"].values
        wi_pax = pax_by_type[pax_by_type["Guest_type"] == "Walk in"]["pax"].values

        dur_by_type = (
            meal[meal["meal_dur"] > 0]
            .groupby(["day", "Guest_type"])["meal_dur"]
            .mean()
            .reindex(pd.MultiIndex.from_product(
                [DAY_ORDER, ["In house", "Walk in"]],
                names=["day", "Guest_type"]))
            .fillna(0)
            .reset_index()
        )
        ih_dur = dur_by_type[dur_by_type["Guest_type"] == "In house"]["meal_dur"].values
        wi_dur = dur_by_type[dur_by_type["Guest_type"] == "Walk in"]["meal_dur"].values

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Pax by guest type per day**")
            fig_pax = go.Figure()
            fig_pax.add_trace(go.Bar(
                name="In house", x=DAY_ORDER, y=ih_pax,
                marker_color=C_BLUE,
                text=[int(v) for v in ih_pax], textposition="outside",
            ))
            fig_pax.add_trace(go.Bar(
                name="Walk in", x=DAY_ORDER, y=wi_pax,
                marker_color=C_ORANGE,
                text=[int(v) for v in wi_pax], textposition="outside",
            ))
            fig_pax.update_layout(barmode="group", yaxis_title="Pax")
            st.plotly_chart(fig_layout(fig_pax, height=360), use_container_width=True)

        with col2:
            st.markdown("**Avg seating (meal) duration by guest type per day**")
            fig_dur = go.Figure()
            fig_dur.add_trace(go.Bar(
                name="In house", x=DAY_ORDER,
                y=[round(v, 1) for v in ih_dur],
                marker_color=C_BLUE,
                text=[f"{v:.0f} min" for v in ih_dur], textposition="outside",
            ))
            fig_dur.add_trace(go.Bar(
                name="Walk in", x=DAY_ORDER,
                y=[round(v, 1) for v in wi_dur],
                marker_color=C_ORANGE,
                text=[f"{v:.0f} min" for v in wi_dur], textposition="outside",
            ))
            fig_dur.update_layout(barmode="group", yaxis_title="Avg duration (min)")
            st.plotly_chart(fig_layout(fig_dur, height=360), use_container_width=True)


        st.divider()
        st.subheader("Summary of findings")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Statement Analysis**")
            st.markdown("Statement 1: Long Waiting Times - **Partially True**")
            st.markdown("Statement 2: Capacity Overload - **False**")
            st.markdown("Statement 3: Low Table Turnover - **True**")
        with c2:
            st.markdown("**Action Analysis**")
            st.markdown("Action 1: Reduce seating time - **Won't Work**")
            st.markdown("Action 2: Raise price - **Won't Work**")
            st.markdown("Action 3: Queue skip - **Won't Work**")
        with c3:
            st.markdown("**Core Insights**")
            st.markdown("Weekend walk-in surge")
            st.markdown("Walk-ins sit significantly longer, especially on weekends")
            st.markdown("Queuing and walk-aways are exclusively a weekend problem")

    # STATEMENT 1

    elif page == "S1: Long Waiting Times":
        verdict_badge("PARTIALLY TRUE", "#FFFFFF", "#F9A822")
        st.title("Statement 1")
        st.markdown(
            """*"In-house customers are unhappy that they have to wait for a table. """
            """Walk-in customers are also unhappy, when they queue up for a long time """
            """and leave the queue because they don't want to wait any longer."*"""
        )

        stayed = df[df["has_queue"] & df["has_meal"]]
        wa     = df[df["is_walkaway"]]
        ih     = df[df["Guest_type"] == "In house"]
        wi     = df[df["Guest_type"] == "Walk in"]

        metric_row([
            ("In-house who queued", f"{ih['has_queue'].sum()} / {ih['has_meal'].sum()} groups", "out of all groups with seating"),
            ("In-house walk-aways", str(int((ih["is_walkaway"]).sum())), "avg 24 min wait"),
            ("Walk-in walk-aways", str(int((wi["is_walkaway"]).sum())), "avg 35 min wait"),
            ("Overall avg queue wait", "34 min", "for those who stayed"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Avg wait time by guest type")
            cats  = ["In-house\nstayed", "In-house\nwalk-away", "Walk-in\nstayed", "Walk-in\nwalk-away"]
            waits = [
                stayed[stayed["Guest_type"] == "In house"]["queue_wait"].mean(),
                wa[wa["Guest_type"] == "In house"]["queue_wait"].mean(),
                stayed[stayed["Guest_type"] == "Walk in"]["queue_wait"].mean(),
                wa[wa["Guest_type"] == "Walk in"]["queue_wait"].mean(),
            ]
            bar_colors = [C_BLUE, C_RED, C_GREEN, C_ORANGE]
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

        st.divider()
        st.subheader("Total pax: stayed vs walked away")

        ih_stayed  = stayed[stayed["Guest_type"] == "In house"]["pax"].sum()
        wi_stayed  = stayed[stayed["Guest_type"] == "Walk in"]["pax"].sum()
        ih_wa_pax  = wa[wa["Guest_type"] == "In house"]["pax"].sum()
        wi_wa_pax  = wa[wa["Guest_type"] == "Walk in"]["pax"].sum()
        ih_direct  = df[~df["has_queue"] & df["has_meal"] & (df["Guest_type"] == "In house")]["pax"].sum()
        wi_direct  = df[~df["has_queue"] & df["has_meal"] & (df["Guest_type"] == "Walk in")]["pax"].sum()

        fig_pax_outcome = go.Figure()
        fig_pax_outcome.add_trace(go.Bar(
            name="Seated directly (no queue)",
            x=["In house", "Walk in"],
            y=[int(ih_direct), int(wi_direct)],
            marker_color=C_BLUE,
            text=[int(ih_direct), int(wi_direct)],
            textposition="inside",
        ))
        fig_pax_outcome.add_trace(go.Bar(
            name="Queued then seated (stayed)",
            x=["In house", "Walk in"],
            y=[int(ih_stayed), int(wi_stayed)],
            marker_color=C_ORANGE,
            text=[int(ih_stayed), int(wi_stayed)],
            textposition="inside",
        ))
        fig_pax_outcome.add_trace(go.Bar(
            name="Queued then left (walk-away)",
            x=["In house", "Walk in"],
            y=[int(ih_wa_pax), int(wi_wa_pax)],
            marker_color=C_RED,
            text=[int(ih_wa_pax), int(wi_wa_pax)],
            textposition="inside",
        ))
        fig_pax_outcome.update_layout(
            barmode="stack",
            yaxis_title="Total pax",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_layout(fig_pax_outcome, height=400), use_container_width=True)

        insight_box(
            "<b>Verdict: Partially True</b><br><br>"

            "<b>Explanation:</b> The fact that 9 groups abandoned the queue proves that "
            "some guests were genuinely unhappy waiting. "
            "However, looking at the full pax breakdown, the walk-away segment (red) is visibly "
            "small for both guest types. The majority of guests (green) sat directly with no queue, "
            "and most who did wait (blue) chose to stay, meaning unhappiness existed but was "
            "not widespread.<br><br>"

            "On top of that, all queuing happened exclusively on <b>Sat and Sun</b>. "
            "Fri, Tue, and Wed had zero queuing across all guests so the 28–39 min waits "
            "and walk-aways the staff describe only affected a subset of days, not every day. "
            "The statement is true in that some guests were unhappy, but overstates it "
            "as an everyday problem.",
            C_AMBER,
        )

    # STATEMENT 2

    elif page == "S2: Capacity Overload":
        verdict_badge("FALSE", "#FFFFFF", C_RED)
        st.title("Statement 2")
        st.markdown(
            """*"We are very busy every day of the week. If it's going to be this busy """
            """every week I think it's impossible to sustain this business. This buffet """
            """business is not possible for this hotel."*"""
        )
        metric_row([
            ("Busiest day — Sun", "166 pax", "49 groups queued"),
            ("Quietest day — Fri", "102 pax", "0 groups queued"),
            ("Days with zero queuing", "3 of 5", "Fri, Tue, Wed"),
            ("Walk-aways all week", "9 total", "8 happened on Sun alone"),
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
                line=dict(color=C_LIGHT_GREEN, width=3.5),
                marker=dict(size=9, color=C_LIGHT_GREEN),
            ),
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Total pax", secondary_y=False)
        fig.update_yaxes(title_text="Groups queued", secondary_y=True, showgrid=False)
        fig_layout(fig, height=400)
        st.plotly_chart(fig, use_container_width=True)

        insight_box(
            "<b>Verdict: False</b><br><br>"

            "<b>Explanation:</b> 3 out of 5 days had <b>zero queuing.<b> "
            "The congestion happened only on Weekend"
            "Fri, Tue, and Wed are running smoothly. "
            "The business is not uniformly unsustainable. it has a specific, fixable "
            "problem on weekend.",
            C_RED,
        )

    # STATEMENT 3

    elif page == "Statement 3: Low Table Turnover":
        verdict_badge("TRUE", "#FFFFFF", C_GREEN)
        st.title("Statement 3")
        st.markdown(
            """*"Walk-in customers sit the whole day. It's very difficult to find seats """
            """for in-house customers. We don't have enough tables so when one customer """
            """sits for a long time it makes the queue very long."*"""
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
            st.subheader("Box plot: meal duration spread")
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
            "<b>Verdict: True</b><br><br>"

            "<b>Explanation:</b> Walk-in guests stay <b>66%</b> longer on average than "
            "in-house guests (73 & 44 min)."
            "On the busiest days (Sat/Sun), 32 walk-in groups stayed over 90 minutes, "
            "directly causing the queue to build up. ",
            C_GREEN,
        )

    # ACTION 1

    elif page == "Action 1 — Reduce seating time":
        verdict_badge("WON'T WORK", "#FFFFFF", C_RED)
        st.title("Action 1")
        st.markdown(
            "*Idea: If we limit how long guests can sit, tables will turn "
            "over faster and the queue will shrink.*"
        )
        metric_row([
            ("Max actual stay", "3h 45m", "nobody reached 5 hours"),
            ("Staying over 3 hrs", "0.9%", "3 groups total"),
            ("Staying over 2 hrs", "7.2%", "25 groups total"),
            ("Walk-in avg stay", "1h 13m"),
        ])
        st.divider()

        bins   = [0, 30, 60, 90, 120, 180, 300]
        labels = ["<30", "30–60", "60–90", "90–120", "120–180", "180+"]
        all_cut = pd.cut(meal["meal_dur"], bins=bins, labels=labels).value_counts().sort_index()
        total   = all_cut.sum()
        cum_pct = (all_cut.cumsum() / total * 100).values

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Guest count by meal duration")
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
            "<b>Explanation why it won't work:</b> <b>Nobody is using the 5-hour allowance.</b> "
            "The longest anyone actually stayed was 3h 45min. "
            "99% of guests leave within 3 hours on their own. "
            "Reducing the cap from 5 hours to 3 hours (or 2 hours) would not change "
            "actual behaviour at all. The real problem "
            "is the <b>volume of guests arriving at the same time on Sat and Sun</b>, "
            "not how long they sit.",
            C_RED,
        )

    # ACTION 2
    
    elif page == "Action 2 — Raise price":
        verdict_badge("WON'T WORK", "#FFFFFF", C_RED)
        st.title("Action 2")
        st.markdown(
            "*Idea: Higher price every day will reduce total demand "
            "and make the buffet manageable.*"
        )
        bad_days  = ["Sat, Mar 14", "Sun, Mar 15"]

        metric_row([
            ("Busy days", "2 of 5", "Tue & Wed only"),
            ("Normal days (no queue)", "3 of 5", "Mon, Fri, Sat"),
            ("Sat/Sun avg pax", "160", "vs Fri/Tue/Wed avg 114"),
        ])
        st.divider()

        st.subheader("Queue problems concentrated on 2 days only")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=DAY_ORDER,
            y=day_stats["total_pax"].values,
            name="Total pax",
            marker_color=[C_RED if d in bad_days else C_BLUE for d in DAY_ORDER],
            text=[f"{int(v)} pax" for v in day_stats["total_pax"].values],
            textposition="outside",
            ))
        fig.add_trace(go.Bar(
            x=DAY_ORDER,
            y=day_stats["queued_groups"].values,
            name="Groups queued",
            marker_color=[C_AMBER if d in bad_days else "rgba(0,0,0,0.05)" for d in DAY_ORDER],
            text=[f"{int(v)} queued" if v > 0 else "" for v in day_stats["queued_groups"].values],
            textposition="inside",
            ))
        fig.update_layout(barmode="overlay", yaxis_title="Count")
        st.plotly_chart(fig_layout(fig), use_container_width=True)    

        insight_box(
            "<b>Explanation why it won't work:</b> Raising prices <b>every day</b> is a blunt instrument "
            "aimed at a precise problem. Fri, Sat, and Sun are already running well,"
            "raising prices there risks losing normal-day guests and revenue. "
            "Meanwhile, the TikTok crowd driving the Sat/Sun spike may be price-insensitive "
            "and still come regardless.",
            C_RED,
        )

    # ACTION 3

    elif page == "Action 3 — Queue skip":
        verdict_badge("WON'T WORK", "#FFFFFF", C_RED)
        st.title("Action 3")
        st.markdown(
            "*Idea: Let in-house hotel guests skip the queue so they "
            "don't feel frustrated waiting behind walk-in guests.*"
        )
        
        sun = df[df["day"] == "Sun, Mar 15"]
        metric_row([
            ("Sun total queued", "49", "groups waiting on worst day"),
            ("In-house queued Sun", "17", "avg 30 min wait"),
            ("Walk-in queued Sun", "32", "avg 48 min wait"),
            ("New tables created by skipping", "0", "no capacity added"),
        ])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Queue composition on Sunday (busiest day)")
            ih_q = int(sun[sun["has_queue"] & (sun["Guest_type"] == "In house") & ~sun["is_walkaway"]].shape[0])
            wi_q = int(sun[sun["has_queue"] & (sun["Guest_type"] == "Walk in") & ~sun["is_walkaway"]].shape[0])
            wa_n = int(sun[sun["is_walkaway"]].shape[0])
            fig = go.Figure(go.Bar(
                x=["In-house\nqueued", "Walk-in\nqueued", "Walk-aways"],
                y=[ih_q, wi_q, wa_n],
                marker_color=[C_ORANGE, C_RED, C_BLUE],
                text=[ih_q, wi_q, wa_n], textposition="outside",
            ))
            fig.update_layout(yaxis_title="Number of groups", showlegend=False)
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        with col2:
            st.subheader("What queue skip actually changes")
            categories = ["Total groups\nin queue"]
            before = [49]
            after  = [49]
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Before skip policy", x=categories, y=before,
                                 marker_color=C_LIGHT_BLUE))
            fig.add_trace(go.Bar(name="After skip policy",  x=categories, y=after,
                                 marker_color=C_ORANGE))
            fig.update_layout(barmode="group", yaxis_title="Value",
                              annotations=[dict(x=0, y=52, text="49", showarrow=False,
                                               font=dict(color=C_RED, size=13))])
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        insight_box(
            "<b>Explanation why it won't work:</b> On the busiest day (Sun), 49 groups were queuing. "
            "If in-house guests skip, those <b>same 49 groups still wait</b>. Walk-in guests "
            "just wait even longer (their avg was already 48 min). "
            "This makes walk-in frustration worse, increasing walk-aways. "
            "In-house guests may feel slightly better, but the "
            "<b> problem of too many guests, not enough table turnover is completely unsolved.</b> ",
            C_RED,
        )

    # TASK 3 — Recommended SOLUTION
    
    elif page == "Recommended Solution":
        verdict_badge("RECOMMENDED SOLUTION", "#185FA5", "#E6F1FB")
        st.title("Task 3 — Dynamic pricing: target the problem days, not all days")
        explain_box(
            "<b>The insight:</b> The problem is a weekend demand spike on Sat & Sun. "
            "Fri, Tue, Wed run normally. The solution should target <b>only the problem days</b> "
            "with higher pricing, smoothing demand across the week rather than suppressing "
            "it everywhere."
        )

        st.subheader("The proposal: keep 159฿ on weekday, raise to 259฿ on weekend only")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Current vs projected pax after dynamic pricing**")
            proj_pax = [102, round(154 * 0.8), round(166 * 0.8), 118, 122]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Current pax",
                x=DAY_ORDER, y=day_stats["total_pax"].astype(int).values,
                marker_color=C_BLUE, opacity=0.8,
            ))
            fig.add_trace(go.Bar(
                name="Projected pax (dynamic price)",
                x=DAY_ORDER, y=proj_pax,
                marker_color=[C_GREEN if i not in [1, 2] else C_LIGHT_BLUE
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
                                 x=DAY_ORDER, y=proj_q, marker_color=C_ORANGE))
            fig.update_layout(barmode="group", yaxis_title="Groups queued")
            st.plotly_chart(fig_layout(fig), use_container_width=True)

        st.divider()
        st.subheader("Why this works")
        steps = [
            ("1", "Data shows 32 walk-in groups stayed 90+ min on Sat/Sun. These guests came for the "
                  "199฿ all-you-can-eat deal and maximise their time. They are the most price-sensitive segment."),
            ("2", "Raising Sat/Sun price to 259฿ makes the deal less attractive for price-sensitive guests. "
                  "They shift to Fri, Tue, or Wed, which have capacity to absorb them."),
            ("3", "Fewer guests on Sat/Sun => less queue => shorter waits => in-house guests seat immediately "
                  "=> walk-in guests don't abandon queue => everyone is happier."),
            ("4", "weekday are untouched. Their working model is preserved, and they may even gain "
                  "demand shifted from weekend."),
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
            "<b>Explanation why the solution is recommended:</b> It is the only action that directly addresses "
            "the <b>root cause</b> which is too many guests on specific days. "
            "It doesn't reduce guests on normal days (unlike every-day price raise). "
            "It doesn't increase the wait time by reordering the queue (unlike queue skip). "
            "It doesn't change rules that has no affect on guest behavior (unlike seating time capacity). "
            "This solution wins for both guest experience and business sustainability.",
            C_GREEN,
        )


if __name__ == "__main__":
    main()
