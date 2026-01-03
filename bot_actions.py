# bot_actions.py
import time
import re
import config

def start_app_and_search(d, keyword, logger):
    logger.write_line("🚀 启动小红书...")
    d.app_start(config.APP_PACKAGE, stop=True) 
    time.sleep(5)

    logger.write_line(f"🔍 执行搜索: {keyword}")
    d.click(0.92, 0.06) 
    time.sleep(2)
    d.click(0.5, 0.06)
    time.sleep(1)
    
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
    logger.write_line("开始设置帖子范围...")
    # (根据你的具体UI逻辑保留这些点击)
    d.click(120, 297)
    time.sleep(1)
    d.click(425, 1518)
    time.sleep(1)
    d.click(59, 287)
    time.sleep(1) 
    logger.write_line("✅ 搜索完成")

def process_single_post(d, agent, index, logger):
    logger.write_line(f"正在处理第 {index} 个帖子...")
    
    img_path = "temp_post.jpg"
    try:
        d.screenshot(img_path)
    except Exception as e:
        logger.write_line(f"❌ 截图失败: {e}")
        d.press("back") 
        return

    decision = agent.see_and_decide(img_path)
    if decision is None: decision = {} 

    should_like = decision.get('should_like', False)
    should_comment = decision.get('should_comment', False)
    image_desc = decision.get('image_desc', '')
    image_kw = decision.get('image_kw', '')
    
    final_comment = ""
    # 新增：初始化匹配信息变量
    matched_infos = [] 
    has_opened_comment_box = False

    if should_like:
        try:
            logger.write_line("❤️ 执行点赞...")
            d.double_click(0.5, 0.5)
            time.sleep(0.5)
        except: pass

    if should_comment:
        try:
                result = agent.write_comment(image_desc, image_kw)
                
                # 安全检查：确保返回的是元组且长度为2
                if isinstance(result, (tuple, list)) and len(result) == 2:
                    final_comment, matched_infos = result
                else:
                    # 如果格式不对（比如只返回了字符串），做兼容处理
                    logger.write_line(f"⚠️ 警告：write_comment 返回格式异常: {type(result)}")
                    final_comment = str(result)
                    matched_infos = []
                    
        except Exception as e:
                logger.write_line(f"❌ 调用 write_comment 发生未知错误: {e}")
                final_comment = "赞！👍"
                matched_infos = []
        if final_comment:
            logger.write_line(f"💬 准备发送: {final_comment}")
            try:
                has_opened_comment_box = True
                logger.write_line("👆 点击右下角唤醒...")
                d.click(964, 2259)
                time.sleep(1.0)
                d.click(964, 2259)
                time.sleep(1.0)

                d.set_input_ime(True)
                d.send_keys(final_comment)
                time.sleep(0.5)
                
                # 物理激活按钮
                d.shell("input keyevent 62")
                time.sleep(0.1)
                d.shell("input keyevent 67")
                time.sleep(0.5)

                logger.write_line("👉 点击发送")
                d.click(964, 2259)
                time.sleep(0.5)
                d.press("enter")
                time.sleep(2)

            except Exception as e:
                logger.write_line(f"❌ 评论过程出错: {e}")

    logger.write_line("🧹 收尾退出...")
    if has_opened_comment_box:
        d.set_input_ime(False)
        d.click(0.5, 0.2)
        time.sleep(0.5)
        d.press("back")
        time.sleep(1.0)
    
    d.press("back")
    time.sleep(2.0)

    logger.log_post_result(index, decision, final_comment, matched_infos)