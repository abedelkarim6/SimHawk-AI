from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Start MAVROS node
        Node(
            package='mavros',
            executable='mavros_node',
            name='mavros_node',
            output='screen',
            parameters=[{
                #'fcu_url': 'udp://127.0.0.1:14540',
                #'gcs_url': '',
                #'target_system_id': 1,
                #'target_component_id': 1,
                #'system_id': 1
            }]
        ),

        # Start IMU listener node
        Node(
            package='x500_sensors',
            executable='imu_listener',
            name='imu_listener',
            output='screen'
        ),

        # Start Camera listener node
        Node(
            package='x500_sensors',
            executable='camera_listener',
            name='camera_listener',
            output='screen'
        )
    ])

