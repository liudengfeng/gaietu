LANGUAGES = ["en-US", "zh-CN", "fr-FR", "ja-JP", "en-GB"]

LAN_MAPS = {
    "en-US": "美式英语",
    "en-GB": "英式英语",
    "zh-CN": "简体中文",
    "ja-JP": "日语",
    "fr-FR": "法语",
}

CEFR_LEVEL_MAPS = {
    "A1": "入门级",
    "A2": "初级",
    "B1": "中级",
    "B2": "中高级",
    "C1": "高级",
    "C2": "母语级",
}

CEFR_LEVEL_DETAIL = {
    "A1": [
        "能够理解并运用与自己最切身相关且经常使用的表达方式和非常简单的语句，例如：个人的姓名、家庭成员、基本日常活动、购物等。",
        "能够用简单的句子与他人进行简单的交流，例如：介绍自己、询问和回答有关个人的信息等。",
    ],
    "A2": [
        "能够理解并运用日常生活中经常使用的表达方式和简单的语句，例如：基本个人和家庭信息、购物、地理位置、就业等。",
        "能够用简单的句子表达个人的需要、想法和感受，例如：介绍自己的兴趣爱好、谈论自己的计划等。",
    ],
    "B1": [
        "能够理解日常生活中常见的口头和书面信息，例如：工作、学习、休闲等方面的信息。",
        "能够用简单的句子和语段表达日常生活和工作中常见的主题，例如：描述个人经历、谈论自己的计划和愿望等。",
    ],
    "B2": [
        "能够理解日常生活中和工作中广泛的口头和书面信息，例如：新闻报道、教育课程、专业文献等。",
        "能够用清晰的句子和语段表达复杂的主题，例如：讨论观点、分析问题等。",
    ],
    "C1": ["能够理解复杂的口头和书面信息，例如：长篇文章、专业文献等。", "能够用流利、准确的语言表达复杂的主题，例如：分析、批评、总结等。"],
    "C2": ["能够理解任何口头和书面信息，无论其复杂程度如何。", "能够用流利、准确、自然的语言表达任何主题，例如：阐述观点、辩论、创作等。"],
}

# 主题场景适用范围
THEME_SCENE = {
    "日常生活": [
        "A1",
        "A2",
        "B1",
        "B2",
    ],
    "社交活动": [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "个人发展": [
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "文化交流": [
        "B2",
        "C1",
        "C2",
    ],
    "学术交流": [
        "C1",
        "C2",
    ],
    "职场交流": [
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "专业领域": [
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "旅游事务": [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "美食文化": [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "饮食健康": [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ],
    "新闻资讯": [
        "B2",
        "C1",
        "C2",
    ],
    "时事热点": [
        "B2",
        "C1",
        "C2",
    ],
}

FAKE_EMAIL_DOMAIN = "example.com"


TOPICS = {
    "en-US": [
        "Current events",
        "Social issues",
        "Science and technology",
        "History and culture",
        "Arts and entertainment",
        "Personal experiences",
        "Work and education",
        "Food and travel",
        "Sports and hobbies",
        "Family and friends",
        "Health and fitness",
        "Business and finance",
        "The environment",
    ],
    "zh-CN": [
        "时事问题",
        "社会问题",
        "科学技术",
        "历史文化",
        "艺术和娱乐",
        "个人经历",
        "工作与教育",
        "美食和旅行",
        "运动和爱好",
        "亲朋好友",
        "健康和健身",
        "商业和金融",
        "环境",
    ],
    "fr-FR": [
        "Actualités",
        "Problèmes sociaux",
        "Science et technologie",
        "Histoire et culture",
        "Les arts et le divertissement",
        "Expériences personnelles",
        "Travail et Education",
        "Nourriture et voyages",
        "Sports et loisirs",
        "Famille et amis",
        "Santé et remise en forme",
        "Entreprise et finance",
        "L'environnement",
    ],
    "ja-JP": [
        "時事問題",
        "社会問題",
        "科学技術",
        "歴史と文化",
        "芸術とエンターテイメント",
        "個人的な経験",
        "仕事と教育",
        "食と旅",
        "スポーツと趣味",
        "家族と友達",
        "健康と運動",
        "ビジネスと金融",
        "環境",
    ],
}

NAMES = {
    "zh-CN": {
        "男性": ["浩然", "子轩", "皓轩", "梓浩", "浩宇", "宇轩", "亦辰", "宇辰", "宇航", "子墨"],
        "女性": ["一诺", "依诺", "欣怡", "梓涵", "诗涵", "欣妍", "可欣", "语汐", "雨桐", "梦瑶"],
    },
    "en-US": {
        "male": [
            "Michael",
            "David",
            "John",
            "Ethan",
            "Daniel",
            "Elijah",
            "Alexander",
            "Matthew",
            "Joseph",
            "William",
        ],
        "female": [
            "Ava",
            "Olivia",
            "Emma",
            "Sophia",
            "Isabella",
            "Mia",
            "Abigail",
            "Evelyn",
            "Charlotte",
            "Emily",
        ],
    },
    "fr-FR": {
        "mâle": [
            "Gabriel",
            "Léo",
            "Raphaël",
            "Louis",
            "Arthur",
            "Noah",
            "Malo",
            "Mae",
            "Elio",
            "Nino",
        ],
        "femelle": [
            "Jade",
            "Louise",
            "Emma",
            "Ambre",
            "Alice",
            "Alba",
            "Ava",
            "Alma",
            "Iris",
            "Romy",
        ],
    },
    "ja-JP": {
        "男": ["翔太", "悠仁", "蓮", "湊", "楓", "大翔", "颯太", "悠真", "湊翔", "優斗"],
        "女": ["凛", "結衣", "紬", "杏", "結衣", "葵", "凜", "結菜", "心愛", "結愛"],
    },
}

PROVINCES = [
    "辽宁",
    "吉林",
    "黑龙江",
    "北京",
    "天津",
    "河北",
    "山西",
    "内蒙古自治区",
    "上海",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "重庆",
    "四川",
    "贵州",
    "云南",
    "西藏自治区",
    "陕西",
    "甘肃",
    "青海",
    "新疆维吾尔自治区",
    "香港特别行政区",
    "澳门特别行政区",
    "台湾",
]


def rearrange_theme_scene():
    level_to_theme = {}
    for theme, levels in THEME_SCENE.items():
        for level in levels:
            if level not in level_to_theme:
                level_to_theme[level] = [theme]
            else:
                level_to_theme[level].append(theme)
    return level_to_theme
