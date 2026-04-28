import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

def tach_phan_hoa(img_bgr):
        # Chuyển sang grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # Làm mờ để giảm nhiễu
    blur = cv2.GaussianBlur(gray, (11,9), 0)
        # Ngưỡng thích nghi để tách nền
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 111, 5)
    
        # 4. Morphology để kín viền
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,6))
    mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        # 5. Tìm contour ngoài cùng (không lấy lỗ bên trong)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

        # chỉ lấy contour lớn nhất (hạt phấn chính)
    mask_clean = np.zeros_like(mask)
    if len(contours) > 0:
        cv2.drawContours(mask_clean, [contours[0]], -1, 255, thickness=-1)

        # 6. Giữ lại hạt phấn
    result = cv2.bitwise_and(img_bgr, img_bgr, mask=mask_clean)
    return thresh, mask_clean, result
# ---- MAIN ----
if __name__ == "__main__":
    # Thư mục chứa ảnh
    folder = r"D:\03. Thac si\04. AI\Test Pic"

    # Lấy 1 ảnh trong thư mục để test (VD: ảnh đầu tiên)
    files = os.listdir(folder)
    img_path = os.path.join(folder, files[0])  # thay [0] thành số khác để lấy ảnh khác

    # Đọc ảnh
    img = cv2.imread(img_path)

    # Tách phấn hoa
    thresh, mask, result = tach_phan_hoa(img)

    # Hiển thị kết quả
    plt.figure(figsize=(15,5))

    plt.subplot(1,3,1)
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title("Origin")
    plt.axis("off")

    plt.subplot(1,3,2)
    plt.imshow(mask, cmap="gray")
    plt.title("Mask")
    plt.axis("off")

    plt.subplot(1,3,3)
    plt.imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    plt.title("Pollen")
    plt.axis("off")

    plt.show()
