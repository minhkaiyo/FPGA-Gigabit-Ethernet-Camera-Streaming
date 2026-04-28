import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

# ---- MAIN ----
if __name__ == "__main__":
    # Thư mục chứa ảnh
    folder = r"D:\03. Thac si\04. AI\Test Pic"
    files = os.listdir(folder)
    img_path = os.path.join(folder, files[0])  # Lấy ảnh đầu tiên
    img = cv2.imread(img_path)

    # 1. Chuyển sang grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Làm mờ để giảm nhiễu
    blur = cv2.GaussianBlur(gray, (11,9), 0)

    # 3. Ngưỡng thích nghi
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 111, 5)

    # 4. Morphology để kín viền
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,6))
    mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 5. Tìm contour ngoài cùng
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 6. Vẽ biên đầy đủ
    edges = np.zeros_like(mask)
    cv2.drawContours(edges, contours, -1, 255, thickness=2)

    # Hiển thị kết quả
    plt.figure(figsize=(15,5))

    plt.subplot(1,3,1)
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title("Ảnh gốc")
    plt.axis("off")

    plt.subplot(1,3,2)
    plt.imshow(mask, cmap="gray")
    plt.title("Mask sau xử lý")
    plt.axis("off")

    plt.subplot(1,3,3)
    plt.imshow(edges, cmap="gray")
    plt.title("Biên đầy đủ")
    plt.axis("off")

    plt.show()
