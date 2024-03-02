from PIL import Image
import numpy as np
import os
import tempfile
import pandas as pd
import pytesseract


def is_text_line(
    block_data,
    line_num,
    img_width,
    img_height,
    size_threshold=0.01,
    area_threshold=0.005,
):
    # 获取指定行的数据
    line_data = block_data[block_data["line_num"] == line_num]

    # 找出 level == 4 的行
    level_4_row = line_data[line_data["level"] == 4].iloc[0]

    # 计算行的面积
    line_area = level_4_row["width"] * level_4_row["height"]

    # 如果行的面积小于阈值，则认为不是文本
    if line_area < img_width * img_height * area_threshold:
        # print(
        #     f'Block: {block_data["block_num"].iloc[0]}, Line: {line_num} has area less than threshold.'
        # )
        return False

    # 如果行的宽度或高度小于图像宽度或高度的阈值，则认为不是文本
    if (
        level_4_row["width"] < img_width * size_threshold
        or level_4_row["height"] < img_height * size_threshold
    ):
        # print(
        #     f'Block: {block_data["block_num"].iloc[0]}, Line: {line_num} has width or height less than threshold.'
        # )
        return False

    # 获取 level == 5 的行
    word_level_data = line_data[line_data["level"] == 5]

    # 获取 level == 5 且 conf > 0 且 text 不为空或者不是 NaN 的单词的宽度
    # 获取满足条件的行
    conf_positive_rows = word_level_data[
        (word_level_data["level"] == 5)
        & (word_level_data["conf"] > 0)
        & word_level_data["text"].notnull()
        & word_level_data["text"].str.strip().ne("")
    ]

    # 计算满足条件的单词的宽度
    conf_positive_width = conf_positive_rows["width"].sum()
    # 计算比例
    ratio = conf_positive_width / level_4_row["width"]

    # 如果比例大于 50%，则返回 True，否则返回 False
    return ratio > 0.5


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

    # 计算图像的宽度和高度
    img_width = img.shape[1]
    img_height = img.shape[0]

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

    # 按 block_num 分组
    grouped = data.groupby("block_num")

    # 遍历每个组
    for _, group in grouped:
        # 找出 level == 4 的行
        level_4_rows = group[group["level"] == 4]
        # 遍历 level == 4 的行
        for _, row in level_4_rows.iterrows():
            # 使用 is_text_line 函数判断该行是否为文本行
            if is_text_line(group, row["line_num"], img_width, img_height):
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
