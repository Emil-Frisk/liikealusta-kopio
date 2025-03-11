import subprocess
import os
import signal
import time

class ModuleManager:
    def __init__(self, logger):
        self.processes = {}
        self.logger = logger

    def launch_module(self, module_path, args=None):
        """Launch a Python module and return PID or none if error"""
        try:
            cmd = ['python', '-m', module_path]
            if args:
                cmd.extend(args)
                
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            pid = process.pid
            self.processes[pid] = {
                'process': process,
                'module': module_path,
                'launch-time': time.time()
            }
            self.logger.info(f"Launched {module_path} with PID: {process.pid}")
            return pid
            
        except Exception as e:
            self.logger.error(f"Failed to launch process {module_path}: {e}")
            return None

    def cleanup_module(self, pid):
        """Cleanup a specific module by module path"""
        if pid not in self.processes:
            self.logger.error(f"No process found with PID: {pid}")
            return False
            
        process_info = self.processes[pid]
        process = process_info['process']
        
        try:
            # First try graceful termination
            if os.name == 'nt':  # Windows
                process.send_signal(signal.CTRL_C_EVENT)
            else:  # Unix-like
                process.terminate()
                
            # Wait for process to exit
            process.wait(timeout=5)
            
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't stop
            process.kill()
            self.logger.warning(f"Force killed process {process_info['module']} with PID {process.pid}")

        except Exception as e:
            self.logger.error(f"Error during module cleanup: {e}")
            return False
            
        finally:
            # Cleanup regardless of success
            del self.processes[pid]
            self.logger.error(f"Cleaned up module with PID {pid}")
            return True

    def cleanup_all(self):
        """Cleanup all running modules"""
        for pid in list(self.processes.keys()):
            self.cleanup_module(pid)

