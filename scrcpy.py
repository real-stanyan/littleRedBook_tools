import subprocess
import re
import math

# --- 配置区域 ---
# 判定阈值：如果手指移动距离超过这个数值（Raw单位），则认为是滑动，否则是点击
# 注意：这是底层Raw坐标，不是像素。通常设为 20-50 左右比较合适。
MOVE_THRESHOLD = 50 
# ----------------

def monitor_touch_actions():
    # 启动 ADB 监听
    cmd = ["adb", "shell", "getevent", "-l"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 正则表达式
    # 匹配 Tracking ID (用于判断按下/抬起)
    pattern_id = re.compile(r"ABS_MT_TRACKING_ID\s+([0-9a-fA-F]+)")
    # 匹配 X 和 Y
    pattern_x = re.compile(r"ABS_MT_POSITION_X\s+([0-9a-fA-F]+)")
    pattern_y = re.compile(r"ABS_MT_POSITION_Y\s+([0-9a-fA-F]+)")

    # 状态变量
    start_x = None
    start_y = None
    last_x = None
    last_y = None
    is_touching = False

    print(f"正在监听... (阈值: {MOVE_THRESHOLD})")

    while True:
        line = process.stdout.readline()
        if not line:
            break
        
        line_str = line.decode('utf-8', errors='ignore').strip()

        # 1. 监测手指状态变化 (按下 或 抬起)
        match_id = pattern_id.search(line_str)
        if match_id:
            val_hex = match_id.group(1)
            
            # ffffffff 代表手指抬起 (RELEASE)
            if val_hex.lower() == "ffffffff":
                if is_touching and start_x is not None and last_x is not None:
                    # 计算移动距离 (欧几里得距离)
                    dx = last_x - start_x
                    dy = last_y - start_y
                    distance = math.sqrt(dx*dx + dy*dy)

                    if distance < MOVE_THRESHOLD:
                        print(f"检测到 [点击] -> 坐标: ({last_x}, {last_y}) (偏移: {int(distance)})")
                    else:
                        print(f"检测到 [滑动] -> 起点: ({start_x}, {start_y}) -> 终点: ({last_x}, {last_y}) (距离: {int(distance)})")
                
                # 重置状态
                is_touching = False
                start_x = None
                start_y = None
            
            else:
                # 其他值代表手指按下 (PRESS)，开始新的追踪
                is_touching = True
                # 这里不重置 last_x/y，因为有时候 X 或 Y 不会在第一帧立即出现
                # 只有当确实读到新坐标时才更新

        # 2. 监测坐标变化
        # 注意：getevent 仅输出变化的轴。如果垂直滑动，X可能一直不打印。
        # 所以我们需要一直保存 last_x 和 last_y
        if is_touching:
            match_x = pattern_x.search(line_str)
            if match_x:
                val = int(match_x.group(1), 16)
                last_x = val
                # 如果是刚开始触摸，记录起点
                if start_x is None: start_x = val

            match_y = pattern_y.search(line_str)
            if match_y:
                val = int(match_y.group(1), 16)
                last_y = val
                # 如果是刚开始触摸，记录起点
                if start_y is None: start_y = val

if __name__ == "__main__":
    try:
        monitor_touch_actions()
    except KeyboardInterrupt:
        print("\n停止监听。")