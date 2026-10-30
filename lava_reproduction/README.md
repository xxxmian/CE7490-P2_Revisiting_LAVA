# LAVA reproduction 项目重建

这是依据课程报告和 PPT **重新实现**的 Python 项目，不是找回的原源码；没有恢复 commit `377cbb1` 或标签 `experiment-final-v2`，也不保证复现原数值/显著性。完整差异见 `REPRODUCTION_DIFFERENCES.md`。仅用 Python 标准库，Python 3.9+，无需安装第三方包。

## 立即运行

在解压后的 `lava_reproduction` 文件夹中打开终端：

```sh
python3 -m unittest discover -s tests -v
python3 run.py --suite smoke --workers 4 --output results/my_smoke
```

Smoke 也使用报告规模（180 主机、2,500 VM），但只有两个种子，用于检查流程，不能作为论文结论。

```sh
# 最终分组：seeds 20–39，7 种预测设置，全部六策略，840 次仿真
python3 run.py --suite heldout --workers 4 --output results/my_heldout
# 初始 accuracy sweep：seeds 0–19，600 次仿真
python3 run.py --suite sweep --workers 4 --output results/my_sweep
# 验证集：seeds 200–205，7 个阈值，168 次仿真
python3 run.py --suite validation --workers 4 --output results/my_validation
# 顺序包含上述三组；仍按 split 分开统计
python3 run.py --suite all --workers 4 --output results/my_all
```

Windows 可以用 `python` 替代 `python3`。运行时间随电脑而异；先 smoke。`--vms 200` 可用于更小的调试，产生的结果不能标作报告规模。若无法启动多进程，用 `--workers 1`。

也可运行 `sh run_all.sh` 执行测试、三组实验、smoke、结果审计及重点图表。

## 内容与输出

- `lava/model.py`：合成 trace、双指数混合条件剩余寿命、分箱置信度、受控 log10 噪声及严格 Oracle。
- `lava/simulator.py`：CPU/内存事件驱动调度、六策略、主机生命周期及模式、资源检查、污染/切换/容量回退计数。
- `lava/stats.py`：逐种子配对差、双侧 Student-t 95% CI；拒绝未配对或接受数不公平的比较。
- `lava/charts.py`：独立 SVG 置信区间图，不依赖绘图库。
- `configs/report_scale.json`：明确的参数配置；既包含报告恢复值，也包含推断值，**不能把整个配置视为报告原参数**。
- `results/*/raw.csv`：新仿真的逐种子、逐设置、逐策略结果。
- `results/*/summary.json`：配对均值、CI、样本数及 split。
- `results/*/manifest.json`：完整配置、Python 版本、源码/配置哈希。
- `results/figures/`：准确率扫描、默认预测器、阈值消融、模式污染四张重点图。
- `results/*/comparison.svg`：新结果误差棒图。
- `results/validation/threshold_selection.json`：仅验证集得到的新阈值建议；不会修改 frozen threshold 0.3。
- `reference/report_table1.csv`：人工转录报告第 9 页，只作对照，仿真器不读取。
- `reference/`：原附件副本、文字提取及 SHA256；附在项目中用于审计。
- `scripts/export_trace.py`：导出指定种子的新 trace，方便检查和后续存档。

## 模型及指标

所有时间单位为小时。对于混合权重 p、指数均值 a,b，观察 uptime u 后的权重为
`w(u)=p exp(-u/a)/(p exp(-u/a)+(1-p) exp(-u/b))`，条件剩余寿命为 `w(u)*a+(1-w(u))*b`。采用 log-sum-exp 稳定计算。置信度为条件剩余分布在预测类别区间中的概率。

合成模式只读取 profile 和已运行时间。受控模式由实验层用真实总寿命生成一次噪声预测，调度器通过预测接口获得数值和全局误差模型下的置信度，不接收未来退出事件或隐含正确桶标签。Oracle 是明确例外：按真实剩余寿命预测，置信度为 1。

`empty_pct = 100 * integral(empty_hosts dt) / (hosts * (final_exit-first_arrival))`。每个事件前用旧占用状态积分；同一时间先退出再到达。非空主机 packing density 是 CPU/内存占用率均值在有非空主机的时间区间上的时间平均，属于明确选择的指标定义。没有 warm-up 或截断 drain tail。

固定种子重新生成同一 trace；噪声采用独立 RNG，所有策略同种子同设置共享相同预测实现。配对差先在种子内计算，再跨种子做 t 区间。区间单位为百分点 pp，不是相对百分比。没有多重检验校正，解释 sweep 中的显著点时应保留这一限制。

## 六种策略

Best-Fit 最小化放置后的 CPU/内存剩余平方和。LA-Binary 在 2 小时分界下一次分类，之后固定。NILAS 用重新预测的最大主机退出时间计算延长成本、分箱，再 Best-Fit。LAVA 采用类别、open/recycling 状态、90% 阈值、残余 cohort 降级和 deadline 升级；同等级内用 NILAS 和 Best-Fit 决胜。VM CA 逐 VM 选择 LAVA/Best-Fit，但可放入另一模式主机。Host CA 保持主机模式到清空，优先相同模式及空主机，只有都放不下才容量回退；回退不改变原主机模式。

具体差异和每项参数来源请读差异报告。请勿把这份重建的结果直接替换到原报告后声称恢复了原始实验。

## 改进：先验融合寿命预测（新增）

`lava/model.py` 的 `BayesPredictor` 把受控噪声预测值与 profile 先验（合成模型）做贝叶斯融合，并把 336h 截断当作删失观测；`lava/simulator.py` 新增 `nilas_bayes`、`lava_bayes`、`vm_ca_bayes`、`host_ca_bayes`，调度规则与原策略完全相同，只换预测器。原 6 个策略的输出逐位不变（1,644 行存档已全部重新核对）。动机、预注册协议、结果与局限见 `IMPROVEMENT.md`。

```sh
python3 -m unittest discover -s tests -v                 # 16 项原测试 + 13 项新测试
python3 run_improvement.py --suite all --workers 8 --output results/improvement
python3 scripts/build_improvement_figures.py             # results/improvement/figures/*.svg
python3 scripts/report_improvement.py                    # 重新生成 IMPROVEMENT.md 第 6 节
python3 scripts/explore_dev.py --workers 8               # 开发期探索（仅 seeds 0–19）
python3 scripts/run_robust_extra.py --suite control --workers 8   # 评审后补跑：同种子协议对照
python3 scripts/run_robust_extra.py --suite load --workers 8      # 评审后补跑：到达率 ×2
python3 scripts/analyze_gate_by_bucket.py --workers 8    # 事后：门控按误差桶的通过率
python3 scripts/verify_reproduction.py --workers 8       # 重跑存档并逐字段核对 → results/verification_log.txt
```

`--suite all` 依次运行 test（seeds 1000–1099）、legacy（20–39）、tau（200–219）、robust（2000–2049），共 20,440 次仿真；两组补跑再加 2,800 次，合计 23,240 次。纯 CPU，不需要 GPU，进程数按机器核数设置。预注册的假设族与判定规则在 `configs/improvement_protocol.json`。注册的 `hosts=90` 鲁棒性变体只是重新标度（见 `IMPROVEMENT.md` 第 6.6 节），负载实验以 `--suite load` 为准。

`verify_reproduction.py` 全量重跑 1,644 次重建仿真，并对每组改进实验均匀抽样 50 次（`--sample -1` 为全量），整数字段要求完全一致，浮点字段报告相对差。`results/test_log.txt` 是 29 项单元测试的输出。

报告与幻灯片（第 3 版）同样由脚本从 `results/` 生成，数字不手抄。这两个脚本需要第三方包（`pip install reportlab python-pptx`），仿真本身仍只用标准库：

```sh
python3 scripts/build_report.py   # → ../Revisiting_Lifetime_Aware_VM_Allocation_Report_v3.pdf
python3 scripts/build_deck.py     # 读 ../..._Presentation_Updated.pptx → ../..._Presentation_v3.pptx
```
