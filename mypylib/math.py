from PIL import Image
import numpy as np
import os
import tempfile
import pandas as pd
import pytesseract
import cv2
from scipy import stats


# def find_combined_box(image_path):
#     # 读取图像
#     img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

#     # 使用 Otsu's 方法自动计算阈值
#     _, binary_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

#     # 找到所有的轮廓
#     contours, _ = cv2.findContours(
#         binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
#     )

#     # 计算所有轮廓的边界矩形
#     boxes = [cv2.boundingRect(contour) for contour in contours]

#     # 找到所有矩形的最小 x 坐标、最小 y 坐标、最大 x 坐标和最大 y 坐标
#     min_x = min(x for x, y, w, h in boxes)
#     min_y = min(y for x, y, w, h in boxes)
#     max_x = max(x + w for x, y, w, h in boxes)
#     max_y = max(y + h for x, y, w, h in boxes)

#     # 创建一个新的矩形
#     combined_box = (min_x, min_y, max_x - min_x, max_y - min_y)

#     return combined_box


# def is_text_line(
#     block_data,
#     line_num,
#     img_width,
#     img_height,
#     size_threshold=0.01,
#     area_threshold=0.005,
# ):
#     # 获取指定行的数据
#     line_data = block_data[block_data["line_num"] == line_num]

#     # 找出 level == 4 的行
#     level_4_row = line_data[line_data["level"] == 4].iloc[0]

#     # 计算行的面积
#     line_area = level_4_row["width"] * level_4_row["height"]

#     # 如果行的面积小于阈值，则认为不是文本
#     if line_area < img_width * img_height * area_threshold:
#         # print(
#         #     f'Block: {block_data["block_num"].iloc[0]}, Line: {line_num} has area less than threshold.'
#         # )
#         return False

#     # 如果行的宽度或高度小于图像宽度或高度的阈值，则认为不是文本
#     if (
#         level_4_row["width"] < img_width * size_threshold
#         or level_4_row["height"] < img_height * size_threshold
#     ):
#         # print(
#         #     f'Block: {block_data["block_num"].iloc[0]}, Line: {line_num} has width or height less than threshold.'
#         # )
#         return False

#     # 获取 level == 5 的行
#     word_level_data = line_data[line_data["level"] == 5]

#     # 获取 level == 5 且 conf > 0 且 text 不为空或者不是 NaN 的单词的宽度
#     # 获取满足条件的行
#     conf_positive_rows = word_level_data[
#         (word_level_data["level"] == 5)
#         & (word_level_data["conf"] > 0)
#         & word_level_data["text"].notnull()
#         & word_level_data["text"].str.strip().ne("")
#     ]

#     # 计算满足条件的单词的宽度
#     conf_positive_width = conf_positive_rows["width"].sum()
#     # 计算比例
#     ratio = conf_positive_width / level_4_row["width"]

#     # 如果比例大于 50%，则返回 True，否则返回 False
#     return ratio > 0.5


def get_combined_bounding_box(img):
    # Apply binary thresholding
    _, binary_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find the contours
    contours, _ = cv2.findContours(
        binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Check if any contour is found
    if contours:
        # Find the combined bounding box of all contours
        x_min = min([cv2.boundingRect(c)[0] for c in contours])
        y_min = min([cv2.boundingRect(c)[1] for c in contours])
        x_max = max([cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] for c in contours])
        y_max = max([cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] for c in contours])

        return (x_min, y_min, x_max, y_max)
    else:
        return None


def is_text_line(row, mode_height):
    # Check if the height of the row is close to the mode height
    # and the conf value is greater than 20
    if (
        abs(row["height"] - mode_height) <= mode_height * 0.3 and row["conf"] > 20.0
    ):  # 10% tolerance
        return True
    return False


def is_text_block(block, img_width, img_height, mode_height):
    # Calculate the width and height of the block
    block_width = block["left"].max() + block["width"].max() - block["left"].min()
    block_height = block["top"].max() + block["height"].max() - block["top"].min()

    # Check if the width or height of the block is less than 1% of the image's width or height
    if block_width < img_width * 0.01 or block_height < img_height * 0.01:
        # 打印信息
        # print(
        #     f"Block num: {block['block_num']} Block Width: {block_width}, Block Height: {block_height}"
        # )
        return False

    level_5_lines = block[block["level"] == 5]
    text_lines = []
    for _, row in level_5_lines.iterrows():
        res = is_text_line(row, mode_height)
        # print(f"Row: {row['block_num']},{row['line_num']} Is Text Line: {res}")
        text_lines.append(res)

    text_lines = sum(text_lines)

    # Check if the number of text lines is more than 1
    if text_lines >= 1:
        return True

    return False


def get_text_blocks(img):
    # img = Image.open(fp)
    # img = np.array(img)
    data = pytesseract.image_to_data(
        img, lang="osd", output_type=pytesseract.Output.DATAFRAME
    )
    mode_height = stats.mode(data[data["level"] == 5]["height"])[0]
    grouped = data.groupby("block_num")
    text_blocks = []
    for name, group in grouped:
        if name == 0:  # Skip block number 0
            continue
        is_text = is_text_block(group, img.shape[1], img.shape[0], mode_height)
        # print(f"Block Number: {name}, Is Text Block: {is_text}")
        if is_text:
            text_blocks.append(group.iloc[0])  # Add the first row of the group

    return text_blocks


def remove_text_keep_illustrations(image_path, output_to_file=False):
    # Use PIL to read image file
    img_pil = Image.open(image_path)

    # Convert the image to grayscale
    img = np.array(img_pil.convert("L"))
    img_copy = np.copy(img)  # Copy the image

    text_blocks = get_text_blocks(img)

    # Set the pixels of the text blocks to 255 in the copied image
    for block in text_blocks:
        img_copy[
            block["top"] : block["top"] + block["height"],
            block["left"] : block["left"] + block["width"],
        ] = 255

    box = get_combined_bounding_box(img_copy)
    img_area = img.shape[0] * img.shape[1]
    if box:
        out = np.full_like(img, 255)
        x_min, y_min, x_max, y_max = box
        box_width = x_max - x_min
        box_height = y_max - y_min
        # Calculate the area of the box
        box_area = box_width * box_height
        if box_area < 0.05 * img_area:
            pass
        else:
            # Crop the original image to the combined bounding box
            out[y_min:y_max, x_min:x_max] = img[y_min:y_max, x_min:x_max]
    else:
        out = img

    if output_to_file:
        # 获取原路径中的扩展名
        _, ext = os.path.splitext(image_path)

        # 创建临时文件输出路径
        output_path = tempfile.mktemp(suffix=ext)

        # 保存图像
        Image.fromarray(out).save(output_path)

        return output_path

    else:
        return out
