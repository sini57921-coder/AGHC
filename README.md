# AGHC：单张RGB身高估计与个体人体展示

本仓库公开AGHC项目的网页、异步任务管理、输入规范化、35维特征定义与冻结算法衔接代码，基于Windows本机原型 `local_fullflow_20261119_r2`。自有代码按MIT发布；第三方内容保留原许可，详见[许可范围](LICENSE_STATUS.md)。

**这不是可独立安装的完整推理包。** 仓库不含第三方模型/权重、ECON派生推理入口、未完成权属确认的衔接工具、人物素材、日志、凭据或冻结回归配置。不宣称完整复现、在线推理已上线或精度达标。

## 公开内容

- `static/`：单图工作台、同任务双模型查看器、照片预览与结果摘要导出；不附带历史人物案例。
- `task_api.py`、`input_image.py`：串行任务、分阶段状态、解码、EXIF方向纠正、统一RGB输入与缓存身份。
- `frozen35_single.py`、`ai_adapter.py`：同图35维构造、缺脸处理、标准化和冻结回归调用；顺序见[特征定义](config/feature_schema.json)。
- `clothed_task.py`、`body_mesh_task.py`等：读取同任务个体参数与ECON产物，组织原姿态着装和规范A姿态人体展示。等比展示缩放不证明厘米准确或隐藏形体真实。
- `environments/`：实际三个Python环境的版本参照，不是经过独立重建验证的安装锁文件。

## 外部条件与启动

1. 准备Windows及记录中的服务/CameraHMR、ECON、人脸三个Python环境，不合并、不自动升级。版本见[依赖记录](environments/README.md)。CUDA、Visual Studio与模型资产须另行准备。
2. 按原许可从官方取得[CameraHMR](https://github.com/pixelite1201/CameraHMR)、[ECON](https://github.com/YuliangXiu/ECON)、SMPL-X等依赖。固定版本、文件名和放置方法见[外部依赖表](EXTERNAL_DEPENDENCIES.csv)。
3. 完整运行还需要合法提供的r2 ECON派生入口及配套修改、三个CameraHMR单图工具、AGHC helper和canonical CLI。**它们没有已确认的公开获取入口，安装默认官方仓库不能代替。**
4. 冻结回归配置暂留内部。必须具备训练时的标准化、缺脸插补参数、35维回归系数与截距；仅有特征定义不能复现厘米预测。不得用重新拟合或其他模型替代。
5. 取得上述条件后，复制 `config.example.json` 为不入库的 `config.local.json` 并填写路径，相对路径以配置文件目录为基准。

```powershell
$env:AGHC_CONFIG = (Resolve-Path './config.local.json').Path
& '<服务Python路径>' ./release_config.py
powershell -NoProfile -ExecutionPolicy Bypass -File ./start_local.ps1
```

打开 `http://127.0.0.1:8000/static/index.html`。只绑定本机回环，API没有公网身份隔离，不能直接公开8000。按Ctrl+C停止。运行后的任务、转换记录和日志留在本地 `runs/`；失败保留分项原因，不加载其他任务模型替代。

## 工作目标与已有结果

10 cm是当前工作目标表述，**不是学校已经确认的验收标准**；原申请存在3 cm与10 cm口径差异。以下均为开发评估，不同来源和遮挡协议不能合并为独立泛化成绩：

| 开发来源 | 原图MAE | 人工遮挡MAE |
|---|---:|---:|
| MTP82 | 7.3413 cm | 7.2998 cm |
| BARACCA30 | 4.9802 cm | 局部躯干4.9079 cm；单侧部分腿部5.0334 cm |

尚未证明稳定的局部遮挡精度增益，未达到3 cm或2秒目标。一次本机完整处理为361.317秒，不含排队0.086秒；它不是平均耗时或性能保证。人物数据和逐人预测不随源码公开。

## 验证与许可边界

发布副本只做过配置、轻量导入、语法及引用检查，没有独立安装或完整推理验收。自有代码采用[MIT](LICENSE)，Three.js与OBJLoader保留原MIT声明。ECON、CameraHMR、SMPL-X、PIXIE及相关数据/模型不因本仓库MIT而获得再分发或商业使用授权。
