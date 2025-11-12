#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, Imu
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
import math
import time
import os


class TrajectoryNode(Node):
    def __init__(self):
        super().__init__('trajectory_node')

        # PX4 state subscriber
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_cb, 10)

        # Camera image
        self.image_sub = self.create_subscription(
            Image,
            '/world/forest/model/x500_mono_cam_down_0/link/camera_link/sensor/imager/image',
            self.image_callback,
            10
        )

        # Camera info
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/world/forest/model/x500_mono_cam_down_0/link/camera_link/sensor/imager/camera_info',
            self.camera_info_callback,
            10
        )

        # Local position publisher
        self.local_pos_pub = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)

        # Services
        self.arming_client = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.set_mode_client = self.create_client(SetMode, '/mavros/set_mode')

        # Internal state
        self.current_state = State()
        self.start_time = None
        self.flight_duration = 120.0  # seconds (0.5 minutes)
        self.takeoff_alt = 3.0       # meters

        # Trajectory params
        self.radius = 5.0
        self.omega = 0.2  # rad/s

        # Logging to file
        log_dir = os.path.expanduser("~/x500_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, "trajectory_node.log")
        self.log_file = open(self.log_path, "w")

        self.log("Trajectory Node initialized.")
        self.timer = self.create_timer(0.05, self.timer_cb)  # 20 Hz

    def log(self, text):
        stamp = self.get_clock().now().to_msg()
        line = f"[{stamp.sec}.{stamp.nanosec:09d}] {text}\n"
        self.log_file.write(line)
        self.log_file.flush()

    def state_cb(self, msg):
        self.current_state = msg

    def image_callback(self, msg):
        self.get_logger().info(f"Received image with width: {msg.width}, height: {msg.height}")

    def camera_info_callback(self, msg):
        self.get_logger().info(f"Received camera info: {msg.width}x{msg.height}, frame_id: {msg.header.frame_id}")

    def imu_callback(self, msg):
        self.get_logger().info(f"Received IMU data: orientation {msg.orientation}")

    def arm_and_offboard(self):
        # Wait for services
        self.log("Waiting for arming and mode services...")
        self.arming_client.wait_for_service()
        self.set_mode_client.wait_for_service()

        # Set mode
        set_mode_req = SetMode.Request()
        set_mode_req.custom_mode = 'OFFBOARD'
        self.set_mode_client.call_async(set_mode_req)

        # Arm
        arm_req = CommandBool.Request()
        arm_req.value = True
        self.arming_client.call_async(arm_req)

        self.log("Sent OFFBOARD + ARM commands.")

    def timer_cb(self):
        now = self.get_clock().now().nanoseconds / 1e9

        if self.start_time is None:
            self.start_time = now
            self.log("Starting trajectory...")

        elapsed = now - self.start_time

        # Generate circular trajectory
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        pose.pose.position.x = self.radius * math.cos(self.omega * elapsed)
        pose.pose.position.y = self.radius * math.sin(self.omega * elapsed)
        pose.pose.position.z = self.takeoff_alt

        # Publish
        self.local_pos_pub.publish(pose)

        # Arm and switch mode if needed
        if self.current_state.mode != "OFFBOARD" or not self.current_state.armed:
            self.arm_and_offboard()

        # Stop after 2 minutes
        if elapsed >= self.flight_duration:
            self.log("2-minute trajectory complete. Shutting down.")
            self.log_file.close()
            self.destroy_timer(self.timer)
            self.destroy_node()
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryNode()
    rclpy.spin(node)


if __name__ == '__main__':
    main()

