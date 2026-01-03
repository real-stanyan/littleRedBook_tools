# main.py
import time
import config
from logger import LogManager
from device_manager import connect_device_robust
from ai_engine import DualAIAgent
from bot_actions import start_app_and_search, process_single_post

def run():
    # 1. 获取输入
    raw_input = input("请输入想看的内容 (回车默认鱼油): ") or "鱼油"
    try:
        target_count = int(input("请输入要刷的帖子数量: "))
    except:
        target_count = 5

    # 2. 连接设备
    try:
        d = connect_device_robust(config.SERIAL)
        w, h = d.window_size()
        print(f"📱 设备分辨率: {w}x{h}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 3. 初始化 AI & 日志
    agent = DualAIAgent()
    logger = LogManager(raw_input)

    # 4. 启动并搜索
    try:
        start_app_and_search(d, raw_input, logger)

        processed = 0
        while processed < target_count:
            processed += 1
            logger.write_line(f"\n🔄 [流程进度 {processed}/{target_count}] 正在列表页选贴...")

            # --- A. 列表页：截图并选择 ---
            feed_img = "temp_feed.jpg"
            d.screenshot(feed_img)
            
            choice_idx = agent.choose_feed_post(feed_img)
            logger.write_line(f"🎯 AI 选择了位置: {choice_idx}")

            # --- B. 计算坐标并点击 (基于屏幕比例) ---
            if choice_idx == 1:
                click_x, click_y = w * 0.25, h * 0.40
            elif choice_idx == 2:
                click_x, click_y = w * 0.75, h * 0.40
            elif choice_idx == 3:
                click_x, click_y = w * 0.25, h * 0.75
            else: 
                click_x, click_y = w * 0.75, h * 0.75
            
            d.click(click_x, click_y)
            time.sleep(3) 

            # --- C. 详情页处理 ---
            process_single_post(d, agent, processed, logger)

            # --- D. 下滑 ---
            if processed < target_count:
                logger.write_line("📉 下滑查看更多帖子...")
                d.swipe(w * 0.5, h * 0.8, w * 0.5, h * 0.2, duration=0.1)
                time.sleep(4) 
            else:
                logger.write_line("🛑 任务全部完成！")
                
    except Exception as e:
        logger.write_line(f"❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()