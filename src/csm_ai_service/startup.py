# startup.py - API 服务启动模块
# 注意：所有重型依赖（server_app, task_queue 等）都在函数内部延迟导入，
# 避免在模块导入阶段就触发 create_engine、LLM 实例化、LangGraph 编译等操作。
import logging
from csm_ai_service.utils import build_logger

logger = build_logger()


def run_api_server():
    """启动 API 服务 — 所有重型依赖在函数内部延迟导入"""
    import uvicorn
    from csm_ai_service.utils import (
        get_config_dict,
        get_log_file,
        get_timestamp_ms,
    )
    from csm_ai_service.settings import Settings
    from csm_ai_service.server.api_server.server_app import create_app
    from csm_ai_service.server.utils import set_httpx_config

    logger.info(f"Api MODEL_PLATFORMS: {Settings.model_settings.MODEL_PLATFORMS}")
    set_httpx_config()
    app = create_app()

    host = Settings.basic_settings.API_SERVER["host"]
    port = Settings.basic_settings.API_SERVER["port"]

    logging_conf = get_config_dict(
        "INFO",
        get_log_file(log_path=Settings.basic_settings.LOG_PATH, sub_dir=f"run_api_server_{get_timestamp_ms()}"),
        1024 * 1024 * 1024 * 3,
        1024 * 1024 * 1024 * 3,
    )
    logging.config.dictConfig(logging_conf)  # type: ignore
    uvicorn.run(app, host=host, port=port, log_level="info")




if __name__ == "__main__":
    run_api_server()
