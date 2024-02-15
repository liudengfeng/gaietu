from mypylib.personalized_task import calculate_sampling_probabilities


def test_calculate_sampling_probabilities():
    word_list = ["apple", "banana", "cherry", "date", "elderberry"]
    learning_records = [("cherry", 5), ("apple", 10), ("banana", 20), ("cherry", 30)]
    test_records = [
        ("apple", 1, 0),
        ("banana", 1, 3),
        ("cherry", 0, 2),
    ]

    probabilities = calculate_sampling_probabilities(
        word_list, learning_records, test_records
    )
    # 通过率高的单词，被抽中概率低
    assert abs(probabilities["apple"] - 0.096) < 0.001
    # 错误率高的单词，被抽中概率高
    assert abs(probabilities["banana"] - 0.229) < 0.001
    assert abs(probabilities["cherry"] - 0.279) < 0.001
    # 从没有学习的单词抽中概率相等
    assert abs(probabilities["date"] - 0.196) < 0.001
    assert abs(probabilities["elderberry"] - 0.196) < 0.001
