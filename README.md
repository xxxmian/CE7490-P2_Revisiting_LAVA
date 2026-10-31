# CE7490-P2 · Revisiting LAVA

CE7490 课程小组项目：重建 Lifetime-Aware VM Allocation（LAVA）仿真流程，分析置信度路由，并评估先验融合寿命预测。

本仓库集中保存代码、实验结果、汇报幻灯片、报告和组内讨论要点，方便组员阅读与协作。

## 最新成果（报告 v8 / 幻灯片 v4）

| 材料 | 文件 |
| --- | --- |
| 提交报告（PDF，MLSys 双栏样式） | [Revisiting Lifetime-Aware VM Allocation · Report v8](Revisiting_Lifetime_Aware_VM_Allocation_Report_v8.pdf) |
| 汇报 PPT（可编辑，15 页） | [Presentation v4 · PowerPoint](Revisiting_Lifetime_Aware_VM_Allocation_Presentation_v4.pptx) |
| 幻灯片（PDF 预览） | [Presentation v4 · PDF](Revisiting_Lifetime_Aware_VM_Allocation_Presentation_v4.pdf) |
| 中文汇报与讨论要点 | [汇报与讨论要点 v4](汇报与讨论要点_v4.md) |

报告 v8 共 12 页，以 [LAVA 原论文（MLSys 2025）](https://proceedings.mlsys.org/paper_files/paper/2025/file/9de62e421d58234dbf773abf43268630-Paper-Conference.pdf) 的字体与双栏风格排版。恢复详细的方法、参数来源、种子设计、验证记录、路由诊断和完整政策比较；仅去掉 4 张重复或辅助表，保留 17 表、3 图和全部 21 项正文引用的学术文献。所有保留结果表的数值与 v6 一致。通过连续分栏和表格自然续栏减少留白，不缩小正文字号。原始结果文件和 [归档报告 v6（14 页）](Revisiting_Lifetime_Aware_VM_Allocation_Report_v6.pdf) 保留供核对。

幻灯片 v4 共 15 页，包含封面与总结，不另设备份页。清楚分为“问题是什么”“实验发现了什么”“我们怎么改进”三块，用直观例子解释 VM、Best-Fit、LAVA 和先验融合；页面用算例、机制对照、诊断证据和关键结果串起论证，逐步解释术语；备注保留通用中文讲解、完整统计和数据来源，不标人员分工。最新报告与 PPT 的成员顺序为 Zhang Qi、Zhang Saining、Zheng Yitao，姓名、学号和邮箱均保留。

## 代码与实验记录

- [完整运行说明](lava_reproduction/README.md)
- [仿真代码](lava_reproduction/lava/) 与 [测试](lava_reproduction/tests/)
- [先验融合改进与实验分析](lava_reproduction/IMPROVEMENT.md)
- [重建范围、参数来源及与原实现的差异](lava_reproduction/REPRODUCTION_DIFFERENCES.md)
- [冻结的评估协议](lava_reproduction/configs/improvement_protocol.json)
- [实验原始数据与汇总](lava_reproduction/results/) 和 [改进实验图表](lava_reproduction/results/improvement/figures/)

`lava_reproduction/reference/` 保存历史参考报告、幻灯片及文字提取；旧版成果保留供对照，阅读最新成果请使用本页上方的报告 v8 和幻灯片 v4。

## 快速运行

仿真和测试需要 Python 3.9 或更新版本，仅使用 Python 标准库。下载本仓库后，在项目目录执行：

```sh
cd lava_reproduction
python3 -m unittest discover -s tests -v
python3 run.py --suite smoke --workers 1 --output results/my_smoke
```

Windows 可使用 `python` 替代 `python3`。Smoke 用于检查流程；完整实验、种子划分、指标及输出格式见[运行说明](lava_reproduction/README.md)。重新运行时建议指定新的输出目录，以保留仓库内已存档结果。

## 阅读结论时的边界

这是依据已有课程材料独立重建的项目，并非恢复的原始源码或原始提交。实验使用合成 workload；结果应作为同一仿真环境内的配对比较解读。新增先验融合方法在预注册测试中，相对 LAVA 的 4 个准确率检验有 3 个成立。方法、统计判定和局限详见报告及实验记录。

## 报告与 PPT 的生成脚本

生成脚本保留在 `lava_reproduction/scripts/`，需要额外安装 `reportlab` 和 `python-pptx`。当前归档有两项已知限制：

- `build_deck.py` 是历史版生成器，默认依赖的 `Revisiting_Lifetime_Aware_VM_Allocation_Presentation_Updated.pptx` 模板未包含在归档中，且要求模板前两页各有插图。15 页 v4 可直接在 PowerPoint 中编辑，旧脚本不会重建这一版；重跑旧脚本前需准备匹配模板并调整配置。
- `build_report.py` 使用 macOS 的 Arial 字体路径；在 Windows/Linux 上运行前需调整字体配置。

MLSys 样式报告可在 `lava_reproduction/` 目录中重新生成：

```sh
python3 scripts/build_report_v8.py
```

脚本复用 v6 的正文、结果计算和文献目录，v8 负责适度去重及连续双栏排版。结果表与图直接读取归档结果；文献按正文首次引用顺序编号，并检查所有条目均被引用。文献信息在 `configs/literature_v6.json`，图表基础在 `scripts/report_figures.py`。报告需要 Times New Roman（本机）或 Liberation Serif 字体。作者信息读取 `lava_reproduction/configs/team_members.json`。未加入原论文的会议版权声明。历史版本、实验结果及校验记录均保留。

## 小组协作

组员可直接查看文件，或通过 **Code → Download ZIP** 下载项目。修改建议可通过 Issues 提出；参与直接编辑需由仓库所有者在 **Settings → Collaborators** 中邀请，也可通过 Fork 和 Pull Request 提交修改。

仓库未新增开源许可证；公开可见不代表授予额外的使用或再分发许可。
