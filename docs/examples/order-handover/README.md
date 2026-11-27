# 订单交接演练与五人试点

本目录供观察员使用。交给参与者的仓库只包含 `project/` 的内容。验收脚本和试题留在仓库外。

## 准备与验收

在本 Skill 仓库根目录运行。每人每题都用一份新的副本和新会话，记录相同的基线树标识。

```sh
sample=$(mktemp -d)
cp -R docs/examples/order-handover/project/. "$sample/"
git -C "$sample" init -q
git -C "$sample" add .
git -C "$sample" -c user.name=Observer -c user.email=observer@example.invalid commit -qm baseline
git -C "$sample" rev-parse 'HEAD^{tree}'
python3 -B docs/examples/order-handover/verify.py "$sample" baseline
```

以下两题各自从基线开始。只向参与者出示本轮的题目。参与者同时说明一个受影响的调用方和判断依据。

| 题 | 给参与者的需求 | 观察员在 Skill 仓库根目录执行 |
| --- | --- | --- |
| A | 下载和对账导出的金额列表头改为 `net_amount`，保持历史归档兼容。 | `python3 -B docs/examples/order-handover/verify.py "$sample" A` |
| B | 下载和对账导出的客户列表头改为 `customer_name`，保持历史归档兼容。 | `python3 -B docs/examples/order-handover/verify.py "$sample" B` |

判题依据是 `orders.py` 和 `reconcile.py` 均调用 `order_csv.py` 中的 `write_orders`。下载含 A1、A2，对账只含已结算的 A1。归档入口独立生成旧表头并保留两个订单。观察员脚本解析三个命令实际输出的 CSV，逐行检查字段顺序、单字段姓名 `Lin, Mei` 和金额。失败时显示第一个不符的入口及差异。

## 演练授权与独立接手

在临时副本里安装当前 Skill。为演练质检，仅在副本 README 中把 `orders.py` 改成 `download_orders.py`，并把 `reconcile.py` 的 `== "settled"` 改成 `!= "settled"`，将这两处改动和技能目录提交为演练基线。

1. 在新会话输入「用 project-architect-skills 检查订单导出的运行说明和对账行为，给我拟修范围和验收方法」。应识别下载命令退出 2，以及对账把 A2 当作已结算订单。授权前 `git status --short` 应无输出。
2. 在本会话只批准对账筛选和相应用例。核对实际差异及测试，观察员的 `baseline` 验收应通过，README 仍保留演练中的错命令。在另一份相同的故障副本中选择「不同意治理」，核对工作区仍干净。
3. 从未注入故障的基线出发，针对调整客户列表头生成维护导读。另开一个未见过试题答案的会话，只给它仓库、导读和相邻题 A。用观察员脚本验收，把实际差异及复验者解释的调用关系记入演练记录。

## 真人试点

邀请 5 名能启动 Python 项目、第一次接触此样板的参与者。对照条件提供项目 README 和编码助手，确认新会话未加载本 Skill。实验条件额外加载本 Skill。两边使用同一模型和项目基线。可将前四人依次分配为「对照 A → 实验 B」「实验 B → 对照 A」「对照 B → 实验 A」「实验 A → 对照 B」，第五人的顺序在开测前选定并记录。

从读题开始计时，原作者和观察员全程不提示。每人每题记录一行，保留参与者编号、题号与先后、条件、模型与基线标识、首次正确定位用时、完成用时、实际改动、验收结果和卡住的步骤。完成后给一个未揭示答案的相邻要求，例如「为当前两个导出追加状态列」，记录参与者自行指出的入口及用自己的话解释的调用方。

30 分钟内完成改动、通过验收并完成相邻题解释，计为一次成功。未定位者按 30 分钟计入定位时间。分别统计实验和对照的成功人数、首次正确定位的中位用时。首轮建议门槛为实验条件至少 4 人成功，且成功人数高于对照，或人数相同时定位更快。[PRD 试点标准](../../project-architect-skills-PRD-v0.3.md#新手维护效果)
