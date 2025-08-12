import sys
import os
import threading
import time
import configparser
import psutil
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                            QPushButton, QLabel, QProgressBar, QGroupBox,
                            QMessageBox, QHBoxLayout, QPlainTextEdit, QToolBar,
                            QSizePolicy, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon

class MemorySignals(QObject):
    """自定义信号类"""
    update_signal = pyqtSignal(int, float, float)  # 进度, 已分配, 可用内存
    alert_signal = pyqtSignal(str)
    complete_signal = pyqtSignal()

class ConfigManager:
    """配置文件管理"""
    def __init__(self):
        # 获取程序所在目录
        self.app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_file = os.path.join(self.app_dir, "config.ini")
        self.config = configparser.ConfigParser()
        
        # 确保配置文件存在
        if not os.path.exists(self.config_file):
            self.create_default_config()
        
        self.config.read(self.config_file)
    
    def create_default_config(self):
        """创建默认配置文件"""
        self.config["Settings"] = {
            "BlockSize": "10",
            "AllocationsPerSecond": "500",
            "ReservePercent": "2",
            "MemoryLimit": "256"
        }
        
        self.config["Window"] = {
            "Width": "600",
            "Height": "600"
        }
        
        self.config["Theme"] = {
            "ProgressBarColor": "0,128,255"
        }
        
        self.config["Logging"] = {
            "LogFile": "memory_squeezer.log"
        }
        
        with open(self.config_file, "w", encoding="utf-8") as f:
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
    """内存压榨器主窗口 - 修复按钮颜色问题"""
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.signals = MemorySignals()
        self.init_config()
        self.init_ui()
        self.connect_signals()
        self.memory_alert_shown = False
        self.show_warning()

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
        
        # 获取日志文件路径
        log_file_name = self.config.get_str("Logging", "LogFile", "memory_squeezer.log")
        self.log_file = os.path.join(self.config.app_dir, log_file_name)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Memory Squeezer started\n")

    def init_ui(self):
        """初始化用户界面 - 修复按钮颜色问题"""
        self.setWindowTitle("Memory Squeezer")
        width = self.config.get_int("Window", "Width", 600)
        height = self.config.get_int("Window", "Height", 600)
        self.setFixedSize(width, height)
        
        # 设置浅灰色背景
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        self.setPalette(palette)
        
        # 创建工具栏用于放置右上角按钮
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        
        # 在工具栏左侧添加占位符，将按钮推到右侧
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        # 添加关于按钮到工具栏右上角
        self.about_btn = QPushButton("关于我们")
        self.about_btn.setFixedSize(90, 30)
        toolbar.addWidget(self.about_btn)
        
        # 主内容区域
        main_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(15)
        
        # 内存状态区域
        status_group = QGroupBox("内存状态")
        status_layout = QVBoxLayout()
        
        self.allocated_label = QLabel("已分配: 0 MB")
        self.available_label = QLabel("可用内存: 0 MB")
        self.progress_bar = QProgressBar()
        
        status_layout.addWidget(self.allocated_label)
        status_layout.addWidget(self.available_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #d0d0d0; margin: 5px 0;")
        
        # 操作控制区域
        control_group = QGroupBox("操作控制")
        control_layout = QHBoxLayout()
        
        # 创建所有按钮
        self.start_btn = QPushButton("开始压榨")
        self.stop_btn = QPushButton("安全停止")
        self.emergency_btn = QPushButton("紧急停止")
        self.config_btn = QPushButton("配置")
        
        # 设置按钮样式 - 确保所有按钮显示颜色
        self.set_button_style()
        
        # 添加按钮到布局
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.emergency_btn)
        control_layout.addWidget(self.config_btn)
        control_group.setLayout(control_layout)
        
        # 分隔线
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet("color: #d0d0d0; margin: 5px 0;")
        
        # 日志显示区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout()
        
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        
        # 添加所有部件到主布局
        layout.addWidget(status_group)
        layout.addWidget(separator)
        layout.addWidget(control_group)
        layout.addWidget(separator2)
        layout.addWidget(log_group)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        # 初始按钮状态 - 所有按钮都启用并显示颜色
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.emergency_btn.setEnabled(True)
        self.config_btn.setEnabled(True)
        
        # 初始化日志
        self.log("程序已启动")
        self.log(f"块大小: {self.block_size/(1024 * 1024)}MB")
        self.log(f"分配速度: {self.allocations_per_second}次/秒")
        self.log(f"保留内存: {self.reserve_percent}%")
        self.log(f"安全限制: {self.memory_limit/(1024 * 1024)}MB")
        self.log("请点击'开始压榨'按钮启动内存压榨")

    def set_button_style(self):
        """设置按钮样式 - 确保所有按钮显示颜色"""
        button_style = """
            QPushButton {
                background-color: %s;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: %s;
            }
            QPushButton:disabled {
                background-color: %s;
                color: white;
            }
        """
        
        # 为每个按钮设置独特的颜色
        self.start_btn.setStyleSheet(button_style % ("#4CAF50", "#45a049", "#a5d6a7"))
        self.stop_btn.setStyleSheet(button_style % ("#FF9800", "#e68a00", "#ffcc80"))
        self.emergency_btn.setStyleSheet(button_style % ("#F44336", "#d32f2f", "#ffcdd2"))
        self.config_btn.setStyleSheet(button_style % ("#2196F3", "#0b7dda", "#bbdefb"))
        self.about_btn.setStyleSheet(button_style % ("#9C27B0", "#7B1FA2", "#e1bee7"))

    def connect_signals(self):
        """连接信号和槽"""
        self.start_btn.clicked.connect(self.start_squeeze)
        self.stop_btn.clicked.connect(self.graceful_stop)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.config_btn.clicked.connect(self.open_config_file)
        self.about_btn.clicked.connect(self.show_about_dialog)
        self.signals.update_signal.connect(self.update_status)
        self.signals.alert_signal.connect(self.show_alert)
        self.signals.complete_signal.connect(self.on_complete)

    def show_about_dialog(self):
        """显示关于对话框"""
        about_text = """
        <h2>Memory Squeezer</h2>
        <p>版本 1.2.0</p>
        <p>专业的内存压力测试工具</p>
        """
        QMessageBox.about(self, "关于我们", about_text)

    def open_config_file(self):
        """打开配置文件"""
        try:
            config_path = self.config.config_file
            self.log(f"尝试打开配置文件: {config_path}")
            
            if not os.path.exists(config_path):
                self.log("配置文件不存在，创建默认配置")
                self.config.create_default_config()
            
            if sys.platform == "win32":
                os.startfile(config_path)
                self.log("Windows系统打开配置文件")
            elif sys.platform == "darwin":
                subprocess.run(["open", config_path])
                self.log("macOS系统打开配置文件")
            else:
                editors = ["xdg-open", "gedit", "kate", "mousepad", "pluma", "nano"]
                for editor in editors:
                    try:
                        subprocess.Popen([editor, config_path])
                        self.log(f"使用 {editor} 打开配置文件")
                        break
                    except FileNotFoundError:
                        continue
                else:
                    self.log("找不到合适的文本编辑器")
                    self.show_alert("找不到合适的文本编辑器，请手动打开配置文件")
            
            self.log("配置文件打开成功")
        except Exception as e:
            error_msg = f"打开配置文件失败: {str(e)}"
            self.log(error_msg)
            self.show_alert(error_msg)

    def show_alert(self, message):
        """显示警告信息"""
        self.log(message)
        QMessageBox.warning(self, "警告", message)

    def update_status(self, progress, allocated, available):
        """更新UI状态"""
        self.progress_bar.setValue(progress)
        self.allocated_label.setText(f"已分配: {allocated / (1024 * 1024):.2f} MB")
        self.available_label.setText(f"可用内存: {available / (1024 * 1024):.2f} MB")

    def show_warning(self):
        """显示四重确认对话框"""
        reply = QMessageBox.question(
            self, '警告', 
            '此程序将消耗大量系统内存，可能导致系统不稳定！\n\n确定要继续吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            self.log("用户取消操作")
            return False
            
        reply = QMessageBox.warning(
            self, '风险确认',
            '此操作可能导致以下严重后果：\n- 系统运行缓慢\n- 其他程序崩溃\n- 需要强制重启\n\n确认了解风险？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
        if reply != QMessageBox.Yes:
            self.log("用户取消操作")
            return False
            
        available_mem = psutil.virtual_memory().available
        if available_mem < 2 * 1024 * 1024 * 1024:  # 小于2GB
            reply = QMessageBox.critical(
                self, '内存不足',
                f'检测到当前系统可用内存较少 ({available_mem/(1024 * 1024):.2f} MB)，继续运行可能立即导致系统无响应\n\n仍要继续吗？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                
            if reply != QMessageBox.Yes:
                self.log("用户取消操作")
                return False
                
        reply = QMessageBox.warning(
            self, '最终确认',
            '这是最后一次警告！\n按下确定后将开始不可逆的内存消耗过程\n\n确定执行？',
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
            
        if reply != QMessageBox.Ok:
            self.log("用户取消操作")
            return False
            
        return True

    def start_squeeze(self):
        """开始内存压榨"""
        if not self.show_warning():
            return
            
        # 禁用开始按钮
        self.start_btn.setEnabled(False)
        
        available_mem = psutil.virtual_memory().available
        reserve = available_mem * (self.reserve_percent / 100)
        self.max_allocation = available_mem - reserve
        
        self.log("=== 内存压榨启动 ===")
        self.log(f"目标分配量: {self.max_allocation / (1024 * 1024):.2f} MB")
        self.log(f"保留内存: {reserve / (1024 * 1024):.2f} MB ({self.reserve_percent}%)")
        self.log(f"分配速度: {self.allocations_per_second} 次/秒")
        
        self.allocated_blocks = []
        self.total_allocated = 0
        self.should_stop.clear()
        
        self.worker_thread = threading.Thread(target=self.squeeze_memory)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
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
                    block = bytearray(self.block_size)
                    self.allocated_blocks.append(block)
                    self.total_allocated += self.block_size
                    next_alloc_time += interval
                    
                    progress = (self.total_allocated / self.max_allocation) * 100
                    available = psutil.virtual_memory().available
                    self.signals.update_signal.emit(int(progress), self.total_allocated, available)
                    
                    if available < self.memory_limit:
                        self.signals.alert_signal.emit("系统可用内存低于安全限制，自动停止")
                        break
                
                time.sleep(0.001)
                
        except MemoryError:
            self.signals.alert_signal.emit("内存耗尽!")
        except Exception as e:
            self.signals.alert_signal.emit(f"发生错误: {str(e)}")
        finally:
            self.signals.complete_signal.emit()

    def monitor_memory(self):
        """监控内存状态"""
        while not self.should_stop.is_set():
            available = psutil.virtual_memory().available
            if available < self.memory_limit:
                if not self.memory_alert_shown:
                    self.signals.alert_signal.emit("系统可用内存低于安全限制，自动停止")
                    self.memory_alert_shown = True
                self.should_stop.set()
                break
            time.sleep(0.5)

    def graceful_stop(self):
        """安全停止"""
        self.log("安全停止中...")
        self.should_stop.set()

    def emergency_stop(self):
        """紧急停止"""
        self.log("紧急停止中...")
        self.should_stop.set()
        self.allocated_blocks = []
        self.total_allocated = 0
        available = psutil.virtual_memory().available
        self.signals.update_signal.emit(0, 0, available)

    def on_complete(self):
        """操作完成处理"""
        self.log("操作完成")
        self.log(f"最终分配量: {self.total_allocated / (1024 * 1024):.2f} MB")
        self.start_btn.setEnabled(True)

    def log(self, message):
        """记录日志"""
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_area.appendPlainText(log_entry)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, 'worker_thread') and self.worker_thread.is_alive():
            confirm = QMessageBox.question(
                self, "确认退出",
                "内存压榨仍在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.No:
                event.ignore()
                return
        
        self.should_stop.set()
        self.allocated_blocks = []
        event.accept()

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("请先安装依赖库: pip install psutil")
        sys.exit(1)
    
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print("请先安装依赖库: pip install PyQt5")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    
    # 设置应用字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    window = MemorySqueezerGUI()
    window.show()
    sys.exit(app.exec_())