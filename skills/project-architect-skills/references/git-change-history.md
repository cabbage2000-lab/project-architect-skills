# Git 变更证据

在目标仓库根目录，向 [git_change_history.py](../scripts/git_change_history.py) 传入本轮可见、相关的自维护源码和测试文件。选择已确认候选涉及的源码和维护任务相关的入口、调用方或测试。目录和生成物留在取证范围之外。

```sh
python3 -B skills/project-architect-skills/scripts/git_change_history.py \
  skills/project-architect-skills/scripts/governance_plan.py tests/test_governance_plan.py
```

脚本固定本地 `HEAD`，沿第一父提交回看 90 天内至多 200 条记录。一条合并提交按合并在主线引入的差异计一次。沿 Git 识别的重命名追溯同一文件，纯重命名和初次创建不算实质修改。触及超过 30 个实质变更文件的提交跳过计数，仍追溯其中的重命名。可用 `--days`、`--limit` 和 `--max-files` 调整口径。已有工作区改动和未提交文件不进入历史统计。

- `available` 表示选定路径至少有 5 次有效修改，分布在至少 3 个提交日期。`hotspots` 按实质修改提交数排序，附最多 3 条代表提交。实际检查条数见 `examined_commits`，`truncated` 标明是否达到提交上限，`absent_paths` 列出在该版本未追踪的路径。
- `co_changes` 只列至少 3 次一起修改的文件对。`together` 为共同提交数，`changes` 按 `paths` 顺序给出两个文件各自的修改提交数，`commits` 提供代表提交。查看提交内容，区分一次业务规则演进、测试随实现更新或批量维护等原因。
- `insufficient` 和 `unavailable` 附样本不足或读不到 Git 的原因。仍可按任务、源码和已核实的调用关系生成治理计划和导读。对缺少提交历史的路径保留这个限制。

使用次数时附窗口、路径与代表提交。候选的维护影响接近时，将已确认异味发生在活跃文件的事实写入治理计划的 `reason` 和 `evidence`。共变先用来挑选待核对位置，沿现有调用、接口契约或测试关系查证，再把已核实的影响和操作写进维护导读。
