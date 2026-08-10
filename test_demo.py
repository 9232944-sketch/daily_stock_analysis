from core.volc_ark_client import ark_client
from config.track_prompt import SYS_PROMPT_QUANT_RESEARCH, TEST_USER_QUERY
from utils.file_helper import save_markdown_report
from utils.logger import logger

def main():
    logger.info("===== 启动火山方舟连通性测试 =====")
    try:
        result = ark_client.chat_completion(
            sys_prompt=SYS_PROMPT_QUANT_RESEARCH,
            user_prompt=TEST_USER_QUERY
        )
        print("\n========模型返回结果========\n")
        print(result)

        # 自动保存md报告
        saved_path = save_markdown_report(result, title="test_demo_output")
        logger.info(f"报告已归档：{saved_path}")
    except Exception as e:
        logger.error(f"测试程序异常：{str(e)}")

if __name__ == "__main__":
    main()