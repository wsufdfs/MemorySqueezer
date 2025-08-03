import sys
import os
import threading
import time
import configparser
import psutil
import multiprocessing
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                            QPushButton, QLabel, QProgressBar, QGroupBox,
                            QMessageBox, QHBoxLayout, QPlainTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPalette

class MemorySignals(QObject):
    """自定义信号类"""
    update_signal = pyqtSignal(int, float, float)  # 进度, 已分配, 可用内存
    alert_signal = pyqtSignal(str)
    complete_signal = pyqtSignal()

class ConfigManager:
    """配置文件管理"""
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(config_file):
            self.create_default_config()
        
        self.config.read(config_file)
    
    def create_default_config(self):
        """创建默认配置文件"""
        self.config["Settings"] = {
            "BlockSize": "10",
            "ShowProgress": "true",
            "AllocationsPerSecond": "500",
            "ReservePercent": "2",
            "MemoryLimit": "256",
            "UseMultiprocessing": "false",
            "WorkerProcesses": "4"
        }
        
        self.config["Window"] = {
            "Width": "600",
            "Height": "500"
        }
        
        self.config["Theme"] = {
            "Theme": "Light",
            "ProgressBarColor": "0,128,255"
        }
        
        self.config["Logging"] = {
            "LogFile": "memory_squeezer.log",
            "LogLevel": "INFO"
        }
        
        with open(self.config_file, "w") as f:
            self.config.write(f)
    
    def get_int(self, section, key, default=0):
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def get_float(self, section, key, default=0.0):
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def get_bool(self, section, key, default=False):
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def get_str(self, section, key, default=""):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def get_rgb(self, section, key, default=(0, 128, 255)):
        try:
            color_str = self.config.get(section, key)
            r, g, b = map(int, color_str.split(","))
            return r, g, b
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default

class MemorySqueezerGUI(QMainWindow):
    """内存压榨器主窗口"""
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.init_config()
        self.init_ui()
        self.connect_signals()
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
        self.show_progress = self.config.get_bool("Settings", "ShowProgress", True)
        self.use_multiprocessing = self.config.get_bool("Settings", "UseMultiprocessing", False)
        self.worker_processes = self.config.get_int("Settings", "WorkerProcesses", 4)
        self.log_file = self.config.get_str("Logging", "LogFile", "memory_squeezer.log")
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Memory Squeezer started\n")
        
        self.signals = MemorySignals()
        self.memory_alert_shown = False
        self.progress_queue = None  # 用于多进程通信的队列

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Memory Squeezer")
        width = self.config.get_int("Window", "Width", 600)
        height = self.config.get_int("Window", "Height", 500)
        self.setFixedSize(width, height)
        
        self.apply_theme()
        
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # 状态显示组
        status_group = QGroupBox("内存状态")
        status_layout = QVBoxLayout()
        
        self.allocated_label = QLabel("已分配: 0 MB")
        self.available_label = QLabel("可用内存: 0 MB")
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        
        r, g, b = self.config.get_rgb("Theme", "ProgressBarColor", (0, 128, 255))
        self.progress_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: rgb({r}, {g}, {b});
            }}
        """)
        
        status_layout.addWidget(self.allocated_label)
        status_layout.addWidget(self.available_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        
        # 控制按钮组
        control_group = QGroupBox("操作控制")
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始压榨")
        self.stop_btn = QPushButton("安全停止")
        self.emergency_btn = QPushButton("紧急停止")
        self.config_btn = QPushButton("配置")
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.emergency_btn)
        control_layout.addWidget(self.config_btn)
        control_group.setLayout(control_layout)
        
        # 日志显示
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout()
        
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        
        layout.addWidget(status_group)
        layout.addWidget(control_group)
        layout.addWidget(log_group)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        self.stop_btn.setEnabled(False)
        self.emergency_btn.setEnabled(False)
        
        self.log("程序已启动")
        self.log(f"配置参数: 块大小={self.block_size/(1024 * 1024)}MB, 分配速度={self.allocations_per_second}次/秒")
        self.log(f"保留内存: {self.reserve_percent}%, 安全限制: {self.memory_limit/(1024 * 1024)}MB")
        self.log("请点击'开始压榨'按钮启动内存压榨")

    def apply_theme(self):
        """应用主题设置"""
        theme = self.config.get_str("Theme", "Theme", "Light")
        
        if theme.lower() == "dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            QApplication.setPalette(palette)
        elif theme.lower() == "blue":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(240, 248, 255))
            palette.setColor(QPalette.WindowText, Qt.darkBlue)
            palette.setColor(QPalette.Base, QColor(225, 238, 255))
            palette.setColor(QPalette.AlternateBase, QColor(200, 225, 255))
            palette.setColor(QPalette.ToolTipBase, Qt.darkBlue)
            palette.setColor(QPalette.ToolTipText, Qt.darkBlue)
            palette.setColor(QPalette.Text, Qt.darkBlue)
            palette.setColor(QPalette.Button, QColor(173, 216, 230))
            palette.setColor(QPalette.ButtonText, Qt.darkBlue)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.Highlight, QColor(0, 0, 255))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            QApplication.setPalette(palette)

    def connect_signals(self):
        """连接信号和槽"""
        self.start_btn.clicked.connect(self.start_squeeze)
        self.stop_btn.clicked.connect(self.graceful_stop)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.config_btn.clicked.connect(self.open_config_file)
        self.signals.update_signal.connect(self.update_status)
        self.signals.alert_signal.connect(self.show_alert)
        self.signals.complete_signal.connect(self.on_complete)

    def show_warning(self):
        """显示四重确认对话框"""
        # 第一重确认
        reply = QMessageBox.question(
            self, '警告', 
            '此程序将消耗大量系统内存，可能导致系统不稳定！\n\n确定要继续吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            self.log("用户取消操作")
            return False
            
        # 第二重确认
        reply = QMessageBox.warning(
            self, '风险确认',
            '此操作可能导致以下严重后果：\n- 系统运行缓慢\n- 其他程序崩溃\n- 需要强制重启\n\n确认了解风险？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
        if reply != QMessageBox.Yes:
            self.log("用户取消操作")
            return False
            
        # 第三重确认（内存检查）
        available_mem = psutil.virtual_memory().available
        if available_mem < 2 * 1024 * 1024 * 1024:  # 小于2GB
            reply = QMessageBox.critical(
                self, '内存不足',
                f'检测到当前系统可用内存较少 ({available_mem/(1024 * 1024):.2f} MB)，继续运行可能立即导致系统无响应\n\n仍要继续吗？',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                
            if reply != QMessageBox.Yes:
                self.log("用户取消操作")
                return False
                
        # 第四重确认
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
        
        if self.use_multiprocessing:
            self.log(f"使用多进程加速: {self.worker_processes} 个工作进程")
            self.progress_queue = multiprocessing.Queue()  # 创建进程间通信队列
        else:
            self.progress_queue = None
        
        self.allocated_blocks = []
        self.total_allocated = 0
        self.should_stop.clear()
        
        if self.use_multiprocessing:
            self.worker_thread = threading.Thread(target=self.squeeze_memory_multiprocess)
        else:
            self.worker_thread = threading.Thread(target=self.squeeze_memory)
            
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        self.monitor_thread = threading.Thread(target=self.monitor_memory)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def squeeze_memory(self):
        """单线程内存压榨"""
        try:
            interval = 1.0 / self.allocations_per_second
            next_alloc_time = time.time()
            
            while not self.should_stop.is_set() and self.total_allocated < self.max_allocation:
                current_time = time.time()
                if current_time >= next_alloc_time:
                    block = bytearray(os.urandom(self.block_size))
                    
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

    def squeeze_memory_multiprocess(self):
        """多进程内存压榨 - 修复版"""
        try:
            pool = multiprocessing.Pool(processes=self.worker_processes)
            
            per_process_target = self.max_allocation // self.worker_processes
            
            results = []
            for _ in range(self.worker_processes):
                result = pool.apply_async(
                    worker_process_function, 
                    (per_process_target, self.block_size, self.memory_limit)
                )
                results.append(result)
            
            # 在主进程中监控进度
            while not self.should_stop.is_set():
                time.sleep(0.1)
                
                # 检查内存限制
                available = psutil.virtual_memory().available
                if available < self.memory_limit:
                    self.signals.alert_signal.emit("系统可用内存低于安全限制，自动停止")
                    break
                
                # 计算总进度(简化版，实际应该从各进程收集进度)
                # 这里使用模拟进度，实际应用中应该通过队列获取精确进度
                simulated_progress = min(100, (self.total_allocated / self.max_allocation) * 100)
                self.signals.update_signal.emit(int(simulated_progress), self.total_allocated, available)
            
            # 等待所有进程完成
            pool.close()
            pool.join()
            
            # 获取最终结果
            self.total_allocated = sum(result.get() for result in results)
            self.signals.update_signal.emit(100, self.total_allocated, psutil.virtual_memory().available)
            self.signals.complete_signal.emit()
            
        except Exception as e:
            self.signals.alert_signal.emit(f"发生错误: {str(e)}")
        finally:
            if 'pool' in locals():
                pool.close()
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

    def update_status(self, progress, allocated, available):
        """更新UI状态"""
        self.progress_bar.setValue(progress)
        self.allocated_label.setText(f"已分配: {allocated / (1024 * 1024):.2f} MB")
        self.available_label.setText(f"可用内存: {available / (1024 * 1024):.2f} MB")

    def show_alert(self, message):
        """显示警告信息"""
        self.log(message)
        QMessageBox.warning(self, "警告", message)

    def on_complete(self):
        """操作完成处理"""
        self.log("操作完成")
        self.log(f"最终分配量: {self.total_allocated / (1024 * 1024):.2f} MB")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.emergency_btn.setEnabled(False)

    def log(self, message):
        """记录日志"""
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_area.appendPlainText(log_entry)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

    def open_config_file(self):
        """打开配置文件"""
        config_path = os.path.abspath("config.ini")
        self.log(f"打开配置文件: {config_path}")
        
        if sys.platform == "win32":
            os.startfile(config_path)
        elif sys.platform == "darwin":
            os.system(f"open {config_path}")
        else:
            os.system(f"xdg-open {config_path}")

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

def worker_process_function(target_allocation, block_size, memory_limit):
    """工作进程函数 - 修复版"""
    allocated = 0
    blocks = []
    
    try:
        while allocated < target_allocation:
            available = psutil.virtual_memory().available
            if available < memory_limit:
                break
                
            block = bytearray(os.urandom(block_size))
            blocks.append(block)
            allocated += block_size
            time.sleep(0.001)
    except MemoryError:
        pass
    
    return allocated

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
    window = MemorySqueezerGUI()
    window.show()
    sys.exit(app.exec_())