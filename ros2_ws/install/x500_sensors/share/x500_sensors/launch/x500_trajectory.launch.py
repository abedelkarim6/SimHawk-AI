#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration, TextSubstitution
import os


def generate_launch_description():
    # ------------------------------------------------------------
    # Declare Launch Arguments
    # ------------------------------------------------------------
    trajectory_type_arg = DeclareLaunchArgument('trajectory_type', default_value='circular')
    run_number_arg = DeclareLaunchArgument('run_number', default_value='01')
    output_dir_arg = DeclareLaunchArgument('output_dir', default_value="training_data")
    trajectory_duration_arg = DeclareLaunchArgument('trajectory_duration', default_value='120.0')
    takeoff_alt_arg = DeclareLaunchArgument('takeoff_alt', default_value='25.0')
    radius_arg = DeclareLaunchArgument('radius', default_value='35.0')
    omega_arg = DeclareLaunchArgument('omega', default_value='0.2')
    num_vertices_arg = DeclareLaunchArgument('num_vertices', default_value='6')
    vertex_duration_arg = DeclareLaunchArgument('vertex_duration', default_value='5.0')
    amplitude_arg = DeclareLaunchArgument('amplitude', default_value='10.0')
    speed_arg = DeclareLaunchArgument('speed', default_value='1.0')
    frequency_arg = DeclareLaunchArgument('frequency', default_value='0.3')
    direction_angle_arg = DeclareLaunchArgument('direction_angle', default_value='0.0')

    # ------------------------------------------------------------
    # Load configurations
    # ------------------------------------------------------------
    trajectory_type = LaunchConfiguration('trajectory_type')
    run_number = LaunchConfiguration('run_number')
    output_dir = LaunchConfiguration('output_dir')
    trajectory_duration = LaunchConfiguration('trajectory_duration')
    takeoff_alt = LaunchConfiguration('takeoff_alt')
    radius = LaunchConfiguration('radius')
    omega = LaunchConfiguration('omega')
    num_vertices = LaunchConfiguration('num_vertices')
    vertex_duration = LaunchConfiguration('vertex_duration')
    amplitude = LaunchConfiguration('amplitude')
    speed = LaunchConfiguration('speed')
    frequency = LaunchConfiguration('frequency')
    direction_angle = LaunchConfiguration('direction_angle')

    # ------------------------------------------------------------
    # Base paths - Fixed: base_path is now a list
    # ------------------------------------------------------------
    base_path = [
        TextSubstitution(text=os.path.expanduser('~/ros2_ws/data_collection/')),
        output_dir,
        TextSubstitution(text="/")
    ]

    # Build paths as concatenated lists
    imgs_path = base_path + [
        trajectory_type,
        TextSubstitution(text='_run'),
        run_number,
        TextSubstitution(text='/images')
    ]

    sensor_path = base_path + [
        trajectory_type,
        TextSubstitution(text='_run'),
        run_number,
        TextSubstitution(text='/sensors')
    ]

    bag_path = base_path + [
        trajectory_type,
        TextSubstitution(text='_run'),
        run_number,
        TextSubstitution(text='/rosbag')
    ]

    # ------------------------------------------------------------
    # MAVROS node
    # ------------------------------------------------------------
    mavros_node = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'mavros', 'mavros_node',
            '--ros-args',
            '-p', 'fcu_url:=udp://:14540@localhost:14557',
            '-p', 'plugin_allowlist:=[camera,command,sys_status,sys_time,imu,local_position,global_position,setpoint_position]'
        ],
        output='screen'
    )

    # ------------------------------------------------------------
    # Dynamic trajectory node
    # ------------------------------------------------------------
    trajectory_node = Node(
        package='x500_sensors',
        executable=[trajectory_type, TextSubstitution(text='_trajectory_node.py')],
        name='trajectory_node',
        output='screen',
        parameters=[{
            'trajectory_duration': trajectory_duration,
            'takeoff_alt': takeoff_alt,
            'radius': radius,
            'omega': omega,
            'num_vertices': num_vertices,
            'vertex_duration': vertex_duration,
            'amplitude': amplitude,
            'speed': speed,
            'frequency': frequency,
            'direction_angle': direction_angle
        }]
    )

    # ------------------------------------------------------------
    # Rosbag Recorder
    # ------------------------------------------------------------
    rosbag = ExecuteProcess(
        cmd=[
            'ros2', 'bag', 'record',
            '--compression-mode', 'file',
            '--compression-format', 'zstd',
            '-o', bag_path,
            '/mavros/imu/data',
            '/mavros/local_position/pose',
            '/mavros/global_position/global',
            '/mavros/state'
        ],
        output='log'
    )

    # ------------------------------------------------------------
    # Image Collector
    # ------------------------------------------------------------
    imgs_collector = TimerAction(
        period=3.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3',
                    os.path.expanduser('~/ros2_ws/data_collection/imgs_collection.py'),
                    '--output', imgs_path
                ],
                output='screen'
            )
        ]
    )

    # ------------------------------------------------------------
    # Sensor Collector
    # ------------------------------------------------------------
    sensor_collector = TimerAction(
        period=3.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3',
                    os.path.expanduser('~/ros2_ws/data_collection/sensor_collector.py'),
                    '--output', sensor_path
                ],
                output='screen'
            )
        ]
    )

    # ------------------------------------------------------------
    # Launch Description
    # ------------------------------------------------------------
    return LaunchDescription([
        trajectory_type_arg,
        run_number_arg,
        output_dir_arg,  
        trajectory_duration_arg,
        takeoff_alt_arg,
        radius_arg,
        omega_arg,
        num_vertices_arg,
        vertex_duration_arg,
        amplitude_arg,
        speed_arg,
        frequency_arg,
        direction_angle_arg,
        mavros_node,
        trajectory_node,
        rosbag,
        imgs_collector,
        sensor_collector
    ])
