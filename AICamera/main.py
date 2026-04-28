"""
Test Camera - Tổng hợp các chức năng xử lý ảnh
Chức năng:
  1. Mở camera laptop (webcam chính)
  2. Chụp ảnh & lưu
  3. Xử lý ảnh: Resize, Grayscale, Tách nền, Phát hiện biên
Sử dụng: python test_camera.py
Nhấn các phím tắt trên cửa sổ camera để thao tác.
"""

import cv2
import numpy as np
import os
import datetime
import sys

# === CẤU HÌNH ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(SCRIPT_DIR, "captured_images")
os.makedirs(SAVE_DIR, exist_ok=True)

# Thử tìm camera khả dụng (ưu tiên camera 0 = webcam chính trên laptop)
CAMERA_INDEX = 1


# === CÁC HÀM XỬ LÝ ẢNH ===

def resize_image(img, max_size=640):
    """Resize ảnh giữ tỷ lệ, chỉ thu nhỏ nếu quá lớn."""
    h, w = img.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img


def to_grayscale(img):
    """Chuyển ảnh sang grayscale."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def segment_object(img):
    """Tách vật thể khỏi nền bằng adaptive threshold + morphology."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)

    # Ngưỡng thích nghi
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 5
    )

    # Morphology: đóng lỗ + mở nhiễu
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Giữ contour lớn nhất
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_clean = np.zeros_like(mask)
    if contours:
        biggest = max(contours, key=cv2.contourArea)
        cv2.drawContours(mask_clean, [biggest], -1, 255, thickness=-1)

    # Áp mask lên ảnh gốc
    result = cv2.bitwise_and(img, img, mask=mask_clean)
    return mask_clean, result


def detect_edges(img):
    """Phát hiện đường biên bằng Canny."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    return edges


def save_image(frame):
    """Lưu ảnh với tên theo timestamp."""
    filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    filepath = os.path.join(SAVE_DIR, filename)
    cv2.imwrite(filepath, frame)
    print(f"[OK] Anh da luu tai: {filepath}")
    return filepath


# === HÀM CHÍNH ===

def draw_help_overlay(frame, mode_name):
    """Vẽ hướng dẫn phím tắt lên frame."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Thanh trạng thái phía trên
    cv2.rectangle(overlay, (0, 0), (w, 40), (30, 30, 30), -1)
    cv2.putText(overlay, f"Mode: {mode_name}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)

    # Thanh hướng dẫn phía dưới
    cv2.rectangle(overlay, (0, h - 35), (w, h), (30, 30, 30), -1)
    help_text = "[Q]uit  [S]ave  [1]Normal  [2]Gray  [3]Segment  [4]Edge"
    cv2.putText(overlay, help_text, (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Blend overlay
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    return frame


def main():
    print("=" * 50)
    print("  TEST CAMERA - IoT Camera System")
    print("=" * 50)
    print(f"  Thu muc luu anh: {SAVE_DIR}")
    print(f"  Camera index: {CAMERA_INDEX}")
    print("-" * 50)
    print("  Phim tat:")
    print("    [Q] - Thoat")
    print("    [S] - Chup va luu anh")
    print("    [1] - Che do binh thuong")
    print("    [2] - Che do Grayscale")
    print("    [3] - Che do Tach nen (Segment)")
    print("    [4] - Che do Phat hien bien (Edge)")
    print("=" * 50)

    # Mở camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[LOI] Khong the mo camera (index={CAMERA_INDEX})!")
        print("  Thu doi CAMERA_INDEX = 1 trong code.")
        sys.exit(1)

    # Cấu hình camera
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  Camera da mo: {actual_w}x{actual_h}")

    mode = "Normal"
    mode_names = {
        "Normal": "Binh thuong",
        "Gray": "Grayscale",
        "Segment": "Tach nen",
        "Edge": "Phat hien bien"
    }

    cv2.namedWindow("IoT Camera Test", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[LOI] Khong doc duoc frame tu camera!")
            break

        # Xử lý theo chế độ
        display = frame.copy()

        if mode == "Gray":
            gray = to_grayscale(frame)
            display = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        elif mode == "Segment":
            mask, segmented = segment_object(frame)
            display = segmented

        elif mode == "Edge":
            edges = detect_edges(frame)
            display = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # Vẽ overlay
        display = draw_help_overlay(display, mode_names.get(mode, mode))

        cv2.imshow("IoT Camera Test", display)

        # Xử lý phím
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == ord('Q'):
            print("\n[OK] Dang dong camera...")
            break
        elif key == ord('s') or key == ord('S'):
            save_image(frame)
        elif key == ord('1'):
            mode = "Normal"
            print(f"  -> Chuyen sang che do: {mode_names[mode]}")
        elif key == ord('2'):
            mode = "Gray"
            print(f"  -> Chuyen sang che do: {mode_names[mode]}")
        elif key == ord('3'):
            mode = "Segment"
            print(f"  -> Chuyen sang che do: {mode_names[mode]}")
        elif key == ord('4'):
            mode = "Edge"
            print(f"  -> Chuyen sang che do: {mode_names[mode]}")

    cap.release()
    cv2.destroyAllWindows()
    print("[OK] Da dong camera va thoat.")


if __name__ == "__main__":
    main()
