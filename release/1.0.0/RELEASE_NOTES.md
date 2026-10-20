## 小白和小鸡毛

- 两只开心的线条小狗一起陪伴，包含 9 种动画状态和 16 个视线方向。
- 小鸡毛尾巴上下摆动，黑色描边的粉色爱心像气泡一样向上冒出。
- 调整左看时的圆润脸型，以及小白依偎坐姿的下半身。
- 提供面向 Windows 10 / Windows 11 的单文件安装器，内置动画预览；无需额外安装 Node、Python，也不需要联网。
- 自动识别当前用户的 Codex 配置目录，支持手动选择目录；重复安装时完整备份同名宠物。

## 安装

下载 **CodeXPets-1.0.0-Windows-Setup.exe**，双击查看动画并点击“安装此形象”。随后打开 Codex → 设置 → 宠物，刷新后选择“小白和小鸡毛”。目标电脑需已安装支持自定义 v2 宠物的 Codex。

也可下载 `maltese-retriever-1.0.0.zip`，将其中的 `maltese-retriever` 文件夹放到 Codex 配置目录的 `pets` 文件夹内。默认配置目录为当前用户的 `.codex`；如设置了 `CODEX_HOME`，则使用该目录。

## 动画与兼容性

- Codex 原生待机固定为 6 帧；安装器展示实际播放效果，与聊天审批中的 28 帧演示节奏存在差异。
- 资源校验、中文及空格路径、首次安装、重复安装备份、失败保护和其他宠物/设置保留测试通过。
- 已在 Windows 10 19045 x64 隔离环境验证；Win11 按兼容接口构建，尚未实机验证。EXE 未签名。

![原生待机预览](https://raw.githubusercontent.com/nerlionki/CodeXPets/v1.0.0/animation/pet-run/qa/previews/idle.gif)

角色原始 IP 归 moonlab_studio 所有。
