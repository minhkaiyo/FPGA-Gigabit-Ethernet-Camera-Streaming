import cv2
import matplotlib.pyplot as plt
import os
import glob

def resize_image(img, max_size=900):
    h, w = img.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:  # chỉ resize khi ảnh quá lớn
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img

folder_path = r"D:\03. Thac si\04. AI\Test Pic"
image_files = glob.glob(os.path.join(folder_path, "*.jpg")) + \
              glob.glob(os.path.join(folder_path, "*.png")) + \
              glob.glob(os.path.join(folder_path, "*.jpeg"))

if not image_files:
    print("Không tìm thấy ảnh nào trong thư mục!")
else:
    for img_path in image_files:
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        resized = resize_image(img, max_size=900)

        print(f"\nẢnh: {os.path.basename(img_path)}")
        print(f" - Kích thước gốc: {img.shape[1]}x{img.shape[0]}")
        print(f" - Sau resize: {resized.shape[1]}x{resized.shape[0]}")

        # Hiển thị so sánh
        plt.figure(figsize=(10,5))
        plt.subplot(1,2,1)
        plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        plt.title("Ảnh gốc")
        plt.axis("off")

        plt.subplot(1,2,2)
        plt.imshow(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
        plt.title("Ảnh sau resize")
        plt.axis("off")

        plt.suptitle(os.path.basename(img_path))
        plt.show()
