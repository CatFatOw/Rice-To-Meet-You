"""File handles the core route logic for the grid_metric routes"""

def add_cell_id(metric):
    """Attach the readable grid cell_id to a metric response."""
    if metric and metric.grid_cell:
        metric.cell_id = metric.grid_cell.cell_id
    return metric

def add_cell_ids(metrics):
    """Attach readable grid cell_id values to metric responses."""
    return [add_cell_id(metric) for metric in metrics]