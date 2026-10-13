"""
预警报告审计任务队列
异步处理告警处置报告：PDF解析 -> 结构化提取 -> 研判审计

纯内存队列模式：
- 接收请求 → 先写入 DB（持久化） → 再 push 到内存队列
- 单线程从内存队列阻塞消费，执行过程中持续更新 DB 状态
"""
import os
import json
import hashlib
import queue
import threading
import traceback
from datetime import datetime

from csm_ai_service.server.db.repository.alert_report_task_repository import (
    get_alert_report_task_by_id,
    update_alert_report_task,
)
from csm_ai_service.server.warning_report_audit.audit.audit_process import (
    get_warning_report_json_by_filepath,
    construct_rag_prompt,
    get_rules_desc,
    find_field_positions, gen_new_filename_by_hash,
)
from csm_ai_service.server.warning_report_audit.audit.report_judge_tool import (
    init_analyze_result_json_data,
    judge_report_by_llm,
)
from csm_ai_service.server.warning_report_audit.audit.risk_judge_tool import is_high_risk_alert
from csm_ai_service.server.warning_report_audit.tools.pdf_parser_tools import parse_text_pdf
from csm_ai_service.settings import Settings
from csm_ai_service.utils import build_logger

logger = build_logger()


def generate_task_id(file_name: str, file_content: bytes) -> str:
    """
    根据文件名 + 文件内容生成 task_id（SHA256 前 32 位）
    同一文件内容生成相同 task_id，可用于去重
    """
    hasher = hashlib.sha256()
    hasher.update(file_content)
    hasher.update(file_name.encode("utf-8"))
    return hasher.hexdigest()[:32]


class AlertReportTaskWorker:
    """任务工作类：单线程从内存队列消费任务，执行 PDF解析 + 研判审计"""

    # 空闲轮询间隔（秒）：未取到任务时最多阻塞等待120秒再查，减少空轮询；
    # 有新任务 put() 时会立即唤醒阻塞的 get，任务响应不受影响
    POLL_INTERVAL = 120.0

    def __init__(self):
        self.task_queue = queue.Queue()
        self._worker_thread = None
        self._running = False

    # ==================== 对外接口 ====================

    def submit_task(self, task_id: str):
        """提交任务到内存队列"""
        self.task_queue.put(task_id)
        logger.info(f"[AlertReportTaskWorker] 任务 {task_id} 已加入内存队列")

    def queue_size(self) -> int:
        """当前队列中待处理任务数"""
        return self.task_queue.qsize()

    # ==================== 生命周期 ====================

    def start(self):
        """启动单工作线程"""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="AlertReportTaskWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("[AlertReportTaskWorker] 工作线程已启动")

    def stop(self):
        """停止工作线程"""
        if not self._running:
            return
        self._running = False
        self.task_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        logger.info("[AlertReportTaskWorker] 工作线程已停止")

    # ==================== 工作循环 ====================

    def _worker_loop(self):
        while self._running:
            try:
                # 队列空时最多阻塞 POLL_INTERVAL 秒（未查到任务则休息30s再查）
                task_id = self.task_queue.get(timeout=self.POLL_INTERVAL)
            except queue.Empty:
                continue

            if task_id is None:
                break

            logger.info(f"[AlertReportTaskWorker] 获取到待处理任务 {task_id}")
            try:
                self._process_task(task_id)
            except Exception as e:
                error_msg = f"{e}\n{traceback.format_exc()}"
                logger.error(f"[AlertReportTaskWorker] 任务 {task_id} 处理异常: {error_msg}")
                try:
                    update_alert_report_task(task_id, status="failed", error_message=error_msg)
                except Exception:
                    pass

    # ==================== 任务编排 ====================

    def _process_task(self, task_id: str):
        """处理单个任务：PDF解析 -> 结构化提取 -> 研判审计"""
        task = get_alert_report_task_by_id(task_id)
        if not task:
            raise Exception(f"任务 {task_id} 在数据库中不存在")

        file_name = task["file_name"]
        content_hash = task["content_hash"]
        new_filename = gen_new_filename_by_hash(file_name, content_hash)
        file_path = os.path.join(Settings.basic_settings.WARNING_REPORT_DIR, new_filename)
        if not os.path.exists(file_path):
            raise Exception(f"文件不存在: {file_path}")

        # 阶段一：PDF解析 + 结构化提取
        report_data, text_blocks = self._run_pdf_parse(task_id, file_name, content_hash, file_path)

        # 阶段二：研判审计
        self._run_audit(task_id, file_name, report_data, text_blocks)

    # ==================== PDF 解析 ====================

    def _run_pdf_parse(self, task_id: str, file_name:str, content_hash:str, file_path: str):
        """执行 PDF 解析 + 结构化信息提取"""
        logger.info(f"[Task {task_id}] 阶段一：PDF解析开始")
        update_alert_report_task(task_id, status="pdf_processing", pdf_status="processing")

        t0 = datetime.now()
        try:
            # 解析 PDF 获取文本块
            pdf_result = parse_text_pdf(file_path)
            text_blocks = pdf_result.text_blocks

            # 提取结构化信息
            report_response = get_warning_report_json_by_filepath(file_path, file_name, content_hash)
            if report_response.code != 200:
                raise Exception(f"PDF解析失败: {report_response.msg}")

            report_data = report_response.data

            t1 = datetime.now()
            logger.info(f"[Task {task_id}] PDF解析完成，耗时: {(t1 - t0).total_seconds():.1f}s")
            update_alert_report_task(
                task_id, status="pdf_done", pdf_status="done",
                pdf_start_time=t0, pdf_end_time=t1,
            )
            return report_data, text_blocks

        except Exception as e:
            t1 = datetime.now()
            error_msg = f"PDF解析阶段失败: {e}"
            update_alert_report_task(
                task_id, status="failed", pdf_status="failed",
                error_message=error_msg,
                pdf_start_time=t0, pdf_end_time=t1,
            )
            raise

    # ==================== 研判审计 ====================

    def _run_audit(self, task_id: str, file_name: str, report_data: dict, text_blocks):
        """执行研判审计：风险判定 -> 规则获取 -> RAG检索 -> LLM研判"""
        logger.info(f"[Task {task_id}] 阶段二：研判审计开始")
        update_alert_report_task(task_id, status="audit_processing", audit_status="processing")

        t0 = datetime.now()
        try:
            # 判断是否高危告警
            alert_content = report_data.get("告警内容", "")
            is_high_risk = is_high_risk_alert(alert_content)
            risk_level = "高危告警" if is_high_risk else "普通告警"
            logger.info(f"[Task {task_id}] 告警类型判定：{risk_level}")

            # 获取规则库
            rules_desc = get_rules_desc(limit=5)
            logger.info(f"[Task {task_id}] 获取规则库完成")

            # 获取历史数据信息
            rag_retrieve_info = construct_rag_prompt(
                alarm_desc=report_data.get("告警内容", ""),
                top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
            )
            logger.info(f"[Task {task_id}] 获取历史数据完成")

            # 组装提示词并进行 LLM 研判
            report_info = json.dumps(report_data, ensure_ascii=False, indent=2)
            # llm 判断的分析原始，不包含匹配text和坐标
            origin_analyze_dic = judge_report_by_llm(
                is_high_risk=is_high_risk,
                rules_info=rules_desc,
                retrieved_info=rag_retrieve_info,
                report_info=report_info,
            )
            analyze_dic = find_field_positions(origin_analyze_dic, text_blocks)

            # 写入数据库
            result_json_str = json.dumps(analyze_dic, ensure_ascii=False)
            t1 = datetime.now()
            logger.info(f"[Task {task_id}] 研判审计完成，耗时: {(t1 - t0).total_seconds():.1f}s")
            update_alert_report_task(
                task_id, status="completed", audit_status="done",
                result_json=result_json_str,
                audit_start_time=t0, audit_end_time=t1,
            )

        except Exception as e:
            t1 = datetime.now()
            error_msg = f"研判审计阶段失败: {e}"
            # 写入失败的初始结果
            fail_result = init_analyze_result_json_data()
            fail_result["audit_result"] = "需人工复核"
            fail_result["conclusion"] = f"研判{file_name}失败"
            result_json_str = json.dumps(fail_result, ensure_ascii=False)
            update_alert_report_task(
                task_id, status="failed", audit_status="failed",
                error_message=error_msg,
                result_json=result_json_str,
                audit_start_time=t0, audit_end_time=t1,
            )
            raise


# ==================== 全局实例 ====================

alert_report_task_worker = AlertReportTaskWorker()


def start_alert_report_task_workers():
    alert_report_task_worker.start()


def stop_alert_report_task_workers():
    alert_report_task_worker.stop()
