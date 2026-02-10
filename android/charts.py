from kivy_garden.graph import Graph, MeshLinePlot
from dateutil.parser import parse as parse_dt


def build_progress_chart(item, completed_cps, estimation):
    """Build a kivy_garden.graph Graph widget showing progress + projection."""
    total = item["total_units"]
    unit = item["unit_type"]

    graph = Graph(
        xlabel="Hours since start",
        ylabel=unit.capitalize(),
        x_ticks_minor=1,
        x_ticks_major=5,
        y_ticks_major=max(1, int(total / 5)),
        y_grid_label=True,
        x_grid_label=True,
        padding=5,
        x_grid=True,
        y_grid=True,
        xmin=0,
        ymin=0,
        xmax=10,
        ymax=max(total, 1),
        size_hint_y=None,
        height=300,
        border_color=[0.3, 0.3, 0.3, 1],
        label_options={"color": [0, 0, 0, 1], "bold": False},
    )

    if len(completed_cps) < 1:
        return graph

    t0 = parse_dt(completed_cps[0]["timestamp"])

    # Actual progress line (blue)
    actual_plot = MeshLinePlot(color=[0.2, 0.4, 1, 1])
    actual_points = []
    max_hours = 0
    for cp in completed_cps:
        t = parse_dt(cp["timestamp"])
        hours = (t - t0).total_seconds() / 3600
        actual_points.append((hours, cp["units_completed"]))
        if hours > max_hours:
            max_hours = hours

    actual_plot.points = actual_points
    graph.add_plot(actual_plot)

    # Projection line (red dashed — MeshLinePlot doesn't support dash, use solid)
    proj_plot = MeshLinePlot(color=[1, 0.2, 0.2, 0.7])
    if estimation.get("slope") and estimation["slope"] > 0:
        end_hours = total / estimation["slope"]
        proj_plot.points = [(0, 0), (end_hours, total)]
        max_hours = max(max_hours, end_hours)
    else:
        proj_plot.points = [(0, 0), (max_hours if max_hours > 0 else 10, total)]
        max_hours = max(max_hours, 10)

    graph.add_plot(proj_plot)

    # Adjust graph axes
    graph.xmax = max(max_hours * 1.1, 1)
    graph.x_ticks_major = max(1, int(graph.xmax / 5))

    return graph
