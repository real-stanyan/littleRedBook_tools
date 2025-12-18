import uiautomator2 as u2
import time
import base64
import re
import json
import os
from datetime import datetime
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

# ================= ⚙️ 配置区域 =================
# 请替换为你的设备序列号
SERIAL = "19291FDF600F9P"

# 视觉模型：负责看图 (推荐 llava:latest)
VISION_MODEL = "llava:latest"

# 文案模型：负责优化搜索词 & 写评论 (推荐 qwen3-vl:4b 或 qwen2.5-vl)
TEXT_MODEL = "qwen3-vl:4b" 
# ==============================================

class LogManager:
    """日志管理器：记录运行全过程"""
    def __init__(self, keyword):
        if not os.path.exists("log"):
            os.makedirs("log")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清洗文件名非法字符
        safe_keyword = re.sub(r'[\\/*?:"<>|]', "", keyword)
        self.filepath = f"log/{timestamp}_{safe_keyword}.txt"
        
        print(f"📁 日志已创建: {self.filepath}")
        self.write_line(f"=== 任务启动: {timestamp} ===")
        self.write_line(f"=== 搜索关键词: {keyword} ===\n")

    def write_line(self, content):
        """写文件并打印到控制台"""
        time_str = datetime.now().strftime("%H:%M:%S")
        formatted_line = f"[{time_str}] {content}"
        
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(formatted_line + "\n")
        print(formatted_line)

    def log_post_result(self, index, decision, comment):
        """记录单条处理结果"""
        # 防止 None 报错
        desc = decision.get('image_desc', '分析失败') if decision else '分析失败'
        like = decision.get('should_like', False) if decision else False
        comm = decision.get('should_comment', False) if decision else False

        log_text = (
            f"\n----------------------------------------\n"
            f"🎬 [第 {index} 个帖子]\n"
            f"👀 视觉描述: {desc}\n"
            f"📊 决策结果: 点赞={like} | 评论={comm}\n"
            f"💬 发送评论: {comment if comment else '无'}\n"
            f"----------------------------------------\n"
        )
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(log_text)
        print(log_text)

class DualAIAgent:
    def __init__(self):
        print(f"🔧 初始化双模型引擎...")
        self.vision_llm = ChatOllama(model=VISION_MODEL, temperature=0.1)
        self.writer_llm = ChatOllama(model=TEXT_MODEL, temperature=0.7)

    def extract_json(self, text):
        text = text.strip()
        try:
            return json.loads(text)
        except:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        return None

    def optimize_keyword(self, user_input):
        """让 AI 决定搜什么"""
        print(f"🧠 {TEXT_MODEL} 正在优化搜索词...")
        system_prompt = "你是一个搜索优化大师。根据用户输入，生成一个最容易搜到高质量内容的搜索关键词。只返回关键词，不要解释。"
        try:
            resp = self.writer_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"用户输入：{user_input}")
            ])
            optimized = resp.content.strip().replace('"', '').replace("'", "").replace("。", "")
            print(f"✨ AI 优化: {user_input} -> {optimized}")
            return optimized
        except:
            return user_input

    def see_and_decide(self, image_path):
        print(f"👀 {VISION_MODEL} 正在分析图片...")
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 狂热粉 Prompt
        prompt = """
        You are a passionate fan. Analyze the image.
        UNLESS it is completely black or error screen, you MUST set should_like and should_comment to TRUE.
        Return STRICT JSON:
        {
            "should_like": true,
            "should_comment": true,
            "image_desc": "visual description..."
        }
        """
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_b64}"}
        ])

        try:
            resp = self.vision_llm.invoke([msg])
            return self.extract_json(resp.content)
        except Exception as e:
            print(f"❌ 视觉分析失败: {e}")
            return None

    def write_comment(self, image_desc):
        print(f"✍️ {TEXT_MODEL} 正在构思评论...")
        system_prompt = "你是友善的小红书用户。写一条中文评论。简短(20字内)，带1个emoji，不要带引号。"
        try:
            resp = self.writer_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"图片内容：{image_desc}\n写一条评论：")
            ])
            return resp.content.strip().replace('"', '').replace("'", "")
        except:
            return "赞！🔥"

def start_app_and_search(d, keyword, logger):
    logger.write_line("🚀 启动小红书...")
    d.shell("monkey -p com.xingin.xhs -c android.intent.category.LAUNCHER 1")
    time.sleep(5)

    logger.write_line(f"🔍 执行搜索: {keyword}")
    d.click(0.92, 0.06) 
    time.sleep(2)
    d.click(0.5, 0.06)
    time.sleep(1)
    
    # 输入处理：中文用粘贴，英文用键盘
    try:
        if re.search(r'[\u4e00-\u9fa5]', keyword):
            d.set_clipboard(keyword)
            d.click(0.5, 0.06)
            time.sleep(0.5)
            d.press(279) # Paste
        else:
            d.send_keys(keyword)
    except:
        d.send_keys(keyword)

    time.sleep(1)
    d.press("enter")
    time.sleep(4)

    logger.write_line("👆 进入第一个帖子...")
    d.click(0.25, 0.5) 
    time.sleep(3)

def process_single_post(d, agent, index, logger):
    logger.write_line(f"正在处理第 {index} 个帖子...")
    
    img_path = "temp_post.jpg"
    d.screenshot(img_path)

    decision = agent.see_and_decide(img_path)
    
    # 🛡️ 防崩溃补丁
    if decision is None:
        logger.write_line("⚠️ 警告：AI 分析无结果，跳过交互。")
        decision = {} 

    should_like = decision.get('should_like', False)
    should_comment = decision.get('should_comment', False)
    image_desc = decision.get('image_desc', '')
    
    final_comment = ""

    # 1. 点赞
    if should_like:
        d.double_click(0.5, 0.5)
        time.sleep(0.5)

    # 2. 评论
    if should_comment:
        final_comment = agent.write_comment(image_desc)
        
        if final_comment:
            logger.write_line(f"💬 准备发送: {final_comment}")
            
            # 点击底部评论框
            d.click(0.5, 0.96) 
            time.sleep(1.5)
            
            try:
                # A. 粘贴文本
                d.set_clipboard(final_comment)
                time.sleep(0.2)
                d.press(279) # KeyCode_PASTE
                time.sleep(0.5)
                
                # 🔥 B. 模拟空格键 (激活发送按钮的核心！)
                d.press(62) 
                time.sleep(0.5)
                
            except:
                d.shell(f"input text 'Nice'")
            
            # C. 发送 (首选回车键)
            d.press("enter")
            time.sleep(1)
            
            # 如果回车没发出去，尝试点击发送按钮
            if d(text="发送").exists:
                d(text="发送").click()
            else:
                d.click(0.92, 0.92) # 盲点右下角
            
            logger.write_line("✅ 发送动作执行完毕")
            time.sleep(3) 

            # D. 复位界面 (收键盘 + 关面板)
            logger.write_line("👆 点击空白处复位...")
            d.click(0.5, 0.3) 
            time.sleep(1.5)
            d.click(0.5, 0.3) # 双重保险

    logger.log_post_result(index, decision, final_comment)

def run():
    # 1. 获取输入
    raw_input = input("请输入想看的内容 (回车默认Blender): ") or "Blender"
    try:
        target_count = int(input("请输入要刷的帖子数量: "))
    except:
        target_count = 5

    print(f"🔌 连接设备 {SERIAL}...")
    try:
        d = u2.connect(SERIAL)
        print("✅ 连接成功")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 2. 初始化
    agent = DualAIAgent()
    final_keyword = agent.optimize_keyword(raw_input)
    logger = LogManager(final_keyword)

    # 3. 启动并搜索
    start_app_and_search(d, final_keyword, logger)

    # 4. 循环刷帖
    processed = 0
    while processed < target_count:
        processed += 1
        
        process_single_post(d, agent, processed, logger)
        
        if processed < target_count:
            logger.write_line(f"👆 上滑切换 (进度: {processed}/{target_count})...")
            # 这里的 swipe 坐标幅度较大，确保带走评论区残留
            d.swipe(0.5, 0.85, 0.5, 0.15, duration=0.1)
            time.sleep(4)
        else:
            logger.write_line("🛑 任务全部完成！")

if __name__ == "__main__":
    run()