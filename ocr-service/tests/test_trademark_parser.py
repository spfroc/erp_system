from app.services.trademark_parser import parse_trademark_certificate_text


def test_parse_trademark_certificate_ocr_lines():
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "*TMZC31822730D01T190520*",
            "商标注册号",
            "31822730",
            "鲁奇亚",
            "Luqiya",
            "注册人",
            "临沂市兰山区尚仕塑料制品厂",
            "注册人地址",
            "山东省临沂市兰山区半程镇水口工业园",
            "国际分类",
            "21",
            "核定使用商品/服务项目",
            "第21类：碗；成套杯、碗、碟；一次性盘子；纸或塑料杯；饭盒（截止）",
            "注册日期",
            "2019年03月21日",
            "有效期至",
            "2029年03月20日",
        ]
    )

    assert result["registration_no"] == "31822730"
    assert "鲁奇亚" in result["trademark_name"]
    assert "Luqiya" in result["trademark_name"]
    assert result["registrant"] == "临沂市兰山区尚仕塑料制品厂"
    assert result["registrant_address"] == "山东省临沂市兰山区半程镇水口工业园"
    assert result["international_class"] == "21"
    assert result["registration_date"] == "2019-03-21"
    assert result["valid_until"] == "2029-03-20"
    assert "碗" in result["approved_goods"]


def test_parse_trademark_certificate_wrapped_approved_goods_lines():
    """Goods text often wraps; second OCR line must still be filled."""
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "商标注册号",
            "31822730",
            "注册人",
            "临沂市兰山区尚仕塑料制品厂",
            "注册人地址",
            "山东省临沂市兰山区半程镇水口工业园",
            "核定使用商品/服务项目（国际分类：21）",
            "第21类：碗；成套杯、碗、碟；一次性盘子；纸或塑料杯；饭盒；餐具（刀、叉、匙除外）；色拉",
            "碗；午餐盒；汤碗；杯（截止）",
            "注册日期",
            "2019年03月21日",
            "有效期至",
            "2029年03月20日",
        ]
    )

    goods = result["approved_goods"]
    assert "色拉碗" in goods or ("色拉" in goods and "午餐盒" in goods)
    assert "午餐盒" in goods
    assert "汤碗" in goods
    assert "截止" in goods


def test_parse_trademark_certificate_multi_class_approved_goods():
    """Multi-class certificates list several「第N类…（截止）」blocks."""
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "商标注册号",
            "83793979",
            "注册人",
            "青岛众拾天成石油化工有限公司",
            "注册人地址",
            "山东省青岛市莱西市日庄镇府前路62-4号",
            "核定使用商品/服务项目（国际分类：1；7）",
            "第1类：硫醇；工业用酒精；工业用废水处理化学品；吸附剂；消泡剂；清洁烟囱用化学品；气体净化剂；毒气中和剂（截止）",
            "第7类：静电工业设备；高压清洗机；清洗设备；清理管道用清管器（截止）",
            "注册日期",
            "2025年11月21日",
            "有效期至",
            "2035年11月20日",
        ]
    )

    assert result["international_class"] == "1、7"
    goods = result["approved_goods"]
    assert "硫醇" in goods
    assert "第7类" in goods
    assert "高压清洗机" in goods
    assert "清管器" in goods


def test_parse_trademark_certificate_mark_from_registrant_fallback():
    """Stylized logo OCR often fails; recover mark embedded in registrant."""
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "*TMZC83793979D01T*",
            "商标注册号",
            "83793979",
            "注册人",
            "青岛众拾天成石油化工有限公司",
            "注册人地址",
            "山东省青岛市莱西市日庄镇府前路62-4号",
            "核定使用商品/服务项目（国际分类：1；7）",
            "第1类：硫醇；工业用酒精（截止）",
            "第7类：静电工业设备；高压清洗机（截止）",
            "注册日期",
            "2025年11月21日",
            "有效期至",
            "2035年11月20日",
        ]
    )

    assert result["trademark_name"] == "众拾天成"
    assert result["registrant"] == "青岛众拾天成石油化工有限公司"


def test_parse_trademark_certificate_keeps_short_mark_inside_registrant():
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "83793979",
            "众拾天成",
            "ZHONGSHITIANCHENG",
            "注册人",
            "青岛众拾天成石油化工有限公司",
            "注册人地址",
            "山东省青岛市莱西市日庄镇府前路62-4号",
            "第1类：硫醇（截止）",
            "注册日期",
            "2025年11月21日",
            "有效期至",
            "2035年11月20日",
        ]
    )

    assert "众拾天成" in result["trademark_name"]
    assert "ZHONGSHITIANCHENG" in result["trademark_name"]


def test_parse_trademark_certificate_does_not_treat_address_label_as_registrant():
    """OCR often concatenates 注册人地址; 注册人 must not become「地址」."""
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "商标注册号",
            "31822730",
            "注册人地址山东省临沂市兰山区半程镇水口工业园",
            "临沂市兰山区尚仕塑料制品厂注册人",
            "国际分类",
            "21",
            "(国际分类：21)",
            "核定使用商品/服务项目",
            "第21类：碗；成套杯、碗、碟；一次性盘子；纸或塑料杯；饭盒；餐具（刀、叉、匙除外）；色拉碗；午餐盒；汤碗；杯（截止）",
            "注册日期2019年03月21日",
            "有效期至2029年03月20日",
        ]
    )

    assert result["registrant"] == "临沂市兰山区尚仕塑料制品厂"
    assert "半程镇水口工业园" in result["registrant_address"]
    assert "碗" in result["approved_goods"]
    assert "国际分类：21" not in result["approved_goods"] or "碗" in result["approved_goods"]


def test_parse_trademark_certificate_glued_registrant_address_label():
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "31822730",
            "注册人地址",
            "山东省临沂市兰山区半程镇水口工业园",
            "注册人",
            "临沂市兰山区尚仕塑料制品厂",
            "国际分类21",
            "核定使用商品/服务项目",
            "(国际分类：21)",
            "第21类：碗；成套杯、碗、碟；一次性盘子（截止）",
            "注册日期",
            "2019年03月21日",
            "有效期至",
            "2029年03月20日",
        ]
    )

    assert result["registrant"] == "临沂市兰山区尚仕塑料制品厂"
    assert result["registrant"] != "地址"
    assert "水口工业园" in result["registrant_address"]
    assert "碗" in result["approved_goods"]


def test_parse_trademark_certificate_split_labels_and_barcode():
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "*TMZC83793979D01T*",
            "注",
            "册",
            "人",
            "青岛众拾天成石油化工有限公司",
            "注",
            "册",
            "人",
            "地",
            "址",
            "山东省青岛市莱西市日庄镇府前路62-4号",
            "国",
            "际",
            "分",
            "类",
            "第4类",
            "注",
            "册",
            "日",
            "期",
            "2025年11月21日",
            "有",
            "效",
            "期",
            "至",
            "2035年11月20日",
        ]
    )

    assert result["registration_no"] == "83793979"
    assert result["registrant"] == "青岛众拾天成石油化工有限公司"
    assert "莱西市" in result["registrant_address"]
    assert result["international_class"] == "4"
    assert result["registration_date"] == "2025-11-21"
    assert result["valid_until"] == "2035-11-20"


def test_parse_trademark_certificate_front_back_approved_goods():
    """Front goods end at 见背面; back page continues mid-phrase until （截止）."""
    result = parse_trademark_certificate_text(
        [
            "商标注册证",
            "21775751",
            "妙潔",
            "核定使用商品/服务项目（国际分类：16）",
            "第16类：纸；羊皮纸：纸带；防锈纸；滤纸；卫生纸；纸巾；纸手帕；卸妆用薄纸；纸餐巾；纸制洗脸巾；湿纸巾；除尘纸；纸桌布；纸制杯盘垫；过滤纸板；滤芯纸板；日历；海报；石印品；锡纸；锥形纸袋；纸制奶油容器；包装纸；包装用再生纤维素纸；瓶用纸板或纸制包装物；包装用粘胶纤维纸；糖果包装纸；纸制或塑料制垃圾袋；包装用纸袋或塑料袋（信封、<见背面>",
            "注册人脱普日用化学品（中国）有限公司",
            "注册人地址江苏省无锡市新区锡达路259号",
            "注册日期2017年12月21日有效期至2027年12月20日",
            "局长",
            "发证机关",
            "商标局",
            "号",
            "小袋）；纸板盒或纸盒；咖啡过滤纸；仿羊皮纸（防油纸）；牛皮纸；水泥袋；纸箱；包装用塑料膜；包装用塑料气泡膜；垫货盘用可伸展塑料膜；保鲜膜；厨房用烹饪纸；微波烹饪袋；装订带（装订用）；夹子（文具）；文具或家用胶条；文具或家用胶带；制模型用塑料；纸制或塑料制食品包装用吸收纸；纸制容器；纸制或塑料制食品包装用湿度调节纸（截止）",
            "（国际分类：16）",
            "核定使用商品/服务项目",
        ]
    )

    goods = result["approved_goods"]
    assert "见背面" not in goods
    assert "信封" in goods
    assert "小袋" in goods
    assert "纸板盒或纸盒" in goods
    assert "湿度调节纸" in goods
    assert "截止" in goods
    assert goods.startswith("第16类")
