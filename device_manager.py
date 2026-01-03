# device_manager.py
import uiautomator2 as u2
import time

def connect_device_robust(serial):
    """
    智能连接设备：如果发现服务挂死，自动执行修复
    """
    print(f"🔌 正在连接设备 {serial}...")
    d = u2.connect(serial)
    
    try:
        print("🩺 正在进行服务健康检查...")
        _ = d.window_size()
        print("✅ 设备服务运行正常")
    except Exception as e:
        print(f"⚠️ 检测到服务异常 ({e})")
        print("🔧 正在自动修复 uiautomator 服务 (耗时约 10-15秒)...")
        try:
            d.reset_uiautomator()
            print("✅ 修复完成，服务已重启")
        except Exception as fatal_e:
            print(f"❌ 修复失败，请检查 USB 连接: {fatal_e}")
            raise fatal_e
            
    return d