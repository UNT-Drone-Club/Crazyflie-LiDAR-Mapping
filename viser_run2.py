import time
from threading import Event

# Crazyflie
import cflib.crtp

# Viser
import viser
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger
from cflib.utils import uri_helper

deck_attached_event = Event()


class DroneVisualizer:
    def __init__(self, uri):
        self.uri = uri
        self.server = viser.ViserServer()
        self._setup_scene()

    def _setup_scene(self):
        """Initialize the 3D scene"""
        self.origin = self.server.scene.add_icosphere(
            "origin", radius=0.1, position=(0, 0, 0)
        )
        self.drone = self.server.scene.add_box(
            "drone", dimensions=(0.1, 0.1, 0.1), position=(0, 0, 0.5)
        )
        self.grid = self.server.scene.add_grid("grid")

    def _position_callback(self, timestamp, data, logconf):
        """Update drone position from Crazyflie data"""
        x = data.get("stateEstimate.x", 0)
        y = data.get("stateEstimate.y", 0)
        z = data.get("stateEstimate.z", 0)
        self.drone.position = (x, y, z)
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

    def _param_deck_flow(_, value_str):
        """Security checking if deck is properly initialized"""
        value = int(value_str)
        print(value)
        if value:
            deck_attached_event.set()
            print("Deck is attached!")
        else:
            print("Deck is NOT attached!")

    def run(self):
        """Main execution loop"""
        cflib.crtp.init_drivers()

        with SyncCrazyflie(self.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            self._setup_logging(scf)
            scf.cf.param.add_update_callback(
                group="deck", name="bcFlow2", cb=self._param_deck_flow
            )
            time.sleep(1)

            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("Shutting down...")


if __name__ == "__main__":
    uri = "radio://0/80/2M"  # Your URI here
    visualizer = DroneVisualizer(uri)
    visualizer.run()
