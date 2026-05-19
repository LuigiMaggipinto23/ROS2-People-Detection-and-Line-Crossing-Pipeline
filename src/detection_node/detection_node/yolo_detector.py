import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Image

import numpy as np
import cv2
import json

from ultralytics import YOLO


class YoloDetector(Node):

    def __init__(self):
        super().__init__('yolo_detector')

        # Subscriber
        self.sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.callback,
            10
        )

        # Publisher
        self.pub = self.create_publisher(
            String,
            '/detections',
            10
        )

        # YOLO model
        self.model = YOLO("yolov8n.pt")

        # Tracking
        self.tracks = {}          # id -> centroid
        self.next_id = 0

        # Event detection
        self.line_x = 400  # scegli tu il punto giusto
        self.prev_positions = {}  # id -> previous y
        self.crossed_ids = set()

        # Frame counter
        self.frame_count = 0

        self.get_logger().info("YOLO + Tracking + Fence Detection started")


    def get_centroid(self, box):
        x1, y1, x2, y2 = box
        return ((x1 + x2) // 2, (y1 + y2) // 2)


    def callback(self, msg):

        # Convert ROS Image → numpy
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(
            (msg.height, msg.width, 3)
        )

        annotated = frame.copy()

        # 🎨 Draw fence line
        cv2.line(annotated, (self.line_x, 0), (self.line_x, frame.shape[0]), (0, 0, 255), 2)

        # YOLO inference
        results = self.model(frame)

        current_centroids = []
        boxes_list = []

        # 🔹 Extract detections
        for r in results:
            if r.boxes is None:
                continue

            boxes = r.boxes.xyxy.cpu().numpy()
            classes = r.boxes.cls.cpu().numpy()

            for box, cls in zip(boxes, classes):
                if int(cls) == 0:  # person

                    x1, y1, x2, y2 = map(int, box)
                    centroid = self.get_centroid((x1, y1, x2, y2))

                    current_centroids.append(centroid)
                    boxes_list.append((x1, y1, x2, y2))


        # 🔥 TRACKING
        new_tracks = {}

        for centroid, box in zip(current_centroids, boxes_list):

            assigned = False

            for track_id, prev_centroid in self.tracks.items():

                dist = ((centroid[0] - prev_centroid[0]) ** 2 +
                        (centroid[1] - prev_centroid[1]) ** 2) ** 0.5

                if dist < 50:

                    new_tracks[track_id] = centroid

                    x1, y1, x2, y2 = box

                    # 🟩 tracked
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        annotated,
                        f"ID {track_id}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                    # 🔥 EVENT DETECTION
                    x_current = centroid[0]

                    if track_id in self.prev_positions:
                        x_prev = self.prev_positions[track_id]

                        # crossing da sinistra → destra
                        if x_prev > self.line_x and x_current <= self.line_x:
                            if track_id not in self.crossed_ids:
                                self.get_logger().info(f"🚨 ID {track_id} CROSSED THE LINE")
                                self.crossed_ids.add(track_id)

                    self.prev_positions[track_id] = x_current
                    self.prev_positions[self.next_id] = centroid[0]

                    assigned = True
                    break

            # 🔵 NEW TRACK
            if not assigned:

                new_tracks[self.next_id] = centroid

                x1, y1, x2, y2 = box

                cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(
                    annotated,
                    f"ID {self.next_id}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )

                # inizializza posizione
                self.prev_positions[self.next_id] = centroid[1]

                self.next_id += 1

        self.tracks = new_tracks


        # 📸 SAVE FRAME
        self.frame_count += 1

        if self.frame_count % 10 == 0:
            filename = f"/workspace/output/frame_{self.frame_count:04d}.jpg"
            cv2.imwrite(filename, annotated)
            self.get_logger().info(f"Saved {filename}")


        # 📡 Publish detections
        msg_out = String()
        msg_out.data = json.dumps({
            "num_person": len(current_centroids)
        })

        self.pub.publish(msg_out)

        self.get_logger().info(f"Persons: {len(current_centroids)}")


def main(args=None):
    rclpy.init(args=args)
    node = YoloDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()