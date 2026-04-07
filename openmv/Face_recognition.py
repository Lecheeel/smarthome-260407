# OpenMV 人脸识别脚本
import sensor, time, image, os, pyb

THRESHOLD = 7000
# === 关键修改：读取路径改为 /sdcard/singtown ===
BASE_DIR = "/sdcard/singtown"

sensor.reset()
sensor.set_contrast(3)
sensor.set_gainceiling(16)
sensor.set_framesize(sensor.QVGA)
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.skip_frames(time = 2000)

# 初始化UART1串口
uart1 = pyb.UART(1, 115200, timeout_char=1000)

face_cascade = image.HaarCascade("/rom/haarcascade_frontalface.cascade", stages=25)

print("正在加载人脸数据...")
faces_db = []

# 检查总目录
try:
    os.stat(BASE_DIR)
except OSError:
    raise Exception("错误: 找不到 " + BASE_DIR + "，请先运行采集脚本！")

# 遍历 /sdcard/singtown 下的 s1, s2...
for d in os.listdir(BASE_DIR):
    if not d.startswith("s"):
        continue

    path = BASE_DIR + "/" + d
    # 遍历图片
    for fname in os.listdir(path):
        if not fname.endswith(".pgm"):
            continue

        # 加载并强制转灰度
        img = image.Image(path + "/" + fname)
        if img.format() != sensor.GRAYSCALE:
            img = img.to_grayscale()

        d1 = img.find_lbp((0, 0, img.width(), img.height()))
        faces_db.append((d1, d)) # d 就是 "s1" 这种名字
        print("加载:", fname)

print("完成! 开始识别...")

clock = time.clock()
last_image_send = time.ticks_ms()  # 记录上次发送图像的时间
while(True):
    clock.tick()
    img = sensor.snapshot()

    # 先进行人脸检测（在图像还是可变的时候）
    objects = img.find_features(face_cascade, threshold=0.75, scale_factor=1.25)

    # 每秒发送一帧JPEG压缩的图像（简易编码）
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_image_send) >= 1000:  # 1000ms = 1秒
        # 将图像压缩为JPEG格式
        jpeg_buffer = img.compress(quality=50)  # 压缩质量50以减小数据量
        # 发送图像标识符和数据
        uart1.write(b"IMG:")
        uart1.write(jpeg_buffer)
        uart1.write(b"\n")
        last_image_send = current_time

    for r in objects:
        try:
            d_curr = img.find_lbp(r)
        except:
            continue

        min_dist = 100000
        name = "Unknown"

        for d_db, db_name in faces_db:
            dist = image.match_descriptor(d_curr, d_db)
            if dist < min_dist:
                min_dist = dist
                name = db_name

        if min_dist < THRESHOLD:
            img.draw_rectangle(r, color=(255,255,255))
            img.draw_string(r[0], r[1]-20, name + " " + str(min_dist), color=(255,255,255), scale=2)
            print("识别:", name, min_dist)
            uart1.write("Recognized: " + name + " " + str(min_dist) + "\n")
        else:
            img.draw_rectangle(r)
            img.draw_string(r[0], r[1]-20, "Unknown", scale=2)
            uart1.write("Unknown face detected\n")

