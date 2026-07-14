# SMT Guard 产品化构建可视化人工验收记录

## 1. 验收结论

本轮使用贴近真实 SMT 上料场景的隔离数据，对最终隔离构建进行了八个页面及全局操作员栏的可视化人工验收。按本报告定义的 48 个验收点统计，**通过 43，失败 5**；另记录 **2 个观察项**。

- P0：0
- P1：2
- P2：2
- P3：1
- 观察项：2

核心业务数据最终一致：SQLite `PRAGMA integrity_check` 为 `ok`；第二个运行完成 6/6 个站位；扫码记录共 8 条（OK 7、NG 1、重复扫码 1）；UI 导出的 CSV 共 8 行，与 SQLite 中该运行的记录逐行一致；扫码记录与审计日志的追加式保护触发器完整。

本轮结论为：**主要业务链路可走通，但不建议在修复两个 P1 前直接作为生产现场最终验收版本。**

## 2. 范围与隔离保证

- 验收工作区：`D:\work\smt\SMT`
- 最终 EXE：`.codex\tmp\productization-build-20260714-final\dist\SMTGuard\SMTGuard.exe`
- EXE SHA-256：`6d685d07b3bddececa1b9785af1444af7b82303edb6c62739ccaafa2e0aae3ff`
- 隔离数据根目录：`.codex\tmp\visual-acceptance-productization`
- 隔离 SQLite：`.codex\tmp\visual-acceptance-productization\data\smt_guard.sqlite3`
- 隔离导出：`.codex\tmp\visual-acceptance-productization\exports\run-CFG-2.0.csv`
- 截图目录：`.codex\tmp\visual-acceptance-productization\screenshots`
- 模拟输入目录：`.codex\tmp\visual-acceptance-productization\inputs`

启动目标 EXE 时显式设置 `SMT_GUARD_DATA_DIR` 指向上述隔离数据目录。未读取或修改 `D:\work\smt\SMT上料防错软件V20.310.3安徽丛科（免费试用一个月）` 中的任何原厂软件和资料；未覆盖工作区根目录现有 `build`/`dist`；未提交、推送、发布；未修改产品源码。验收完成后只关闭了本轮启动的窗口，环境中原先存在的另一个相同 EXE 进程保持运行且未操作。

## 3. 环境与输入数据

### 3.1 环境

- 验收日期：2026-07-14
- Windows 应用窗口：1183 × 791 像素（内容区域约为默认 1180 × 760）
- 操作员：`OP-A`、`OP-B`
- Python：uv 管理的 CPython 3.13.12，复用 `.venv\Lib\site-packages`
- 数据库：SQLite，隔离文件见上

### 3.2 模拟输入

| 文件 | 内容 | SHA-256 |
|---|---|---|
| `bom-v1.xlsx` | 产品 `90010001`，6 个 BOM 物料，其中 5 个用于站位配置 | `95e97032a4c65a0027ba2acc58170e1851b1feab087655e5f87eac584c4c7622` |
| `bom-v2.xlsx` | 同产品，7 个 BOM 物料；新增、删除及变更物料 | `c12dd53902f62fb877230c7e96f8757e7bc1719dde67f607d3fcae1dd21a0e43` |
| `station-v1.xlsx` | `CFG-1.0`，5 个站位分配 | `09d1d97b42b6e2708660e9b6d1d52edb5cb0535052695a4efa030862c3489d4f` |
| `station-v2.xlsx` | `CFG-2.0`，6 个站位分配 | `3b77da1af4b7fd6a60967b7df5e0e93fe7e41b497d59f2ffda865172bc70a501` |

设备及站位：

- `MNT-A` / 高速贴片机 A / SMT-1线：`F-01`、`F-02`、`F-03`、`F-04`
- `MNT-B` / 多功能贴片机 B / SMT-2线：`R-01`、`R-02`、`R-03`

BOM 差异在 UI 中显示为：

> 新增：ESD0402USB, ICMCUQFN32B；删除：ICMCUQFN32；变化：01005R10K, 0402C100N

四个 XLSX 均经过程序化结构检查及渲染目视检查，未发现公式错误，物料编码的前导零保持正确。渲染证据位于 `renders` 子目录。

## 4. 验收覆盖与统计

| 区域 | 验收点 | 通过 | 失败 | 结果摘要 |
|---|---:|---:|---:|---|
| 全局操作员栏 | 3 | 3 | 0 | OP-A 登录、OP-B 切换、运行随操作员切换中断 |
| 设备与站位 | 4 | 4 | 0 | 两设备、七站位、列表刷新、引用状态 |
| 导入配置 | 5 | 4 | 1 | 两套 BOM/站位表导入、数量与哈希正确；错误提示未完全中文化 |
| BOM 管理 | 5 | 4 | 1 | 对比、发布、启用、作废、归档通过；关键信息默认布局截断 |
| 产品配置 | 4 | 4 | 0 | 两版本、分配数量、BOM 关联、只读按钮状态 |
| 扫码 | 9 | 8 | 1 | 正确、错误、重复、跨设备、进度、切换操作员、恢复、完成；完成后输入未锁定 |
| 生产运行 | 5 | 4 | 1 | 零扫码中断、新运行中断、恢复、最终快照；首次进入详情错配 |
| 记录查询/CSV | 4 | 4 | 0 | 筛选、8 条记录、中文表头、与数据库逐行一致 |
| 审计日志 | 4 | 3 | 1 | 26 条日志、OP-B 筛选、非法时间校验；首次进入未自动刷新 |
| SQLite/持久化 | 5 | 5 | 0 | 完整性、运行状态、来源哈希、追加式触发器、CSV 对齐 |
| **合计** | **48** | **43** | **5** | 另有 2 个观察项 |

## 5. 关键业务流结果

1. 使用 OP-A 建立 2 台设备与 7 个站位。
2. 在未导入 BOM 前尝试导入站位表，系统阻止了错误顺序。
3. 导入 BOM v1/站位表 v1，形成 `CFG-1.0`；导入 BOM v2/站位表 v2，形成 `CFG-2.0`。
4. 比较两个 BOM 版本，新增、删除、变化物料与模拟输入一致。
5. 完成 BOM v1 发布、启用；BOM v2 发布、启用；BOM v1 作废、归档。最终 v1 为 `ARCHIVED`，v2 为 `ACTIVE`。
6. 启动 `CFG-1.0` 的零扫码运行 `RUN-20260714-055432-FB060465`；启动 `CFG-2.0` 后，前一个运行以“开始新的生产运行”中断，进度 0/5。
7. 在 `CFG-2.0` 运行中执行：
   - `MNT-A/F-01` 扫入错误物料 `01005R10X`，得到 NG；
   - 同站位扫入正确物料 `01005R10K`，得到 OK；
   - 再次扫描相同物料，记录为重复扫码，完成进度不重复增加；
   - 切换到 `MNT-B/R-01`，正确扫描 `LED0603GREEN`；
   - 将操作员从 OP-A 切换至 OP-B，运行自动中断；
   - 在生产运行页恢复该运行，扫码页显示恢复人 OP-B；
   - 完成其余四个站位，最终 6/6、100%、状态 `COMPLETED`。
8. 记录查询得到 8 条扫码尝试；导出 CSV 后直接与 SQLite 对齐。
9. 审计日志共 26 条：OP-A 24 条，OP-B 2 条；OP-B 的记录为 `RESUME` 与 `COMPLETE`。

## 6. 问题清单

### P1-01 生产运行页首次进入时表格选中行与详情快照错配

- 环境：上述最终 EXE，隔离 SQLite；窗口 1183 × 791。
- 前置条件：至少存在两个运行，首行是 `CFG-2.0` 已完成运行，第二行是 `CFG-1.0` 已中断运行。
- 复现步骤：
  1. 完成 `CFG-2.0` 的 6/6 扫码；
  2. 从扫码页首次切换到“生产运行”；
  3. 查看左侧/上方运行表第一行与右侧配置快照、站位状态。
- 预期：高亮第一行后，详情立即显示同一运行：`CFG-2.0`、OP-B、`COMPLETED`、6 个站位均完成，恢复/中断按钮禁用。
- 实际：表格第一行高亮且显示 `CFG-2.0`、OP-B、`COMPLETED`、6/6；右侧却显示旧运行/旧状态（`INTERRUPTED`、启动操作员 OP-A、仅 2 个站位完成），恢复按钮仍可用。单击已高亮行不能修复；先选择第二行再重新选择第一行后详情才正确。
- 证据：
  - 首次进入错配：[06-run-first-entry.png](../../.codex/tmp/visual-acceptance-productization/screenshots/06-run-first-entry.png)
  - 切换行后的正确状态：[06-run-corrected-selection.png](../../.codex/tmp/visual-acceptance-productization/screenshots/06-run-corrected-selection.png)
  - SQLite 正确状态：`database-audit.json` 中 `RUN-20260714-055515-4AF737EA` 为 OP-B、`COMPLETED`、6/6。
- 影响：操作员可能对错误运行执行恢复或中断，也可能据此误判当前生产状态；属于运行控制页面的高风险状态一致性问题。
- 建议方向：刷新后不要只调用 `selectRow(0)`；应显式调用一次选中项详情渲染，或先清除选择再设置当前单元格，并为“刷新后首行已处于选中状态、不触发 selectionChanged”增加 UI 回归测试。相关实现位于 `src/smt_guard/ui/runs.py:146-179`。

### P1-02 运行完成后扫码输入和提交按钮仍启用

- 环境：上述最终 EXE，`CFG-2.0` 运行已完成 6/6。
- 前置条件：最后一个站位 `MNT-B/R-03` 扫码成功，页面显示“全部对料完成”和 100%。
- 复现步骤：
  1. 完成最后一个站位；
  2. 观察扫码输入框和“提交扫码”按钮；
  3. 再输入 `R-03` 并提交；
  4. 再输入 `ESD0402USB` 并提交。
- 预期：运行完成后输入框和提交按钮应立即禁用，并明确提示该运行已经完成；如允许查看记录，不应再进入扫码阶段。
- 实际：输入框和提交按钮继续启用；输入站位后 UI 切换到“请扫描物料码”，再次输入物料后没有新增记录，也没有明确错误，输入框保留 `ESD0402USB`，要求物料/扫码物料显示 `-`，进度仍为 100%。
- 证据：
  - [05-scan-post-complete.png](../../.codex/tmp/visual-acceptance-productization/screenshots/05-scan-post-complete.png)
  - SQLite 记录仍为 8 条，证明没有静默追加第 9 条，但 UI 允许进入了无效交互状态。
- 影响：现场操作员会误以为运行仍可继续扫码；扫描枪连续输入时可能造成节拍延误、误判或重复操作。
- 建议方向：`handle_scan` 返回完成态后立即禁用输入和提交按钮、清空输入、维持“全部对料完成”终态；恢复页面时也应根据运行状态统一设置控件。当前 `_submit_scan` / `_render_feedback` 仅刷新反馈与进度，没有在完成后锁定控件，相关实现位于 `src/smt_guard/ui/scanning.py:257-281`。

### P2-01 面向中文操作员的业务错误仍显示英文

- 环境：上述最终 EXE，中文 UI。
- 前置条件：可触发导入顺序错误或 BOM 生命周期非法操作。
- 复现步骤 A：
  1. 在隔离空库中先进入“导入配置”；
  2. 未导入 BOM，直接尝试导入站位表。
- 复现步骤 B：
  1. 在 BOM 管理选择已归档的 `BOM-AH-9001`；
  2. 单击“启用”。
- 预期：错误信息与其余界面一致，使用明确中文，并给出可执行的下一步。
- 实际：
  - A 显示 `Import a BOM before importing a station table`；
  - B 显示 `BOM must be published before activation: 90010001/BOM-AH-9001`。
- 证据：[03-bom-english-error.png](../../.codex/tmp/visual-acceptance-productization/screenshots/03-bom-english-error.png)
- 影响：降低现场中文操作员对错误原因和纠正步骤的理解速度。
- 建议方向：在 UI 边界统一映射领域异常为中文，不直接向用户显示仓储/领域层英文原文；保留英文原文到诊断日志即可。对应英文字符串可见 `src/smt_guard/importing.py:100` 与 `src/smt_guard/sqlite.py:833`。

### P2-02 默认窗口下关键标识和追溯字段普遍截断

- 环境：窗口 1183 × 791，默认列宽。
- 前置条件：存在长度接近真实项目的 BOM 版本、物料编码、运行编号、SHA-256 和时间戳。
- 复现步骤：
  1. 依次打开 BOM 管理、产品配置、生产运行、记录查询与审计日志；
  2. 不手动拉宽窗口或逐列拖动；
  3. 比较表格中的版本、物料编码、运行编号、时间、来源 SHA-256、操作员等字段。
- 预期：默认布局能辨识关键标识；至少应提供可靠的自动列宽、工具提示、复制能力或固定关键列。
- 实际：多个页面显示 `BOM-...`、`CONNUSBC...`、截断的运行编号/时间/哈希；需要水平滚动或反复调列宽，且部分对比场景难以确认两行是否为同一对象。
- 证据：
  - [03-bom-lifecycle-diff.png](../../.codex/tmp/visual-acceptance-productization/screenshots/03-bom-lifecycle-diff.png)
  - [04-configurations.png](../../.codex/tmp/visual-acceptance-productization/screenshots/04-configurations.png)
  - [06-run-first-entry.png](../../.codex/tmp/visual-acceptance-productization/screenshots/06-run-first-entry.png)
  - [07-records-export.png](../../.codex/tmp/visual-acceptance-productization/screenshots/07-records-export.png)
- 影响：降低现场核对效率和追溯准确性，尤其影响 BOM 版本、运行编号与长物料码的人工比对。
- 建议方向：按内容或业务优先级设置列宽；为被省略单元格增加完整文本工具提示与复制；将运行编号、版本、结果、操作员等关键列固定在首屏。

### P3-01 审计日志页面首次进入不自动展示最新数据

- 环境：在本轮已产生 26 条审计日志后首次进入“审计日志”。
- 前置条件：应用启动后在其他页面产生了新的审计记录，审计页此前未手动查询。
- 复现步骤：
  1. 完成设备、导入、BOM、运行等操作；
  2. 首次切换到“审计日志”；
  3. 观察计数，再单击“查询”。
- 预期：首次显示或切换到页面时自动加载当前日志，或明确显示“尚未查询”而不是 0。
- 实际：首次进入显示 0 条；单击“查询”后立即显示 26 条。
- 证据：
  - 查询后 26 条：[08-audit-all.png](../../.codex/tmp/visual-acceptance-productization/screenshots/08-audit-all.png)
  - SQLite 同期 `audit_logs` 为 26 条。
  - 页面只在构造时及查询按钮触发 `refresh`，见 `src/smt_guard/ui/audits.py:45,85-89`。
- 影响：用户可能误以为审计未记录，造成不必要的合规或追溯疑虑。
- 建议方向：页面获得激活焦点时刷新；或显示“点击查询加载”并区分“未查询”和“结果为 0”。

## 7. 观察项

### O-01 同一产品的两个配置版本同时为 ACTIVE

`CFG-1.0` 与 `CFG-2.0` 在产品配置页和 SQLite 中同时为 `ACTIVE`；其中 `CFG-1.0` 仍关联已归档的 BOM v1。扫码页在启动运行前也可选择两者。

证据：[04-configurations.png](../../.codex/tmp/visual-acceptance-productization/screenshots/04-configurations.png) 及 `database-audit.json`。

当前文档未明确“同一产品是否只允许一个 ACTIVE 配置”以及“归档 BOM 是否应使关联配置不可新开运行”，因此暂不定为缺陷。建议产品负责人明确规则后补充约束与测试。

### O-02 页面切换后偶发短暂黑色表格区域

自动化抓取中，部分页面切换/操作后的第一帧出现黑色表格视口，约 1 秒后的第二帧恢复正常；未能稳定在人工等待后复现，且稳定截图正常。可能是 Qt 绘制或截图时序交互，暂列观察项。建议在目标现场显卡、远程桌面和高 DPI 环境做长时间观察。

## 8. 持久化与导出核对

核对结果文件：[database-audit.json](../../.codex/tmp/visual-acceptance-productization/database-audit.json)

- `PRAGMA integrity_check`：`ok`
- 表计数：
  - `devices` 2
  - `stations` 7
  - `bom_versions` 2
  - `bom_items` 13
  - `product_configurations` 2
  - `station_assignments` 11
  - `production_runs` 2
  - `run_station_states` 11
  - `attempts` 8
  - `audit_logs` 26
- BOM 文件 SHA-256 与数据库来源哈希：两个版本均匹配。
- 第二个运行：OP-B、`COMPLETED`、6/6。
- 扫码汇总：OK 7、NG 1、重复 1。
- 审计汇总：OP-A 24、OP-B 2；动作包含 CREATE、IMPORT、PUBLISHED、ACTIVATE、OBSOLETE、ARCHIVED、START、INTERRUPT、RESUME、COMPLETE。
- 只读取了 SQLite 触发器定义，没有对扫码记录或审计日志执行 UPDATE/DELETE。以下追加式触发器均存在：
  - `attempts_no_update`
  - `attempts_no_delete`
  - `audit_logs_no_update`
  - `audit_logs_no_delete`
- CSV：
  - UTF-8 BOM：有
  - 中文表头：11 列，与预期一致
  - 行数：8
  - 与数据库逐行一致：是
  - SHA-256：`c8719e1102a065cc8da0a726b269d6ed8fedd088af63554194ff3695549d62d7`

## 9. 证据索引

- 设备与站位：[01-master-data-stable.png](../../.codex/tmp/visual-acceptance-productization/screenshots/01-master-data-stable.png)
- 导入 v2：[02-import-v2.png](../../.codex/tmp/visual-acceptance-productization/screenshots/02-import-v2.png)
- BOM 生命周期与差异：[03-bom-lifecycle-diff.png](../../.codex/tmp/visual-acceptance-productization/screenshots/03-bom-lifecycle-diff.png)
- BOM 英文错误：[03-bom-english-error.png](../../.codex/tmp/visual-acceptance-productization/screenshots/03-bom-english-error.png)
- 产品配置：[04-configurations.png](../../.codex/tmp/visual-acceptance-productization/screenshots/04-configurations.png)
- 完成后仍可扫码：[05-scan-post-complete.png](../../.codex/tmp/visual-acceptance-productization/screenshots/05-scan-post-complete.png)
- 生产运行首次进入错配：[06-run-first-entry.png](../../.codex/tmp/visual-acceptance-productization/screenshots/06-run-first-entry.png)
- 生产运行切换行后正确：[06-run-corrected-selection.png](../../.codex/tmp/visual-acceptance-productization/screenshots/06-run-corrected-selection.png)
- 记录查询与导出：[07-records-export.png](../../.codex/tmp/visual-acceptance-productization/screenshots/07-records-export.png)
- 审计日志：[08-audit-all.png](../../.codex/tmp/visual-acceptance-productization/screenshots/08-audit-all.png)
- 审计非法时间提示：[08-audit-invalid-time.png](../../.codex/tmp/visual-acceptance-productization/screenshots/08-audit-invalid-time.png)
- 模拟输入：`../../.codex/tmp/visual-acceptance-productization/inputs`
- 输入渲染：`../../.codex/tmp/visual-acceptance-productization/renders`
- 导出 CSV：`../../.codex/tmp/visual-acceptance-productization/exports/run-CFG-2.0.csv`

## 10. 验证命令与结果

本轮执行的主要非破坏性检查：

- `git status --short --untracked-files=all`
  - 结果：仓库没有可用的已提交基线，现有项目文件整体为未跟踪状态；因此只能按路径与本轮操作范围保证未覆盖用户已有内容，不能依赖 Git diff 区分历史改动。
- `Get-FileHash ...\SMTGuard.exe -Algorithm SHA256`
  - 结果：`6d685d07b3bddececa1b9785af1444af7b82303edb6c62739ccaafa2e0aae3ff`。
- 使用 artifact-tool 对四个 XLSX 进行结构检查和渲染。
  - 结果：工作表结构可读、无公式错误、前导零正常；渲染 PNG 已保存。
- 使用 uv CPython 3.13.12 运行 `.codex\tmp\visual-acceptance-productization\work\audit_evidence.py`。
  - 结果：SQLite 完整性、表计数、运行状态、来源哈希、追加式触发器与 CSV 对齐全部通过，输出 `database-audit.json`。
- 可视化 Windows 应用自动化实际操作最终 EXE。
  - 结果：八页及全局操作员栏均已打开并交互；关键状态截图已保存。
- 结束时检查 `Get-Process -Name SMTGuard`。
  - 结果：本轮 PID 40180 已关闭；原有 PID 38524 仍运行且未操作。

## 11. 环境限制与未覆盖项

- 没有可用的 Git 提交基线，无法通过 Git 精确证明哪些未跟踪文件属于历史状态；本轮严格按绝对路径限制操作范围。
- 未在不同 DPI、不同分辨率、多显示器、触摸屏、远程桌面及不同显卡驱动下重复布局验收。
- 未连接真实扫码枪和蜂鸣器；输入使用键盘楔入等价操作，视觉反馈已验收，实体硬件节拍和音量未覆盖。
- 未覆盖所有损坏 XLSX 组合、超大 BOM、并发导入、磁盘满、数据库锁、权限不足和断电恢复。
- 未执行设备/站位删除或归档等会扩大数据变更面的操作；只覆盖创建、显示、引用与启用状态。
- 未覆盖应用关闭时中断再启动恢复；已覆盖“开始新运行导致零扫码中断”和“切换操作员中断后恢复”。
- 未对追加式扫码记录和审计日志执行破坏性 UPDATE/DELETE 验证，只读取并核对保护触发器定义。
- 本轮是人工验收，不重复运行用户已报告通过的全量 139 项自动化测试、覆盖率、Ruff/Pyright/Bandit/uv lock 检查。
