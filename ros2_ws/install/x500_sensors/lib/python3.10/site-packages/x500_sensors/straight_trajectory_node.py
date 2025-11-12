#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
import math
import os


class StraightLineNode(Node):
    def __init__(self):
        super().__init__('straight_line_node')

        # ------------------------------------------------------------
        # Declare parameters with defaults
        # ------------------------------------------------------------
        self.declare_parameter('trajectory_duration', 300.0)
        self.declare_parameter('takeoff_alt', 25.0)
        self.declare_parameter('forward_speed', 1.0)
        self.declare_parameter('direction_angle', 0.0)

        # ------------------------------------------------------------
        # Read parameter values
        # ------------------------------------------------------------
        self.flight_duration = float(self.get_parameter('trajectory_duration').value)
        self.takeoff_alt = float(self.get_parameter('takeoff_alt').value)
        self.forward_speed = float(self.get_parameter('forward_speed').value)
        self.direction_angle = float(self.get_parameter('direction_angle').value)

        # ------------------------------------------------------------
        # Logging setup
        # ------------------------------------------------------------
        log_dir = os.path.expanduser("~/x500_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, "straight_node.log")
        self.log_file = open(self.log_path, "w")

        self.log("=== Straight-Line Trajectory Node Initialized ===")
        self.log(f"Trajectory duration: {self.flight_duration:.1f} s")
        self.log(f"Takeoff altitude: {self.takeoff_alt:.1f} m")
        self.log(f"Forward speed: {self.forward_speed:.2f} m/s")
        self.log(f"Direction angle: {math.degrees(self.direction_angle):.1f}°")

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
    # Helpers
    # ------------------------------------------------------------
    def log(self, text):
        stamp = self.get_clock().now().to_msg()
        line = f"[{stamp.sec}.{stamp.nanosec:09d}] {text}\n"
        self.log_file.write(line)
        self.log_file.flush()
        self.get_logger().info(text)

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
            self.log("Starting straight-line trajectory...")

        elapsed = now - self.start_time

        # Straight-line trajectory
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        pose.pose.position.x = self.forward_speed * elapsed * math.cos(self.direction_angle)
        pose.pose.position.y = self.forward_speed * elapsed * math.sin(self.direction_angle)
        pose.pose.position.z = self.takeoff_alt

        # Publish to MAVROS
        self.local_pos_pub.publish(pose)

        # Arm and mode
        if self.current_state.mode != "OFFBOARD" or not self.current_state.armed:
            self.arm_and_offboard()

        # Stop after flight duration
        if elapsed >= self.flight_duration:
            self.log(f"Flight complete after {elapsed:.1f} seconds. Shutting down.")
            self.log_file.close()
            self.destroy_timer(self.timer)
            self.destroy_node()
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = StraightLineNode()
    rclpy.spin(node)


if __name__ == '__main__':
    main()
