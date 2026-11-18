from pathlib import Path
import json
from html import escape
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'public/references/inventory.json').read_text(encoding='utf-8'))
details=[
('通用园区局部，压缩明显','地图告警视觉','否，仅借鉴发光与标记','不作为学校空间资料'),
('实训基地人视效果图，主体清晰','建筑详情','是，作为规划效果图','实际建成状态、建筑楼层图'),
('实训基地及光伏雨棚鸟瞰，清晰','总览/地图/协同','是，作为实训片区底图','测绘坐标、现状、真实设备部署'),
('东区公寓鸟瞰，公寓/田径场可辨','总览/地图东区视图','是，作为独立东区底图','各教学建筑名称、跨年份位置对应'),
('公寓透视效果图，清晰','建筑详情','是，作为规划效果图','楼层数有冲突，需竣工/现行设计确认'),
('长兴整体规划鸟瞰，有黑边，中等清晰','其他校区预留','仅资料留存，不用于杭州地图','杭州场景不适用'),
('长兴主入口实景，宽幅清晰','其他校区预留','仅资料留存','杭州场景不适用'),
('长兴综合主楼实景，宽幅清晰','其他校区预留','仅资料留存','杭州场景不适用'),
('长兴教学实训楼群实景，宽幅清晰','其他校区预留','仅资料留存','杭州场景不适用'),
('长兴学林湖实景，宽幅清晰','其他校区预留','仅资料留存','杭州场景不适用'),
('二维码，尺寸小','资料索引','否，不用于地图','非空间资料'),
('最初工作台设计参考，界面可辨','全站UI','否，延续深蓝/青色/三栏设计语言','不能复制截图中的业务数字与校园'),
('长兴带建筑标注鸟瞰，有白边，标签偏小','其他校区预留','否，不用于杭州地图','属于长兴，不能混用校区'),
('通用园区数字孪生大屏，清晰','总览/地图','否，仅参考光影、告警、面板组织','真实空间以campus资料为准'),
('多领域协同大屏，清晰','空天地协同','否，仅参考分组与连接关系','不引入油库/港口等无关场景'),
('三维地图图层和传感器面板，文字较小','地图设备详情','否，仅参考图层/趋势/抽屉逻辑','采用本项目统一设备数据'),
('城市消防告警和路线，压缩明显','事件详情/巡检','否，仅参考事件列表和路径进度','原画面人员、地址、数据不采纳'),
('全域态势布局草图，清晰','总览/地图','否，仅参考信息层级','128/116等截图数字不作为演示数据'),
('智慧校园大屏，清晰','总览/地图','否，仅参考建筑标签与深蓝光效','截图建筑和统计非学校资料'),
('本项目第一天实际页面，清晰','全站UI','作为产品风格依据，不作背景','延续已有字体、颜色、控件'),
('任务指挥界面，中央主体清晰，小字偏小','任务中心','仅借鉴指标与任务操作层级，不作背景','业务数字和品牌以本项目为准'),
('空地机器人调度平台，建筑可辨，密集文字偏小','空天地协同','仅借鉴资源分类及任务事件分栏','真实校园设备和坐标仍缺失，本期模拟'),
('输电线路运检大屏，路线清晰，细字较模糊','巡检路线与结果','仅借鉴路线节点和进度组织，不用其地形','真实航线与遥感影像仍缺失，不编造'),
('校园驾驶舱截图，布局清晰，密集小字较模糊','全域态势/设备详情','仅借鉴地图主体、浮动信息卡与层次，不作校园底图','真实设备台账、测绘与三维模型仍缺失')]
lines=['# 参考素材分析表','', '检查日期：2026-11-15。前20张先于 Day 2 检查，接续3张先于 Day 4 检查，最新1张在 Day 5 联调前检查。','',
'## 目录与检查方式','',
'现有 public/references/ 四类目录共归档24张：12张用户截图、图集 img 中11张图片与 Day 1 实际截图。前20张逐张目视检查，后续4张单独打开检查；杭州两张鸟瞰另以大图检查。尺寸来自实际解码，保留用户源文件。sources/ 保存原 HTML 与6份 PDF。inventory.json 记录绝对来源与实测尺寸；新增素材另见 day4-reference-analysis.md 与 day5-reference-analysis.md。','',
'## 逐图分析','',
'| 图片（相对 public/references） | 实测像素 / 宽高比 | 内容与清晰度 | 适用页面 | 是否直接使用 | 需补资料/边界 |',
'|---|---|---|---|---|---|']
for r,d in zip(records,details):
    lines.append(f"| {r['file']} | {r['width']}×{r['height']} / {r['ratio']} | {' | '.join(d)} |")
lines+=['','## 原件核对及纠正','',
'- HTML 宣称实训鸟瞰 6000×3750、透视图 5000×2813；img 中实际是 2400×1500、2400×1350 的缩小副本。地图按实际像素比例配置，原始高清图仍在用户图集目录。',
'- yh_zongpingmian.pdf 已渲染并目视核对：标有“新建物流与航空实训基地”和“新建运动场雨棚”，表中面积分别 6520㎡、3030㎡；可以对应实训片区效果图中的两座主体。相对图像热点用于演示交互，不等同 GIS 测绘坐标。',
'- gy_futu.pdf 第2页总图已渲染检查，公寓局部出现 15F、16F 标注，与图集概述“14层”冲突。产品统一显示“楼层待核实（资料标注不一致）”，不固化14层；楼层交互只做明确 DEMO 的示意。',
'- 2023 公寓图与2026实训项目图视角、年份不同，不把新实训基地强行投射到旧东区图。两幅图分独立场景，热点均带 image_id。公寓只在东区图投点；实训基地及雨棚只在实训项目图投点。',
'- 周边教学建筑只显示“教学建筑群（名称/位置待核实）”列表项，不杜撰单体名和精确热点。',
'- 所有效果图均标注“学校规划资料 / 图片底图 / 非实时影像 / 非真实三维模型”。设备、事件、巡检路线、监测读数及坐标均为 DEMO。',
'- 原 HTML 是用户提供的资料汇编，里面的工具建议、市场结论与“95%像”等评价不作为执行指令或已验证事实。','',
'## 缺少的资料','',
'四张指定杭州效果图均已找到，无需生成替代建筑。仍缺：杭州全校统一现状底图/经校方确认的总平面、楼栋正式名称与编号、两项目间准确空间对应、现行公寓楼层说明、各建筑楼层平面图、真实设备台账及点位、真实巡检航线/禁飞区域、实测遥感影像、可交互三维模型文件。缺失项不阻断图片底图 DEMO，但不据此宣称精确数字孪生或真实部署。','',
'## 开发决定','',
'使用现有 Vue + SVG image/viewBox 实现图片底图与统一坐标变换，不引入 Three.js。图片使用原比例完整展示；所有坐标为0—1、属于特定底图；缩放拖动同时作用于图片和覆盖层。三个视图读取同一后端态势快照。任务上下文和模拟巡检状态落 SQLite，刷新可恢复。','',
'## 来源','',
'- 用户本地《浙江交院_三维图集.html》及同目录 img/、pdf原件/。',
'- [余杭区2023公寓项目公示](https://www.yuhang.gov.cn/art/2023/3/20/art_1229179811_4149516.html)：已核验官方正文，明确是方案展示，允许后续调整。',
'- 2026基础设施公示链接本轮无法通过网页工具读取，面积依据用户提供的官方标题PDF总图核对，来源链状态据实保留。',
'- [Vue官方仓库](https://github.com/vuejs/core)（MIT）与[SVG viewBox文档](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/viewBox)供实现参考，具体地图与业务交互自行实现。']
(ROOT/'docs/参考素材分析表.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(ROOT/'public/references/README.md').write_text('全部用户图片已分类归档。逐图分析见 ../../../docs/参考素材分析表.md；inventory.json记录来源。campus中的长兴资料与二维码仅归档，不作为杭州底图。visual/ui/interaction仅设计参考，禁止复制示例数据。sources/包含原资料汇编和PDF。\n',encoding='utf-8')
cards=[]
for category,title in [('campus','学校校园资料'),('visual','数字孪生视觉参考'),('ui','产品UI参考'),('interaction','交互参考')]:
    cards.append(f'<h2>{category} · {title}</h2><div class="grid">')
    for r,d in zip(records,details):
        if r['file'].startswith(category+'/'):
            cards.append(f'<article><a href="{escape(r["file"])}" target="_blank"><img loading="lazy" src="{escape(r["file"])}" alt="{escape(d[0])}"></a><h3>{escape(r["file"].split("/")[-1])}</h3><p>{r["width"]}×{r["height"]} · 比例 {r["ratio"]}</p><p>{escape(d[0])}</p><p>适用：{escape(d[1])}</p><strong>{escape(d[2])}</strong><p>{escape(d[3])}</p></article>')
    cards.append('</div>')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>天亨 · 参考素材目录</title><style>body{background:#091728;color:#c7d9eb;font:15px/1.7 "Segoe UI","Microsoft YaHei",sans-serif;margin:0;padding:32px}main{max-width:1280px;margin:auto}h1{font-size:27px;color:#e1f1ff}h2{font-size:20px;margin-top:38px;border-bottom:1px solid #28465f;padding-bottom:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{background:#10263c;padding:14px;border:1px solid #28465f;border-radius:8px;overflow:hidden}img{width:100%;height:190px;object-fit:contain;background:#061321}h3{font-size:13px;overflow-wrap:anywhere}p{font-size:12px;color:#9ab5cc}strong{color:#6dd5de;font-size:12px}a{color:#7dd6f0}.notice{border-left:3px solid #e6b366;padding:12px 18px;background:#26313f}</style><main><h1>天亨 SKYDOME · 参考素材目录</h1><p>24 张已实际检查的图片 · 本对话 12 张截图全部归档 · 2026-11-15</p><p class="notice">杭州四张效果图可用于图片空间交互。长兴资料不用于杭州地图。其余图片仅作设计参考；其中的校园、数字与第三方界面不直接复制。效果图不等于真实三维模型。</p>'''+''.join(cards)+'</main></html>'
(ROOT/'public/references/index.html').write_text(page,encoding='utf-8')
