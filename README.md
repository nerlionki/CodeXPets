# CodeX Pets · 小白和小鸡毛

版本与分支：`1.0.0`。按用户提供的 moonlab_studio 线条小狗参考制作：小鸡毛（金毛）在左、小白（马尔济斯）在右，两只开心地靠在一起。左视采用修订后的圆润脸型，待机采用用户选定的依偎坐姿。小鸡毛尾巴上下摆动；黑色描边、粉色填充的爱心像气泡一样从下向上冒出。

## 安装

将 `dist/CodeXPets-1.0.0-Windows-Setup.exe` 复制到另一台电脑，双击打开，查看动画后点击“安装此形象”。目标电脑需要已安装支持自定义 v2 宠物的 Codex。

安装器面向 Windows 10 / Windows 11，使用系统自带的 .NET Framework 和 Windows Forms；素材全部内嵌，不需要额外安装 Node、Python，也不需要联网。默认安装到当前用户的 `CODEX_HOME/pets/maltese-retriever`；未配置 `CODEX_HOME` 时使用用户目录的 `.codex`，也可手动更改配置目录。默认用户目录安装无需管理员权限。

安装完成后，在 Codex 设置的宠物页面刷新并选择“小白和小鸡毛”。同名宠物会先完整备份到配置目录下的 `pet-backups`，不会在宠物列表制造重复条目。

## 动画与审批

当前本地素材已按待机统一各动画和视线方向的颜色与描边粗细，保留原动作、帧数、播放时序和透明轮廓。对比图与处理记录位于 `approval/idle-style-unified-v19/`。旧候选和失败稿已清理，逐文件验证过的恢复归档为 `build/obsolete-animation-candidates-20261021.zip`，清单为 `approval/cleanup-20261021.json`。

等待输入采用已审批的胸前轻合手与期待侧头，检查结果采用双手自然放低、侧头观察和开心点头。对应审批稿为 `approval/anthro-wait-review-v20/waiting.gif` 与 `approval/review-relaxed-v21/review.gif`。统一造型与后续修改约定见 `线条小狗-design.md`。

跳跃已修正细鼻线、眼嘴间距、小白立耳及身体和耳根描边；首尾直接回到实际待机姿态，落脚位置一致。完整衔接审批稿为 `approval/hover-transition-v26/idle-hover-idle.gif`。其他状态与待机的衔接检查记录位于 `approval/state-transition-audit-v27/`。

用户已确认 `approval/idle-bubble-v4/idle-approval-v4.gif` 的角色、尾巴和向上气泡爱心效果。聊天演示为 28 帧；Codex 原生待机格式固定为 6 帧，因此已保留选定造型和效果方向，适配为 6 个关键帧。**安装器展示实际原生播放预览**，节奏与演示 GIF 有差异。

最终图集是 1536×2288 的透明 WebP，包含 9 种动画状态与 16 个视线方向，`spriteVersionNumber: 2`。结构、透明边缘、独立方向盲审及最终视觉检查通过；部分中间视线角度存在已复核的细微方向提示警告。

## 验证与构建

- `installer/Build.ps1`：构建单文件 EXE 与 SHA256 校验文件。
- `installer/Test.ps1`：使用工作区独立目录测试资源校验、中文和空格路径、初次安装、重复安装备份、失败保护及其他宠物/设置保留。
- `release/1.0.0/installer-tests.json`：最终安装器测试记录。
- `dist/maltese-retriever-1.0.0.zip`：可手工部署的原生宠物包。

本机隔离测试报告为 Windows 10 19045 x64；Win11 兼容性依据相同 .NET Framework/Win32 接口目标，尚未完成 Win11 实机验证。EXE 未使用代码签名证书。已按用户要求安装到当前 Codex 并备份旧版；云端沿用原宠物 ID，同步后逐像素验证，记录见 `release/1.0.0/local-install.json` 与 `release/1.0.0/cloud-pet-sync.json`。

## 参考

- 作者主页：https://linktr.ee/moonlab_studio
- 角色参考：https://www.marieclaire.com.tw/lifestyle/news/88371
- 用户提供的坐姿、左视及爱心参考位于 `assets/maltese-retriever/references/`。

角色原始 IP 归 moonlab_studio 所有。
