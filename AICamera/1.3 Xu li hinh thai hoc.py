import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

def tach_phan_hoa(img_bgr):
    # 1. Chuyển sang grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 2. Làm mờ để giảm nhiễu
    blur = cv2.GaussianBlur(gray, (5,5), 0)

    # 3. Ngưỡng thích nghi để tách nền
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 99, 7)

    # 4. Morphology Closing mạnh hơn + Opening để làm sạch nhiễu
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15,15))
    mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=6)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

    # 5. Lấy contour lớn nhất (đối tượng chính)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    mask_clean = np.zeros_like(mask)
    if len(contours) > 0:
        cv2.drawContours(mask_clean, [contours[0]], -1, 255, thickness=-1)

    # 6. Lấp kín các lỗ bên trong đối tượng
    mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel, iterations=8)

    # 7. Giữ lại vùng đối tượng
    result = cv2.bitwise_and(img_bgr, img_bgr, mask=mask_clean)

    # Trả về các ảnh trung gian
    return thresh, mask, mask_clean, result


# ---- MAIN ----
if __name__ == "__main__":
    # Thư mục chứa ảnh
    folder = r"D:\03. Thac si\04. AI\Test Pic"

    # Lấy 1 ảnh trong thư mục để test
    files = os.listdir(folder)
    if len(files) == 0:
        print("⚠️ Không tìm thấy ảnh trong thư mục!")
        exit()

    img_path = os.path.join(folder, files[0])  
    img = cv2.imread(img_path)
    print(f"Đang xử lý ảnh: {img_path}")

    # Tách vật thể
    thresh, mask_morph, mask_final, result = tach_phan_hoa(img)

    # Hiển thị kết quả
    plt.figure(figsize=(18,5))

    plt.subplot(1,4,1)
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    plt.title("Ảnh gốc")
    plt.axis("off")

    plt.subplot(1,4,2)
    plt.imshow(thresh, cmap="gray")
    plt.title("Ngưỡng thích nghi")
    plt.axis("off")

    plt.subplot(1,4,3)
    plt.imshow(mask_morph, cmap="gray")
    plt.title("Sau Morphology (Closing + Opening)")
    plt.axis("off")

    plt.subplot(1,4,4)
    plt.imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    plt.title("Kết quả cuối (đã lấp kín lỗ)")
    plt.axis("off")

    plt.tight_layout()
    plt.show()
