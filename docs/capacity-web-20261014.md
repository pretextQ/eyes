# 容量 Web 展示与真实页面验收（2026-10-14）

Asia/Shanghai；起点 `80270dc`，Windows PowerShell / 本机 Docker Linux，PostgreSQL18.6、缓存控制镜像Python3.14.7、Node22.14.0。本轮补齐实际前端，未修改后端、容量规则、迁移、依赖或权限。它解决按需使用时管理者在既有运行状态页识别接收容量及未知测量的问题。

## 实现

入口为 Web「工作空间 → 运行状态」（`/operations`）的「容量与当前告警」。`frontend/src/components/CapacityStatus.tsx` 接入原 `GET /v1/operations/capacity`，`pages/Operations.tsx` 挂载。复用 panel、按钮、Badge、Loading、Empty、ErrorNotice及React Query；没有新控制台、设置额度、删除数据或通知功能。

展示项目UUID、JSON文本正文bytes/额度/后端warning百分比，及整个产物文件系统used/available/total bytes/最低余量。单位B，测量时间完整保留秒和时区；明确正文逻辑额度不是PostgreSQL硬磁盘上限、卷空间包含其他进程。状态和原因来自后端，0阈值显示未启用，不另算容量阈值。

可见页面15秒轮询、隐藏页面不后台轮询、单次查询不自动重试（读取错误仍随15秒轮询重读）；手动刷新在请求进行中禁用，`cancelRefetch:false`复用在途请求。401/403停止容量轮询；原连接切换清空全部项目缓存。告警按后端ID去重更新，不toast、不追加历史；恢复后下次测量移除。首次loading、未连接、无measurement/缺字段、读取错误、403、单项unknown均分别显示。读取错误不显示旧容量；计量或接收时间超过60秒标为历史/无法确认，此60秒仅为页面新鲜度策略。缺失/无效数值不会补0；后端已测得的真实0仍可显示。

## 隔离环境与原始证据

原现场保持停止；只读复制上一轮 `eyes-independent-20261014-pg/artifacts` 到新 `eyes-capacity-web-20261014-*` 卷、网络，仅运行PG/API，当前src只读挂载。API绑定127.0.0.1:18141，前端本地18140代理它。不启动Runner/Scheduler/Agent/评分器，不调用模型，不填充磁盘。沿用副本的独立项目 `42d92a4c-9077-4d24-9a50-d7323c3ca6cd`，起始真实归档事件1条/530B；新来源明确标为archival replay，仅复用原完整 `observation-real-first.json`，不改事件ID/时间/内容，不称为新执行。

私有API响应、SQL/访问日志、DOM及截图保留在忽略目录 `data/capacity-web-20261014/`。真实浏览器为本机Codex内置Chromium；Edge自动化入口不可用，未宣称Edge/Chrome扩展检查。浏览器以原有效项目令牌连接，不保存凭据到仓库或页面截图。

| 实际检查 | 页面及持久结果 |
| --- | --- |
| 正常与默认关闭 | quota1000时530B/1000B、90%、正常，空间最低余量0为未启用；后续quota0时1060B仍真实显示、两限制未启用，无虚构无限存储保证 |
| 接近阈值 | quota580、用量530，后端warning/quota_near_limit，页面接近阈值/580B/90%一致 |
| 满额及空间不足 | quota530时blocked/quota_reached；产物最低余量2TB高于真实free约1.013TB，页面空间不足/below_minimum_free_bytes，未填满磁盘 |
| 新增拒收 | 新归档来源上传原事件507，growth530；SQL仍1条/530B；已有容量独立轮次的并发/幂等证据继续保留，未重复制造Agent执行 |
| 恢复 | 停旧API，以quota2000/空间门槛0启动；原拒收请求重传200，SQL2条/1060B。页面1060B/2000B正常、告警集合为空；原blocked告警消失 |
| 读取失败 | 实际停止本轮API，刷新返回502；页面无法确认当前容量，旧数字/正常状态消失，提供重试 |
| 无权限/连接切换 | 使用真实read令牌，容量403；页面无权限且无前管理项目的容量/卷读数，其他read运维及审计仍可用。原API权限未改 |
| 部分未知 | 独立API配置实际不存在且不可建立的 `/proc/eyes-capacity-unavailable` 测量目录，卷API为null/null/null、unknown/volume_measurement_failed:2；页面三字节项无法确认，正文1060B/2000B仍正常，显示unknown告警。ready同时实际失败，没有伪造成功页面 |
| 浏览器布局与刷新 | 1280×900桌面两列、390×844窄屏一列；UUID、长字节和时间换行，无容量区块横向溢出。真实刷新切换正常→warning→blocked→error→恢复、权限与unknown均读取DOM/截图；服务访问日志保留自动GET，不弹出重复告警 |

浏览器原始测量时间更新、正文精确值及状态与API一致；卷空间是动态采样，不把不同时间响应的free差异认定为数据错误。正常、blocked、恢复、403、错误及unknown均有真实截图/DOM；没有通过响应替换、固定成功数据或测试fixture制造状态。

## 检查、操作失败与限制

已有 `npm run lint`、`npm run format:check`、`npm run build`（包含`tsc -b`）通过；修改后重跑相关检查。`git diff --check`与文档链接核对通过。未新增或修改测试、fixtures、mocks、自测脚手架；未安装项目依赖。只修改前端和需要同步的说明，无后端改动，因此未重新跑后端迁移/构建矩阵。

保留操作失败：Edge入口不可用；Start-Process后台Vite命令被执行策略拒绝，改用受管终端进程成功启动。一次容器env-file使用frontend工作目录的相对路径失败，改绝对路径后成功；首次恢复请求在API刚启动时ResponseEnded，服务就绪后原请求200。API切换期间页面及日志曾出现502，作为真实错误验证而非成功证据。README补丁一次上下文不匹配，重新按完整原文编辑后核对。

空数组/缺失计量/无效数字保护为源码检查，当前API固定返回两项，不注入假响应验证。未增加慢响应/网络长期阻塞的重叠请求故障注入；刷新去重来自既有Query机制、禁用按钮和cancelRefetch:false。未覆盖磁盘耗尽、强杀、inode、local/recovery新增拒收、产物竞争或长期趋势；此前“部分通过”的独立验收原样保留，本轮只关闭Web展示缺口，不升级整个容量故障矩阵。过期读数与隐藏标签暂停为源码/查询选项检查；内置浏览器第二标签操作后原页仍持续获取新测量，未形成真实过期读数，因此不记作该分支实测通过。最终DOM计量宽度/scrollWidth桌面均991px、窄屏均342px。

无额度修改或外部通知，审计追加容量、数据库物理硬配额仍为能力边界；真实版本改善/退化及24h仍为未来可选验证。结束时停止本轮服务，保留私有材料和新卷，原现场不启动/不修改。提交及推送结果以交付报告为准。
