# 和前端交互的非大模型方法
from fastapi import Body
import random

from server.utils import BaseResponse, ListResponse
from utils import build_logger
from server.db.repository import conversation_repository, message_repository

logger = build_logger()

# ============ 全局状态 ============

# 问题池
_QUESTION_POOL = [
    "如何配置网络安全策略？",
    "请介绍一下等保测评的流程",
    "系统出现警告如何处理？",
    "如何生成安全评估报告？",
    "什么是SQL注入攻击，如何防范？",
    "请解释一下XSS攻击原理",
    "如何查看系统运行日志？",
    "网络故障排查的基本步骤是什么？",
    "如何进行漏洞扫描？",
    "系统安全加固的建议有哪些？",
    "如何配置防火墙规则？",
    "什么是CSRF攻击，如何防护？",
    "如何备份和恢复数据库？",
    "服务器被入侵了怎么处理？",
    "如何监控服务器性能指标？",
    "什么是中间人攻击？",
    "如何配置HTTPS证书？",
    "密码策略应该如何设置？",
    "如何进行代码安全审计？",
    "常见的Web漏洞有哪些？"
]

# 上一次返回的问题索引集合
_last_question_indices = set()


def get_possible_questions(
        limit: int = Body(4, description="获取问题列表")
) -> ListResponse:
    """
    获取可能的提问列表
    每次返回4个问题，和上一次不一样
    """
    global _last_question_indices

    # 如果问题池小于4个，直接返回全部
    if len(_QUESTION_POOL) <= limit:
        return ListResponse(data=_QUESTION_POOL)

    # 获取可选的索引（排除上一次的）
    available_indices = list(set(range(len(_QUESTION_POOL))) - _last_question_indices)

    # 如果可选的不够4个，重置限制
    if len(available_indices) < limit:
        available_indices = list(range(len(_QUESTION_POOL)))

    # 随机选择4个不重复的索引
    selected_indices = random.sample(available_indices, limit)

    # 记录本次选择的索引
    _last_question_indices = set(selected_indices)

    # 根据索引获取问题
    questions = [_QUESTION_POOL[i] for i in selected_indices]

    return ListResponse(data=questions)


def get_user_conversations(
        user_id: str = Body("user", description="用户ID"),
        limit: int = Body(5, description="返回数量限制"),
        offset: int = Body(0, description="偏移量")
) -> ListResponse:
    """
    获取用户最近的对话列表
    """
    try:
        sessions = conversation_repository.get_conversations_by_user(user_id, limit=limit, offset=offset)
        data = []
        for s in sessions:
            data.append({
                "conversation_id": s["id"],
                "conversation_name": s["conversation_name"],
                "is_favorite": s["is_favorite"],
                "create_time": s["create_time"],
            })

        return ListResponse(data=data)
    except Exception as e:
        logger.error(f"获取用户对话列表失败: {e}")
        return ListResponse(code=500, msg=f"获取用户对话列表失败: {str(e)}")


def get_conversation_messages(
        conversation_id: str = Body("test", description="对话框ID"),
        offset: int = Body(0, description="偏移量"),
        limit: int = Body(100, description="返回数量限制")
) -> ListResponse:
    """
    获取某个会话的所有对话内容
    """
    try:
        # 检查会话是否存在
        if not conversation_repository.conversation_exists(conversation_id):
            return ListResponse(code=201, msg=f"会话不存在")

        messages = message_repository.filter_message(conversation_id, limit=limit, offset=offset, asc=False)

        return ListResponse(data=messages)
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        return ListResponse(code=500, msg=f"获取会话消息失败: {str(e)}")


def delete_conversation(conversation_id: str = Body("test", description="会话ID")) -> BaseResponse:
    """
    删除会话
    """
    try:
        success = conversation_repository.delete_conversation(conversation_id)
        if not success:
            return BaseResponse(code=404, msg="会话不存在")
        else:
            return BaseResponse(code=200, msg="删除成功")
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        return BaseResponse(code=500, msg=f"删除会话失败: {str(e)}")


def save_conversation(conversation_id: str = Body("test1", description="会话ID"),
                      user_id: str = Body("user1", description="用户ID")) -> BaseResponse:
    """
    保存本次会话信息
    """
    try:
        # 获取会话的消息
        messages = message_repository.filter_message(conversation_id, limit=1, offset=0, asc=True)

        # 根据第一条用户消息生成名称，或生成默认名称
        conversation_name = "新会话"
        if messages:
            first_query = messages[0].get("query", "").strip()
            if first_query:
                # 取前12个字符作为名称
                conversation_name = first_query[:12] + "..." if len(first_query) > 12 else first_query

        # 更新会话
        if conversation_repository.conversation_exists(conversation_id=conversation_id):
            success = conversation_repository.update_conversation_name(conversation_id=conversation_id, conversation_name=conversation_name)
            if not success:
                return BaseResponse(code=500, msg=f"更新会话: {str(conversation_id)} 失败")
            else:
                return BaseResponse(code=200, msg=f"更新会话: {str(conversation_id)} 成功")
        else: # 创建会话
            conversation_repository.create_conversation(conversation_id=conversation_id, user_id=user_id, conversation_name=conversation_name)
            return BaseResponse(code=200, msg=f"创建会话: {str(conversation_id)} 成功")

    except Exception as e:
        logger.error(f"生成会话名称失败: {e}")
        return BaseResponse(code=500, msg=f"更新会话: {str(conversation_id)} 失败")


def toggle_conversation_favorite(conversation_id: str = Body("test", description="会话ID"),
                                 is_favorite: int = Body(1, description="1表示收藏，0表示取消收藏")) -> BaseResponse:
    """
    给会话增加或取消收藏标记
    """
    try:
        if is_favorite not in [0, 1]:
            return BaseResponse(code=400, msg="is_favorite 只能是 0 或 1")

        success = conversation_repository.toggle_conversation_favorite(
            conversation_id,
            is_favorite
        )
        if not success:
            return BaseResponse(code=400, msg="is_favorite 只能是 0 或 1")

        return BaseResponse(code=200, msg="success", data={
            "conversation_id": conversation_id,
            "is_favorite": is_favorite
        })

    except Exception as e:
        logger.error(f"更新收藏状态失败: {e}")
        return BaseResponse(code=400, msg=f"更新收藏状态失败: {str(e)}")
