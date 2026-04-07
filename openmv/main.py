# OpenMV 人脸系统脚本 - 支持串口命令控制
import sensor, time, image, pyb, os

# ================= 配置区域 =================
THRESHOLD = 7000
BASE_DIR = "/sdcard/singtown"
NUM_PHOTOS = 20  # 每次收集的照片数量
# ===========================================

# 初始化传感器
sensor.reset()
sensor.set_contrast(3)
sensor.set_gainceiling(16)
sensor.set_framesize(sensor.QVGA)
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.skip_frames(time=2000)

# 初始化串口
uart1 = pyb.UART(1, 115200, timeout_char=1000)

# 初始化Haar级联
face_cascade = image.HaarCascade("/rom/haarcascade_frontalface.cascade", stages=25)

# 初始化LED
red_led = pyb.LED(1)
green_led = pyb.LED(2)

# 全局变量
current_mode = "idle"  # idle, collect, recognize
collect_name = ""
collect_subject_id = ""
collect_count = 0
faces_db = []
name_to_subject = {}  # 名字到subject_id的映射
current_image = None  # 存储当前帧图像

def send_message(msg):
    """发送消息到串口"""
    uart1.write(msg + "\n")
    print(msg)

def send_image(img):
    """发送图像到串口"""
    try:
        jpeg_buffer = img.compress(quality=30)  # 降低质量以减小数据量
        uart1.write(jpeg_buffer)
        uart1.write(b"\n")
    except Exception as e:
        send_message("Image send error: {}".format(e))

def load_faces_db():
    """加载人脸数据库"""
    global faces_db, name_to_subject
    faces_db = []
    name_to_subject = {}

    try:
        os.stat(BASE_DIR)
    except OSError:
        send_message("Warning: No face database found")
        return

    total_loaded = 0

    # 遍历 /sdcard/singtown 下的文件夹
    for d in os.listdir(BASE_DIR):
        # 跳过非人脸文件夹（现在使用名字而不是s编号）
        if d.startswith("s") or d == "singtown":
            continue

        path = BASE_DIR + "/" + d
        subject_samples = 0

        # 遍历图片
        for fname in os.listdir(path):
            if not fname.endswith(".pgm"):
                continue

            try:
                # 加载图像并立即处理，然后释放内存
                img = image.Image(path + "/" + fname)
                if img.format() != sensor.GRAYSCALE:
                    img = img.to_grayscale()

                # 使用全图LBP，和原脚本保持一致
                d1 = img.find_lbp((0, 0, img.width(), img.height()))
                faces_db.append((d1, d))
                subject_samples += 1
                total_loaded += 1

                # 强制垃圾回收
                img = None
                import gc
                gc.collect()

            except Exception as e:
                send_message("Error loading {}: {}".format(fname, e))
                continue

        if subject_samples > 0:
            send_message("Loaded {} samples for {}".format(subject_samples, d))

    send_message("Total loaded: {} face samples from {} subjects".format(total_loaded, len(set([name for _, name in faces_db]))))

def create_subject_dir(name):
    """创建人脸目录"""
    person_dir = BASE_DIR + "/" + name

    # 如果目录已存在，先删除它
    try:
        os.stat(person_dir)
        # 目录存在，删除它及其内容
        send_message("Directory {} already exists, removing old data...".format(person_dir))
        try:
            # 删除目录中的所有文件
            for fname in os.listdir(person_dir):
                try:
                    os.remove(person_dir + "/" + fname)
                except:
                    pass
            # 删除目录
            os.rmdir(person_dir)
            send_message("Removed old directory: {}".format(person_dir))
        except Exception as e:
            send_message("Warning: Could not remove old directory: {}".format(e))
    except OSError:
        # 目录不存在，这是正常的
        pass

    # 创建新目录
    try:
        os.mkdir(person_dir)
        send_message("Created directory: {}".format(person_dir))
        return person_dir, name
    except Exception as e:
        send_message("Error creating directory: {}".format(e))
        return None, None

def process_command(cmd):
    """处理串口命令"""
    global current_mode, collect_name, collect_subject_id, collect_count

    cmd = cmd.strip()
    if not cmd:
        return

    if cmd.startswith("COLLECT:"):
        # 命令格式: COLLECT:name (纯英文名字)
        name = cmd[8:].strip()
        if not name or not name.isalpha():
            send_message("Error: Invalid name. Use only English letters.")
            return

        # 检查目录并创建
        person_dir, subject_id = create_subject_dir(name)
        if person_dir is None:
            return

        current_mode = "collect"
        collect_name = name
        collect_subject_id = subject_id
        collect_count = 0  # 重置计数器
        send_message("Starting face collection for: {}".format(name))
        send_message("Subject ID: {}".format(subject_id))

    elif cmd == "RECOGNIZE":
        current_mode = "recognize"
        load_faces_db()
        if len(faces_db) == 0:
            send_message("Warning: No face data loaded, staying in idle mode")
            current_mode = "idle"
        else:
            send_message("Starting face recognition mode")

    elif cmd == "STOP":
        current_mode = "idle"
        send_message("Stopped current operation")

    elif cmd == "STATUS":
        send_message("Current mode: {}".format(current_mode))
        if current_mode == "collect":
            send_message("Collecting for: {}, Progress: {}/{}".format(collect_name, collect_count, NUM_PHOTOS))

    elif cmd == "GET_IMAGE":
        # 直接发送当前帧的新副本，避免可变性问题
        try:
            fresh_copy = sensor.snapshot()
            send_image(fresh_copy)
        except Exception as e:
            send_message("Failed to capture image: {}".format(e))

    elif cmd == "LIST_FACES":
        list_faces()

    elif cmd.startswith("DELETE_FACE:"):
        # 命令格式: DELETE_FACE:name
        name = cmd[12:].strip()
        if not name:
            send_message("Error: Please specify a face name to delete")
        else:
            delete_face(name)

    else:
        send_message("Unknown command. Available: COLLECT:name, RECOGNIZE, STOP, STATUS, GET_IMAGE, LIST_FACES, DELETE_FACE:name")

def list_faces():
    """列出所有已保存的人脸"""
    try:
        os.stat(BASE_DIR)
    except OSError:
        send_message("No face database found")
        return

    face_count = 0
    send_message("=== Face Database ===")

    # 遍历所有文件夹
    for d in os.listdir(BASE_DIR):
        # 跳过旧的s编号文件夹，只处理名字文件夹
        if d.startswith("s") or d == "singtown":
            continue

        person_dir = BASE_DIR + "/" + d
        try:
            # 统计这个人的照片数量
            photo_count = 0
            for fname in os.listdir(person_dir):
                if fname.endswith(".pgm"):
                    photo_count += 1

            if photo_count > 0:
                send_message("Name: {}, Photos: {}".format(d, photo_count))
                face_count += 1
        except:
            continue

    send_message("Total faces: {}".format(face_count))
    send_message("===================")

def delete_face(name):
    """删除指定的人脸数据"""
    if not name:
        send_message("Error: Invalid name")
        return

    person_dir = BASE_DIR + "/" + name

    try:
        os.stat(person_dir)
    except OSError:
        send_message("Face '{}' not found".format(name))
        return

    try:
        # 删除目录中的所有文件
        file_count = 0
        for fname in os.listdir(person_dir):
            if fname.endswith(".pgm"):
                try:
                    os.remove(person_dir + "/" + fname)
                    file_count += 1
                except Exception as e:
                    send_message("Error deleting {}: {}".format(fname, e))

        # 删除目录
        os.rmdir(person_dir)
        send_message("Deleted face '{}': {} files removed".format(name, file_count))

        # 如果当前在识别模式，重新加载数据库
        if current_mode == "recognize":
            load_faces_db()

    except Exception as e:
        send_message("Error deleting face '{}': {}".format(name, e))

def collect_face(img):
    """收集人脸"""
    global collect_count, current_mode

    # 如果已经收集完成，停止收集
    if collect_count >= NUM_PHOTOS:
        current_mode = "idle"
        send_message("Collection complete for: {}".format(collect_name))
        return

    objects = img.find_features(face_cascade, threshold=0.75, scale_factor=1.25)

    if objects:
        green_led.on()
        red_led.off()
        face_rect = objects[0]

        # 裁剪并保存
        person_dir = BASE_DIR + "/" + collect_subject_id
        file_name = person_dir + "/" + str(collect_count) + ".pgm"

        try:
            img.save(file_name, roi=face_rect)
            collect_count += 1
            send_message("Collected: {}/{}".format(collect_count, NUM_PHOTOS))

            if collect_count >= NUM_PHOTOS:
                current_mode = "idle"
                send_message("Collection complete for: {}".format(collect_name))

        except Exception as e:
            send_message("Save error: {}".format(e))

        img.draw_rectangle(face_rect, color=(255, 255, 255))
        time.sleep(0.3)
        green_led.off()
    else:
        red_led.on()
        green_led.off()

def recognize_face(img):
    """识别人脸"""
    objects = img.find_features(face_cascade, threshold=0.75, scale_factor=1.25)

    # 限制同时处理的识别数量，避免过载
    max_faces = min(len(objects), 3)  # 最多同时识别3张脸，减少负载

    for i in range(max_faces):
        r = objects[i]
        try:
            # 使用检测到的人脸矩形区域，和原脚本保持一致
            d_curr = img.find_lbp(r)
        except Exception as e:
            send_message("LBP error: {}".format(e))
            continue

        min_dist = 100000
        name = "Unknown"

        # 限制匹配的样本数量，避免过长的计算时间
        max_matches = min(len(faces_db), 30)  # 最多匹配30个样本，进一步减少负载

        for j in range(max_matches):
            d_db, db_name = faces_db[j]
            try:
                dist = image.match_descriptor(d_curr, d_db)
                if dist < min_dist:
                    min_dist = dist
                    name = db_name
            except Exception as e:
                continue

        if min_dist < THRESHOLD:
            img.draw_rectangle(r, color=(255, 255, 255))
            img.draw_string(r[0], r[1]-20, name, color=(255, 255, 255), scale=2)
            send_message("Recognized: {} ({})".format(name, min_dist))
        else:
            img.draw_rectangle(r)
            img.draw_string(r[0], r[1]-20, "Unknown", scale=2)
            send_message("Unknown face detected")

# 创建基础目录
try:
    if "singtown" not in os.listdir("/sdcard"):
        os.mkdir(BASE_DIR)
        send_message("Created base directory: {}".format(BASE_DIR))
except:
    pass

send_message("Face System Ready. Send commands via UART1.")
send_message("Commands: COLLECT:name, RECOGNIZE, STOP, STATUS, GET_IMAGE, LIST_FACES, DELETE_FACE:name")

clock = time.clock()
frame_count = 0

while True:
    clock.tick()
    frame_count += 1

    try:
        img = sensor.snapshot()

        # 检查串口命令（在创建副本之前）
        if uart1.any():
            try:
                cmd = uart1.readline().decode().strip()
                process_command(cmd)
            except Exception as e:
                send_message("Command error: {}".format(e))

        # 根据当前模式处理，只在需要时创建副本
        if current_mode == "collect":
            # 收集模式：需要修改图像（绘制框和保存）
            img_copy = img.copy()
            collect_face(img_copy)
            # 释放副本
            img_copy = None
            import gc
            gc.collect()

        elif current_mode == "recognize":
            # 识别模式：需要修改图像（绘制框）
            img_copy = img.copy()
            recognize_face(img_copy)
            # 释放副本
            img_copy = None
            import gc
            gc.collect()

        else:
            # idle 模式：检测人脸并绘制灰色框
            objects = img.find_features(face_cascade, threshold=0.75, scale_factor=1.25)
            for r in objects:
                img.draw_rectangle(r, color=(128, 128, 128))  # 灰色框表示检测到但不处理
                img.draw_string(r[0], r[1]-15, "Face", color=(128, 128, 128), scale=1)

        # 保存当前图像供命令请求使用（使用原始图像）
        current_image = img

    except Exception as e:
        send_message("Main loop error: {}".format(e))
        current_mode = "idle"  # 出错时重置到idle模式
        # 清理可能的内存泄漏
        try:
            import gc
            gc.collect()
        except:
            pass


    # 小延迟避免CPU占用过高
    # time.sleep(0.01)
