# AGHC

AGHC 是单张 RGB 身高估计与个体人体展示的研究原型。本仓库提供自有网页工作台、异步任务接口、输入规范化、人物选择、35 维特征衔接，以及同图人体和着装结果的组织代码。

## 功能

- 上传图片并查看真实阶段、预测身高和失败原因。
- 多人检测歧义时由用户选择目标，不同目标分别保存结果。
- 并列查看本任务规范 A 姿态人体与原姿态着装重建。
- 接续允许恢复的失败任务，取消尚未执行的排队任务。

## 主要入口

| 文件 | 用途 |
|---|---|
| `main.py`、`task_api.py` | 本机 API、串行任务 |
| `input_image.py`、`target_selection.py` | 图片规范化、目标选择 |
| `frozen35_single.py`、`ai_adapter.py` | 冻结 35 维估高衔接 |
| `body_mesh_task.py`、`clothed_task.py` | 同任务人体与着装结果 |
| `static/index.html` | 网页工作台 |

35 维字段见 [特征定义](config/feature_schema.json)。本机启动入口为 `start_local.ps1`，路径配置示例为 `config.example.json`。

## 运行条件

代码面向 Windows 本机环境，使用独立的 CameraHMR、ECON 和人脸 Python 环境。外部依赖的来源与版本见 [依赖清单](EXTERNAL_DEPENDENCIES.csv) 和 [环境说明](environments/README.md)。

完整厘米推理还需要未随仓库发布的冻结回归配置（插补、标准化、系数和截距）及部分 ECON、CameraHMR 集成组件。**本仓库不能单独运行完整推理。** 具备相应组件后，填写 `config.local.json`，设置 `AGHC_CONFIG`，运行 `start_local.ps1`，在本机打开 `http://127.0.0.1:8000/static/index.html`。服务只绑定本机回环地址。

## 已有结果

冻结 35 维读出在 MTP82 人物留一原图上的 MAE 为 7.34 cm，在 BARACCA30 人物五折原图上的 MAE 为 4.98 cm。这些是开发评估，不能合并为同一数据集成绩。局部遮挡下尚无稳定的精度增益；展示网格按预测身高等比缩放，不构成额外精度验证。

## 许可

自有代码采用 [MIT](LICENSE)。第三方代码、模型和数据遵循各自条款，范围见 [许可说明](LICENSE_STATUS.md)。仓库不包含人物照片、网格、任务日志、凭据或模型权重。
