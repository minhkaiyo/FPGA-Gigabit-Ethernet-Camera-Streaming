import cv2
import matplotlib.pyplot as plt
import os
import glob

# Thư mục chứa ảnh test
folder_path = r"D:\03. Thac si\04. AI\Test Pic"

# Lấy danh sách file ảnh
image_files = glob.glob(os.path.join(folder_path, "*.jpg")) + \
              glob.glob(os.path.join(folder_path, "*.jpeg")) + \
              glob.glob(os.path.join(folder_path, "*.png"))

if not image_files:
    print("Không tìm thấy ảnh nào trong thư mục!")
else:
    for img_path in image_files:
        # Đọc ảnh màu
        img_color = cv2.imread(img_path)
        if img_color is None:
            continue

        # Chuyển sang ảnh xám
        img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

        print(f"\nẢnh: {os.path.basename(img_path)}")
        print(f" - Kích thước gốc (màu): {img_color.shape[1]}x{img_color.shape[0]}x{img_color.shape[2]}")
        print(f" - Kích thước ảnh xám: {img_gray.shape[1]}x{img_gray.shape[0]}")

        # Hiển thị so sánh
        plt.figure(figsize=(10,5))
        plt.subplot(1,2,1)
        plt.imshow(cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB))
        plt.title("Ảnh gốc (màu)")
        plt.axis("off")

        plt.subplot(1,2,2)
        plt.imshow(img_gray, cmap="gray")
        plt.title("Ảnh sau khi chuyển sang xám")
        plt.axis("off")

        plt.suptitle(os.path.basename(img_path))
        plt.show()