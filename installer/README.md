# CodeX Pets Windows 安装器

面向 Windows 10 / Windows 11 的单文件 EXE。使用系统 .NET Framework CLR 4 和 Windows Forms，不需要 Node、Python、联网或管理员提权。目标电脑须已安装支持自定义宠物 v2 的 Codex。

安装器先展示**实际原生六帧待机预览**；确认后点击安装，写入 `CODEX_HOME/pets/maltese-retriever`，未设置 `CODEX_HOME` 时使用当前用户的 `.codex` 目录。可以手动选择 Codex 配置目录。原有同名宠物备份到配置目录的 `pet-backups`，其他宠物和设置不变。

安装完成后，在 Codex 的宠物设置刷新并选择“小白和小鸡毛”。

## 构建与验证

`Build.ps1` 使用 Windows 自带的 .NET Framework C# 编译器，将已校验的图集、配置和原生预览嵌入 EXE。输出在项目 `dist/`。

测试入口：

- `--verify-assets <report.json>`：验证嵌入资源和哈希，不安装。
- `--install-to <Codex配置目录> --report <report.json>`：在指定目录执行安装与备份，可用于隔离测试。
- `--render-preview <preview.png>`：离屏渲染安装器窗口，不安装。

构建未使用代码签名证书。兼容性依据 .NET Framework 与 Win32 API 目标约束；发布测试记录会区分本机测试和未覆盖的其他系统。
