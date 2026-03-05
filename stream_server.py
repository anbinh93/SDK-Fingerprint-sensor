#!/usr/bin/env python3
"""
Persistent Fingerprint Streaming Server for Jetson Nano
Keeps USB connection open and streams frames continuously via stdin/stdout.

Protocol:
- Input commands (one per line):
  - "CAPTURE" - capture one frame
  - "START <fps>" - start continuous streaming at fps rate  
  - "STOP" - stop streaming
  - "LED <color>" - set LED (0=off, 1=red, 2=green, 4=blue, 7=white)
  - "INFO" - get sensor info
  - "QUIT" - exit

- Output (one per line):
  - "IMAGE:<base64 data>" - captured image
  - "OK:<message>" - success response
  - "ERROR:<message>" - error response
  - "INFO:<user_count>:<level>" - sensor info
"""

import sys
import base64
import time
import threading
import queue

# Add SDK path
sys.path.insert(0, '/home/binhan3/SDK-Fingerprint-sensor')

try:
    from fingerprint import FingerprintReader, LED
except ImportError:
    print("ERROR:Cannot import fingerprint module", flush=True)
    sys.exit(1)


class StreamingServer:
    def __init__(self):
        self.fp = FingerprintReader()
        self.streaming = False
        self.fps = 10
        self.running = True
        self.cmd_queue = queue.Queue()
        
    def run(self):
        # Open device
        if not self.fp.open():
            print("ERROR:Device not found", flush=True)
            return
        
        print("OK:Device opened", flush=True)
        
        # Start command reader thread
        cmd_thread = threading.Thread(target=self._read_commands, daemon=True)
        cmd_thread.start()
        
        try:
            self._main_loop()
        finally:
            self.fp.close()
            
    def _read_commands(self):
        """Read commands from stdin in background."""
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    self.running = False
                    break
                self.cmd_queue.put(line.strip())
            except:
                self.running = False
                break
                
    def _main_loop(self):
        last_capture = 0
        
        while self.running:
            # Process commands (non-blocking)
            try:
                while True:
                    cmd = self.cmd_queue.get_nowait()
                    self._handle_command(cmd)
            except queue.Empty:
                pass
            
            # Stream if enabled
            if self.streaming:
                now = time.time()
                interval = 1.0 / self.fps
                
                if now - last_capture >= interval:
                    self._capture_and_send()
                    last_capture = now
                else:
                    # Small sleep to prevent busy loop
                    time.sleep(0.005)
            else:
                # Longer sleep when not streaming
                time.sleep(0.01)
                
    def _handle_command(self, cmd: str):
        parts = cmd.upper().split()
        if not parts:
            return
            
        action = parts[0]
        
        if action == "QUIT":
            self.running = False
            print("OK:Quitting", flush=True)
            
        elif action == "CAPTURE":
            self._capture_and_send()
            
        elif action == "START":
            if len(parts) > 1:
                try:
                    self.fps = max(1, min(30, int(parts[1])))
                except:
                    self.fps = 10
            self.streaming = True
            print(f"OK:Streaming at {self.fps} FPS", flush=True)
            
        elif action == "STOP":
            self.streaming = False
            print("OK:Stopped", flush=True)
            
        elif action == "LED":
            color = 0
            if len(parts) > 1:
                try:
                    color = int(parts[1])
                except:
                    pass
            if color == 0:
                self.fp.led_off()
            else:
                self.fp.led_on(color)
            print(f"OK:LED {color}", flush=True)
            
        elif action == "INFO":
            count = self.fp.get_user_count()
            level = self.fp.get_compare_level()
            print(f"INFO:{count}:{level}", flush=True)
            
        else:
            print(f"ERROR:Unknown command: {action}", flush=True)
            
    def _capture_and_send(self):
        try:
            image = self.fp.capture_image()
            if image:
                b64 = base64.b64encode(image).decode('ascii')
                print(f"IMAGE:{b64}", flush=True)
            else:
                print("ERROR:Capture returned None", flush=True)
        except Exception as e:
            print(f"ERROR:Capture exception: {e}", flush=True)


if __name__ == "__main__":
    server = StreamingServer()
    server.run()
