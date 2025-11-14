import os
import time

import viser


def server_start():
    # Initializing scene
    server = viser.ViserServer()
    server.scene.add_frame("/arm",wxyz=(1,0,0,0),position=(2,2,0.2))
    server.scene.add_frame("/arm/hand",wxyz=(1,0,0,0),position=(2,2,0.2))
    server.scene.add_box("/arm/box", dimensions=(1,1,1), position=(0,0,0))

def main():
    server_start()

    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
