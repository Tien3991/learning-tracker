import plotly.graph_objects as go
from dateutil.parser import parse as parse_dt
from datetime import datetime, timezone, timedelta

def build_progress_chart(
    item: dict, completed_cps: list[dict], estimation: dict
) -> go.Figure:
    """Build a Plotly scatter chart with actual progress + projection line."""
    total = item["total_units"]
    unit = item["unit_type"]

    fig = go.Figure()

    if not completed_cps:
        fig.update_layout(
            title="No checkpoints yet",
            xaxis_title="Time",
            yaxis_title=unit.capitalize(),
            yaxis=dict(range=[0, total]),
        )
        return fig

    # Actual progress data (completed only)
    times = [parse_dt(cp["timestamp"]) for cp in completed_cps]
    values = [cp["units_completed"] for cp in completed_cps]
    notes = [cp.get("notes") or "" for cp in completed_cps]

    fig.add_trace(
        go.Scatter(
            x=times,
            y=values,
            mode="lines+markers+text",
            name="Progress",
            line=dict(color="#4a6cf7", width=2),
            marker=dict(color="#4a6cf7", size=8),
            text=notes,
            textposition="top center",
            textfont=dict(size=10),
        )
    )

    # Projection line
    if estimation.get("slope") and estimation.get("t0"):
        t0 = estimation["t0"]
        slope = estimation["slope"]
        end_hours = (total - 0) / slope
        end_time = t0 + timedelta(hours=end_hours)

        fig.add_trace(
            go.Scatter(
                x=[t0, end_time],
                y=[0, total],
                mode="lines",
                name="Projection",
                line=dict(color="#e74c3c", width=2, dash="dash"),
            )
        )

    fig.update_layout(
        xaxis_title="Time",
        yaxis_title=unit.capitalize(),
        yaxis=dict(range=[0, total]),
        height=400,
        margin=dict(l=40, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )

    return fig
