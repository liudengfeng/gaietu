import difflib


def display_grammar_errors(original, corrected, explanations):
    if not explanations:  # 如果解释列表为空
        return " ".join(f"<span>{word}</span>" for word in corrected.split())

    diff = difflib.ndiff(original.split(), corrected.split())
    diff = list(diff)  # 生成列表

    result = []
    explanations_copy = explanations.copy()  # 创建副本

    for i in range(len(diff)):
        if diff[i][0] == "-":
            if explanations_copy:  # 检查副本是否为空
                explanation = (
                    explanations_copy.pop(0)
                    .replace("'", "&#39;")
                    .replace('"', "&quot;")
                )
            else:
                explanation = "No explanation available"  # 提供一个默认的解释
            result.append(
                f"<del style='color:red;text-decoration: line-through' title='{explanation}'>{diff[i][2:].lstrip()}</del>"
            )
            if i + 1 < len(diff) and diff[i + 1][0] == "+":
                result.append(
                    f"<ins style='color:blue;text-decoration: underline' title='{explanation}'>{diff[i + 1][2:].lstrip()}</ins>"
                )
                i += 1  # 跳过下一个元素
        elif diff[i][0] == "+":
            if i == 0 or diff[i - 1][0] != "-":
                explanation = (
                    explanations.pop(0).replace("'", "&#39;").replace('"', "&quot;")
                )
                result.append(
                    f"<ins style='color:blue;text-decoration: underline' title='{explanation}'>{diff[i][2:].lstrip()}</ins>"
                )
        else:
            result.append(f"<span>{diff[i][2:].lstrip()}</span>")

    return " ".join(result)
