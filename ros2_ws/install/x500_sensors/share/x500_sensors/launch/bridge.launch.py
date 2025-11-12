from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Bridge camera image
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=[
                "/world/default/model/x500_mono_cam_down_0/link/camera_link/sensor/imager/image" +
                "@sensor_msgs/msg/Image@gz.msgs.Image"
            ],
            output="screen"
        ),

        # Bridge camera info
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=[
                "/world/default/model/x500_mono_cam_down_0/link/camera_link/sensor/imager/camera_info" +
                "@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo"
            ],
            output="screen"
        ),

        # Bridge camera IMU
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=[
                "/world/default/model/x500_mono_cam_down_0/link/camera_link/sensor/camera_imu/imu" +
                "@sensor_msgs/msg/Imu@gz.msgs.IMU"
            ],
            output="screen"
        ),
    ])

