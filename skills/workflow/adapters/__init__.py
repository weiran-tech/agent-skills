# 适配层 — I/O 边界，零业务逻辑
# 业务逻辑全在 engine/；本层只做：读/写状态文件、配置、日志、派生视图、生成文档
# 依赖方向：adapters → engine → model
