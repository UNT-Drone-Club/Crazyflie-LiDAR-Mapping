from ultralytics import YOLO
from picamera2 import Picamera2
import cv2, os
from flask import Flask, Response

os.system("clear")
model = YOLO("yolo_models/yolo11n.pt")  # smallest model for speed

# Flask app
app = Flask(__name__)

# Pi Camera setup
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
)
picam2.configure(config)
picam2.start()

frame_count = 0
skip_frames = 2

def generate_frames():
    global frame_count
    while True:
        image = picam2.capture_array()

        if frame_count % skip_frames == 0:
            results = model(image, imgsz=320, verbose=False)
            annotated_frame = results[0].plot()
        frame_count += 1

        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame if 'annotated_frame' in locals() else image)
        frame = buffer.tobytes()

        # Yield frame in multipart format for MJPEG
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Run Flask on all network interfaces so you can view it from other devices
    app.run(host="0.0.0.0", port=5000, debug=False)
