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
    return message
