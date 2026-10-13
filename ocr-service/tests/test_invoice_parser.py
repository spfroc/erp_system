from app.services.invoice_parser import parse_invoice_text


def test_parse_invoice_text_extracts_core_fields():
    text = """
    电子发票（增值税专用发票）
    发票号码：26372000002896402906
    开票日期：2026年06月17日
    购 名称：郓城金木商贸销售有限公司 销 名称：山东壹知产数字科技有限公司
    买 售
    方 方
    信 统一社会信用代码/纳税人识别号：91371725MA3WE8QPXA 信 统一社会信用代码/纳税人识别号：91370103MA3T1BXA6N
    息 息
    合 计 ¥12831.86 ¥1668.14
    价税合计（大写） 壹万肆仟伍佰圆整 （小写）¥14500.00
    """

    result = parse_invoice_text(text)

    assert result["invoice_no"] == "26372000002896402906"
    assert result["invoice_date"] == "2026-06-17"
    assert result["buyer_name"] == "郓城金木商贸销售有限公司"
    assert result["buyer_tax_no"] == "91371725MA3WE8QPXA"
    assert result["seller_name"] == "山东壹知产数字科技有限公司"
    assert result["seller_tax_no"] == "91370103MA3T1BXA6N"
    assert result["amount_without_tax"] == 12831.86
    assert result["tax_amount"] == 1668.14
    assert result["total_amount"] == 14500.0


def test_parse_invoice_text_handles_spaced_glyphs():
    text = """
电 子 发 票 （ 普 通 发 票 ）
发 票 号 码 ：26372000003985897306
开 票 日 期 ：2026年08月14日
购 名称：鄄城县通源电子经贸有限公司 销 名称：济南云集企业管理有限公司
买 售
方 方
信 统一社会信 用代码 /纳税人识别号 ：91371726MA3EL7AC07 信 统一社会信 用代码 /纳税人识别号 ：91370103MAD1JHX36U
息 息
合 计 ¥990.10 ¥9.90
价税合计（ 大写） 壹仟圆整 （ 小写）¥1000.00
"""

    result = parse_invoice_text(text)

    assert result["invoice_no"] == "26372000003985897306"
    assert result["invoice_date"] == "2026-08-14"
    assert result["buyer_name"] == "鄄城县通源电子经贸有限公司"
    assert result["buyer_tax_no"] == "91371726MA3EL7AC07"
    assert result["seller_name"] == "济南云集企业管理有限公司"
    assert result["seller_tax_no"] == "91370103MAD1JHX36U"
    assert result["amount_without_tax"] == 990.10
    assert result["tax_amount"] == 9.90
    assert result["total_amount"] == 1000.0


def test_parse_invoice_text_collapses_doubled_glyphs():
    text = """
电子发票（增值税专用发票）
发票号码：2266337777000000000000445533331122448822
开票日期：22002266年年0088月月0055日日
购 销
买 名称：山山东东壹壹知知产产数数字字科科技技有有限限公公司司 售 名称：济济南南美美的的智智慧慧家家居居有有限限公公司司
方 方
信 统一社会信用代码/纳税人识别号：9911337700110033MMAA33TT11BBXXAA66NN 信 统一社会信用代码/纳税人识别号：9911337700111122MMAA77MM99DD11BB00FF
息 息
合 计 ¥19247.79 ¥2502.21
价税合计（大写） 贰万壹仟柒佰伍拾圆整 （小写） ¥21750.00
"""

    result = parse_invoice_text(text)

    assert result["invoice_no"] == "26377000000453312482"
    assert result["invoice_date"] == "2026-08-05"
    assert result["buyer_name"] == "山东壹知产数字科技有限公司"
    assert result["buyer_tax_no"] == "91370103MA3T1BXA6N"
    assert result["seller_name"] == "济南美的智慧家居有限公司"
    assert result["seller_tax_no"] == "91370112MA7M9D1B0F"
    assert result["amount_without_tax"] == 19247.79
    assert result["tax_amount"] == 2502.21
    assert result["total_amount"] == 21750.0


def test_parse_invoice_text_reads_unstructured_footer_fields():
    text = """
电子发票（增值税专用发票）
发票号码：
开票日期：
购 销
买 名称： 售 名称：
方 方
信 统一社会信用代码/纳税人识别号： 信 统一社会信用代码/纳税人识别号：
息 息
项目名称 规格型号 单 位 数 量 单 价 金 额 税率/征收率 税 额
*橡胶制品*胶带 B银布基4.8*50 卷 10 9.372 93.72 13% 12.18
合 计
价税合计（大写） （小写）
26342000002315877286
2026年07月22日
山东壹知产数字科技有限公司 安徽中圣包装材料有限公司
91370103MA3T1BXA6N 91340100MA2MXB4R79
¥93.72 ¥12.18
壹佰零伍圆玖角整 ¥105.90
"""

    result = parse_invoice_text(text)

    assert result["invoice_no"] == "26342000002315877286"
    assert result["invoice_date"] == "2026-07-22"
    assert result["buyer_name"] == "山东壹知产数字科技有限公司"
    assert result["seller_name"] == "安徽中圣包装材料有限公司"
    assert result["buyer_tax_no"] == "91370103MA3T1BXA6N"
    assert result["seller_tax_no"] == "91340100MA2MXB4R79"
    assert result["amount_without_tax"] == 93.72
    assert result["tax_amount"] == 12.18
    assert result["total_amount"] == 105.9
    assert result["line_items"]
    assert result["line_items"][0]["product_name"].startswith("胶带")


def test_parse_invoice_text_reads_wrapped_multi_product_lines():
    text = """
电子发票（增值税专用发票）
发票号码：26372000003722683666
开票日期：2026年07月30日
购 名称：青岛国易采购服务有限公司 销 名称：山东壹知产数字科技有限公司
买 售
方 方
信 统一社会信用代码/纳税人识别号：91370281MAK3F5MQ4E 信 统一社会信用代码/纳税人识别号：91370103MA3T1BXA6N
息 息
项目名称 规格型号 单 位 数 量 单 价 金 额 税率/征收率 税 额
*文具*得力（deli）得力 10只 透明色 个 3 13.2743362831858 39.82 13% 5.18
5589拉链袋
*茶*野生红茶礼盒装 盒 32 171.83185840708 5498.62 13% 714.82
*茶*曜韵崂山绿茶一盒 盒 28 171.83185840708 4811.29 13% 625.47
*配电控制设备*电热水壶 套 3 34.5132743362832 103.54 13% 13.46
配件温控器+下连接器
G60-1
*文具*得力（deli）大双 1.5mm/5.7mm 黑 套 1 18.5840707964602 18.58 13% 2.42
头粗头物流快递记号笔 色 10支
*文具*得力（deli） 票 大号 办公文具 套 3 20.2654867256637 60.80 13% 7.90
夹 山形铁票夹 画板夹 【山型铁票夹】
铁夹子 特大127mm-4
*原电池*南孚9V碱性电池 6LR61 4粒 套 1 36.5840707964602 36.58 13% 4.76
万用表麦克风儿童玩具遥
控
*配电控制设备*适用施耐 NSX/CVS250-4P 套 1 41.4159292035398 41.42 13% 5.38
德断路器隔弧罩 一套*2片
LV529516
*配电控制设备*接触器触 3TF47 套 3 141.592920353982 424.78 13% 55.22
头
合 计
¥11035.43 ¥1434.61
价税合计（大写） 壹万贰仟肆佰柒拾圆零肆分 （小写） ¥12470.04
"""
    result = parse_invoice_text(text)
    names = [item["product_name"] for item in result["line_items"]]
    amounts = [item["amount"] for item in result["line_items"]]
    assert len(result["line_items"]) == 9
    assert "5589拉链袋" in names[0]
    assert names[1] == "野生红茶礼盒装"
    assert names[2] == "曜韵崂山绿茶一盒"
    assert "电热水壶" in names[3] and "G60-1" in names[3]
    assert "记号笔" in names[4]
    assert "票" in names[5] and "夹" in names[5]
    assert "南孚9V碱性电池" in names[6]
    assert "隔弧罩" in names[7]
    assert "接触器触" in names[8]
    assert amounts == [39.82, 5498.62, 4811.29, 103.54, 18.58, 60.8, 36.58, 41.42, 424.78]
    assert round(sum(amounts), 2) == 11035.43


def test_parse_invoice_text_reads_doubled_glyph_line_items():
    """美的等进项票文本层常把每个字/数字加倍，去重后需保留单位与数量间距。"""
    text = """
电子发票（增值税专用发票）
发票号码：2266337777000000000000449999995544559955
开票日期：22002266年年0099月月1155日日
购 销
买 名称：山山东东壹壹知知产产数数字字科科技技有有限限公公司司 售 名称：济济南南美美的的智智慧慧家家居居有有限限公公司司
方 方
信 统一社会信用代码/纳税人识别号：9911337700110033MMAA33TT11BBXXAA66NN 信 统一社会信用代码/纳税人识别号：9911337700111122MMAA77MM99DD11BB00FF
息 息
项目名称 规格型号 单位 数量 单价 金额 税率/征收率 税额
**空空调调**家家用用空空调调套套机机**美美 KKFFRR--3355GGWW//GG33--11AA 套套 44 11559922..9922 66337711..6688 1133%% 882288..3322
的的 变变频频 分分体体套套机机
极极地地白白 美美的的
**空空调调**家家用用空空调调套套机机**美美 KKFFRR--3355GGWW//GG33--11AA 套套 33 11559922..9922 44777788..7766 1133%% 662211..2244
的的 变变频频 分分体体套套机机
极极地地白白 美美的的
**空空调调**家家用用空空调调套套机机**美美 KKFFRR--7722LLWW//GG33--11 套套 11 33884499..5566 33884499..5566 1133%% 550000..4444
的的 变变频频 柜柜机机套套机机
极极地地白白 美美的的
合 计 ¥15000.00 ¥1950.00
价税合计（大写） 壹万陆仟玖佰伍拾圆整 （小写） ¥16950.00
"""
    result = parse_invoice_text(text)
    assert result["invoice_no"] == "26377000000499954595"
    assert result["buyer_name"] == "山东壹知产数字科技有限公司"
    assert result["seller_name"] == "济南美的智慧家居有限公司"
    assert len(result["line_items"]) == 3
    assert result["line_items"][0]["quantity"] == 4
    assert result["line_items"][0]["amount"] == 6371.68
    assert result["line_items"][1]["quantity"] == 3
    assert result["line_items"][2]["quantity"] == 1
    assert round(sum(item["amount"] for item in result["line_items"]), 2) == 15000.0


def test_parse_invoice_text_reads_ream_unit_line_items():
    """纸品常用单位「令」，且品名可能换行。"""
    text = """
电子发票（增值税专用发票）
发票号码：26372000004651102726
开票日期：2026年09月20日
购 名称：济南泉易采科技投资发展有限公司 销 名称：山东壹知产数字科技有限公司
买 售
方 方
信 统一社会信用代码/纳税人识别号：91370102MAEL8FJM70 信 统一社会信用代码/纳税人识别号：91370103MA3T1BXA6N
息 息
项目名称 规格型号 单 位 数 量 单 价 金 额 税率/征收率 税 额
*油墨*荣大油墨 荣大油墨R-413 盒 30 97.3451327433628 2920.35 13% 379.65
*纸制品*荣大版纸 荣大版纸R-31 卷 10 199.115044247788 1991.15 13% 258.85
*油墨*理想油墨 理想油墨8113 盒 30 154.867256637168 4646.02 13% 603.98
*纸制品*理想版纸SV8131 理想版纸SV8131 卷 10 345.132743362832 3451.33 13% 448.67
*纸制品*GOLDEN TOP金东 GOLDEN TOP金东 令 115 216.814159292035 24933.63 13% 3241.37
8K试卷纸 8K试卷纸
*通用设备*安吉尔反渗透 安吉尔反渗透膜 支 10 606.58407079646 6065.84 13% 788.56
膜滤芯 滤芯-400G
*通用设备**安吉尔净水 AHR2801-4030K3 支 10 1505.28318584071 15052.83 13% 1956.87
器全套滤芯组合
合 计
¥59061.15 ¥7677.95
价税合计（大写） 陆万陆仟柒佰叁拾玖圆壹角整 （小写） ¥66739.10
"""
    result = parse_invoice_text(text)
    assert len(result["line_items"]) == 7
    names = [item["product_name"] for item in result["line_items"]]
    assert all(not name.startswith("*") for name in names)
    assert any("GOLDEN TOP" in name and "8K试卷纸" in name for name in names)
    golden = next(item for item in result["line_items"] if "GOLDEN TOP" in item["product_name"])
    assert golden["unit"] == "令"
    assert golden["quantity"] == 115
    assert golden["amount"] == 24933.63
    assert golden["product_name"] == "GOLDEN TOP金东 8K试卷纸"
    assert golden["specification"] == "GOLDEN TOP金东 8K试卷纸"
    angel = next(item for item in result["line_items"] if "安吉尔净水" in item["product_name"])
    assert not angel["product_name"].startswith("*")
    assert "AHR2801-4030K3" in (angel["specification"] or angel["product_name"])
    first = result["line_items"][0]
    assert first["product_name"] == "荣大油墨"
    assert first["specification"] == "荣大油墨R-413"
    assert round(sum(item["amount"] for item in result["line_items"]), 2) == 59061.15



