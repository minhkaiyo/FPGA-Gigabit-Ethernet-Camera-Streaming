# High-Speed Camera Streaming System via FPGA & Gigabit Ethernet

![Project Status](https://img.shields.io/badge/Status-Under%20Development-orange)
![FPGA](https://img.shields.io/badge/FPGA-Altera%20Cyclone%20IV%20GX-blue)
![Language](https://img.shields.io/badge/Language-Verilog%20HDL-green)

## 📌 Project Overview
This project focuses on designing and implementing a high-performance, real-time video acquisition and transmission system. It leverages an FPGA as the central processing unit to interface with a camera module and transmit video data over a Gigabit Ethernet link with minimal latency.

### 🚀 Key Features
- **Hardware-based UDP/IPv4 Stack**: Entirely implemented in Verilog for ultra-low latency transmission without CPU overhead.
- **RGMII Interface**: High-speed communication with Gigabit Ethernet PHY.
- **Custom SDRAM Controller**: Designed to manage frame buffering and clock domain crossing between camera and network interfaces.
- **Real-time Video Processing**: Capture and packetize video data directly on hardware.

## 🛠 Technical Specifications
- **FPGA**: Altera Cyclone IV GX (DE2i-150 Development Board)
- **Networking**: Gigabit Ethernet (RGMII)
- **Memory**: 128MB SDRAM (Frame Buffer)
- **Protocol Stack**: Hardware-accelerated UDP/IP
- **Programming Language**: Verilog HDL, Python (Receiver GUI)

## 📂 Current Progress
- [x] Research & System Architecture Design
- [x] Gigabit Ethernet PHY Interface (RGMII) implementation
- [x] Basic UDP Packet transmission tests
- [ ] SDRAM Controller integration for frame buffering
- [ ] Camera interface & Video packetization
- [ ] Python-based high-speed receiver application

---
**Note:** This repository is currently under active development. Source code and documentation are being updated periodically.

---
© 2026 Pham Van Minh. All rights reserved.
