Memory Squeezer - 内存压榨器

 简介

Memory Squeezer 是一个用于测试系统在内存压力下的表现，使用deepseek R1编写。

## 功能特性

- ✅ 单线程和多进程内存压榨模式
- ✅ 可配置的内存块大小和分配速度
- ✅ 实时内存状态监控
- ✅ 四重安全确认机制防止误操作
- ✅ 内存安全限制保护
- ✅ 详细的日志记录
- ✅ 支持多种主题风格

## 系统要求

- windows10 +
- 建议内存大小4GB+(避免因为内存过小，程序写入速度过快导致系统问题！)

## 安装

### 第一种

1. 从Releases下载最新版本的程序

![9b5f71d8-b98f-413a-8157-ab6cadb9ec49.png](https://youke1.picui.cn/s1/2025/08/05/6891b7b470e3a.png)
点击后下滑，然后点击图片箭头所指的地方
![d9fe2610-a5ed-446b-bfcb-509a5befc000.png](https://youke1.picui.cn/s1/2025/08/05/6891bbb9c9254.png)

2. 运行程序

双击下载的程序，弹出的弹窗一直选Yes(PS：第一个选No更快)
<img width="351" height="151" alt="image" src="https://github.com/user-attachments/assets/a99ed54a-f5c4-4f1c-bcea-285220e647c4" />
<img width="243" height="202" alt="image" src="https://github.com/user-attachments/assets/f949a56d-9ae1-4ad0-9e73-8dee411c7ca2" />
<img width="497" height="151" alt="image" src="https://github.com/user-attachments/assets/28ee1027-551e-40bb-8a37-6a8b585cc701" />
<img width="291" height="168" alt="image" src="https://github.com/user-attachments/assets/e7e901d3-f189-4ccf-86f5-3d84f027f7e0" />

3. 开始压榨

点击开始压榨按钮后弹出的弹窗一直选Yes(PS：这次不能No)
![e869d12d-aff0-4d50-910b-8e5233023813.png](https://youke1.picui.cn/s1/2025/08/05/6891bf72934e.png)

### 第二种
1. 克隆仓库或下载源代码
```bash
git clone https://github.com/wsufdfs/memory-squeezer.git
```

```bash
cd memory-squeezer
```
2. 安装依赖
```bash
pip install PyQt5 psutil
```
3. 运行程序

双击下载的程序，弹出的弹窗一直选Yes(PS：第一个选No更快)
<img width="351" height="151" alt="image" src="https://github.com/user-attachments/assets/a99ed54a-f5c4-4f1c-bcea-285220e647c4" />
<img width="243" height="202" alt="image" src="https://github.com/user-attachments/assets/f949a56d-9ae1-4ad0-9e73-8dee411c7ca2" />
<img width="497" height="151" alt="image" src="https://github.com/user-attachments/assets/28ee1027-551e-40bb-8a37-6a8b585cc701" />
<img width="291" height="168" alt="image" src="https://github.com/user-attachments/assets/e7e901d3-f189-4ccf-86f5-3d84f027f7e0" />

4. 开始压榨

点击开始压榨按钮后弹出的弹窗一直选Yes(PS：这次不能No)
![e869d12d-aff0-4d50-910b-8e5233023813.png](https://youke1.picui.cn/s1/2025/08/05/6891bf72934e.png)

## 使用方法

### 基本使用

1. 运行程序
```bash
python memory_squeezer.py
```

2. 点击"开始压榨"按钮启动内存压榨

3. 观察内存使用情况和进度

4. 使用"安全停止"或"紧急停止"结束压榨

### 配置选项

程序会自动创建 `config.ini` 配置文件，您可以修改以下参数：

```ini
[Settings]
BlockSize=10           ; 内存块大小(MB)
AllocationsPerSecond=500 ; 每秒分配次数
ReservePercent=2        ; 保留内存百分比
MemoryLimit=256         ; 内存安全限制(MB)
VirtualMemoryLimit=1024  ;虚拟内存安全限制（MB）
UseMultiprocessing=false ; 是否使用多进程
WorkerProcesses=4       ; 工作进程数
SqueezeVirtualMemory=false ;是否压榨虚拟内存（默认false）


[Window]
Width=600              ; 窗口宽度
Height=500             ; 窗口高度

[Theme]
Theme=Light            ; 主题风格
ProgressBarColor=0,128,255 ; 进度条颜色(RGB)

[Logging]
LogFile=memory_squeezer.log ; 日志文件路径
LogLevel=INFO           ; 日志级别
```

## 注意事项

⚠️ **重要警告**  
此程序会消耗大量系统内存，可能导致系统不稳定！使用时请确保：

1. 已保存所有工作
2. 了解操作风险
3. 系统有足够的内存资源

## 开发计划

- [ ] 添加更多可视化图表
- [ ] 支持自定义内存分配模式
- [ ] 增加压力测试报告功能
- [ ] 支持多语言界面
- [ ] 添加程序主界面直接修改配置

## 贡献指南

欢迎提交 Issue 或 Pull Request 来改进本项目。

### 程序作者QQ：640384548

官方QQ群：925707447