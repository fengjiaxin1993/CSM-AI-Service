import argparse
import atexit
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from csm_ai_service.server.protection_audit.common.task_queue import stop_task_workers, start_task_workers
from csm_ai_service.server.protection_audit.ocr.ocr_service import startup_event
from csm_ai_service.server.api_server.audit_result_routes import audit_result_router
from csm_ai_service.server.api_server.audit_rule_routes import audit_rule_router
from csm_ai_service.server.api_server.contract_routes import contract_router
from csm_ai_service.server.api_server.ocr_routes import ocr_router
from csm_ai_service.server.api_server.task_routes import task_router
from starlette.responses import RedirectResponse, FileResponse

from csm_ai_service.server.api_server.platform_warning_routes import platform_warning_router
from csm_ai_service.server.api_server.tickets_routes import ticket_router
from csm_ai_service.server.api_server.warning_routes import warning_router
from csm_ai_service.settings import Settings
from csm_ai_service.server.api_server.chat_routes import chat_router
from csm_ai_service.server.api_server.kb_routes import kb_router
from csm_ai_service.server.utils import MakeFastAPIOffline
from csm_ai_service.server.api_server.pdf_extract_routes import pdf_extract_router
from csm_ai_service.server.api_server.chat_manager_routes import chat_manager_router
from csm_ai_service.utils import build_logger
from csm_ai_service.server.protection_audit.ocr.single_ocr_engine import _rapid_doc_engine
logger = build_logger()


def _force_cleanup():
    """注册 atexit 钩子，确保退出时释放资源，避免卡住"""
    try:
        stop_task_workers()
    except Exception:
        pass
    # 尝试释放 RapidDoc 全局引擎实例
    try:
        if _rapid_doc_engine is not None:
            del _rapid_doc_engine
    except Exception:
        pass


# 注册退出钩子，确保 Ctrl+C 时不会被 ONNX Runtime 线程阻塞
atexit.register(_force_cleanup)

def create_app():
    app = FastAPI(title="Langchain-Chatchat API Server")
    if Settings.basic_settings.DEBUG:
        MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # 在config.py中设置OPEN_DOMAIN=True，允许跨域
    # set OPEN_DOMAIN=True in config.py to allow cross-domain
    if Settings.basic_settings.OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/", summary="首页", include_in_schema=False)
    async def document():
        return RedirectResponse(url="/index")

    @app.on_event("shutdown")
    def shutdown():
        """服务关闭时停止 TaskWorker 线程"""
        logger.info("服务正在关闭...")
        stop_task_workers()
        logger.info("服务关闭完成")

    @app.on_event("startup")
    def on_startup():
        """服务启动时执行初始化"""
        start_task_workers()
        startup_event()

    @app.get("/index",summary="文档展示页面", include_in_schema=False)
    async def root():
        """根路由 - 返回前端页面"""
        frontend_path = os.path.join(Settings.basic_settings.DATA_PATH, "frontend", "index.html")
        if os.path.exists(frontend_path):
            return FileResponse(frontend_path)
        return {"message": "PDF OCR API 服务运行中", "docs": "/docs"}

    @app.get("/rules",summary="规则库管理文档", include_in_schema=False)
    async def rules_page():
        """规则管理页面"""
        rules_path = os.path.join(Settings.basic_settings.DATA_PATH, "frontend", "rules.html")
        if os.path.exists(rules_path):
            return FileResponse(rules_path)
        return {"message": "规则管理页面不存在", "docs": "/rules"}

    @app.get("/contracts",summary="合同与任务管理", include_in_schema=False)
    async def contracts_page():
        """合同与任务管理页面"""
        contracts_path = os.path.join(Settings.basic_settings.DATA_PATH, "frontend", "contracts.html")
        if os.path.exists(contracts_path):
            return FileResponse(contracts_path)
        return {"message": "合同管理页面不存在", "docs": "/contracts"}

    @app.get("/results",summary="审计结果查看", include_in_schema=False)
    async def results_page():
        """审计结果查看页面"""
        results_path = os.path.join(Settings.basic_settings.DATA_PATH, "frontend", "results.html")
        if os.path.exists(results_path):
            return FileResponse(results_path)
        return {"message": "审计结果页面不存在", "docs": "/results"}

    @app.get("/docs", summary="swagger 文档", include_in_schema=False)
    async def document():
        return RedirectResponse(url="/docs")

    @app.get("/", summary="界面首页", include_in_schema=False)
    async def document():
        return RedirectResponse(url="/index")

    app.include_router(ocr_router)
    app.include_router(audit_rule_router)
    app.include_router(audit_result_router)
    app.include_router(contract_router)
    app.include_router(task_router)

    app.include_router(chat_router)
    app.include_router(kb_router)
    app.include_router(warning_router)
    app.include_router(ticket_router)
    app.include_router(pdf_extract_router)
    app.include_router(chat_manager_router)
    app.include_router(platform_warning_router)


    return app


def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_keyfile=kwargs.get("ssl_keyfile"),
            ssl_certfile=kwargs.get("ssl_certfile"),
        )
    else:
        uvicorn.run(app, host=host, port=port)


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="langchain-ChatGLM",
        description="About langchain-ChatGLM, local knowledge based ChatGLM with langchain"
        " ｜ 基于本地知识库的 ChatGLM 问答",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    # 初始化消息
    args = parser.parse_args()
    args_dict = vars(args)

    run_api(
        host=args.host,
        port=args.port,
        ssl_keyfile=args.ssl_keyfile,
        ssl_certfile=args.ssl_certfile,
    )
