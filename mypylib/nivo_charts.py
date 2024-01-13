import uuid
from typing import Dict

from streamlit_elements import elements, mui, nivo


def gen_radar(data: Dict[str, float], maps: Dict[str, str] | None, height=320):
    """
    Generate a radar chart using nivo library.

    Args:
        data (Dict[str, float]): A dictionary containing the data to be plotted.
        maps (Dict[str, str] | None): A dictionary containing the mapping of keys to labels.
        height (int): The height of the chart.

    Returns:
        None
    """
    DATA = []
    for key, value in data.items():
        DATA.append({"item": maps[key] if maps else key, "得分": value / 100})
    with elements(f"nivo_charts_{str(uuid.uuid4())}"):  # type: ignore
        with mui.Box(sx={"height": height}):
            nivo.Radar(
                data=DATA,
                maxValue=1.0,
                colors={"scheme": "set2"},
                fillOpacity=0.15,
                indexBy="item",
                keys=["得分"],
                valueFormat=">-.0%",
                enableDotLabel=True,
                isInteractive=False,
                margin={"top": 40, "right": 80, "bottom": 40, "left": 80},
                borderColor={"from": "color"},
                gridLabelOffset=36,
                dotSize=1,
                dotColor={"theme": "background"},
                dotBorderWidth=1,
                motionConfig="wobbly",
            )
