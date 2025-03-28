import sys
import json
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSpinBox

CONFIG_FILE = "config.json"

class ServerStartupGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.project_root = ""
        self.setWindowTitle("Server Startup")
        self.setGeometry(100, 100, 400, 250)

        self.layout = QVBoxLayout()

        # IP Field for Servo Arm 1
        self.label1 = QLabel("Servo Arm 1 IP:")
        self.layout.addWidget(self.label1)

        self.ip_input1 = QLineEdit()
        self.layout.addWidget(self.ip_input1)

        # IP Field for Servo Arm 2
        self.label2 = QLabel("Servo Arm 2 IP:")
        self.layout.addWidget(self.label2)

        self.ip_input2 = QLineEdit()
        self.layout.addWidget(self.ip_input2)

        # Update Frequency Field (1-70 Hz)
        self.freq_label = QLabel("Update Frequency (Hz):")
        self.layout.addWidget(self.freq_label)

        self.freq_input = QSpinBox()
        self.freq_input.setRange(1, 70)  # Restrict range from 1 to 70 Hz
        self.layout.addWidget(self.freq_input)

        # Load last used values
        self.load_config()

        # Start Button
        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        self.layout.addWidget(self.start_button)

        self.setLayout(self.layout)

        
    def get_project_root(self):
        # Start from the directory of the current script
            current_dir = Path(__file__).resolve().parent
            # Traverse up until you find the 'venv' folder or another marker
            for parent in current_dir.parents:
                if (parent / "venv").exists():  # Check if 'venv' folder exists
                    return parent
            raise FileNotFoundError("Could not find project root (containing 'venv' folder)")

    def get_venv_python(self):
        # Get the project root
        project_root = self.get_project_root()
        self.project_root = project_root
        # Determine the path to the venv's Python executable based on the OS
        venv_python = project_root / "venv" / "Scripts" / "python.exe"
        
        # Verify the Python executable exists
        if not venv_python.exists():
            raise FileNotFoundError(f"Python executable not found at: {venv_python}")
        return str(venv_python)

    def load_config(self):
        """Load the last used IPs and frequency from config.json."""
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.ip_input1.setText(config.get("servo_ip_1", ""))
                self.ip_input2.setText(config.get("servo_ip_2", ""))
                self.freq_input.setValue(config.get("update_frequency", 10))  # Default to 10 Hz
        except FileNotFoundError:
            pass

    def save_config(self, ip1, ip2, freq):
        """Save the entered IPs and frequency to config.json."""
        with open(CONFIG_FILE, "w") as f:
            json.dump({"servo_ip_1": ip1, "servo_ip_2": ip2, "update_frequency": freq}, f)

    def start_server(self):
        """Start the Quart server with the entered IPs and frequency."""
        ip1 = self.ip_input1.text().strip()
        ip2 = self.ip_input2.text().strip()
        freq = self.freq_input.value()

        if not ip1 or not ip2:
            QMessageBox.warning(self, "Input Error", "Please enter valid IP addresses for both servo arms.")
            return

        # Save values for next time
        self.save_config(ip1, ip2, freq)

        # Start Quart server as a separate process
        try:
            venv_python = self.get_venv_python()
            server_path = self.project_root / "src" / "palvelin.py"

            subprocess.Popen([venv_python, server_path, "--server_left", ip1, "--server_right", ip2, "--freq", str(freq)])
            QMessageBox.information(self, "Success", "Server started successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server: {str(e)}")

# Run the GUI
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServerStartupGUI()
    window.show()
    sys.exit(app.exec())
