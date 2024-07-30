from collections import defaultdict
import re
from math import floor, log10
from datetime import datetime
from flask_login import current_user
from coyote.util.common_utility import CommonUtility
from flask import current_app as app
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder
from typing import Any
import json


class DashBoardUtility:
    """
    Utility class for variants blueprint
    """

    @staticmethod
    def generate_pie_chart(data, title) -> Any:
        fig = go.Figure(
            data=[go.Pie(labels=list(data.keys()), values=list(data.values()), hole=0.3)]
        )
        fig.update_layout(title_text=title, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        fig.update_traces(textinfo="value+label", marker=dict(colors=px.colors.qualitative.Plotly))
        return json.dumps(fig, cls=PlotlyJSONEncoder)
