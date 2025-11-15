import os
import time

# Crazyflie
import cflib.crtp
# Viser
import viser
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger
from cflib.utils import uri_helper

# URI to the Crazyflie to connect to
uri = uri_helper.uri_from_env(default="radio://0/80/2M/E7E7E7E7E7")


def log_stab_callback(timestamp, data, logconf):
    print("[%d][%s]: %s" % (timestamp, logconf.name, data))


# def viser_drone_position_callback(timestamp, data, logconf):


def simple_log_async(scf, logconf):
    cf = scf.cf
    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(log_stab_callback)
    logconf.start()


def server_start():
    # Initializing scene
    server = viser.ViserServer()
    origin = server.scene.add_icosphere("origin", radius=0.1, position=(0, 0, 0))
    drone = server.scene.add_box("drone", dimensions=(1, 1, 1), position=(0, 0, 0.5))
    grid = server.scene.add_grid("grid")

    # Initializing drone
    # Initialize the low-level drivers
    cflib.crtp.init_drivers()

    # Initializing async logging
    lg_stab = LogConfig(name="State Estimate", period_in_ms=10)
    lg_stab.add_variable("stateEstimate.x", "float")
    lg_stab.add_variable("stateEstimate.y", "float")
    lg_stab.add_variable("stateEstimate.z", "float")

    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        simple_log_async(scf, lg_stab)

        while True:
            time.sleep(6)


def main():
    server_start()


if __name__ == "__main__":
    main()
