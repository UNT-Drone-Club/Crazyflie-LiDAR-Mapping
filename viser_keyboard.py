import logging
import threading
import time
from threading import Event

import cflib
import cflib.crtp
import viser
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander

# Configure logging to show only errors
logging.basicConfig(level=logging.ERROR)

# Connection URI and flight control constants
URI = "radio://0/80/2M/E7E7E7E7E7"
DEFAULT_HEIGHT = 0.5
BASE_SPEED = 0.35
SPEED_STEP = 0.05
TURN_STEP = 5
RUNNING = True
motors_on = False
speed = BASE_SPEED
turn_speed = 500

# Track Flowdeck presence
deck_attached_event = Event()


class DroneVisualizer:
    def __init__(self, uri):
        self.uri = uri
        self.server = viser.ViserServer()
        self.mc_instance = None
        self.vx, self.vy, self.vz, self.yaw_rate = 0.0, 0.0, 0.0, 0.0
        self._setup_scene()

    def _setup_scene(self):
        """Initialize the 3D scene"""
        # self.origin = self.server.scene.add_icosphere(
        #     "origin", radius=0.1, position=(0, 0, 0), color=(255, 0, 0)
        # )
        self.origin = self.server.scene.add_box(
            "origin",
            dimensions=(0.1, 0.1, 0.01),
            position=(0, 0, 0),
            color=(0, 0, 0),
        )
        self.drone = self.server.scene.add_box(
            "drone",
            dimensions=(0.1, 0.1, 0.05),
            position=(0, 0, 0.5),
            color=(0, 150, 255),
        )
        self.grid = self.server.scene.add_grid(
            "grid", width=10, height=10, cell_size=0.1
        )

        # Add trajectory trail
        self.trajectory_points = []

        # Setup GUI controls
        self._setup_gui()

    def _setup_gui(self):
        """Setup GUI controls in Viser"""
        # Flight control section
        self.takeoff_button = self.server.gui.add_button(
            "Takeoff", color="green", hint="Press to takeoff", order=0
        )
        self.land_button = self.server.gui.add_button(
            "Land", color="orange", hint="Press to land", order=1
        )
        self.emergency_button = self.server.gui.add_button(
            "EMERGENCY STOP", color="red", hint="Emergency landing", order=2
        )

        # Height control
        self.height_slider = self.server.gui.add_slider(
            "Target Height (m)",
            min=0.2,
            max=3.0,
            step=0.1,
            initial_value=DEFAULT_HEIGHT,
            hint="Adjust target flight height",
            order=3,
        )

        # Speed control
        self.speed_slider = self.server.gui.add_slider(
            "Speed (m/s)",
            min=0.05,
            max=1.0,
            step=0.05,
            initial_value=BASE_SPEED,
            hint="Adjust movement speed",
            order=4,
        )

        # Turn speed control
        self.turn_slider = self.server.gui.add_slider(
            "Turn Speed (deg/s)",
            min=5.0,
            max=500.0,
            step=5.0,
            initial_value=90.0,
            hint="Adjust rotation speed",
            order=5,
        )

        # Movement buttons
        self.forward_button = self.server.gui.add_button(
            "Forward", color="blue", hint="Move forward", order=6
        )
        self.backward_button = self.server.gui.add_button(
            "Backward", color="blue", hint="Move backward", order=7
        )
        self.left_button = self.server.gui.add_button(
            "Left", color="blue", hint="Move left", order=8
        )
        self.right_button = self.server.gui.add_button(
            "Right", color="blue", hint="Move right", order=9
        )

        # Vertical movement
        self.up_button = self.server.gui.add_button(
            "Up", color="cyan", hint="Move up", order=10
        )
        self.down_button = self.server.gui.add_button(
            "Down", color="cyan", hint="Move down", order=11
        )

        # Rotation buttons
        self.rotate_left_button = self.server.gui.add_button(
            "Rotate Left", color="violet", hint="Rotate counterclockwise", order=12
        )
        self.rotate_right_button = self.server.gui.add_button(
            "Rotate Right", color="violet", hint="Rotate clockwise", order=13
        )

        # Setup button callbacks
        self.takeoff_button.on_click(lambda _: self.handle_takeoff())
        self.land_button.on_click(lambda _: self.handle_land())
        self.emergency_button.on_click(lambda _: self.handle_emergency())

        self.forward_button.on_click(lambda _: self.handle_movement(0.5, 0, 0, 0))
        self.backward_button.on_click(lambda _: self.handle_movement(-0.5, 0, 0, 0))
        self.left_button.on_click(lambda _: self.handle_movement(0, 0.5, 0, 0))
        self.right_button.on_click(lambda _: self.handle_movement(0, -0.5, 0, 0))
        self.up_button.on_click(lambda _: self.handle_movement(0, 0, 0.3, 0))
        self.down_button.on_click(lambda _: self.handle_movement(0, 0, -0.3, 0))
        self.rotate_left_button.on_click(lambda _: self.handle_movement(0, 0, 0, -90))
        self.rotate_right_button.on_click(lambda _: self.handle_movement(0, 0, 0, 90))

    def handle_takeoff(self):
        """Handle takeoff button click"""
        global motors_on
        if not motors_on and self.mc_instance:
            print("[INFO] Taking off...")
            try:
                height = self.height_slider.value
                self.mc_instance.take_off(height)
                motors_on = True
            except Exception as e:
                print(f"[ERROR] Takeoff failed: {e}")

    def handle_land(self):
        """Handle land button click"""
        global motors_on
        if motors_on and self.mc_instance:
            print("[INFO] Landing...")
            try:
                self.mc_instance.land()
                motors_on = False
            except Exception as e:
                print(f"[ERROR] Landing failed: {e}")

    def handle_emergency(self):
        """Handle emergency stop"""
        print("[INFO] Emergency stop!")
        threading.Thread(target=self.safe_stop, daemon=True).start()

    def handle_movement(self, vx, vy, vz, yaw):
        """Handle movement button clicks"""
        if motors_on and self.mc_instance:
            try:
                speed = self.speed_slider.value
                turn_speed = self.turn_slider.value

                # Scale velocities by speed
                scaled_vx = vx * speed if vx != 0 else 0
                scaled_vy = vy * speed if vy != 0 else 0
                scaled_vz = vz * speed if vz != 0 else 0
                scaled_yaw = yaw * (turn_speed / 90) if yaw != 0 else 0

                # Send command for duration
                duration = 0.5  # seconds
                end_time = time.time() + duration
                while time.time() < end_time and motors_on:
                    self.mc_instance._set_vel_setpoint(
                        scaled_vx, scaled_vy, scaled_vz, scaled_yaw
                    )
                    time.sleep(0.01)

                # Stop movement
                self.mc_instance._set_vel_setpoint(0, 0, 0, 0)

            except Exception as e:
                print(f"[ERROR] Movement failed: {e}")

    def _position_callback(self, timestamp, data, logconf):
        """Update drone position from Crazyflie data"""
        x = data.get("stateEstimate.x", 0)
        y = data.get("stateEstimate.y", 0)
        z = data.get("stateEstimate.z", 0)

        self.drone.position = (x, y, z)

        # Add to trajectory
        self.trajectory_points.append((x, y, z))
        if len(self.trajectory_points) > 500:  # Keep last 500 points
            self.trajectory_points.pop(0)

        print(f"[{timestamp}] Position: ({x:.2f}, {y:.2f}, {z:.2f})")

    def _setup_logging(self, scf):
        """Configure Crazyflie logging"""
        lg_stab = LogConfig(name="State Estimate", period_in_ms=10)
        lg_stab.add_variable("stateEstimate.x", "float")
        lg_stab.add_variable("stateEstimate.y", "float")
        lg_stab.add_variable("stateEstimate.z", "float")

        scf.cf.log.add_config(lg_stab)
        lg_stab.data_received_cb.add_callback(self._position_callback)
        lg_stab.start()

    def param_deck_flow(self, _, value_str):
        """Security checking if deck is properly initialized"""
        if int(value_str):
            deck_attached_event.set()
            print("[INFO] Flowdeck is attached.")
        else:
            print("[WARNING] Flowdeck is NOT attached!")

    def safe_stop(self):
        """Emergency stop and landing"""
        global RUNNING, motors_on
        try:
            if self.mc_instance:
                print("[INFO] Emergency landing...")
                self.mc_instance.land()
        except Exception as e:
            print(f"[ERROR] During emergency stop: {e}")
        finally:
            motors_on = False
            RUNNING = False

    def print_info(self):
        """Print control instructions"""
        print("\n[INFO] Crazyflie Drone Visualizer")
        print("  Control the drone using the GUI at http://localhost:8080")
        print("  - Use Takeoff/Land buttons to control flight")
        print("  - Adjust height and speed with sliders")
        print("  - Use directional buttons for movement")
        print("  - Emergency stop button for immediate landing\n")

    def run(self):
        """Main execution loop"""
        global RUNNING
        self.print_info()
        cflib.crtp.init_drivers()

        with SyncCrazyflie(self.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            scf.cf.param.add_update_callback(
                group="deck", name="bcFlow2", cb=self.param_deck_flow
            )
            print("[INFO] Waiting for Flowdeck...")
            if not deck_attached_event.wait(timeout=5):
                print("[ERROR] No Flowdeck detected!")
                return

            self.mc_instance = MotionCommander(scf, default_height=DEFAULT_HEIGHT)
            print("[INFO] Connected to Crazyflie!")

            # Setup logging for visualization
            self._setup_logging(scf)

            # Main loop
            try:
                while RUNNING:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[INFO] Keyboard interrupt received...")

            # Cleanup
            try:
                if motors_on:
                    self.mc_instance.land()
            except Exception as e:
                print(f"[ERROR] During shutdown landing: {e}")

            print("\n[INFO] Flight Ended. Shutdown complete.")


if __name__ == "__main__":
    visualizer = DroneVisualizer(URI)
    visualizer.run()
