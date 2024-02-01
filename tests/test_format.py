from mypylib.html_fmt import display_grammar_errors


def test_display_grammar_errors():
    # 测试案例1：一个单词被替换
    original = "I has a pen"
    corrected = "I have a pen"
    explanations = ["'has' should be 'have' in this context."]
    assert (
        display_grammar_errors(original, corrected, explanations)
        == "<span>I</span> <del style='color:red;text-decoration: line-through' title='&#39;has&#39; should be &#39;have&#39; in this context.'>has</del> <ins style='color:blue;text-decoration: underline' title='&#39;has&#39; should be &#39;have&#39; in this context.'>have</ins> <span>a</span> <span>pen</span>"
    )

    # 测试案例2：一个单词被删除
    original = "I am a the student"
    corrected = "I am a student"
    explanations = ["'the' is unnecessary in this context."]
    assert (
        display_grammar_errors(original, corrected, explanations)
        == "<span>I</span> <span>am</span> <span>a</span> <del style='color:red;text-decoration: line-through' title='&#39;the&#39; is unnecessary in this context.'>the</del> <span>student</span>"
    )

    # 测试案例3：一个单词被添加
    original = "I student"
    corrected = "I am a student"
    explanations = [
        "'am' is missing in this context.",
        "'a' is missing in this context.",
    ]
    assert (
        display_grammar_errors(original, corrected, explanations)
        == "<span>I</span> <ins style='color:blue;text-decoration: underline' title='&#39;am&#39; is missing in this context.'>am</ins> <ins style='color:blue;text-decoration: underline' title='&#39;a&#39; is missing in this context.'>a</ins> <span>student</span>"
    )

    # 测试案例4：没有修改
    original = "I am a student"
    corrected = "I am a student"
    explanations = []
    assert (
        display_grammar_errors(original, corrected, explanations)
        == "<span>I</span> <span>am</span> <span>a</span> <span>student</span>"
    )
