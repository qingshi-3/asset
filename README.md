# asset

游戏素材 PNG 轻量包：68,960 张图片，约 2.01 GB。原始全集保存在本地；本仓库保留图片与来源映射。

Windows 克隆时启用长路径支持：

```sh
git clone -c core.longpaths=true https://github.com/qingshi-3/asset.git
```

- `assets/`：按原素材包和包内路径保存的 PNG。
- `index/packages.json`：素材包、中文别名、许可与说明文件的原始位置。
- `index/files.jsonl`：每张图片的路径、尺寸、字节数、SHA-256 与来源。
- `index/mirrors.jsonl`：原全集 `PNG/` 目录的镜像路径；通过 SHA-256 关联图片索引。
- `index/summary.json`：数量、体积、排除项及校验结果。

`source.kind=file` 的 `path` 相对于全集根目录。`source.kind=zip` 的 `archive` 相对于全集根目录，`member` 是 ZIP 内原始路径。图片保持原始字节，不重新编码。

包含已展开素材及 25 套 game kits 内的 PNG。排除系统附带文件、`COUPON.png` 推广图及重复的顶层 `PNG/` 镜像目录；横版角色的 91 个 ZIP 已有对应展开目录，不重复提取。各包和界面内共用图片保留原路径，Git 自动共享相同文件内容。

原包中的字体、地图和可编辑文件从全集取用。素材版权与许可归原作者，许可来源见包索引；Craftpix 原包指向其 [许可页面](https://craftpix.net/file-licenses/)。

校验全部图片：`python tools/verify.py`。从全集生成或复核轻量包：`python tools/build.py --source <全集目录> --output <输出目录>`，优先使用新的输出目录。
