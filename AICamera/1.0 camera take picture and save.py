import cv2
import os
import datetime
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# --- Cấu hình đường dẫn lưu ảnh ---
SAVE_DIR = r"D:\03. Thac si\04. AI\Luu anh chup"  # Dùng raw string (r"") để tránh lỗi ký tự '\'

# --- Hàm chụp và lưu ảnh ---
def capture_image():
    if frame_data is not None:
        filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
        filepath = os.path.join(SAVE_DIR, filename)
        # Chuyển RGB sang BGR để lưu đúng màu
        cv2.imwrite(filepath, cv2.cvtColor(frame_data, cv2.COLOR_RGB2BGR))
        messagebox.showinfo("📷 Ảnh đã lưu", f"Ảnh được lưu tại:\n{filepath}")

# --- Cập nhật khung hình ---
def update_frame():
    global frame_data
    ret, frame = cap.read()
    if ret:
        # Chuyển BGR → RGB (để hiển thị bằng Tkinter)
        frame_data = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_data)
        imgtk = ImageTk.PhotoImage(image=img)
        lbl_video.imgtk = imgtk
        lbl_video.configure(image=imgtk)
    lbl_video.after(10, update_frame)

# --- Giao diện chính ---
root = tk.Tk()
root.title("Camera - Chụp ảnh và lưu tự động")
root.geometry("1080x960")

lbl_video = tk.Label(root)
lbl_video.pack()

btn_capture = tk.Button(
    root,
    text="📸 Chụp ảnh",
    command=capture_image,
    font=("Arial", 14, "bold"),
    bg="#4CAF50",
    fg="white",
    padx=15,
    pady=8
)

btn_capture.pack(pady=15)

# --- Khởi tạo camera ---
cap = cv2.VideoCapture(1)
frame_data = None

update_frame()

# --- Xử lý khi đóng cửa sổ ---
def on_closing():
    cap.release()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
