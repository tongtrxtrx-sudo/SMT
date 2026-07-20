"""Translate known domain diagnostics into operator-facing Chinese guidance."""


def operator_error_message(error: BaseException | str) -> str:
    """Return clear Chinese guidance for known import and BOM lifecycle errors."""
    message = str(error)
    if message == "Import a BOM before importing a station table":
        return "请先导入 BOM，再导入站位表。"
    if message.startswith("BOM must be published before activation:"):
        identity = message.partition(":")[2].strip()
        return f"启用前必须先发布 BOM：{identity}。请先执行“发布”，再执行“启用”。"
    if message == "Active BOM must be obsoleted before archival":
        return "当前 BOM 仍处于启用状态。请先执行“作废”，再执行“归档”。"
    if message.startswith("BOM cannot be obsoleted from "):
        status = message.removeprefix("BOM cannot be obsoleted from ")
        return f"当前状态不允许作废 BOM：{status}。请先确认 BOM 生命周期状态。"
    if message.startswith("BOM version already exists:"):
        identity = message.partition(":")[2].strip()
        return f"BOM 版本已存在：{identity}。请填写新的 BOM 版本号。"
    if message.startswith("Unknown BOM version identifier:"):
        identifier = message.partition(":")[2].strip()
        return f"未找到 BOM 版本 ID：{identifier}。请刷新后重新选择。"
    if message.startswith("Unknown BOM version:"):
        identity = message.partition(":")[2].strip()
        return f"未找到 BOM 版本：{identity}。请刷新后重新选择。"
    if message.startswith("Duplicate product configuration:"):
        identity = message.partition(":")[2].strip()
        return f"产品配置已存在：{identity}。请填写新的配置版本。"
    if message == "Product code is required":
        return "产品编码不能为空。"
    if message in {
        "Product configuration version is required",
        "Configuration version is required",
    }:
        return "配置版本不能为空。"
    if message == "Station worksheet name is required":
        return "工作表名称不能为空。"
    if message == "Station table must contain at least one assignment":
        return "配置表至少需要一条站位与物料关系。"
    if message.startswith("Row "):
        row, _, detail = message.partition(": ")
        row_number = row.removeprefix("Row ")
        replacements = (
            ("missing column", "缺少列："),
            ("station and material are required", "站位编码和物料编码不能为空"),
            ("unknown station", "未找到站位："),
            ("unknown or disabled device", "设备不存在或已停用："),
            ("unknown or disabled station", "站位不存在或已停用："),
            ("duplicate station", "站位重复："),
        )
        if " belongs to device " in detail and ", not " in detail:
            station, _, ownership = detail.partition(" belongs to device ")
            device, _, supplied = ownership.partition(", not ")
            return (
                f"第 {row_number} 行：站位 {station} 属于设备 {device}，"
                f"与表中设备 {supplied} 不一致。"
            )
        for source, target in replacements:
            if detail.startswith(source):
                value = detail.removeprefix(source).strip()
                return f"第 {row_number} 行：{target}{value}。"
    return message
