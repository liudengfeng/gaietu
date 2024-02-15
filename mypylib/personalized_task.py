from datetime import datetime, timedelta
import random


def create_memory_task(word, start_date=None):
    # 根据艾宾浩斯遗忘曲线的规律，我们可以制定以下复习计划：

    # 在学习后20分钟内进行第一次复习；
    # 在学习后1小时内进行第二次复习；
    # 在学习后1天内进行第三次复习；
    # 在学习后1周内进行第四次复习；
    # 在学习后1个月内进行第五次复习；
    # 在学习后6个月内进行第六次复习。
    if start_date is None:
        start_date = datetime.now()

    # 艾宾浩斯遗忘曲线的复习间隔
    intervals = [
        timedelta(minutes=20),
        timedelta(hours=1),
        timedelta(days=1),
        timedelta(weeks=1),
        timedelta(days=30),
        timedelta(days=180),
    ]

    memory_task = []
    for i in intervals:
        review_date = start_date + i
        memory_task.append((word, review_date))

    return memory_task


def calculate_sampling_probabilities(word_list, learning_records, test_records):
    # 初始化权重为等概率
    weights = {word: 1 for word in word_list}

    total_learning_time = sum(duration for _, duration in learning_records)
    # 按学习时长反向调整权重，降低学习时长的影响
    for word, duration in learning_records:
        weights[word] *= 1 - 0.1 * duration / total_learning_time

    # 根据测试记录调整权重
    for word, passed, failed in test_records:
        pass_factor = 1 - 0.5 * (passed / (passed + failed))
        fail_factor = 1 + 0.5 * (failed / (passed + failed))
        weights[word] *= pass_factor * fail_factor

    total_weight = sum(weights.values())
    probabilities = {word: weight / total_weight for word, weight in weights.items()}

    return probabilities
