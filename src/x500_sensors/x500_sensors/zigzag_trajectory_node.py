#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
import math
import os


class ZigZagNode(Node):
    def __init__(self):
        super().__init__('zigzag_node')

        # ------------------------------------------------------------
        # Declare parameters with defaults
        # ------------------------------------------------------------
        self.declare_parameter('trajectory_duration', 120.0)
        self.declare_parameter('takeoff_alt', 25.0)
        self.declare_parameter('amplitude', 10.0)
        self.declare_parameter('speed', 1.0)
        self.declare_parameter('frequency', 0.3)

        # ------------------------------------------------------------
        # Read parameter values
        # ------------------------------------------------------------
        self.flight_duration = float(self.get_parameter('trajectory_duration').value)
        self.takeoff_alt = float(self.get_parameter('takeoff_alt').value)
        self.amplitude = float(self.get_parameter('amplitude').value)
        self.speed = float(self.get_parameter('speed').value)
        self.frequency = float(self.get_parameter('frequency').value)

        # ------------------------------------------------------------
        # Logging setup
        # ------------------------------------------------------------
        log_dir = os.path.expanduser("~/x500_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, "zigzag_node.log")
        self.log_file = open(self.log_path, "w")

        self.log("=== Zigzag Trajectory Node Initialized ===")
        self.log(f"Trajectory duration: {self.flight_duration:.1f} s")
        self.log(f"Takeoff altitude: {self.takeoff_alt:.1f} m")
        self.log(f"Amplitude: {self.amplitude:.2f} m")
        self.log(f"Speed: {self.speed:.2f} m/s")
        self.log(f"Frequency: {self.frequency:.2f} Hz")

        # ------------------------------------------------------------
        # MAVROS setup
        # ------------------------------------------------------------
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_cb, 10)
        self.local_pos_pub = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        self.arming_client = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.set_mode_client = self.create_client(SetMode, '/mavros/set_mode')

        # Internal state
        self.current_state = State()
        self.start_time = None

        # Run timer (20 Hz)
        self.timer = self.create_timer(0.05, self.timer_cb)

    # ------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------
    def log(self, text):
        stamp = self.get_clock().now().to_msg()
        self.log_file.write(f"[{stamp.sec}.{stamp.nanosec:09d}] {text}\n")
        self.log_file.flush()
        self.get_logger().info(text)

    # ------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------
    def state_cb(self, msg):
        self.current_state = msg

    def arm_and_offboard(self):
        self.log("Waiting for arming and mode services...")
        self.arming_client.wait_for_service()
        self.set_mode_client.wait_for_service()

        set_mode_req = SetMode.Request()
        set_mode_req.custom_mode = 'OFFBOARD'
        self.set_mode_client.call_async(set_mode_req)

        arm_req = CommandBool.Request()
        arm_req.value = True
        self.arming_client.call_async(arm_req)

        self.log("Sent OFFBOARD + ARM commands.")

    # ------------------------------------------------------------
    # Main trajectory logic
    # ------------------------------------------------------------
    def timer_cb(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.start_time is None:
            self.start_time = now
            self.log("Starting zigzag trajectory...")

        t = now - self.start_time

        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"

        # Zigzag motion: move forward in X, oscillate in Y
        pose.pose.position.x = self.speed * t
        pose.pose.position.y = self.amplitude * math.sin(self.frequency * t * math.pi * 2)
        pose.pose.position.z = self.takeoff_alt

        # Publish position
        self.local_pos_pub.publish(pose)

        # Arm and switch mode if needed
        if self.current_state.mode != "OFFBOARD" or not self.current_state.armed:
            self.arm_and_offboard()

        # Stop after duration
        if t >= self.flight_duration:
            self.log(f"Flight complete after {t:.1f} seconds. Shutting down.")
            self.log_file.close()
            self.destroy_timer(self.timer)
            self.destroy_node()
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = ZigZagNode()
    rclpy.spin(node)


if __name__ == '__main__':
    main()

