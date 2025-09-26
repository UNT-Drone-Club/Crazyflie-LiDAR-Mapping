# This program allows the Crazyflie 2.1+ with a Flowdeck V2 to be controlled with only a keyboard.
# Need to figure out how to make the Flowdeck stable when flying over objects of varying heights
import time
import logging
import threading
from pynput import keyboard
import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.crazyflie.log import LogConfig
from threading import Event

# Configure logging to show only errors
logging.basicConfig(level=logging.ERROR)

# Connection URI and flight control constants
# Uniform Resource Identifier, InterfaceType://InterfaceId/InterfaceChannel/InterfaceSpeed Change to match your Crazyflies URI
URI = "radio://0/80/2M" 
DEFAULT_HEIGHT = 0.5        # Sets the default height for takeoff range: 0.2 <= X <= 3.0 meters, limited by the ranged of optical sensor on flowdeck V2. Flight above 3m will be unstable
BASE_SPEED = 0.35           # Sets the base speed of the drone in m/s range: 0 <= X <= 1 m/s by default you can change this limit with the parameter posCtlPid.xyVelMax in cfclient. Max speed ~3m/s, depending on whats attached to your crazyflie.
SPEED_STEP = 0.05           # Changes the crazyflies speed by 0.05 m/s. As long as the cf wont be past max or min BASE_SPEED once executed this number can be anything.
TURN_STEP = 5               # Changes the turning speed of the crazyflie by 5 deg/s. 
RUNNING = True              # Helps in the launch process
motors_on = False           # Helps in the launch process
speed = BASE_SPEED          # Sets the speed to the Base speed by default
turn_speed = 500            # Sets the turn speed to 90 deg/s range: 0 <= X <= 500. As you approach 500 deg/sec, the cf becomes more and more unstable. 480 deg/sec is max for sustained yaw rotation.

# Adjust speed and yaw rate
def adjust_speed(increase=True):
    global speed, turn_speed
    if increase:
        speed += SPEED_STEP
        turn_speed += TURN_STEP
    else:
        speed = max(0.05, speed - SPEED_STEP)
        turn_speed = max(5, turn_speed - TURN_STEP)
    print(f"[INFO] Speed adjusted: {speed:.2f}, Turn step: {turn_speed}")

# Track Flowdeck presence
deck_attached_event = Event()

# Keyboard state
key_states = {
    "w": False, "s": False, "a": False, "d": False,
    "space": False, "ctrl": False,
    "+": False, "-": False, "left": False, "right": False
}

mc_instance = None
vx, vy, vz, yaw_rate = 0.0, 0.0, 0.0, 0.0

def print_controls():
    print("\n[INFO] Crazyflie Drone Controls:")
    print("  W / S - Move Forward / Backward")
    print("  A / D - Move Left / Right")
    print("  SPACE / CTRL - Ascend / Descend")
    print("  ← / →  - Rotate Left / Right (Yaw)")
    print("  + / -  - Adjust Speed / Yaw Step")
    print("  `      - Toggle Motors ON/OFF (Takeoff/Land)")
    print("  ESC    - Emergency Stop\n")

def param_deck_flow(_, value_str):
    if int(value_str):
        deck_attached_event.set()
        print('[INFO] Flowdeck is attached.')
    else:
        print('[WARNING] Flowdeck is NOT attached!')

def control_loop():
    global RUNNING, motors_on, speed, turn_speed, mc_instance, vx, vy, vz, yaw_rate
    while RUNNING:
        if motors_on and mc_instance:
            try:
                vx = speed if key_states["w"] else -speed if key_states["s"] else 0.0
                vy = speed if key_states["a"] else -speed if key_states["d"] else 0.0
                vz = speed if key_states["space"] else -speed if key_states["ctrl"] else 0.0
                yaw_rate = turn_speed if key_states["right"] else -turn_speed if key_states["left"] else 0.0

                mc_instance._set_vel_setpoint(vx, vy, vz, yaw_rate)

            except Exception as e:
                print(f"[ERROR] Motion error: {e}")
        time.sleep(0.01)

def safe_stop():
    global RUNNING, motors_on
    try:
        if mc_instance:
            print("[INFO] Emergency landing...")
            mc_instance.land()
    except Exception as e:
        print(f"[ERROR] During emergency stop: {e}")
    finally:
        motors_on = False
        RUNNING = False

def on_press(key):
    global motors_on
    try:
        if key == keyboard.Key.space:
            key_states["space"] = True
        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            key_states["ctrl"] = True
        elif key == keyboard.Key.left:
            key_states["left"] = True
        elif key == keyboard.Key.right:
            key_states["right"] = True
        elif key == keyboard.Key.esc:
            print("[INFO] Emergency Stop!")
            threading.Thread(target=safe_stop, daemon=True).start()
        elif hasattr(key, 'char') and key.char:
            lowered = key.char.lower()
            if lowered in key_states:
                key_states[lowered] = True

            if lowered == '`':
                if not motors_on:
                    print("[INFO] Motors ON. Taking off...")
                    mc_instance.take_off(DEFAULT_HEIGHT)
                else:
                    print("[INFO] Motors OFF. Landing...")
                    mc_instance.land()
                motors_on = not motors_on

            elif lowered == '+':
                adjust_speed(True)
            elif lowered == '-':
                adjust_speed(False)
    except Exception as e:
        print(f"[ERROR] on_press: {e}")

def on_release(key):
    try:
        if key == keyboard.Key.space:
            key_states["space"] = False
        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            key_states["ctrl"] = False
        elif key == keyboard.Key.left:
            key_states["left"] = False
        elif key == keyboard.Key.right:
            key_states["right"] = False
        elif hasattr(key, 'char') and key.char:
            lowered = key.char.lower()
            if lowered in key_states:
                key_states[lowered] = False
    except Exception as e:
        print(f"[ERROR] on_release: {e}")


def main():
    global RUNNING, mc_instance
    print_controls()
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
        scf.cf.param.add_update_callback(group="deck", name="bcFlow2", cb=param_deck_flow)
        print("[INFO] Waiting for Flowdeck...")
        if not deck_attached_event.wait(timeout=5):
            print("[ERROR] No Flowdeck detected!")
            return

        mc_instance = MotionCommander(scf, default_height=DEFAULT_HEIGHT)
        print("[INFO] Connected to Crazyflie!")

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        threading.Thread(target=control_loop, daemon=True).start()

        while RUNNING:
            time.sleep(0.1)

        try:
            if motors_on:
                mc_instance.land()
        except Exception as e:
            print(f"[ERROR] During shutdown landing: {e}")

        print("\n[INFO] Flight Ended. Shutdown complete.")

if __name__ == "__main__":
    main()
