# 待机与坐姿状态衔接修订 v29

用户确认：“拖拽还是不调整了，其他的可以”。仅批准挥手、蹭脸、等待输入、亲吻处理和检查结果五项。

## 生效范围

五项坐姿动画首尾使用真实待机首帧；中间帧沿用已确认动作，仅整帧平移校准落脚位置，不缩放、不重画。原生帧数及播放时长保持不变。

左右拖拽保留当前正式版本的侧身牵手行走及逐帧精确镜像，不采用固定角色左右位置的提案。本轮生成的拖拽素材和相关实验脚本已移至工作区 build/rejected-walking-v29，未进入正式图集或安装包。此前的待机、hover 与 16 个视线方向亦保持不变。

## 已批准 GIF

逐项预览：待机一轮 → 动作连续两轮 → 待机一轮。

- [挥手](waving-transition-2x.gif)
- [蹭脸](failed-transition-2x.gif)
- [等待输入](waiting-transition-2x.gif)
- [亲吻处理](running-transition-2x.gif)
- [检查结果](review-transition-2x.gif)

`*-comparison.gif` 为左旧版、右修订版，使用相同原生时序。汇总预览 seated-overview.gif 中，较短面板结束后保持末帧；逐项 GIF 为时序审批依据。

## 校验与复现

frame-review.json 为官方逐帧检查，validation.json 为官方 v2 图集检查。preview-qa.json 核对 GIF 原生时长、往返总时长、坐姿首尾逐像素匹配待机，以及未改状态的像素一致性。status.json 分别记录审批、集成、安装和同步状态。

source/*.png 保留五项精确原生行像素，frames/ 保留获批帧，candidate-atlas.webp 仅替换获批五行。references/user-turnaround.jpg 为用户提供的参考图；该图触发的拖拽重画方案已取消。

可使用 python tools/preview-state-transitions.py 重新生成本地候选，再执行 python tools/review-state-transitions.py 核对时序；二者均不安装或上传宠物。正式集成依据本轮用户确认，而非结构校验自动批准。
