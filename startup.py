import uvicorn
from utils import build_logger
import click
from settings import Settings
from server.api_server.server_app import create_app
from server.utils import set_httpx_config
logger = build_logger()


def run_api_server():
    from utils import (
        get_config_dict,
        get_log_file,
        get_timestamp_ms,
    )



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
    uvicorn.run(app, host=host, port=port)


@click.command(help="启动服务")
def main():
    run_api_server()


if __name__ == "__main__":
    main()
