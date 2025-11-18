#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
import math
import time
import os


class CircularNode(Node):
    def __init__(self):
        super().__init__('circular_node')

        # ------------------------------------------------------------
        # Declare parameters with defaults
        # ------------------------------------------------------------
        self.declare_parameter('trajectory_duration', 300.0)
        self.declare_parameter('takeoff_alt', 25.0)
        self.declare_parameter('radius', 35.0)
        self.declare_parameter('omega', 0.2)

        # ------------------------------------------------------------
        # Read parameter values
        # ------------------------------------------------------------
        #self.start_x = self.get_parameter('start_x').value
        #self.start_y = self.get_parameter('start_y').value
        self.flight_duration = float(self.get_parameter('trajectory_duration').value)
        self.takeoff_alt = float(self.get_parameter('takeoff_alt').value)
        self.radius = float(self.get_parameter('radius').value)
        self.omega = float(self.get_parameter('omega').value)
        
        #self.get_logger().info(f"Starting position: ({self.start_x}, {self.start_y})")

        # ------------------------------------------------------------
        # Log configuration
        # ------------------------------------------------------------
        log_dir = os.path.expanduser("~/x500_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, "trajectory_node.log")
        self.log_file = open(self.log_path, "w")

        self.log(f"=== Circular Trajectory Node Initialized ===")
        self.log(f"Trajectory duration: {self.flight_duration:.1f} s")
        self.log(f"Takeoff altitude: {self.takeoff_alt:.1f} m")
        self.log(f"Radius: {self.radius:.1f} m")
        self.log(f"Angular velocity (omega): {self.omega:.3f} rad/s")

        # ------------------------------------------------------------
        # PX4 Communication
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
    # Helper Functions
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
        
    def calculate_trajectory_point(self, t):
        """Calculate trajectory point at time t, offset by start position"""
        # Original circular trajectory calculation
        x = self.radius * cos(self.omega * t)
        y = self.radius * sin(self.omega * t)
        
        # Add offset for random starting position
        #x += self.start_x
        #y += self.start_y
        z = self.takeoff_alt
        
        return x, y, z

    # ------------------------------------------------------------
    # Main timer callback
    # ------------------------------------------------------------
    def timer_cb(self):
        now = self.get_clock().now().nanoseconds / 1e9

        if self.start_time is None:
            self.start_time = now
            self.log("Starting trajectory...")

        elapsed = now - self.start_time

        # Circular trajectory
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        pose.pose.position.x = self.radius * math.cos(self.omega * elapsed)
        pose.pose.position.y = self.radius * math.sin(self.omega * elapsed)
        pose.pose.position.z = self.takeoff_alt

        # Publish to MAVROS
        self.local_pos_pub.publish(pose)

        # Arm and set OFFBOARD if not already
        if self.current_state.mode != "OFFBOARD" or not self.current_state.armed:
            self.arm_and_offboard()

        # Stop after flight duration
        if elapsed >= self.flight_duration:
            self.log(f"Trajectory complete after {elapsed:.1f} seconds. Shutting down.")
            self.log_file.close()
            self.destroy_timer(self.timer)
            self.destroy_node()
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = CircularNode()
    rclpy.spin(node)


if __name__ == '__main__':
    main()

