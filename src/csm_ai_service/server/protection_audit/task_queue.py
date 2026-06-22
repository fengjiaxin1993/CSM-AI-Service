"""
任务队列系统
用于异步处理合同文件：OCR识别 -> 审计

纯内存队列模式：
- 接收请求 → 先写入 DB（持久化） → 再 push 到内存队列
- 单线程从内存队列阻塞消费，执行过程中持续更新 DB 状态
"""
import os
import queue
import threading
import traceback
from datetime import datetime

from csm_ai_service.server.db.repository.audit_result_repository import batch_add_audit_results, update_audit_result, \
    get_audit_result_by_result_id
from csm_ai_service.server.db.repository.task_repository import (
    get_task_by_id,
    update_task
)
from csm_ai_service.server.db.repository import get_contract_by_id, update_contract
from csm_ai_service.server.db.repository import list_audit_rules
from csm_ai_service.server.protection_audit.tools.file_tools import save_ocr_result, load_cached_ocr_result, ensure_cache_dir
from csm_ai_service.server.protection_audit.audit.audit_graph import AuditRule, GLOBAL_AUDIT_GRAPH
from csm_ai_service.settings import Settings
from csm_ai_service.server.utils import build_logger
from csm_ai_service.server.db.repository import init_default_rules
from csm_ai_service.server.protection_audit.pdf_extract_service import process_file_ocr_by_path

logger = build_logger()

class TaskWorker:
    """任务工作类：单线程从内存队列消费任务，执行 OCR + 审计两个阶段"""

    def __init__(self):
        self.task_queue = queue.Queue()
        self._worker_thread = None
        self._running = False

    # ==================== 对外接口 ====================

    def submit_task(self, task_id: int):
        """提交任务到内存队列"""
        self.task_queue.put(task_id)
        logger.info(f"[TaskWorker] 任务 {task_id} 已加入内存队列")

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
            name="TaskWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("[TaskWorker] 工作线程已启动")

    def stop(self):
        """停止工作线程（等待当前任务完成后退出）"""
        if not self._running:
            return
        self._running = False
        # 向队列放入一个哨兵值，唤醒阻塞在 get() 上的线程
        self.task_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            # 缩短等待时间到 3 秒，避免长时间阻塞关闭流程
            # worker 线程是 daemon=True，主线程退出后会被强制终止
            self._worker_thread.join(timeout=3)
        logger.info("[TaskWorker] 工作线程已停止")

    # ==================== 工作循环 ====================

    def _worker_loop(self):
        while self._running:
            try:
                task_id = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # 哨兵值，退出循环
            if task_id is None:
                break

            logger.info(f"[TaskWorker] 获取到待处理任务 {task_id}")
            try:
                self._process_task(task_id)
            except Exception as e:
                error_msg = f"{e}\n{traceback.format_exc()}"
                logger.error(f"[TaskWorker] 任务 {task_id} 处理异常: {error_msg}")
                try:
                    update_task(task_id, status="failed", error_message=error_msg)
                except Exception:
                    pass

    # ==================== 任务编排 ====================

    def _process_task(self, task_id: int):
        """处理单个任务：加载信息 -> OCR -> 审计"""
        task = get_task_by_id(task_id)
        if not task:
            raise Exception(f"任务 {task_id} 在数据库中不存在")

        contract = get_contract_by_id(task["contract_id"])
        if not contract:
            raise Exception(f"合同 {task['contract_id']} 在数据库中不存在")

        file_path = os.path.join(Settings.basic_settings.UPLOADS_DIR, contract["file_name"])
        if not os.path.exists(file_path):
            raise Exception(f"合同文件不存在: {file_path}")

        contract_id = task["contract_id"]
        ensure_cache_dir(contract_id)

        ocr_result = self._run_ocr(task_id, contract_id, file_path)
        self._run_audit(task_id, contract_id, ocr_result)

    # ==================== OCR 识别 ====================

    def _run_ocr(self, task_id: int, contract_id: int, file_path: str) -> dict:
        """执行 OCR：优先缓存，缓存未命中则调用 OCR 服务并缓存结果"""
        logger.info(f"[Task {task_id}] 阶段一：OCR识别开始")
        update_task(task_id, status="processing", ocr_status="processing")
        update_contract(contract_id, status="processing")

        t0 = datetime.now()
        try:
            result = load_cached_ocr_result(contract_id)
            if result:
                logger.info(f"[Task {task_id}] 使用已有文件缓存")
            else:
                result = process_file_ocr_by_path(file_path)
                if not result or result.get("error"):
                    raise Exception(f"OCR识别失败: {result.get('error', '未知错误')}")
                save_ocr_result(
                    contract_id,
                    result.get("locate_json_result", {}),
                    result.get("markdown_text", ""),
                    result.get("structure_json_result", {}),
                )
                logger.info(f"[Task {task_id}] OCR结果已保存到文件缓存")

            t1 = datetime.now()
            logger.info(f"[Task {task_id}] OCR完成，耗时: {(t1 - t0).total_seconds():.1f}s")
            update_task(task_id, ocr_status="done", ocr_start_time=t0, ocr_end_time=t1)
            update_contract(contract_id, status="done")
            return result

        except Exception as e:
            t1 = datetime.now()
            update_task(
                task_id, status="failed", ocr_status="failed",
                error_message=f"OCR阶段失败: {e}",
                ocr_start_time=t0, ocr_end_time=t1,
            )
            update_contract(contract_id, status="failed")
            raise

    # ==================== 审计 ====================

    def _run_audit(self, task_id: int, contract_id: int, ocr_result: dict):
        """执行审计：加载规则 -> LangGraph 审计 -> 保存结果"""
        logger.info(f"[Task {task_id}] 阶段二：审计开始")
        update_task(task_id, audit_status="processing")

        t0 = datetime.now()
        try:
            rules = list_audit_rules()
            if not rules:
                init_default_rules()
                rules = list_audit_rules()
                logger.info(f"创建默认审计规则")
            logger.info(f"[Task {task_id}] 使用 {len(rules)} 条审计规则")

            result_ids = batch_add_audit_results(task_id, contract_id, rules)


            # 不用走审计流程了，因为ocr没识别出来
            if len(ocr_result.get("markdown_text", "")) <= Settings.basic_settings.OCR_MIN_TEXT_LENGTH:
                for rid in result_ids:
                    update_audit_result(
                        rid,
                        conclusion="无法识别上传的合同文件，无法进行审计",
                        reasoning="由于客观因素，暂不支持识别扫描件",
                    )
            else:
                audit_rules = [
                    AuditRule(id=r["id"], name=r["name"],
                              description=r.get("description", ""),
                              chapter_keywords=r.get("chapter_keywords", []),
                              judge_logic=r.get("judge_logic", ""))
                    for r in rules
                ]
                graph = GLOBAL_AUDIT_GRAPH
                res = graph.invoke({
                    "contract_id": contract_id,
                    "contract_markdown_json": ocr_result.get("structure_json_result", {}),
                    "rule_list": audit_rules,
                    "single_rule_results": [],
                    "final_report": "",
                })
                single_results = res.get("single_rule_results", [])
                for i, rid in enumerate(result_ids):
                    if i >= len(single_results):
                        break
                    r = single_results[i]
                    update_audit_result(
                        rid,
                        rule_name=r.rule_name,
                        rule_description=getattr(r, 'rule_description', ""),
                        rule_judge_logic=getattr(r, 'rule_judge_logic', ""),
                        is_compliant=r.is_compliant,
                        conclusion=getattr(r, 'conclusion', ""),
                        reasoning=getattr(r, 'reasoning', ""),
                        origin_text=getattr(r, 'origin_text', ""),
                        related_chapters=getattr(r, 'related_chapters', []),
                        related_text=getattr(r, 'related_text', ""),
                        related_doc_ids=getattr(r, 'related_doc_ids', []),
                    )

            t1 = datetime.now()
            update_task(
                task_id, status="completed", audit_status="done", audit_start_time=t0, audit_end_time=t1
            )
            logger.info(f"[Task {task_id}] 审计完成，耗时: {(t1 - t0).total_seconds():.1f}s")

        except Exception as e:
            t1 = datetime.now()
            update_task(
                task_id, status="failed", audit_status="failed",
                error_message=f"审计阶段失败: {e}",
                audit_start_time=t0, audit_end_time=t1,
            )
            raise


# ==================== 全局实例 ====================

task_worker = TaskWorker()


def start_task_workers():
    task_worker.start()


def stop_task_workers():
    task_worker.stop()
