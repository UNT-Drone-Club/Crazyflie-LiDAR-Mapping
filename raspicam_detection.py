from ultralytics import YOLO
from picamera2 import Picamera2
import cv2, os

os.system('clear')
model = YOLO("yolo_models/yolo11n.pt")  # use smallest model

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
    # ,lores={"format": "YUV420", "size": (320, 240)}
)
picam2.configure(config)
picam2.start()

frame_count = 0
skip_frames = 2

while True:
    # Capture low-res for inference
    image = picam2.capture_array()
    # image_convert = cv2.cvtColor(image, cv2.COLOR_YUV420p2RGB)

    if frame_count % skip_frames == 0:
        annotated_frame = model(image, imgsz=256, verbose=False)[0].plot()

    cv2.imshow("Frame", annotated_frame if 'annotated_frame' in locals() else image)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
    frame_count += 1

picam2.stop()
cv2.destroyAllWindows()
