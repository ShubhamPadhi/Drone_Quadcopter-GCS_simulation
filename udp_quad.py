import quadcopter, gui, controller
import signal, sys, argparse, threading, time, socket, json, os
import numpy as np

# ===========================================================
# ---- Global Constants & Settings ----
# ===========================================================
TIME_SCALING = 1.0
QUAD_DYNAMICS_UPDATE = 0.002
CONTROLLER_DYNAMICS_UPDATE = 0.005
run = True

# UDP Configuration
UDP_IP = "127.0.0.1"
UDP_PORT_RX = 9000  # Receive commands (from GCS)
UDP_PORT_TX = 9001  # Send telemetry (to GCS)

# Flight modes
MODES = ['GUIDED', 'TAKEOFF', 'LAND', 'RTL']
current_mode = 'GUIDED'

# Battery Simulation
BATTERY_DRAIN_RATE = 0.01
battery = 100.0

# Waypoints
WAYPOINTS = [(1, 1, 2), (0, 0, 0), (-1, -1, 2), (-1, 1, 4)]
current_wp_index = 0

# Thread lock
lock = threading.Lock()

# UDP Sockets
sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rx.bind((UDP_IP, UDP_PORT_RX))
sock_rx.setblocking(False)

sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ===========================================================
# ---- UDP Communication Threads ----
# ===========================================================

def udp_listener(ctrl):
    """Receive control commands (mode, PID, waypoints, reboot)."""
    global current_mode, WAYPOINTS, current_wp_index, run
    print(f"[UDP] Listening for incoming GCS commands on {UDP_IP}:{UDP_PORT_RX} ...")
    while run:
        try:
            data, addr = sock_rx.recvfrom(2048)
            msg = json.loads(data.decode())

            # ---- Update PID ----
            if 'pid' in msg:
                with lock:
                    print("[UDP] Updating PID parameters...")
                    for key in msg['pid']:
                        if key in ctrl.params:
                            ctrl.params[key].update(msg['pid'][key])
                        elif key in ctrl.params.get('Linear_PID', {}):
                            ctrl.params['Linear_PID'][key] = msg['pid'][key]

            # ---- Change Flight Mode ----
            if 'mode' in msg:
                with lock:
                    mode = msg['mode'].upper()
                    if mode in MODES:
                        current_mode = mode
                        current_wp_index = 0
                        print(f"[MODE] Switched to {current_mode}")

            # ---- Update Waypoints ----
            if 'waypoints' in msg:
                with lock:
                    WAYPOINTS = msg['waypoints']
                    current_wp_index = 0
                    print(f"[UDP] Received new waypoints: {WAYPOINTS}")

            # ---- Reboot Command ----
            if 'reboot' in msg and msg['reboot']:
                print("[SIM] Reboot command received. Restarting simulation...")
                sock_tx.sendto(json.dumps({"status": "rebooting"}).encode(), (UDP_IP, UDP_PORT_TX))
                os.execv(sys.executable, [sys.executable] + sys.argv)

        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[UDP] Error: {e}")
        time.sleep(0.01)


def telemetry_sender(quad):
    """Send live telemetry to GCS."""
    global battery
    print(f"[UDP] Telemetry broadcasting on {UDP_IP}:{UDP_PORT_TX} ...")
    while run:
        try:
            pos = quad.get_position('q1')
            ori = quad.get_orientation('q1')

            if isinstance(pos, np.ndarray):
                pos = pos.tolist()
            if isinstance(ori, np.ndarray):
                ori = ori.tolist()

            telemetry = {
                'position': pos,
                'orientation': ori,
                'battery': round(battery, 2),
                'mode': current_mode,
                'waypoint_index': current_wp_index
            }

            sock_tx.sendto(json.dumps(telemetry).encode(), (UDP_IP, UDP_PORT_TX))

        except Exception as e:
            print(f"[UDP] Telemetry error: {e}")
        time.sleep(0.05)  # ~20 Hz

# ===========================================================
# ---- Battery Simulation ----
# ===========================================================
def update_battery():
    """Simulate battery draining over time."""
    global battery
    while run:
        battery = max(0.0, battery - BATTERY_DRAIN_RATE)
        time.sleep(0.5)

# ===========================================================
# ---- Flight Mode Handling ----
# ===========================================================
def flight_mode_handler(ctrl, quad):
    """Manage TAKEOFF, LAND, RTL, GUIDED modes."""
    global current_mode, current_wp_index, WAYPOINTS
    while run:
        pos = quad.get_position('q1')

        if current_mode == 'TAKEOFF':
            ctrl.update_target((pos[0], pos[1], 2.0))
        elif current_mode == 'LAND':
            ctrl.update_target((pos[0], pos[1], 0.0))
        elif current_mode == 'RTL':
            ctrl.update_target((0, 0, 0))
        elif current_mode == 'GUIDED':
            if current_wp_index < len(WAYPOINTS):
                target = WAYPOINTS[current_wp_index]
                ctrl.update_target(target)
                curr = quad.get_position('q1')
                if all(abs(a - b) < 0.1 for a, b in zip(curr, target)):
                    current_wp_index += 1
                    print(f"[GUIDED] Reached waypoint {current_wp_index}/{len(WAYPOINTS)}")

        time.sleep(0.05)

# ===========================================================
# ---- Main Simulation ----
# ===========================================================
def Single_Point2Point():
    global run

    QUADCOPTER = {'q1': {
        'position': [0, 0, 0],
        'orientation': [0, 0, 0],
        'L': 0.3,
        'r': 0.1,
        'prop_size': [10, 4.5],
        'weight': 1.2
    }}

    CONTROLLER_PARAMETERS = {
        'Motor_limits': [4000, 9000],
        'Tilt_limits': [-10, 10],
        'Yaw_Control_Limits': [-900, 900],
        'Z_XY_offset': 500,
        'Linear_PID': {'P': [300, 300, 7000], 'I': [0.04, 0.04, 4.5], 'D': [450, 450, 5000]},
        'Linear_To_Angular_Scaler': [1, 1, 0],
        'Yaw_Rate_Scaler': 0.18,
        'Angular_PID': {'P': [22000, 22000, 1500], 'I': [0, 0, 1.2], 'D': [12000, 12000, 0]},
    }

    signal.signal(signal.SIGINT, signal_handler)

    quad = quadcopter.Quadcopter(QUADCOPTER)
    gui_object = gui.GUI(quads=QUADCOPTER)
    ctrl = controller.Controller_PID_Point2Point(
        quad.get_state, quad.get_time, quad.set_motor_speeds,
        params=CONTROLLER_PARAMETERS, quad_identifier='q1'
    )

    quad.start_thread(dt=QUAD_DYNAMICS_UPDATE, time_scaling=TIME_SCALING)
    ctrl.start_thread(update_rate=CONTROLLER_DYNAMICS_UPDATE, time_scaling=TIME_SCALING)

    threading.Thread(target=udp_listener, args=(ctrl,), daemon=True).start()
    threading.Thread(target=telemetry_sender, args=(quad,), daemon=True).start()
    threading.Thread(target=update_battery, daemon=True).start()
    threading.Thread(target=flight_mode_handler, args=(ctrl, quad), daemon=True).start()

    print("[SIM] Quadcopter simulator started with UDP telemetry & control.")

    while run:
        gui_object.quads['q1']['position'] = quad.get_position('q1')
        gui_object.quads['q1']['orientation'] = quad.get_orientation('q1')
        gui_object.update()
        time.sleep(0.02)

    quad.stop_thread()
    ctrl.stop_thread()
    print("[SIM] Simulation stopped.")

# ===========================================================
# ---- CLI & Signal Handling ----
# ===========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Quadcopter Simulator with UDP GCS Interface")
    parser.add_argument("--time_scale", type=float, default=-1.0)
    parser.add_argument("--quad_update_time", type=float, default=0.0)
    parser.add_argument("--controller_update_time", type=float, default=0.0)
    return parser.parse_args()

def signal_handler(signal, frame):
    global run
    run = False
    print("\n[SIM] Stopping simulation...")
    sys.exit(0)

# ===========================================================
# ---- Entry Point ----
# ===========================================================
if __name__ == "__main__":
    args = parse_args()
    if args.time_scale >= 0:
        TIME_SCALING = args.time_scale
    if args.quad_update_time > 0:
        QUAD_DYNAMICS_UPDATE = args.quad_update_time
    if args.controller_update_time > 0:
        CONTROLLER_DYNAMICS_UPDATE = args.controller_update_time

    Single_Point2Point()
