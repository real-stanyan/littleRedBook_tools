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

# ================= 🛠️ 核心修复功能 =================
def connect_device_robust(serial):
    """
    智能连接设备：如果发现服务挂死，自动执行修复
    无需手动运行 python -m uiautomator2 init
    """
    print(f"🔌 正在连接设备 {serial}...")
    d = u2.connect(serial)
    
    try:
        # 尝试一个轻量级操作来检测服务是否存活
        # 获取屏幕大小是一个很好的测试，如果服务挂了这里会报错
        print("🩺 正在进行服务健康检查...")
        _ = d.window_size()
        print("✅ 设备服务运行正常")
    except Exception as e:
        print(f"⚠️ 检测到服务异常 ({e})")
        print("🔧 正在自动修复 uiautomator 服务 (耗时约 10-15秒)...")
        try:
            # 这一步相当于在代码里执行了 init，会清理缓存并重启服务
            d.reset_uiautomator()
            print("✅ 修复完成，服务已重启")
        except Exception as fatal_e:
            print(f"❌ 修复失败，请检查 USB 连接: {fatal_e}")
            raise fatal_e
            
    return d
# ===================================================

def start_app_and_search(d, keyword, logger):
    logger.write_line("🚀 启动小红书...")
    # 使用 package name 启动更稳
    d.app_start("com.xingin.xhs", stop=True) 
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
    try:
        d.screenshot(img_path)
    except Exception as e:
        logger.write_line(f"❌ 截图失败: {e}")
        return

    decision = agent.see_and_decide(img_path)
    if decision is None: decision = {} 

    should_like = decision.get('should_like', False)
    should_comment = decision.get('should_comment', False)
    image_desc = decision.get('image_desc', '')
    final_comment = ""

    # 1. 点赞
    if should_like:
        try:
            d.double_click(0.5, 0.5)
            time.sleep(0.5)
        except: pass

    # 2. 评论 (动态坐标修复版)
    if should_comment:
        final_comment = agent.write_comment(image_desc)
        
        if final_comment:
            logger.write_line(f"💬 准备发送: {final_comment}")
            
            # 点击底部唤起评论框
            d.click(0.5, 0.96) 
            time.sleep(1.0)
            
            try:
                # -----------------------------------------------
                # 步骤 A: 注入中文 (必须用 set_input_ime)
                # -----------------------------------------------
                d.set_input_ime(True) 
                time.sleep(1.0)
                
                d.send_keys(final_comment)
                time.sleep(0.5)
                
                # 激活按钮状态
                d.send_keys(" ")
                d.press("del")
                time.sleep(0.5)

                # -----------------------------------------------
                # 步骤 B: 智能查找“发送”按钮 (核心修复)
                # -----------------------------------------------
                # 既然找不到 text="发送"，我们就找输入框右边那个位置
                
                # 1. 获取当前屏幕上的输入框元素
                edit_text = d(className="android.widget.EditText")
                
                if edit_text.exists:
                    # 获取输入框的坐标边界: (left, top, right, bottom)
                    bounds = edit_text.info['bounds'] 
                    # 计算输入框右侧的中心位置
                    # 发送按钮通常在输入框右边，高度居中
                    send_x = bounds['right'] + 50 # 往右偏移 50 像素
                    send_y = (bounds['top'] + bounds['bottom']) / 2
                    
                    # 考虑到屏幕边缘，如果超出了屏幕宽度，就点屏幕最右侧减一点
                    screen_width = d.window_size()[0]
                    if send_x >= screen_width:
                        send_x = screen_width - 30

                    logger.write_line(f"📍 锁定输入框，尝试点击右侧坐标: ({send_x}, {send_y})")
                    d.click(send_x, send_y)
                else:
                    # 如果连输入框都找不到，执行纯盲点兜底
                    logger.write_line("⚠️ 未找到输入框结构，使用绝对坐标盲点")
                    # 针对 FastInputIME 隐藏键盘后的底部栏位置
                    d.click(0.92, 0.965) 

                # -----------------------------------------------
                # 步骤 C: 补刀 (回车键)
                # -----------------------------------------------
                time.sleep(0.5)
                d.press("enter")

            except Exception as e:
                logger.write_line(f"❌ 评论流程异常: {e}")
            
            time.sleep(2) 

            # -----------------------------------------------
            # 步骤 D: 恢复输入法并复位
            # -----------------------------------------------
            d.set_input_ime(False)
            time.sleep(0.5)
            
            # 点击上方空白处退出评论区
            d.click(0.5, 0.3) 
            time.sleep(1.0)

    logger.log_post_result(index, decision, final_comment)
def run():
    # 1. 获取输入
    raw_input = input("请输入想看的内容 (回车默认Blender): ") or "Blender"
    try:
        target_count = int(input("请输入要刷的帖子数量: "))
    except:
        target_count = 5

    # 2. 使用增强版连接函数
    try:
        d = connect_device_robust(SERIAL)
    except Exception as e:
        print(f"❌ 最终连接失败，程序退出: {e}")
        return

    # 3. 初始化 AI
    agent = DualAIAgent()
    # final_keyword = agent.optimize_keyword(raw_input)
    final_keyword = raw_input
    logger = LogManager(final_keyword)

    # 4. 启动并搜索
    try:
        start_app_and_search(d, final_keyword, logger)

        # 5. 循环刷帖
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
                
    except Exception as e:
        logger.write_line(f"❌ 运行中途发生错误: {e}")
        # 如果中途报错，尝试最后一次复活，方便下次运行
        # d.reset_uiautomator() 

if __name__ == "__main__":
    run()