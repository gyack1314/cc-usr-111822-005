# 企业 AI 试点经营核算

项目按来源版本保存业务资料，已有 adoption、accounts、rollout 环节。已有采用、收入和账单的单期利润，尚未区分调价、人员调整与 AI 的净贡献。

运行与检查：

    python -m unittest discover -s tests -v
    python -m compileall -q pilot_economics tests
    python -m pilot_economics.cli data/example.json
