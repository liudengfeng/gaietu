from PIL import Image
import numpy as np
import os
import tempfile
from matplotlib import pyplot as plt
import pandas as pd
import pytesseract


def remove_text_keep_illustrations(image_path, output_to_file=False):
    """
    Removes text from an image while preserving illustrations.

    Args:
        image_path (str): The path to the input image file.
        output_to_file (bool, optional): Whether to save the modified image to a file.
            Defaults to False.

    Returns:
        numpy.ndarray or str: If `output_to_file` is False, returns a numpy array
            representing the modified image. If `output_to_file` is True, returns the
            path to the saved image file.

    """

    # 读取图像
    img = Image.open(image_path)
    img = np.array(img)

    # 计算图像的平均像素值
    avg_pixel_value = np.mean(img)

    # 如果平均像素值大于一半，那么将掩码设置为 0（黑色）
    # 否则，将掩码设置为 255（白色）
    mask_value = 255 if avg_pixel_value > 128 else 0

    # 创建一个副本图像
    img_copy = img.copy()

    data = pytesseract.image_to_data(
        img, lang="osd", output_type=pytesseract.Output.DATAFRAME
    )
    # 按 block_num 分组取第一行
    first_rows = data.groupby("block_num").first()
    first_rows["is_text"] = False

    # 遍历每一行
    for index, row in first_rows.iterrows():
        # 找到每个组内的所有行
        group_rows = data[data["block_num"] == index]

        # 遍历组内的每一项的 text
        for _, group_row in group_rows.iterrows():
            # 如果存在有效文本，则将其属性 is_text 更改为 True
            if not pd.isna(group_row["text"]) and group_row["text"].strip() != "":
                first_rows.at[index, "is_text"] = True
                break

    # 遍历每一行，跳过第一行
    for index, row in first_rows.iloc[1:].iterrows():
        # 检查 text 是否为文本
        if not row["is_text"]:
            continue

        # 将文本部分的区域像素值设置为 mask_value
        img_copy[
            row["top"] : row["top"] + row["height"],
            row["left"] : row["left"] + row["width"],
        ] = mask_value

    if output_to_file:
        # 获取原路径中的扩展名
        _, ext = os.path.splitext(image_path)

        # 创建临时文件输出路径
        output_path = tempfile.mktemp(suffix=ext)

        # 保存图像
        Image.fromarray(img_copy).save(output_path)

        return output_path

    else:
        return img_copy
