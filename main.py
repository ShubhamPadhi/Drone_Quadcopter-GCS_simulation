import socket
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import math
import csv  
from datetime import datetime
UDP_IP = "127.0.0.1"
UDP_PORT_RX = 9001
UDP_PORT_TX = 9000  
BG_COLOR = "#2e2e2e"
FG_COLOR = "#ffffff"
ACCENT_COLOR = "#007acc"
PANEL_COLOR = "#3e3e3e"
SUCCESS_COLOR = "#28a745"
WARNING_COLOR = "#ffc107"
DANGER_COLOR = "#dc3545"

class ModernDroneGCS:
    def __init__(self, root):
        self.root = root
        self.root.title("AeroCommand GCS - Advanced Dashboard")
        self.root.geometry("900x650")
        self.root.configure(bg=BG_COLOR)
        self.telemetry = {"position": [0,0,0], "orientation": [0,0,0], "battery": 100, "mode": "DISCONNECTED"}
        self.running = True
        self.altitude_history = [0] * 50
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_filename = f"flight_log_{timestamp}.csv"
        self.log_file = open(self.log_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(["Timestamp", "Mode", "Battery", "X", "Y", "Z", "Yaw"])
        print(f"Logging telemetry to: {self.log_filename}")

        self.sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_rx.bind((UDP_IP, UDP_PORT_RX))
        self.sock_rx.setblocking(False)
        self.sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.setup_styles()

        main_container = tk.Frame(root, bg=BG_COLOR)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_top_bar(main_container)

        middle_frame = tk.Frame(main_container, bg=BG_COLOR)
        middle_frame.pack(fill="both", expand=True, pady=10)

        self.create_visuals_panel(middle_frame)

        self.create_controls_panel(middle_frame)
        self.create_bottom_bar(main_container)
        self.thread = threading.Thread(target=self.listen_telemetry, daemon=True)
        self.thread.start()
        self.update_gui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background=PANEL_COLOR, relief="flat")
        style.configure("TLabel", background=PANEL_COLOR, foreground=FG_COLOR, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground=ACCENT_COLOR)
        style.configure("Value.TLabel", font=("Consolas", 12, "bold"), foreground="#00ff00")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6, background=ACCENT_COLOR, foreground="white", borderwidth=0)
        style.map("TButton", background=[("active", "#005f9e")])
        style.configure("Danger.TButton", background=DANGER_COLOR)
        style.map("Danger.TButton", background=[("active", "#a71d2a")])
        style.configure("TEntry", fieldbackground="#505050", foreground="white", insertcolor="white")
        style.configure("Green.Horizontal.TProgressbar", 
                        troughcolor="#444444", 
                        background=SUCCESS_COLOR, 
                        lightcolor=SUCCESS_COLOR, 
                        darkcolor=SUCCESS_COLOR,
                        bordercolor=PANEL_COLOR,
                        thickness=20)

    def create_top_bar(self, parent):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", ipady=10)
        self.lbl_mode = ttk.Label(frame, text="MODE: WAIT", font=("Segoe UI", 16, "bold"), foreground=WARNING_COLOR)
        self.lbl_mode.pack(side="left", padx=20)
        self.lbl_bat_text = ttk.Label(frame, text="BATTERY: 100%", font=("Segoe UI", 12, "bold"))
        self.lbl_bat_text.pack(side="right", padx=(10, 20))
        self.progress_bat = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate", style="Green.Horizontal.TProgressbar")
        self.progress_bat.pack(side="right")
        self.progress_bat['value'] = 100
    def create_visuals_panel(self, parent):
        frame = tk.Frame(parent, bg=BG_COLOR)
        frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        compass_frame = ttk.Frame(frame, style="Card.TFrame")
        compass_frame.pack(fill="both", expand=True, pady=(0, 10)) 
        ttk.Label(compass_frame, text="Drone Orientation (Top Down)", style="Header.TLabel").pack(pady=5)
        
        self.canvas_compass = tk.Canvas(compass_frame, bg="black", height=200, highlightthickness=0)
        self.canvas_compass.pack(fill="both", expand=True, padx=10, pady=10)
        self.draw_compass_base()

        alt_frame = ttk.Frame(frame, style="Card.TFrame")
        alt_frame.pack(fill="both", expand=True)
        ttk.Label(alt_frame, text="Live Altitude (Z-Axis)", style="Header.TLabel").pack(pady=5)
        
        self.canvas_graph = tk.Canvas(alt_frame, bg="black", height=150, highlightthickness=0)
        self.canvas_graph.pack(fill="both", expand=True, padx=10, pady=10)

    def create_controls_panel(self, parent):
        frame = tk.Frame(parent, bg=BG_COLOR, width=300)
        frame.pack(side="right", fill="y")
        
        data_card = ttk.Frame(frame, style="Card.TFrame", padding=15)
        data_card.pack(fill="x", pady=(0, 10)) 
        ttk.Label(data_card, text="Telemetry Data", style="Header.TLabel").pack(anchor="w")
        self.lbl_pos_x = ttk.Label(data_card, text="X: 0.00 m")
        self.lbl_pos_x.pack(anchor="w")
        self.lbl_pos_y = ttk.Label(data_card, text="Y: 0.00 m")
        self.lbl_pos_y.pack(anchor="w")
        self.lbl_pos_z = ttk.Label(data_card, text="Z: 0.00 m")
        self.lbl_pos_z.pack(anchor="w")
        mode_card = ttk.Frame(frame, style="Card.TFrame", padding=15)
        mode_card.pack(fill="x", pady=(0, 10))
        ttk.Label(mode_card, text="Quick Actions", style="Header.TLabel").pack(anchor="w", pady=(0, 5))
        
        grid_frame = tk.Frame(mode_card, bg=PANEL_COLOR)
        grid_frame.pack(fill="x")
        
        ttk.Button(grid_frame, text="TAKEOFF", command=lambda: self.send_command("mode", "TAKEOFF")).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(grid_frame, text="LAND", command=lambda: self.send_command("mode", "LAND")).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(grid_frame, text="RTL", command=lambda: self.send_command("mode", "RTL")).pack(side="left", fill="x", expand=True, padx=2)
        mission_card = ttk.Frame(frame, style="Card.TFrame", padding=15)
        mission_card.pack(fill="x", pady=(0, 10))
        ttk.Label(mission_card, text="Mission Planning", style="Header.TLabel").pack(anchor="w")
        
        ttk.Label(mission_card, text="Waypoints JSON:").pack(anchor="w")
        self.entry_wp = ttk.Entry(mission_card)
        self.entry_wp.insert(0, "[[0,0,2], [2,2,2], [-2,2,2]]")
        self.entry_wp.pack(fill="x", pady=5)
        
        ttk.Button(mission_card, text="UPLOAD & FLY", command=self.upload_mission).pack(fill="x", pady=2)
        sys_card = ttk.Frame(frame, style="Card.TFrame", padding=15)
        sys_card.pack(fill="x")
        ttk.Button(sys_card, text="EMERGENCY REBOOT", style="Danger.TButton", command=self.send_reboot).pack(fill="x")
    def create_bottom_bar(self, parent):
        self.lbl_status = tk.Label(parent, text="System Ready.", bg=BG_COLOR, fg="#888888", font=("Segoe UI", 9), anchor="w")
        self.lbl_status.pack(fill="x", pady=(5,0))


    def draw_compass_base(self):
        w = 300; h = 200
        cx = w/2; cy = h/2
        self.canvas_compass.create_oval(cx-80, cy-80, cx+80, cy+80, outline="#444", width=2)
        self.canvas_compass.create_text(cx, cy-90, text="N", fill="#666")
        self.drone_arrow = self.canvas_compass.create_line(cx, cy, cx, cy-60, fill=ACCENT_COLOR, width=4, arrow=tk.LAST)

    def update_compass(self, yaw_rad):
        w = self.canvas_compass.winfo_width()
        h = self.canvas_compass.winfo_height()
        cx = w/2; cy = h/2
        
      
        length = 60
        end_x = cx + length * math.sin(yaw_rad)
        end_y = cy - length * math.cos(yaw_rad)
        
        self.canvas_compass.coords(self.drone_arrow, cx, cy, end_x, end_y)

    def update_graph(self):
        c = self.canvas_graph
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        
       
        c.create_line(0, h/2, w, h/2, fill="#333", dash=(2,4))

        if not w or not h: return

       
        max_h = 5.0
        step_x = w / len(self.altitude_history)
        
        points = []
        for i, alt in enumerate(self.altitude_history):
            x = i * step_x
            y = h - ((alt / max_h) * h)
            points.append(x)
            points.append(y)
        
        if len(points) >= 4:
            c.create_line(points, fill=SUCCESS_COLOR, width=2, smooth=True)

    
    def listen_telemetry(self):
        print(f"Listening on {UDP_IP}:{UDP_PORT_RX}")
        while self.running:
            try:
                data, _ = self.sock_rx.recvfrom(2048)
                self.telemetry = json.loads(data.decode())
                
                
                pos = self.telemetry.get("position", [0,0,0])
                self.altitude_history.append(pos[2])
                self.altitude_history.pop(0)
                ori = self.telemetry.get("orientation", [0,0,0])
                self.csv_writer.writerow([
                    datetime.now().strftime("%H:%M:%S"),
                    self.telemetry.get("mode", "N/A"),
                    self.telemetry.get("battery", 0),
                    f"{pos[0]:.2f}", f"{pos[1]:.2f}", f"{pos[2]:.2f}",
                    f"{ori[2]:.2f}"
                ])
                self.log_file.flush()
                
            except Exception:
                pass
            time.sleep(0.02)

    def update_gui(self):
        t = self.telemetry
        mode = t.get("mode", "N/A")
        self.lbl_mode.config(text=f"MODE: {mode}", foreground=SUCCESS_COLOR if mode == "GUIDED" else WARNING_COLOR)  
        bat = t.get("battery", 0)
        self.lbl_bat_text.config(text=f"BATTERY: {bat:.1f}%")
        self.progress_bat['value'] = bat
        pos = t.get("position", [0,0,0])
        self.lbl_pos_x.config(text=f"X: {pos[0]:.2f} m")
        self.lbl_pos_y.config(text=f"Y: {pos[1]:.2f} m")
        self.lbl_pos_z.config(text=f"Z: {pos[2]:.2f} m")
        ori = t.get("orientation", [0,0,0])
        yaw = ori[2]
        self.update_compass(yaw)
        self.update_graph()

        self.root.after(50, self.update_gui)

    def send_command(self, key, value):
        msg = json.dumps({key: value}).encode()
        self.sock_tx.sendto(msg, (UDP_IP, UDP_PORT_TX))
        self.lbl_status.config(text=f"Sent Command: {key} -> {value}")

    def upload_mission(self):
        try:
            wps = json.loads(self.entry_wp.get())
            self.send_command("waypoints", wps)
            self.send_command("mode", "GUIDED")
            messagebox.showinfo("Mission", "Waypoints uploaded & GUIDED mode started!")
        except:
            messagebox.showerror("Error", "Invalid JSON format for waypoints.")

    def send_reboot(self):
        self.send_command("reboot", True)

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernDroneGCS(root)
    root.mainloop()