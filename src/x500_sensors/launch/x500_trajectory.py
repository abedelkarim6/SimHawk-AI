#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, DeclareLaunchArgument, TimerAction, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration, TextSubstitution
import os


def launch_setup(context, *args, **kwargs):
    """Setup function to resolve LaunchConfiguration values"""
    
    # Get all launch configuration values
    trajectory_type = context.launch_configurations['trajectory_type']
    run_number = context.launch_configurations['run_number']
    output_dir = context.launch_configurations['output_dir']
    trajectory_duration = context.launch_configurations['trajectory_duration']
    takeoff_alt = context.launch_configurations['takeoff_alt']
    radius = context.launch_configurations['radius']
    omega = context.launch_configurations['omega']
    num_vertices = context.launch_configurations['num_vertices']
    vertex_duration = context.launch_configurations['vertex_duration']
    amplitude = context.launch_configurations['amplitude']
    speed = context.launch_configurations['speed']
    frequency = context.launch_configurations['frequency']
    direction_angle = context.launch_configurations['direction_angle']
    
    # Build absolute paths as strings
    base_dir = os.path.expanduser('~/ros2_ws/data_collection')
    run_name = f"{trajectory_type}_run{run_number}"
    
    imgs_path = os.path.join(base_dir, output_dir, run_name, 'images')
    sensor_path = os.path.join(base_dir, output_dir, run_name, 'sensors')
    bag_path = os.path.join(base_dir, output_dir, run_name, 'rosbag')
    
    # Ensure directories exist
    os.makedirs(imgs_path, exist_ok=True)
    os.makedirs(sensor_path, exist_ok=True)
    os.makedirs(bag_path, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Data Collection Launch Configuration")
    print(f"{'='*60}")
    print(f"Trajectory: {trajectory_type}")
    print(f"Run Number: {run_number}")
    print(f"Duration: {trajectory_duration}s")
    print(f"Images Path: {imgs_path}")
    print(f"Sensor Path: {sensor_path}")
    print(f"Bag Path: {bag_path}")
    print(f"{'='*60}\n")
    
    actions = []
    
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
        output='screen',
        name='mavros_node'
    )
    actions.append(mavros_node)
    
    # ------------------------------------------------------------
    # Dynamic trajectory node
    # ------------------------------------------------------------
    trajectory_executable = f"{trajectory_type}_trajectory_node.py"
    
    trajectory_node = Node(
        package='x500_sensors',
        executable=trajectory_executable,
        name='trajectory_node',
        output='screen',
        parameters=[{
            'trajectory_duration': float(trajectory_duration),
            'takeoff_alt': float(takeoff_alt),
            'radius': float(radius),
            'omega': float(omega),
            'num_vertices': int(num_vertices),
            'vertex_duration': float(vertex_duration),
            'amplitude': float(amplitude),
            'speed': float(speed),
            'frequency': float(frequency),
            'direction_angle': float(direction_angle)
        }]
    )
    actions.append(trajectory_node)
    
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
        output='log',
        name='rosbag_recorder'
    )
    actions.append(rosbag)
    
    # ------------------------------------------------------------
    # Image Collector - Started after 3 second delay
    # ------------------------------------------------------------
    img_collector_script = os.path.join(base_dir, 'scripts', 'imgs_collection.py')
    
    # Verify script exists
    if not os.path.exists(img_collector_script):
        print(f"ERROR: Image collector script not found: {img_collector_script}")
    else:
        print(f"Found image collector: {img_collector_script}")
    
    imgs_collector = TimerAction(
        period=3.0,
        actions=[
            LogInfo(msg=f"Starting image collector: {img_collector_script} --output {imgs_path}"),
            ExecuteProcess(
                cmd=['python3', img_collector_script, '--output', imgs_path],
                output='screen',
                shell=False,
                name='imgs_collector'
            )
        ]
    )
    actions.append(imgs_collector)
    
    # ------------------------------------------------------------
    # Sensor Collector - Started after 3 second delay
    # ------------------------------------------------------------
    sensor_collector_script = os.path.join(base_dir, 'scripts', 'sensor_collector.py')
    
    # Verify script exists
    if not os.path.exists(sensor_collector_script):
        print(f"ERROR: Sensor collector script not found: {sensor_collector_script}")
    else:
        print(f"Found sensor collector: {sensor_collector_script}")
    
    sensor_collector = TimerAction(
        period=3.0,
        actions=[
            LogInfo(msg=f"Starting sensor collector: {sensor_collector_script} --output {sensor_path}"),
            ExecuteProcess(
                cmd=['python3', sensor_collector_script, '--output', sensor_path],
                output='screen',
                shell=False,
                name='sensor_collector'
            )
        ]
    )
    actions.append(sensor_collector)
    
    return actions


def generate_launch_description():
    # ------------------------------------------------------------
    # Declare Launch Arguments
    # ------------------------------------------------------------
    trajectory_type_arg = DeclareLaunchArgument(
        'trajectory_type',
        default_value='circular',
        description='Type of trajectory to execute'
    )
    
    run_number_arg = DeclareLaunchArgument(
        'run_number',
        default_value='01',
        description='Run number for this collection'
    )
    
    output_dir_arg = DeclareLaunchArgument(
        'output_dir',
        default_value='training_data',
        description='Output directory name'
    )
    
    trajectory_duration_arg = DeclareLaunchArgument(
        'trajectory_duration',
        default_value='120.0',
        description='Trajectory flight duration in seconds'
    )
    
    takeoff_alt_arg = DeclareLaunchArgument(
        'takeoff_alt',
        default_value='25.0',
        description='Takeoff altitude in meters'
    )
    
    radius_arg = DeclareLaunchArgument(
        'radius',
        default_value='35.0',
        description='Circular/Polygon trajectory radius in meters'
    )
    
    omega_arg = DeclareLaunchArgument(
        'omega',
        default_value='0.2',
        description='Circular trajectory angular velocity in rad/s'
    )
    
    num_vertices_arg = DeclareLaunchArgument(
        'num_vertices',
        default_value='6',
        description='Number of vertices for polygon trajectory'
    )
    
    vertex_duration_arg = DeclareLaunchArgument(
        'vertex_duration',
        default_value='5.0',
        description='Time to hover at each vertex in seconds'
    )
    
    amplitude_arg = DeclareLaunchArgument(
        'amplitude',
        default_value='10.0',
        description='Zigzag amplitude in meters'
    )
    
    speed_arg = DeclareLaunchArgument(
        'speed',
        default_value='1.0',
        description='Speed for zigzag/straight trajectories in m/s'
    )
    
    frequency_arg = DeclareLaunchArgument(
        'frequency',
        default_value='0.3',
        description='Zigzag frequency in Hz'
    )
    
    direction_angle_arg = DeclareLaunchArgument(
        'direction_angle',
        default_value='0.0',
        description='Direction angle for zigzag/straight in degrees'
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
        OpaqueFunction(function=launch_setup)
    ])
