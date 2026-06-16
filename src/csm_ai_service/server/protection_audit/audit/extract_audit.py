from typing import Dict, Any, Optional, List

from csm_ai_service.server.protection_audit.audit.audit_graph import RuleAuditResult, AuditRule
from csm_ai_service.server.protection_audit.common.file_tools import load_cached_ocr_result
from csm_ai_service.server.protection_audit.common.locate_tools import find_text_positions_in_json
from csm_ai_service.server.db.repository.audit_result_repository import get_audit_results_by_task_id

# =========================================================
# 从数据库中根据task_id获取审计结果
# =========================================================
def get_audit_fields_from_db(contract_id:int, task_id: int) -> Dict[str, Any]:
    """
    提取合同关键字段

    Args:
        task_id: 任务ID
    Returns:
        {
            'extract_info': 提取的字段信息,
            'field_positions': 字段位置信息
        }
        :param task_id:
        :param contract_id:
    """
    audit_results = get_audit_results_by_task_id(task_id)


    ocr_result = load_cached_ocr_result(contract_id)
    field_positions = find_field_positions(audit_results, ocr_result.get("locate_json_result", {}))
    return {
        'check_info': audit_results,
        'field_positions': field_positions,
    }



def find_field_positions(
        check_list: List[RuleAuditResult],
        json_result: Optional[Dict],
) -> Dict[str, List]:
    """
    找到提取的字段信息 在json中的位置信息
    """

    field_positions = {}  # 记录位置

    if json_result:
        for check in check_list:
            field_name = check.rule_name
            field_value = check.origin_text
            chapter_list = check.related_doc_ids
            if field_value and field_value != '-':
                # 搜索value的所有位置
                value_positions = find_text_positions_in_json(field_value, chapter_list, json_result)
                if value_positions:
                    # 如果有多个匹配，选择第一个
                    field_positions[field_name] = value_positions

    return field_positions
