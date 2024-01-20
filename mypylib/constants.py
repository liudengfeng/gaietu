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


SCENARIO_MAPS = {
    "日常生活": [
        "1. 起床准备上班",
        "2. 在上班路上遇到堵车",
        "3. 进入办公室，打开电脑，开始工作",
        "4. 接到客户的电话，讨论项目细节",
        "5. 参加一个会议，讨论项目的进展",
        "6. 在午餐时间去餐厅吃饭",
        "7. 下午继续工作，完成项目",
        "8. 下班回家，在路上买一些菜",
        "9. 到家后，开始做晚饭",
        "10. 和家人一起吃饭",
        "11. 吃完饭后，洗碗筷",
        "12. 看电视或上网放松一下",
        "13. 洗澡睡觉",
        "14. 在公园里散步",
        "15. 去超市购物",
        "16. 去图书馆借书",
        "17. 去健身房锻炼身体",
        "18. 去理发店理发",
        "19. 去医院看病",
        "20. 去银行取钱",
        "21. 去邮局寄信",
        "22. 去洗衣店洗衣服",
        "23. 去餐厅吃饭",
        "24. 去电影院看电影",
        "25. 去游乐园玩耍",
        "26. 去动物园看动物",
        "27. 去博物馆参观展览",
        "28. 去美术馆欣赏艺术品",
        "29. 去音乐厅听音乐会",
        "30. 去剧院看戏",
    ],
    "职场沟通": [
        "1. 与老板进行绩效评估面试",
        "2. 向同事提出反馈意见",
        "3. 与客户进行投诉处理",
        "4. 在会议上进行项目汇报",
        "5. 与客户进行谈判",
        "6. 与供应商进行价格谈判",
        "7. 向领导申请项目经费",
        "8. 与同事进行项目协作",
        "9. 与客户进行产品演示",
        "10. 向同事寻求帮助",
        "11. 向同事道歉",
        "12. 与客户进行售后服务",
        "13. 向客户进行产品推介",
        "14. 与客户进行产品培训",
        "15. 向客户进行产品回访",
        "16. 与客户进行产品维护",
        "17. 向客户进行产品维修",
        "18. 向客户进行产品退货",
        "19. 向客户进行产品退款",
        "20. 向客户进行产品换货",
        "21. 向客户进行产品赔偿",
        "22. 向客户进行产品延期交货",
        "23. 向客户进行产品缺货",
        "24. 向客户进行产品价格调整",
        "25. 向客户进行产品促销活动",
        "26. 向客户进行产品抽奖活动",
        "27. 向客户进行产品问卷调查",
        "28. 向客户进行产品满意度调查",
        "29. 向客户进行产品投诉处理",
        "30. 向客户进行产品售后服务",
    ],
    "学术研究": [
        "1. 研究生正在研究中国古代史，需要模拟一个唐朝的科考场景",
        "2. 历史学家正在研究法国大革命，需要模拟一个巴士底狱攻占场景",
        "3. 社会学家正在研究现代社会的贫富差距，需要模拟一个底层家庭的日常生活场景",
        "4. 经济学家正在研究全球化的影响，需要模拟一个跨国公司的生产流程场景",
        "5. 心理学家正在研究人类的学习和记忆，需要模拟一个学生参加考试的场景",
        "6. 生物学家正在研究动物的行为，需要模拟一个动物群体的迁徙场景",
        "7. 化学家正在研究化学反应的机理，需要模拟一个化学反应的分子运动场景",
        "8. 物理学家正在研究宇宙的起源，需要模拟一个大爆炸场景",
        "9. 天文学家正在研究恒星的演变，需要模拟一个恒星从诞生到死亡的过程",
        "10. 地质学家正在研究地壳的运动，需要模拟一个地震场景",
        "11. 海洋学家正在研究海洋的环流，需要模拟一个洋流的流动场景",
        "12. 气象学家正在研究天气的变化，需要模拟一个龙卷风的形成过程",
        "13. 农业学家正在研究农作物的生长，需要模拟一个农作物生长过程",
        "14. 医学家正在研究疾病的治疗，需要模拟一个药物作用于人体的过程",
        "15. 工程师正在研究新产品的开发，需要模拟一个产品的生产过程",
        "16. 计算机科学家正在研究人工智能，需要模拟一个人类大脑的运作过程",
        "17. 教育学家正在研究教学方法，需要模拟一个课堂教学场景",
        "18. 艺术家正在研究创作新作品，需要模拟一个创作过程",
        "19. 音乐家正在研究演奏新乐曲，需要模拟一个演奏过程",
        "20. 舞蹈家正在研究编舞新舞蹈，需要模拟一个编舞过程",
        "21. 演员正在研究表演新角色，需要模拟一个表演过程",
        "22. 模特正在研究走秀新服装，需要模拟一个走秀过程",
        "23. 运动员正在研究比赛新项目，需要模拟一个比赛过程",
        "24. 厨师正在研究烹饪新菜肴，需要模拟一个烹饪过程",
        "25. 调酒师正在研究调制新鸡尾酒，需要模拟一个调制过程",
        "26. 咖啡师正在研究冲泡新咖啡，需要模拟一个冲泡过程",
        "27. 花艺师正在研究插花新作品，需要模拟一个插花过程",
        "28. 园艺师正在研究培育新花卉，需要模拟一个培育过程",
        "29. 宠物训练师正在研究训练新宠物，需要模拟一个训练过程",
        "30. 瑜伽教练正在研究教授新瑜伽姿势，需要模拟一个教授过程",
    ],
    "旅行交通": [
        "1. 北京一家三口乘坐飞机前往上海，度过一个欢乐的假期",
        "2. 广州一对情侣乘坐高铁前往深圳，共度浪漫时光",
        "3. 成都三五好友驾车前往丽江，拍摄美丽的自然风光",
        "4. 西安一群学生乘坐旅游巴士前往敦煌，感受古老文明的魅力",
        "5. 厦门一对老人乘坐轮渡前往鼓浪屿，享受悠闲的海岛生活",
        "6. 三亚商务人士乘坐邮轮前往海南岛，洽谈合作事宜",
        "7. 香港游客乘坐直通巴士前往澳门，体验购物的乐趣",
        "8. 日本年轻人乘坐国际航班前往韩国，打卡网红景点",
        "9. 机场接送服务，让旅客出行更便捷",
        "10. 酒店接送服务，让旅客入住更舒适",
        "11. 景点接送服务，让旅客游玩更便利",
        "12. 市内交通服务，让旅客出行更经济",
        "13. 租车服务，让旅客自由行更随心",
        "14. 拼车服务，让旅客出行更省钱",
        "15. 旅游保险，保障旅客出行安全",
        "16. 交通意外保险，保障旅客出行意外",
        "17. 签证，保障旅客出入境顺利",
        "18. 换汇，保障旅客出国消费",
        "19. 出行规划，让旅客旅行更顺利",
        "20. 行程安排，让旅客旅行更充实",
        "21. 交通拥堵，影响旅客出行效率",
        "22. 航班延误，打乱旅客行程安排",
        "23. 行李丢失，给旅客带来不便",
        "24. 交通事故，给旅客带来伤害",
        "25. 语言不通，给旅客带来沟通困难",
        "26. 饮食不习惯，给旅客带来身体不适",
        "27. 旅行疲劳，影响旅客身体健康",
        "28. 水土不服，给旅客带来身体不适",
        "29. 晒伤，给旅客带来皮肤损伤",
        "30. 蚊虫叮咬，给旅客带来身体不适",
    ],
    "餐饮美食": [
        "1. 一个繁忙的城市餐厅，熙熙攘攘的顾客正在享受着美味的食物",
        "2. 一个温馨的家庭厨房，一家人正在其乐融融地准备晚餐",
        "3. 一个浪漫的烛光晚餐，情侣们正在享受着彼此的陪伴和美味的食物",
        "4. 一个热闹的烧烤派对，朋友们正在烤制各种肉类和蔬菜，享受着夏日的时光",
        "5. 一个精致的米其林星级餐厅，顾客们正在品尝着大厨精心准备的美食",
        "6. 一个街头小摊，老板正在熟练地制作着各种小吃，吸引着络绎不绝的顾客",
        "7. 一个农家乐，游客们正在品尝着当地特色菜，享受着田园风光",
        "8. 一个学校食堂，学生们正在排队领取午餐，脸上洋溢着笑容",
        "9. 一个医院餐厅，病人正在享用着营养均衡的餐点，脸上露出满足的笑容",
        "10. 一个养老院餐厅，老人正在享用着美味的食物，脸上露出幸福的神情",
        "11. 一个飞机上的餐厅，乘客正在享用着空中美食，俯瞰着壮丽的景色",
        "12. 一个火车上的餐厅，乘客正在享用着火车上提供的美食，欣赏着沿途的风景",
        "13. 一个游轮上的餐厅，乘客正在享用着游轮上提供的美食，享受着海上航行的乐趣",
        "14. 一个酒店餐厅，住客正在享用着酒店提供的美食，享受着舒适的住宿环境",
        "15. 一个度假村餐厅，游客正在享用着度假村提供的美食，享受着度假时光",
        "16. 一个主题公园餐厅，游客正在享用着主题公园提供的美食，享受着游玩的乐趣",
        "17. 一个博物馆餐厅，游客正在享用着博物馆提供的美食，欣赏着博物馆的展品",
        "18. 一个动物园餐厅，游客正在享用着动物园提供的美食，观看动物表演",
        "19. 一个水族馆餐厅，游客正在享用着水族馆提供的美食，欣赏着海洋生物",
        "20. 一个游乐园餐厅，游客正在享用着游乐园提供的美食，体验着游乐园的乐趣",
        "21. 一个马戏团餐厅，游客正在享用着马戏团提供的美食，观看马戏团的表演",
        "22. 一个音乐节餐厅，游客正在享用着音乐节提供的美食，欣赏着音乐节的表演",
        "23. 一个体育赛事餐厅，游客正在享用着体育赛事提供的美食，观看体育赛事",
        "24. 一个展览会餐厅，游客正在享用着展览会提供的美食，参观展览会",
        "25. 一个集市餐厅，游客正在享用着集市提供的美食，感受集市的热闹气氛",
        "26. 一个庙会餐厅，游客正在享用着庙会提供的美食，体验庙会的传统文化",
        "27. 一个古镇餐厅，游客正在享用着古镇提供的美食，感受古镇的古色古香",
        "28. 一个山村餐厅，游客正在享用着山村提供的美食，感受山村的自然风光",
        "29. 一个海边餐厅，游客正在享用着海边提供的美食，享受着海边的景色",
        "30. 一个湖边餐厅，游客正在享用着湖边提供的美食，欣赏着湖边的美景",
    ],
    "健康医疗": [
        "1. 医生诊断患者的疾病",
        "2. 护士给患者输液",
        "3. 护士给患者打针",
        "4. 患者在医院接受检查",
        "5. 医生给患者开药",
        "6. 患者在医院做手术",
        "7. 患者在医院康复",
        "8. 患者出院回家",
        "9. 患者在家中服药",
        "10. 患者在家中康复",
        "11. 患者在社区卫生中心就诊",
        "12. 患者在社区卫生中心接受检查",
        "13. 患者在社区卫生中心开药",
        "14. 患者在社区卫生中心康复",
        "15. 患者在家中接受护理",
        "16. 护士在家中给患者输液",
        "17. 护士在家中给患者打针",
        "18. 护士在家中给患者换药",
        "19. 护士在家中给患者做康复训练",
        "20. 护士在家中给患者提供心理支持",
        "21. 患者在社区卫生中心接受心理咨询",
        "22. 患者在社区卫生中心参加健康教育活动",
        "23. 患者在社区卫生中心参加慢性病管理项目",
        "24. 患者在社区卫生中心参加老年人健康管理项目",
        "25. 患者在社区卫生中心参加儿童健康管理项目",
        "26. 患者在社区卫生中心参加妇女健康管理项目",
        "27. 患者在社区卫生中心参加计划生育服务",
        "28. 患者在社区卫生中心参加艾滋病预防和控制服务",
        "29. 患者在社区卫生中心参加结核病预防和控制服务",
        "30. 患者在社区卫生中心参加精神疾病预防和控制服务",
    ],
    "购物消费": [
        "1. 在杂货店购买新鲜的水果和蔬菜、肉类、奶制品和零食",
        "2. 在服装店购买衣服、鞋子和配饰",
        "3. 在电子商店购买手机、电脑、电视和其他电子产品",
        "4. 在家具店购买家具、家用电器和其他家居用品",
        "5. 在药店购买药品、保健品和其他医疗用品",
        "6. 在超市购买日常生活用品，如洗漱用品、清洁用品、厨房用品等",
        "7. 在大型购物中心购买各种各样的商品，包括服装、电子产品、家居用品、食品等",
        "8. 在网上购物平台购买商品，如淘宝、京东、天猫等",
        "9. 在二手市场购买旧货，如旧家具、旧衣服、旧电子产品等",
        "10. 在农贸市场购买新鲜的农产品，如蔬菜、水果、肉类、鸡蛋等",
        "11. 在花店购买鲜花、花盆、花肥等",
        "12. 在文具店购买文具用品，如钢笔、铅笔、本子、书包等",
        "13. 在玩具店购买玩具，如毛绒玩具、积木、玩具车等",
        "14. 在宠物店购买宠物用品，如宠物食品、宠物玩具、宠物窝等",
        "15. 在体育用品店购买体育用品，如运动服、运动鞋、球类等",
        "16. 在汽车用品店购买汽车用品，如汽车轮胎、汽车配件、汽车清洗用品等",
        "17. 在家居用品店购买家居用品，如窗帘、地毯、灯具等",
        "18. 在园艺用品店购买园艺用品，如花盆、肥料、工具等",
        "19. 在烘焙用品店购买烘焙用品，如面粉、糖、酵母等",
        "20. 在手工艺品店购买手工艺品，如毛线、布料、珠子等",
        "21. 在化妆品店购买化妆品，如口红、粉底、睫毛膏等",
        "22. 在香水店购买香水，如淡香精、香水、古龙水等",
        "23. 在保健品店购买保健品，如维生素、矿物质、蛋白质粉等",
        "24. 在图书店购买书籍，如小说、散文、诗歌、教科书等",
        "25. 在音像店购买音乐和电影，如CD、DVD、蓝光等",
        "26. 在游戏店购买游戏，如电子游戏、棋盘游戏、卡牌游戏等",
        "27. 在体育场馆购买体育比赛的门票",
        "28. 在电影院购买电影票",
        "29. 在游乐园购买游乐设施的门票",
        "30. 在博物馆购买博物馆的门票",
    ],
    "娱乐休闲": [
        "1. 电影之夜： 在家或影院观看新电影，并与朋友或家人分享爆米花和其他零食",
        "2. 游戏之夜： 举办游戏之夜，邀请朋友或家人一起玩棋盘游戏、纸牌游戏或电子游戏",
        "3. 音乐会： 去音乐会或音乐节，欣赏现场音乐表演",
        "4. 体育赛事： 去体育场观看足球、篮球、棒球或其他体育比赛",
        "5. 艺术展： 参观艺术展或博物馆，欣赏艺术作品和历史展览",
        "6. 游乐园： 去游乐园或主题公园，乘坐游乐设施、玩游戏并观看表演",
        "7. 海滩： 去海滩游泳、日光浴、冲浪或在沙滩上玩耍",
        "8. 公园： 去公园散步、野餐、玩耍或只是放松",
        "9. 图书馆： 去图书馆借书、阅读或参加活动",
        "10. 购物： 去购物中心或商店购物，购买衣服、电子产品、书籍或其他物品",
        "11. 博物馆： 参观博物馆，了解历史、科学、艺术或其他主题",
        "12. 动物园： 去动物园看动物，了解不同的动物种类和习性",
        "13. 水族馆： 去水族馆看鱼和其他海洋生物，了解海洋生态系统",
        "14. 天文馆： 去天文馆看星星和行星，了解宇宙和天文学",
        "15. 植物园： 去植物园看花草树木，了解不同的植物种类和习性",
        "16. 游船： 乘坐游船游览河川、湖泊或海洋，欣赏沿途风景",
        "17. 登山： 去山区登山，欣赏山顶风光，挑战自我",
        "18. 露营： 去野外露营，搭建帐篷、生火做饭，享受大自然",
        "19. 钓鱼： 去河边、湖边或海边钓鱼，放松心情，享受钓鱼的乐趣",
        "20. 划船： 乘坐皮划艇、独木舟或其他船只在河川、湖泊或海洋上划船，欣赏沿途风景",
        "21. 骑自行车： 骑自行车在城市或乡间小路上骑行，锻炼身体，享受骑行的乐趣",
        "22. 远足： 去山区或森林里远足，欣赏沿途风景，挑战自我",
        "23. 滑雪： 去雪山滑雪，享受滑雪的乐趣，挑战自我",
        "24. 滑冰： 去冰场滑冰，享受滑冰的乐趣，挑战自我",
        "25. 音乐会： 去音乐会或音乐节，欣赏现场音乐表演",
        "26. 话剧： 去剧院看话剧，欣赏演员的精彩表演",
        "27. 歌剧： 去歌剧院看歌剧，欣赏歌手的优美歌声",
        "28. 芭蕾舞： 去芭蕾舞剧院看芭蕾舞，欣赏舞者的优美舞姿",
        "29. 马戏团： 去马戏团观看杂技表演，惊叹于杂技演员的精彩表演",
        "30. 脱口秀： 去脱口秀俱乐部观看脱口秀表演，享受欢笑和幽默",
    ],
}

CEFR_LEVEL_TOPIC = {
    "A1": [
        "做简单的自我介绍、打招呼",
        "叙述自己和别人来自哪里、做简单的关于城市的描述",
        "简单介绍自己的家庭和同事，描述他们的外表和性格",
        "对穿着进行基本的讨论，可以问服装店客服一些简单的问题",
        "讨论喜爱的食物，可以自行叫外卖",
        "谈论每日的日常活动，跟朋友和同时安排见面或会议" "讨论天气状况，根据天气预报提出活动建议",
        "很浅显的讨论自己的身体状况，向医生描述常见的病状",
        "描述自己家的位置，可以给与简单的方向指示",
        "谈论自己的爱好和兴趣，为朋友和同事计划有趣的活动",
        "自行在酒店完成基本的交易，包括check in和check out",
        "讨论一些常用产品，能过自行购买和退换物件",
    ],
    "A2": [
        "在工作场合中评估同事的表现",
        "回忆你过去参加的活动，包括周末活动和有趣的故事",
        "描述你以前的生活，能记述重要的人生事件",
        "在家待客或是去朋友家里做客可以娱乐别人",
        "讨论你的假期计划并且告诉朋友和同事你的假期活动",
        "讨论自然世界，在自己的国家旅行、观察自然界的动物",
        "讨论你喜欢的电影，能够选择电影和朋友一起去看",
        "讨论衣装以及你所喜爱的衣服",
        "在工作中有初步的讨论，包括参加熟悉题目的会议",
        "描述一次事故或意外，向医生求助并获得药方",
        "进行简单的商务社交，欢迎客人并参加社交活动",
        "理解并撰写属于自己专业领域的简单商业计划",
        "谈论并解释游戏的规则",
    ],
    "B1": [
        "讨论个人和职业方面的愿景及梦想",
        "安排或参与一个和你工作领域相关的面试",
        "探讨你看电视的习惯和最喜爱的节目",
        "描述你的教育背景和你对未来的相关计划",
        "谈论你最喜欢的音乐、流行趋势并计划一个去听现场音乐的夜晚",
        "谈论关于怎样保持健康的生活方式，给予或得到关于健康习惯的建议",
        "谈论亲友关系和约会，包括与社交媒体上认识的人碰面",
        "去一个餐厅、独立点餐、在晚餐中礼貌的交谈并为自己付款",
        "在你的专长领域并受到帮助的情况下进行谈判",
        "讨论工作环境的安全问题、汇报伤情并解释规则和条款",
        "对无理的要求和行為可以正确的回应并对应有的礼貌行为作出解释",
    ],
    "B2": [
        "在某些节点上得到帮助的情况下参加你专业领域的会议",
        "讨论与文化信条及对礼仪相关的性别类话题",
        "谈论你的个人财务并可以对朋友及同事作出财务上的建议",
        "谈论个人生活和工作方式，包括对你的工作生活作出一个描述",
        "解释你的教育背景、经历、长处、短处，并讨论你的职业生涯",
        "谈论精神思想，以及你怎样在工作上提高效率",
        "谈论你所喜欢的读物，并可以作出阅读方面的推荐",
        "在社交场合运用合适的言辞，包括赞美和表达同情",
        "讨论领袖特质，并说一下你所欣赏的领袖",
        "处理在社交和工作场合出现的相对复杂而尴尬的处境",
        "讨论一般的政治局势及政治人物的行为",
    ],
    "C1": [
        "讨论取得成功的细节问题，包括怎样组织和建立一个有朝气的成功的团队",
        "围绕你最喜爱的画作和建筑进行深入的探讨",
        "讨论社会问题、可能的解决方案以及一个企业所扮演的角色",
        "参与讨论文物的维护、保存，以及住宅的保护",
        "谈论新闻中的事件和话题，以及它们如何影响人们及企业",
        "谈论生活中的危机，包括更换工作以及做危险的运动",
        "比较不同的教育体制和学校",
        "讨论不同种类的幽默，包括微妙的讽刺",
        "理解各种交流的风格，包括直接的、间接的、正式的和非正式的",
        "讨论和你生活质量相关的话题，包括工作和生活的平衡和家庭环境",
        "理解并讨论关于种族、市民动乱等话题",
    ],
    "C2": [
        "讨论科学和技术相关的话题，包括机器人和新的创新",
        "谈论名人、名人軼事和他们的绯闻",
        "在你的演讲和写作中用不同的技巧来提高创新度",
        "讨论经济计划，并理解个人财务状况且可以提出建议",
        "谈论生活中的压力和朋友及同事的生活",
        "讨论做不同话题研究所需要用到的技术和技巧",
    ],
}
