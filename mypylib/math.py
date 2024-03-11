from PIL import Image
import numpy as np
import os
import tempfile
import pandas as pd
import pytesseract
import cv2
from scipy import stats


def get_text_rows(data, height_range):
    # 提取图片的宽高
    img_width, _ = data["width"].max(), data["height"].max()
    # 初始化一个空列表来存储文字行
    text_rows = []

    # 按照 block_num 和 line_num 进行分组
    grouped = data.groupby(["block_num", "line_num"])

    # 对于每个组，检查单词的高度是否在给定的范围内
    for _, group in grouped:
        words_in_range = group[
            (group["level"] == 5)
            & (group["height"] >= height_range[0])
            & (group["height"] <= height_range[1])
        ]

        # 如果有至少5个单词的高度在给定的范围内，那么这个组就是一个文字行
        if len(words_in_range) >= 5:
            line = group[(group["level"] == 4)].iloc[0]
            if line["width"] >= img_width * 0.2:
                text_rows.append(line)

    return text_rows


def get_height_range(data, factor):
    # 选择 level==5 的行，这些行对应单词
    words = data[
        (data["level"] == 5)
        & (data["text"].notnull())
        & (data["text"].ne(""))
        & (data["conf"] > 30)
    ]

    # 获取单词高度的众数
    mode_word_height = words["height"].mode()

    # 计算众数的平均值
    average_mode_word_height = mode_word_height.mean()

    # 计算高度范围
    min_height = round(average_mode_word_height * (1 - factor))
    max_height = round(average_mode_word_height * (1 + factor))

    return min_height, max_height


def expand_bounding_box(text_rows, original_box, img_array, pixel_expansion_limit=30):
    # Initialize the expanded bounding box to the original bounding box
    x_min_exp, y_min_exp, x_max_exp, y_max_exp = original_box

    for direction in ["up", "down", "left", "right"]:
        pixel_expansion_count = 0
        while pixel_expansion_count < pixel_expansion_limit:
            if direction == "up" and y_min_exp > 0:
                y_min_exp -= 1
            elif direction == "left" and x_min_exp > 0:
                x_min_exp -= 1
            elif direction == "right" and x_max_exp < img_array.shape[1] - 1:
                x_max_exp += 1
            elif direction == "down" and y_max_exp < img_array.shape[0] - 1:
                y_max_exp += 1
            else:
                break

            pixel_expansion_count += 1

            # Check if the expanded area intersects with any text row
            for row in text_rows:
                row_x_min = row["left"]
                row_y_min = row["top"]
                row_x_max = row["left"] + row["width"]
                row_y_max = row["top"] + row["height"]

                if (
                    x_min_exp < row_x_max
                    and x_max_exp > row_x_min
                    and y_min_exp < row_y_max
                    and y_max_exp > row_y_min
                ):
                    # If it intersects, stop expanding in this direction
                    if direction == "up":
                        y_min_exp += 1
                    elif direction == "left":
                        x_min_exp += 1
                    elif direction == "right":
                        x_max_exp -= 1
                    elif direction == "down":
                        y_max_exp -= 1
                    break

    return x_min_exp, y_min_exp, x_max_exp, y_max_exp


def remove_text_keep_illustrations(image_path, output_to_file=False):
    # Use PIL to read the image
    pil_img = Image.open(image_path)
    img_gray = pil_img.convert("L")
    # Convert the PIL image to a NumPy array
    img_array = np.array(img_gray)

    # Perform OCR on the image to get the text bounding boxes
    data = pytesseract.image_to_data(
        img_array,
        # lang="chi_sim",
        lang="osd",
        output_type=pytesseract.Output.DATAFRAME,
    )

    min_height, max_height = get_height_range(data, 0.3)

    # Check if the image is already grayscale
    if len(img_array.shape) == 2:
        gray = img_array
    else:
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    # Use a higher threshold for edge detection
    edges = cv2.Canny(gray, 50, 300)  # Increase the thresholds
    # Find contours in the image
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Initialize the list of bounding boxes
    boxes = []
    # For each contour, check if it is likely to be an illustration
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Only add bounding boxes with area greater than 300 to all_boxes
        if w > 30 and h > 30:
            # This contour is likely to be an illustration, so add its bounding box to the list
            boxes.append([x, y, x + w, y + h])

    # Create a blank image with the same size as the original image
    blank_img = np.full((*img_array.shape, 3), 255)
    # Check if boxes is empty
    if boxes:
        # Combine the bounding boxes into a large bounding box
        original_box = (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        text_rows = get_text_rows(data, (min_height, max_height))

        # Initialize the expanded bounding box to the original bounding box
        x_min_exp, y_min_exp, x_max_exp, y_max_exp = expand_bounding_box(
            text_rows, original_box, img_array
        )

        # Convert the grayscale image to a color image
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

        # Update the blank image with the expanded bounding box
        blank_img[y_min_exp:y_max_exp, x_min_exp:x_max_exp] = img_array[
            y_min_exp:y_max_exp, x_min_exp:x_max_exp
        ]

    # If output_to_file is True, save the image to a file
    if output_to_file:
        _, temp_filename = tempfile.mkstemp(suffix=os.path.splitext(image_path)[1])
        cv2.imwrite(temp_filename, blank_img)
        return temp_filename

    # Return the image array
    return blank_img


def remove_illustrations_keep_text(image_path, output_to_file=False):
    # Use PIL to read the image
    pil_img = Image.open(image_path)
    img_gray = pil_img.convert("L")
    # Convert the PIL image to a NumPy array
    img_array = np.array(img_gray)

    # Perform OCR on the image to get the text bounding boxes
    data = pytesseract.image_to_data(
        img_array,
        lang="osd",
        output_type=pytesseract.Output.DATAFRAME,
    )

    min_height, max_height = get_height_range(data, 0.3)

    # Check if the image is already grayscale
    if len(img_array.shape) == 2:
        gray = img_array
    else:
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    # Use a higher threshold for edge detection
    edges = cv2.Canny(gray, 50, 300)  # Increase the thresholds
    # Find contours in the image
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Initialize the list of bounding boxes
    boxes = []
    # For each contour, check if it is likely to be an illustration
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Only add bounding boxes with area greater than 300 to all_boxes
        if w > 30 and h > 30:
            # This contour is likely to be an illustration, so add its bounding box to the list
            boxes.append([x, y, x + w, y + h])

    # Create a blank image with the same size as the original image
    blank_img = np.full((*img_array.shape, 3), 255)
    # Check if boxes is empty
    if boxes:
        # Combine the bounding boxes into a large bounding box
        original_box = (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        text_rows = get_text_rows(data, (min_height, max_height))

        # Initialize the expanded bounding box to the original bounding box
        x_min_exp, y_min_exp, x_max_exp, y_max_exp = expand_bounding_box(
            text_rows, original_box, img_array
        )

        # Convert the grayscale image to a color image
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

        # Update the blank image with the expanded bounding box
        blank_img[y_min_exp:y_max_exp, x_min_exp:x_max_exp] = img_array[
            y_min_exp:y_max_exp, x_min_exp:x_max_exp
        ]

    # If output_to_file is True, save the image to a file
    if output_to_file:
        _, temp_filename = tempfile.mkstemp(suffix=os.path.splitext(image_path)[1])
        cv2.imwrite(temp_filename, blank_img)
        return temp_filename

    # Return the image array
    return blank_img
