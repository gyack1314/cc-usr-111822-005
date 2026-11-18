# 企业 AI 试点经营核算

项目按来源版本保存业务资料，已有 adoption、accounts、rollout 环节。单期毛利（确认收入 − 云账单）之外，现支持可核对的试点比较：覆盖人群、实际采用、服务成本、订单结果和财务归属按各自有效期间对齐，区分效率改善、收入增量和费用转移，不再把调价与人员调整当作 AI 的净贡献。

## 资料种类

在原有 team、usage、invoice、cloud_cost 之上新增：

- `pilot`：试点定义，`team`、`assistant`、`baseline_periods`、`pilot_periods`
- `coverage`：覆盖人群，`team`、`period`、`eligible_users`
- `hour_report`：部门自报节省工时，`team`、`period`、`saved_hours`
- `order`：客户订单，`team`、`period`、`amount`；冲销单带 `reverses` 指向原单，金额为负
- `price_change`：调价，`effective`、`factor`，`scope: all` 或指定 `team`
- `staff_change`：人员调整，`team`、`effective`、`headcount_delta`
- `cost_transfer`：费用转移，`from_team`、`to_team`、`period`、`amount`

team 资料可带 `cost_center`、`loaded_hourly_cost`、`monthly_hours_per_user`，用于财务归属与效率估值。

## 比较口径

- 效率改善：自报节省工时剔除人员调整可解释的部分（减员 × 人均月工时），按工时单价估值
- 收入增量：订单结果按基线价格重述后与基线比较，调价影响单列不计入
- 费用转移：成本中心之间转移的金额单列，账面服务成本变化加回转出、剔除转入后才是真实服务成本
- 商业闭环：效率改善 + 收入增量 − 真实服务成本（均为每期均值），大于 0 为闭环成立

缺少可比对照（无基线订单）、试点期成本账单未结清、覆盖人群缺失、采用或订单数据缺失的试点只显示证据缺口，判断为证据不足。每期对齐事实与每个结论都附来源资料摘要，可逐条核对。

## 复现与改写

建议只依赖 `known_at` 之前收到的资料：后补的云账单或订单冲销不会改变历史建议，按原已知时间重算结果一致（摘要相同）。`--diff` 对比两个已知时间，列出商业闭环判断被改写的试点及原因（云账单到账、订单冲销、订单结果变化等）。

运行与检查：

    python -m unittest discover -s tests -v
    python -m compileall -q pilot_economics tests
    python -m pilot_economics.cli data/example.json
    python -m pilot_economics.cli data/pilots.json --compare
    python -m pilot_economics.cli data/pilots.json --recommend
    python -m pilot_economics.cli data/pilots.json --diff
