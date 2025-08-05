import sys
import os
import threading
import time
import configparser
import psutil
import multiprocessing
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                            QPushButton, QLabel, QProgressBar, QGroupBox,
                            QMessageBox, QHBoxLayout, QPlainTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPalette

class MemorySignals(QObject):
    """自定义信号类"""
    update_signal = pyqtSignal(int, float, float)  # 进度, 已分配内存, 可用内存
    alert_signal = pyqtSignal(str)
    complete_signal = pyqtSignal()

class ConfigManager:
    """配置文件管理"""
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(config_file):
            self.create_default_config()
        else:
            self.config.read(config_file)
    
    def create_default_config(self):
        """创建默认配置文件"""
        self.config["Settings"] = {
            "BlockSize": "10",            # 内存块大小(MB)
            "AllocationsPerSecond": "500", # 每秒分配次数
            "ReservePercent": "2",        # 保留内存百分比
            "MemoryLimit": "256"           # 安全限制(MB)
        }
        
        self.config["Window"] = {
            "Width": "600",  # 窗口宽度
            "Height": "500"  # 窗口高度
        }
        
        self.config["Appearance"] = {
            "ProgressBarColor": "0,128,255" # 进度条颜色(RGB)
        }
        
        with open(self.config_file, "w") as f:
            self.config.write(f)
    
    def get_int(self, section, key, default=0):
        try:
            return self.config.getint(section, key)
        except:
            return default
    
    def get_float(self, section, key, default=0.0):
        try:
            return self.config.getfloat(section, key)
        except:
            return default
    
    def get_str(self, section, key, default=""):
        try:
            return self.config.get(section, key)
        except:
            return default
    
    def get_rgb(self, section, key, default=(0, 128, 255)):
        try:
            color_str = self.config.get(section, key)
            r, g, b = map(int, color_str.split(","))
            return r, g, b
        except:
            return default

class MemorySqueezerGUI(QMainWindow):
    """内存压榨器主窗口 - 严格按照图片设计"""
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.setWindowTitle("Memory Squeezer")  # 窗口标题
        self.init_config()
        self.init_ui()
        self.connect_signals()
        self.log("程序已启动")
    
    def init_config(self):
        """初始化配置参数"""
        self.allocated_blocks = []
        self.block_size = self.config.get_int("Settings", "BlockSize", 10) * 1024 * 1024
        self.should_stop = threading.Event()
        self.total_allocated = 0
        self.max_allocation = 0
        self.memory_limit = self.config.get_int("Settings", "MemoryLimit", 256) * 1024 * 1024
        self.reserve_percent = self.config.get_float("Settings", "ReservePercent", 2.0)
        self.allocations_per_second = self.config.get_int("Settings", "AllocationsPerSecond", 500)
        self.log_file = "memory_squeezer.log"
        
        # 创建日志文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Session started\n")
    
    def init_ui(self):
        """严格按照图片设计初始化用户界面"""
        # 设置窗口大小
        width = self.config.get_int("Window", "Width", 600)
        height = self.config.get_int("Window", "Height", 500)
        self.setFixedSize(width, height)
        
        # 设置背景颜色为浅灰色（与图片一致）
        self.setStyleSheet("background-color: #f0f0f0;")
        
        main_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 内存状态区域 - 与图片一致
        status_group = QGroupBox("内存状态")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        status_layout = QVBoxLayout()
        
        # 已分配内存标签
        self.allocated_label = QLabel("已分配: 0 MB")
        self.allocated_label.setStyleSheet("font-size: 14px;")
        
        # 可用内存标签
        self.available_label = QLabel("可用内存: 0 MB")
        self.available_label.setStyleSheet("font-size: 14px;")
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "   border: 2px solid grey;"
            "   border-radius: 5px;"
            "   text-align: center;"
            "   background: white;"
            "   height: 20px;"
            "}"
            "QProgressBar::chunk {"
            "   background-color: #0080ff;"
            "}"
        )
        
        # 设置进度条颜色
        r, g, b = self.config.get_rgb("Appearance", "ProgressBarColor", (0, 128, 255))
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                background: white;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: rgb({r}, {g}, {b});
            }}
        """)
        
        # 添加组件到状态布局
        status_layout.addWidget(self.allocated_label)
        status_layout.addWidget(self.available_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        
        # 操作控制区域 - 与图片一致
        control_group = QGroupBox("操作控制")
        control_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        control_layout = QHBoxLayout()
        
        # 创建按钮（保持与图片相同的文本）
        self.start_btn = QPushButton("开始压榨")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        
        self.stop_btn = QPushButton("安全停止")
        self.stop_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 8px;")
        self.stop_btn.setEnabled(False)  # 初始不可用
        
        self.emergency_btn = QPushButton("紧急停止")
        self.emergency_btn.setStyleSheet("background-color: #F44336; color: white; padding: 8px;")
        self.emergency_btn.setEnabled(False)  # 初始不可用
        
        self.config_btn = QPushButton("配置")
        self.config_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        
        # 添加按钮到布局
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop极速赛车开奖结果_btn)
        control_layout.addWidget(self.emergency_btn)
        control_layout.addWidget(self.config_btn)
        control_group.setLayout(control_layout)
        
        # 日志区域
        log_group = QGroupBox("操作日志")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout()
        
        # 日志文本框
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: white; border: 1px solid gray;")
        
        # 添加日志文本框到布局
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        
        # 添加所有分组框到主布局
        layout.addWidget(status_group)
        layout.addWidget(control_group)
        layout.addWidget(log_group)
        
        # 设置主窗口的中心部件
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        # 初始化内存信息
        available = psutil.virtual_memory().available
        self.allocated_label.setText("已分配: 0 MB")
        self.available_label.setText(f"可用内存: {available/(1024 * 1024):.2f} MB")
        
        # 初始化日志
        self.log("软件初始化完成")
        self.log(f"配置参数: 块大小={self.block_size/(1024 * 1024)}MB, 分配速度={self.allocations_per_second}次/秒")
        self.log(f"保留内存: {self.reserve_percent}%, 安全限制: {self.memory_limit/(1024 * 1024)}MB")

    def connect_signals(self):
        """连接信号和槽函数"""
        self.start_btn.clicked.connect(self.start_squeeze)
        self.stop_btn.clicked.connect(self.graceful_stop)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.config_btn.clicked.connect(self.open_config_file)

    def start_squeeze(self):
        """开始内存压榨"""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.emergency_btn.setEnabled(True)
        
        available_mem = psutil.virtual_memory().available
        reserve = available_mem * (self.reserve_percent / 100)
        self.max_allocation = available_mem - reserve
        
        self.log("=== 内存压榨启动 ===")
        self.log(f"目标分配量: {self.max_allocation / (1024 * 1024):.2f} MB")
        self.log(f"保留内存: {reserve / (1024 * 1024):.2f} MB ({self.reserve_percent}%)")
        self.log(f"安全限制: {self.memory_limit / (1024 * 1024)} MB")
        self.log(f"分配速度: {self.allocations_per_second} 次/秒")
        self.log(f"内存块大小: {self.block_size / (1024 * 1024)} MB")
        
        # 启动内存压榨线程
        self.worker_thread = threading.Thread(target=self.squeeze_memory)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        # 启动内存监控线程
        self.monitor_thread = threading.Thread(target=self.monitor_memory)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def squeeze_memory(self):
        """内存压榨核心逻辑"""
        try:
            interval = 1.0 / self.allocations_per_second
            next_alloc_time = time.time()
            
            while not self.should_stop.is_set() and self.total_allocated < self.max_allocation:
                current_time = time.time()
                if current_time >= next_alloc_time:
                    # 分配内存块
                    block = bytearray(os.urandom(self.block_size))
                    self.allocated_blocks.append(block)
                    self.total_allocated += self.block_size
                    next_alloc_time += interval
                    
                    # 更新UI
                    progress = (self.total_allocated / self.max_allocation) * 100
                    available = psutil.virtual_memory().available
                    
                    self.allocated_label.setText(f"已分配: {self.total_allocated / (1024 * 1024):.2f} MB")
                    self.available_label.setText(f"可用内存: {available / (1024 * 1024):.2f} MB")
                    self.progress_bar.setValue(int(progress))
                    
                    if available < self.memory_limit:
                        self.log("系统可用内存低于安全限制，自动停止")
                        self.stop_btn.click()
                        break
                
                time.sleep(0.001)
                
        except MemoryError:
            self.log("内存耗尽!")
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
        finally:
            self.allocated_blocks = []  # 释放内存
            self.on_complete()

    def monitor_memory(self):
        """监控内存状态"""
        while not self.should_stop.is_set():
            available = psutil.virtual_memory().available
            if available < self.memory_limit:
                self.log("内存监控检测到系统可用内存低于安全限制")
                self.graceful_stop()
                break
            time.sleep(0.5)

    def graceful_stop(self):
        """安全停止"""
        self.log("安全停止中...")
        self.should_stop.set()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.emergency_btn.setEnabled(False)

    def emergency_stop(self):
        """紧急停止"""
        self.log("紧急停止中...")
        self.should_stop.set()
        self.allocated_blocks = []  # 立即释放内存
        
        # 更新UI
        available = psutil.virtual_memory().available
        self.allocated_label.setText("已分配: 0 MB")
        self.available_label.setText(f"可用内存: {available / (1024 * 1024):.2f} MB")
        self.progress_bar.setValue(0)
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.emergency_btn.setEnabled(False)
        
        self.log("紧急停止完成，所有内存已释放")

    def open_config_file(self):
        """打开配置文件 - 完全修复版本"""
        try:
            config_path = os.path.abspath("config.ini")
            self.log(f"打开配置文件: {config_path}")
            
            # 如果配置文件不存在则创建
            if not os.path.exists(config_path):
                self.config.create_default_config()
                self.log("已创建默认配置文件")
            
            # 跨平台打开文件
            if sys.platform == "win32":
                os.startfile(config_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", config_path])
            else:
                editors = ["xdg-open", "gedit", "kate", "mousepad", "pluma", "nano"]
                for editor in editors:
                    try:
                        subprocess.Popen([editor, config_path])
                        break
                    except FileNotFoundError:
                        continue
                else:
                    self.log("找不到文本编辑器，请手动打开配置文件")
            
            self.log("配置文件打开成功")
        except Exception as e:
            self.log(f"打开配置文件失败: {str(e)}")

    def on_complete(self):
        """压榨完成后的处理"""
        available = psutil.virtual_memory().available
        self.allocated_label.setText("已分配: 0 MB")
        self.available_label.setText(f"可用内存: {available / (1024 * 1024):.2f} MB")
        self.progress_bar.setValue(0)
        
        self.log("内存压榨完成")
        self.log(f"最终分配量: {self.total_allocated / (1024 * 1024):.2f} MB")
        self.log("内存已释放")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.emergency_btn.setEnabled(False)

    def log(self, message):
        """记录日志"""
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_area.appendPlainText(log_entry)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
        
        # 保存到日志文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        if hasattr(self, 'worker_thread') and self.worker_thread.is_alive():
            reply = QMessageBox.question(self, "确认退出", 
                                         "内存压榨仍在进行中，确定要退出吗？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        self.should_stop.set()
        self.allocated_blocks = []  # 确保释放内存
        event.accept()

if __name__ == "__main__":
    # 检查依赖库
    try:
        import psutil
    except ImportError:
        print("请安装依赖库: pip install psutil")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = MemorySqueezerGUI()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())