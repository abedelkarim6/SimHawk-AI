#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
import math
import random
import os


class PolygonNode(Node):
    def __init__(self):
        super().__init__('polygon_node')

        # ------------------------------------------------------------
        # Declare parameters with defaults
        # ------------------------------------------------------------
        self.declare_parameter('trajectory_duration', 120.0)
        self.declare_parameter('takeoff_alt', 25.0)
        self.declare_parameter('radius', 8.0)
        self.declare_parameter('num_vertices', 6)
        self.declare_parameter('vertex_duration', 5.0)

        # ------------------------------------------------------------
        # Read parameter values
        # ------------------------------------------------------------
        self.flight_duration = float(self.get_parameter('trajectory_duration').value)
        self.takeoff_alt = float(self.get_parameter('takeoff_alt').value)
        self.radius = float(self.get_parameter('radius').value)
        self.num_vertices = int(self.get_parameter('num_vertices').value)
        self.vertex_duration = float(self.get_parameter('vertex_duration').value)

        # ------------------------------------------------------------
        # Logging setup
        # ------------------------------------------------------------
        log_dir = os.path.expanduser("~/x500_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, "polygon_node.log")
        self.log_file = open(self.log_path, "w")

        self.log(f"=== Polygon Trajectory Node Initialized ===")
        self.log(f"Trajectory duration: {self.flight_duration:.1f} s")
        self.log(f"Takeoff altitude: {self.takeoff_alt:.1f} m")
        self.log(f"Radius: {self.radius:.1f} m")
        self.log(f"Vertices: {self.num_vertices}")
        self.log(f"Vertex duration: {self.vertex_duration:.1f} s")

        # ------------------------------------------------------------
        # MAVROS communication
        # ------------------------------------------------------------
        self.state_sub = self.create_subscription(State, '/mavros/state', self.state_cb, 10)
        self.local_pos_pub = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', 10)
        self.arming_client = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.set_mode_client = self.create_client(SetMode, '/mavros/set_mode')

        # Internal state
        self.current_state = State()
        self.start_time = None
        self.current_vertex = 0

        # Generate random polygon vertices
        self.vertices = [
            (random.uniform(-self.radius, self.radius),
             random.uniform(-self.radius, self.radius))
            for _ in range(self.num_vertices)
        ]
        self.log(f"Generated {len(self.vertices)} polygon vertices.")

        # 20 Hz timer
        self.timer = self.create_timer(0.05, self.timer_cb)

    # ------------------------------------------------------------
    # Helper functions
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
    # Main control loop
    # ------------------------------------------------------------
    def timer_cb(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.start_time is None:
            self.start_time = now
            self.log("Starting polygon trajectory...")

        elapsed = now - self.start_time
        total_vertices = len(self.vertices)

        # Determine which segment we’re on
        segment_index = int(elapsed / self.vertex_duration)
        self.current_vertex = segment_index % total_vertices

        # Interpolate between current and next vertex
        t_seg = (elapsed % self.vertex_duration) / self.vertex_duration
        v1 = self.vertices[self.current_vertex]
        v2 = self.vertices[(self.current_vertex + 1) % total_vertices]

        x = v1[0] + (v2[0] - v1[0]) * t_seg
        y = v1[1] + (v2[1] - v1[1]) * t_seg
        z = self.takeoff_alt

        # Publish position
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = z

        self.local_pos_pub.publish(pose)

        # Ensure mode/arming
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
    node = PolygonNode()
    rclpy.spin(node)


if __name__ == '__main__':
    main()

