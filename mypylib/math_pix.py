import base64
import io
from datetime import timedelta

import requests
import streamlit as st
from PIL import Image, ImageDraw

service = "https://api.mathpix.com/v3/text"
default_headers = {
    "app_id": st.secrets["MATHPIX_APP_ID"],
    "app_key": st.secrets["MATHPIX_APP_KEY"],
    "Content-type": "application/json",
}


def image_uri(bytes_data):
    # bytes_data = uploaded_file.getvalue()
    return "data:image/jpg;base64," + base64.b64encode(bytes_data).decode("utf-8")


@st.cache_data(ttl=timedelta(days=1))
def mathpix_ocr_read(bytes_data, include_word_data=False, timeout=10) -> dict:
    src = image_uri(bytes_data)
    r = requests.post(
        service,
        json={
            "src": src,
            "ocr": ["text", "math"],
            "formats": [
                "text",
                "wolfram",
                "mathml",
            ],
            "math_inline_delimiters": ["$", "$"],
            # "include_line_data": True,
            "include_word_data": include_word_data,
        },
        headers=default_headers,
        timeout=timeout,
    )
    return r.json()


def get_diagram_box(data, threshold=0.05):
    diagram_box = None
    diagram_areas = []
    width = data["image_width"]
    height = data["image_height"]
    # 遍历 "line_data" 数组
    for item in data["word_data"]:
        if item["type"] in ["diagram", "chart"]:
            # 获取矩形区域的坐标
            coordinates = item["cnt"]

            left = min(co[0] for co in coordinates)
            top = min(co[1] for co in coordinates)
            right = max(co[0] for co in coordinates)
            bottom = max(co[1] for co in coordinates)

            # 计算矩形区域的宽度和高度
            rect_width = right - left
            rect_height = bottom - top

            # 检查矩形区域的宽度和高度是否小于图片宽度和高度的阈值
            if rect_width > width * threshold and rect_height > height * threshold:
                diagram_areas.append((left, top, right, bottom))
            # else:
            #     print(f"Discard diagram area: {(left, top, right, bottom)}")

    # 合并插图的 box
    offset = 2
    if diagram_areas:
        diagram_left = min(area[0] for area in diagram_areas)
        diagram_top = min(area[1] for area in diagram_areas)
        diagram_right = max(area[2] for area in diagram_areas)
        diagram_bottom = max(area[3] for area in diagram_areas)
        new_diagram_top = max(0, diagram_top + offset)
        new_diagram_bottom = min(height, diagram_bottom - offset)
        # 创建新的插图 box
        diagram_box = (
            diagram_left,
            new_diagram_top,
            diagram_right,
            new_diagram_bottom,
        )
    return diagram_box


def erase_diagram_and_recognize(uploaded_file_content, has_diagram):
    if has_diagram:
        ocr = mathpix_ocr_read(uploaded_file_content, include_word_data=True)
        box = get_diagram_box(ocr)
        if box:
            # 将 bytes 转换为 BytesIO 对象
            uploaded_file = io.BytesIO(uploaded_file_content)
            # 打开图片
            img = Image.open(uploaded_file)
            draw = ImageDraw.Draw(img)
            draw.rectangle(box, fill=(255, 255, 255))
            # 创建一个新的 BytesIO 对象来保存修改后的图片
            modified_image = io.BytesIO()
            img.save(modified_image, "PNG")
            # st.image(modified_image, use_column_width=True)
            # 重置新的 BytesIO 对象的指针到开始位置
            modified_image.seek(0)
            ocr = mathpix_ocr_read(modified_image.getvalue(), include_word_data=False)
        else:
            ocr = mathpix_ocr_read(uploaded_file_content, include_word_data=False)
    else:
        ocr = mathpix_ocr_read(uploaded_file_content, include_word_data=False)
    return ocr
