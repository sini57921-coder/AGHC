# 依赖记录

三个`*.installed.json`与`*.reference-pins.txt`记录本机现有环境的发行包名称和版本，不导入模型、不运行GPU，不包含本地路径或直接下载凭据。它们是环境参照快照，不是经过重新安装验证的锁文件。Python解释器版本及已验证关键版本见`verified_versions.json`。

服务/CameraHMR、ECON、人脸分别保持三个环境，不用旧工程124字节根requirements。快照不能代替作者仓库原安装步骤、CUDA/驱动、Visual Studio、PyTorch3D等编译扩展及受限模型。自建或非标准发行版本不能保证从PyPI直接安装；安装失败不得擅自改版本。所有上游源码和权重仍按各自许可获取。本包不新增安装/升级步骤到当前生产环境。
