# CE7490-P2 · Revisiting LAVA

CE7490 课程小组项目：重建 Lifetime-Aware VM Allocation（LAVA）仿真流程，分析置信度路由，并评估先验融合寿命预测。

本仓库集中保存代码、实验结果、汇报幻灯片、报告和组内讨论要点，方便组员阅读与协作。

## 最新成果（报告 v6 / 幻灯片 v3）

| 材料 | 文件 |
| --- | --- |
| 提交报告（PDF，MLSys 双栏样式） | [Revisiting Lifetime-Aware VM Allocation · Report v6](Revisiting_Lifetime_Aware_VM_Allocation_Report_v6.pdf) |
| 汇报 PPT（可编辑） | [Presentation v3 · PowerPoint](Revisiting_Lifetime_Aware_VM_Allocation_Presentation_v3.pptx) |
| 幻灯片（PDF 预览） | [Presentation v3 · PDF](Revisiting_Lifetime_Aware_VM_Allocation_Presentation_v3.pdf) |
| 中文汇报与讨论要点 | [汇报与讨论要点 v3](汇报与讨论要点_v3.md) |

报告 v6 共 14 页，沿用 [LAVA 原论文（MLSys 2025）](https://proceedings.mlsys.org/paper_files/paper/2025/file/9de62e421d58234dbf773abf43268630-Paper-Conference.pdf) 的双栏样式，保留精简后的摘要、引言和重绘的三张图。图 6.1 和表 6.1 均为单栏；实验数据和统计口径不变。学术参考文献扩充至 21 项，均在正文对应论述中引用，并附 DOI 或原始出版来源链接；历史课程材料和项目文件单列为来源说明。[原报告 v3](Revisiting_Lifetime_Aware_VM_Allocation_Report_v3.pdf)、[排版版 v4](Revisiting_Lifetime_Aware_VM_Allocation_Report_v4_MLSys.pdf) 和 [精简版 v5](Revisiting_Lifetime_Aware_VM_Allocation_Report_v5.pdf) 保留供对照。幻灯片共 22 页（20 页正文、2 页备份），PPT 备注中包含英文讲稿要点和数据来源。最新报告及 PPT 首页已填写 26S1 Group 5 的成员姓名、学号和邮箱。

## 代码与实验记录

- [完整运行说明](lava_reproduction/README.md)
- [仿真代码](lava_reproduction/lava/) 与 [测试](lava_reproduction/tests/)
- [先验融合改进与实验分析](lava_reproduction/IMPROVEMENT.md)
- [重建范围、参数来源及与原实现的差异](lava_reproduction/REPRODUCTION_DIFFERENCES.md)
- [冻结的评估协议](lava_reproduction/configs/improvement_protocol.json)
- [实验原始数据与汇总](lava_reproduction/results/) 和 [改进实验图表](lava_reproduction/results/improvement/figures/)

`lava_reproduction/reference/` 保存历史参考报告、幻灯片及文字提取；阅读最新成果请使用本页上方的报告 v6 和幻灯片 v3。

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

- `build_deck.py` 默认依赖的 `Revisiting_Lifetime_Aware_VM_Allocation_Presentation_Updated.pptx` 模板未包含在归档中，且要求模板前两页各有插图。根目录 v3 PPT 可直接阅读、编辑；重新生成前需准备匹配模板并调整脚本配置。
- `build_report.py` 使用 macOS 的 Arial 字体路径；在 Windows/Linux 上运行前需调整字体配置。

MLSys 样式报告可在 `lava_reproduction/` 目录中重新生成：

```sh
python3 scripts/build_report_v6.py
```

脚本复用 v3 生成器的结果计算、v5 的内容精简与图表排版；v6 从 `configs/literature_v6.json` 读取已核实的文献信息，按正文首次引用顺序编号，并检查所有条目均被引用。图表由 `scripts/report_figures.py` 直接读取同一结果生成。报告需要 Times New Roman（本机）或 Liberation Serif 字体。作者信息读取 `lava_reproduction/configs/team_members.json`。未加入原论文的会议版权声明。历史版本、实验结果及校验记录均保留。

## 小组协作

组员可直接查看文件，或通过 **Code → Download ZIP** 下载项目。修改建议可通过 Issues 提出；参与直接编辑需由仓库所有者在 **Settings → Collaborators** 中邀请，也可通过 Fork 和 Pull Request 提交修改。

仓库未新增开源许可证；公开可见不代表授予额外的使用或再分发许可。
