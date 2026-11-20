# 许可与归属

根据项目所有者本次公开发布授权，仓库中的项目自有代码采用根目录MIT许可证，版权主体为sini57921-coder。该授权不覆盖第三方代码、模型、数据或未纳入本仓库的归属未确认组件。不得将整个依赖链宣称为MIT或无条件可商用。

## 已保留第三方声明

`static/three.min.js`为Three.js r128，原版权头保留；`static/OBJLoader.js`属于Three.js附加加载器。两者按MIT许可保留`third_party/threejs-LICENSE.txt`。原始取得提交尚未核实，不将版本号等同于已核实的上游提交。

来源：https://github.com/mrdoob/three.js/tree/r128
许可证：https://raw.githubusercontent.com/mrdoob/three.js/r128/LICENSE

## 不随包分发

ECON本地许可证明确限制第三方再分发及派生代码分享，因此排除`staged_infer.py`、ECON源码、库内修改、模型资产和配置文件，以外部入口引用。官方来源：https://github.com/YuliangXiu/ECON 。此处理不是取得分发许可，第三方仍须自行遵守其授权。

CameraHMR官方许可已于2026-11-20核实：https://camerahmr.is.tue.mpg.de/license.html 。虽本地仓库没有顶层LICENSE，官方条款已明确覆盖代码、脚本及检查点，允许约定范围的非商业科研等使用，并限制第三方分发。不能再写成“CameraHMR许可未知”，也不能将官方允许自行下载解释成可随本包再分发。项目的三个衔接脚本并非仓库中的官方入口；本地AGHC工具没有可用Git提交证明归属，仍需实际作者/单位确认。

## 核实后的外部取得与版本

ECON本地上游基线提交为`d8f4e8b7171e30868acd94a1d1f6fcc1238e3e32`。官方获取脚本：https://github.com/YuliangXiu/ECON/blob/d8f4e8b7171e30868acd94a1d1f6fcc1238e3e32/fetch_data.sh 。使用者须按官方流程注册、接受条款并自行取得模型。源码提交与r2本地修改分开记录；`staged_infer.py`、低显存配置及TestDataset/render/NormalNet修改不是下载上游提交后自动具备的文件，其公开分发仍缺授权及取得渠道。官方许可：https://raw.githubusercontent.com/YuliangXiu/ECON/master/LICENSE 。本轮仅查阅，没有注册、下载模型或代为接受新条款。

CameraHMR本地基线提交为`65d11a0640d23c60f55ec82ae54298e9e7e549e0`。官方SMPL-X获取说明：https://github.com/pixelite1201/CameraHMR/blob/65d11a0640d23c60f55ec82ae54298e9e7e549e0/docs/bedlam2.md ，对应脚本为同提交下`scripts/fetch_demo_data_bedlam2.sh`，要求分别注册BEDLAM2、CameraHMR和SMPL-X。版本号仅标识本地上游基线，不宣称工作树完全等同于该提交。

准确文件及放置关系见EXTERNAL_DEPENDENCIES.csv。资产hash来自既有下载/核对记录，是项目本地文件指纹，不是作者发布的官方校验值，也未在本轮重哈希大型权重。

## 冻结回归参数：有来源，分享权未确定

`frozen_full112_clear_only_candidate.json`记录82名MTP人物各两图及30名BARACCA人物各一张原图，共112人、194行、每人等权、Ridge200；不是第三方提供的预训练回归器。文件SHA256为`5633d27762e926ac3b760117287dc54fe1a85f714a37c59dc9b64e192ad38a05`。发布时必须同时明确fit.center、fit.spread、fit.coefficients、fit.offset和face_medians，不能只给35个回归系数。

MTP/TUCH官方条款：https://tuch.is.tue.mpg.de/license.html ，限制原数据/软件第三方分发；BARACCA官方入口：https://aimagelab-legacy.ing.unimore.it/imagelab/page.asp?IdPage=37 ，只明确科研教育使用、禁止商业使用。这些页面均不足以直接确定本项目训练得到的回归参数能否公开分享；不能据此自动判为允许，也不能直接判为禁止。项目负责人须先确认训练代码/参数成果权属和实际接受的协议；若协议对训练后参数/派生模型没有明确授权，由学校知识产权管理或相应数据权利方确认。BARACCA联系入口为官方页所列Guido Borghi；MTP联系入口以官方许可/项目站点为准。本轮不联系任何人。

SMPL-X、PIXIE、人体模型文件、NormalNet/IFNet/U2Net与检测权重、所有人物照片/网格/标签/逐人结果、日志、凭据、冻结回归系数均不分发。SMPL-X：https://smpl-x.is.tue.mpg.de/ ；PIXIE：https://pixie.is.tue.mpg.de/ 。数据或输出的使用/展示授权不能由源码许可代替。

`low_memory_silhouette.py`只调用PyTorch3D的公开接口，没有复制其混合实现；`generate_individual_body.py`等仅调用受限模型，模型本身不分发。这里仍须作者确认项目代码归属；调用许可与模型使用许可是不同事项。
