from app.services.business_license_parser import parse_business_license_text


def test_parse_business_license_ocr_lines():
    result = parse_business_license_text(
        [
            "营业执照",
            "统一社会信用代码 91370103MA3N9PN31J",
            "名称 济南测试印刷有限公司",
            "类型 有限责任公司（自然人独资）",
            "法定代表人 张三",
            "注册资本 伍拾万元整",
            "成立日期 2018年09月01日",
            "住所 山东省济南市市中区测试路1号",
            "经营范围 印刷品和办公用品销售",
        ]
    )

    assert result["unified_credit_code"] == "91370103MA3N9PN31J"
    assert result["name"] == "济南测试印刷有限公司"
    assert result["legal_person"] == "张三"
    assert result["address"] == "山东省济南市市中区测试路1号"
    assert result["confidence"] == 1


def test_parse_business_license_accepts_value_on_next_line():
    result = parse_business_license_text(["名称", "青岛测试商贸有限公司", "统一社会信用代码", "91370202MA3TUDF032"])

    assert result["name"] == "青岛测试商贸有限公司"
    assert result["unified_credit_code"] == "91370202MA3TUDF032"


def test_parse_business_license_merges_split_layout_labels():
    result = parse_business_license_text(
        [
            "名",
            "称青岛盛霖合源商贸有限公司",
            "类",
            "型有限责任公司（自然人独资）",
            "住",
            "所山东省青岛市李沧区永平路2号",
        ]
    )

    assert result["name"] == "青岛盛霖合源商贸有限公司"
    assert result["entity_type"] == "有限责任公司（自然人独资）"
    assert result["address"] == "山东省青岛市李沧区永平路2号"


def test_parse_business_license_recovers_missing_first_label_character():
    result = parse_business_license_text(
        [
            "名类",
            "称青岛弘佳宜电子有限公司",
            "型有限责任公司（自然人投资或控股）",
            "住",
            "所青岛胶州市胶北街道办事处西松",
        ]
    )

    assert result["name"] == "青岛弘佳宜电子有限公司"
    assert result["entity_type"] == "有限责任公司（自然人投资或控股）"


def test_parse_business_license_joins_multiline_address():
    result = parse_business_license_text(
        [
            "住所山东省青岛市李沧区永平路2号10号楼",
            "2002室",
            "经营范围",
        ]
    )

    assert result["address"] == "山东省青岛市李沧区永平路2号10号楼2002室"


def test_parse_business_license_joins_address_suffix_across_column_labels():
    result = parse_business_license_text(
        [
            "住所青岛胶州市胶北街道办事处西松",
            "登记机关",
            "胶州市市场监督管理局",
            "园村",
        ]
    )

    assert result["address"] == "青岛胶州市胶北街道办事处西松园村"


def test_parse_business_license_does_not_append_registration_date_fragments_to_address():
    result = parse_business_license_text(
        [
            "住所山东省青岛市市北区合肥路501-2号",
            "登记机关",
            "2026",
            "06",
            "16",
        ]
    )

    assert result["address"] == "山东省青岛市市北区合肥路501-2号"
