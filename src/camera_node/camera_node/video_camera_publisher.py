import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

import cv2


class CameraPublisher(Node):
    def __init__(self):
        super().__init__('camera_publisher')

        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)

        # usa webcam (0) oppure metti path video
        self.cap = cv2.VideoCapture("/workspace/test.mp4")

        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return
        
        msg = Image()
        msg.height = frame.shape[0]
        msg.width = frame.shape[1]
        msg.encoding = 'bgr8'
        msg.step = frame.shape[1] * 3
        msg.data = frame.tobytes()

        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CameraPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
