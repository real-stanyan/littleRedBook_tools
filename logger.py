# logger.py
import os
import re
from datetime import datetime

class LogManager:
    """日志管理器：记录运行全过程"""
    def __init__(self, keyword):
        if not os.path.exists("log"):
            os.makedirs("log")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = re.sub(r'[\\/*?:"<>|]', "", keyword)
        self.filepath = f"log/{timestamp}_{safe_keyword}.txt"
        
        print(f"📁 日志已创建: {self.filepath}")
        self.write_line(f"=== 任务启动: {timestamp} ===")
        self.write_line(f"=== 搜索关键词: {keyword} ===\n")

    def write_line(self, content):
        time_str = datetime.now().strftime("%H:%M:%S")
        formatted_line = f"[{time_str}] {content}"
        
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(formatted_line + "\n")
        print(formatted_line)

    def log_post_result(self, index, decision, comment, matched_infos=None):
        desc = decision.get('image_desc', '分析失败') if decision else '分析失败'
        like = decision.get('should_like', False) if decision else False
        comm = decision.get('should_comment', False) if decision else False
        kw = decision.get('image_kw', '') if decision else ''

        # 处理匹配到的产品信息，将其格式化为字符串
        rag_log_str = "无关联产品"
        if matched_infos and isinstance(matched_infos, list) and len(matched_infos) > 0:
            # 将列表转换为带序号的字符串，例如: "1. 灵芝孢子粉... | 2. 澳洲TGA认证..."
            rag_items = [f"{i+1}. {info[:30]}..." for i, info in enumerate(matched_infos)] # 只截取前30个字避免日志太长
            rag_log_str = " | ".join(rag_items)

        log_text = (
            f"\n----------------------------------------\n"
            f"🎬 [第 {index} 个帖子]\n"
            f"👀 视觉描述: {desc}\n"
            f"🏷️ 关键词: {kw}\n"
            f"🧠 RAG匹配: {rag_log_str}\n"  # 新增这一行
            f"📊 决策结果: 点赞={like} | 评论={comm}\n"
            f"💬 发送评论: {comment if comment else '无'}\n"
            f"----------------------------------------\n"
        )
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(log_text)
        print(log_text)