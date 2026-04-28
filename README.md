# High-Speed IoT Camera Streaming System via FPGA & Gigabit Ethernet

![FPGA](https://img.shields.io/badge/FPGA-Altera%20Cyclone%20IV-blue)
![Language](https://img.shields.io/badge/Language-Verilog-orange)
![Protocol](https://img.shields.io/badge/Protocol-UDP%2FIPv4-green)
![Ethernet](https://img.shields.io/badge/Ethernet-Gigabit%20RGMII-red)

A high-performance real-time video acquisition and streaming system built on the **Terasic DE2i-150 (Cyclone IV GX)** FPGA platform. This project demonstrates low-latency video transmission from a camera sensor to a host PC using **Gigabit Ethernet** with raw **UDP** hardware acceleration.

## 🚀 Key Features

- **Real-time Video Pipeline**: Captures raw image data from camera sensors (e.g., OV7670) and processes it in hardware.
- **High-Speed Networking**: Custom UDP/IPv4 hardware stack implemented in Verilog for direct Gigabit Ethernet transmission (RGMII interface) without an OS or soft processor.
- **External Memory Management**: Built-in **SDRAM Controller** serving as a frame buffer to handle high-bandwidth video data and clock domain crossing.
- **Python Integration**: PC-side receiver scripts utilizing OpenCV for real-time frame reconstruction, display, and analysis.
- **Scalable Architecture**: Modular Verilog design easily adaptable to different camera resolutions and Ethernet throughput requirements.

## 🛠 Tech Stack

- **Hardware Description**: Verilog HDL
- **Platform**: Altera/Intel Cyclone IV GX (DE2i-150)
- **Tools**: Quartus II 13.0sp1, Modelsim
- **PC Side**: Python 3.x, OpenCV, Socket programming
- **Network Stack**: Raw UDP over IPv4, RGMII PHY interface

## 📂 Project Structure

- `/FPGA`: Core Verilog modules including camera interface, SDRAM controller, and UDP stack.
- `/Scripts`: Python scripts for receiving and processing the live stream on the host machine.
- `/Docs`: Technical documentation and hardware wiring diagrams.

## 🔧 Setup & Installation

1. **FPGA**: Open the `.qpf` project in Quartus II, compile, and program the `.sof` file to the DE2i-150 board.
2. **Wiring**: Ensure the camera sensor is correctly connected to the GPIO pins as specified in the `.tcl` pin assignment file.
3. **Network**: Connect the board to your PC via a Gigabit Ethernet cable. Set your PC's static IP to match the target subnet defined in the Verilog code.
4. **Run**: Execute the Python receiver:
   ```bash
   python Scripts/stream_live_webcam.py
   ```

---
*Developed as part of the Microprocessor Engineering Project (Project 1) at Hanoi University of Science and Technology.*
