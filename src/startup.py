import sys
import json
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox
from setup_logging import setup_logging

CONFIG_FILE = "config.json"

class ServerStartupGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = setup_logging("startup", "startup.log")
        self.project_root = ""
        self.setWindowTitle("Server Startup")
        self.setGeometry(100, 100, 400, 350)
        
        self.layout = QVBoxLayout()

        # IP Field for Servo Arm 1
        self.layout.addWidget(QLabel("Servo Arm 1 IP:"))
        self.ip_input1 = QLineEdit()
        self.layout.addWidget(self.ip_input1)

        # IP Field for Servo Arm 2
        self.layout.addWidget(QLabel("Servo Arm 2 IP:"))
        self.ip_input2 = QLineEdit()
        self.layout.addWidget(self.ip_input2)

        # Update Frequency Field (1-70 Hz)
        self.layout.addWidget(QLabel("Update Frequency (Hz):"))
        self.freq_input = QSpinBox()
        self.freq_input.setRange(1, 70)
        self.layout.addWidget(self.freq_input)

        # Speed Field
        self.layout.addWidget(QLabel("Speed (mm/sec):"))
        self.speed_input = QSpinBox()
        self.speed_input.setRange(1, 500)  # Adjust range as needed
        self.layout.addWidget(self.speed_input)

        # Acceleration Field
        self.layout.addWidget(QLabel("Acceleration (mm/s^2):"))
        self.accel_input = QSpinBox()
        self.accel_input.setRange(1, 1000)  # Adjust range as needed
        self.layout.addWidget(self.accel_input)

        # Load last used values
        self.load_config()

        # Start Button
        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        self.layout.addWidget(self.start_button)
        
        # Shutdown Button (Initially Disabled)
        self.shutdown_button = QPushButton("Shutdown Server")
        self.shutdown_button.setEnabled(False)
        self.shutdown_button.clicked.connect(self.shutdown_server)
        self.layout.addWidget(self.shutdown_button)
        
        self.setLayout(self.layout)

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.ip_input1.setText(config.get("servo_ip_1", ""))
                self.ip_input2.setText(config.get("servo_ip_2", ""))
                self.freq_input.setValue(config.get("update_frequency", 10))
                self.speed_input.setValue(config.get("speed", 50))
                self.accel_input.setValue(config.get("acceleration", 100))
        except FileNotFoundError:
            pass

    def save_config(self, ip1, ip2, freq, speed, accel):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "servo_ip_1": ip1,
                "servo_ip_2": ip2,
                "update_frequency": freq,
                "speed": speed,
                "acceleration": accel
            }, f)

    def get_project_root(self):
        current_dir = Path(__file__).resolve().parent
        for parent in current_dir.parents:
            if (parent / "venv").exists():
                return parent
        raise FileNotFoundError("Could not find project root (containing 'venv' folder)")

    def get_venv_python(self):
        project_root = self.get_project_root()
        self.project_root = project_root
        venv_python = project_root / "venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            raise FileNotFoundError(f"Python executable not found at: {venv_python}")
        return str(venv_python)

    def start_server(self):
        ip1 = self.ip_input1.text().strip()
        ip2 = self.ip_input2.text().strip()
        freq = self.freq_input.value()
        speed = self.speed_input.value()
        accel = self.accel_input.value()

        if not ip1 or not ip2:
            QMessageBox.warning(self, "Input Error", "Please enter valid IP addresses for both servo arms.")
            return

        self.save_config(ip1, ip2, freq, speed, accel)
        
        try:
            venv_python = self.get_venv_python()
            server_path = self.project_root / "src" / "palvelin.py"
            cmd = f'start /B "" "{venv_python}" "{server_path}" --server_left "{ip1}" --server_right "{ip2}" --freq "{freq}" --speed "{speed}" --accel "{accel}"'
            self.process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            self.logger.info(f"Server launched with PID: {self.process.pid}")
            QMessageBox.information(self, "Success", "Server started successfully!")
            self.shutdown_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server: {str(e)}")

    def shutdown_server(self):
        try:
            response = subprocess.run(["curl", "-X", "POST", "http://localhost:5000/shutdown"], capture_output=True, text=True)
            if response.returncode == 0:
                QMessageBox.information(self, "Success", "Server shutdown successfully!")
                self.shutdown_button.setEnabled(False)
            else:
                QMessageBox.warning(self, "Warning", "Failed to shutdown server!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to shutdown server: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServerStartupGUI()
    window.show()
    sys.exit(app.exec())