# OpenMV 人脸采集脚本
import sensor, time, image, pyb, os

# ================= 配置区域 =================
NUM_SUBJECTS = 1     # 这是第几个人？(1, 2, 3...)
NUM_PHOTOS = 20      # 拍多少张
# ===========================================

sensor.reset()
sensor.set_contrast(3)
sensor.set_gainceiling(16)
sensor.set_framesize(sensor.QVGA)
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.skip_frames(time = 2000)

face_cascade = image.HaarCascade("/rom/haarcascade_frontalface.cascade", stages=25)
red_led = pyb.LED(1)
green_led = pyb.LED(2)

# === 关键修改：指定路径到 /sdcard ===
# 你的设备必须写完整路径 "/sdcard/singtown"
base_path = "/sdcard/singtown"

# 1. 检查并创建总目录 /sdcard/singtown
try:
    if "singtown" not in os.listdir("/sdcard"):
        os.mkdir(base_path)
except Exception as e:
    print("目录检测提示:", e) # 只要不报错停止就行

# 2. 创建个人目录 /sdcard/singtown/s1
person_dir = base_path + "/s" + str(NUM_SUBJECTS)
try:
    # 检查 s1 是否存在
    os.stat(person_dir) 
except OSError:
    # 如果不存在(报错)，就创建它
    os.mkdir(person_dir)
    print("创建新文件夹:", person_dir)

print("当前保存路径: " + person_dir)
print("准备好... 开始采集！")

count = 0
clock = time.clock()

while(count < NUM_PHOTOS):
    clock.tick()
    img = sensor.snapshot()
    objects = img.find_features(face_cascade, threshold=0.75, scale_factor=1.25)

    if objects:
        green_led.on()
        red_led.off()
        face_rect = objects[0]
        
        # 裁剪并保存
        # 注意：使用 roi=face_rect 直接在保存时裁剪，节省内存
        # 路径格式: /sdcard/singtown/s1/0.pgm
        file_name = person_dir + "/" + str(count) + ".pgm"
        img.save(file_name, roi=face_rect)
        
        print("已保存: %s" % file_name)
        img.draw_rectangle(face_rect)
        
        count += 1
        time.sleep(0.3) # 暂停0.3秒让你换个表情
        green_led.off()
    else:
        red_led.on()
        green_led.off()

print("采集完成！")