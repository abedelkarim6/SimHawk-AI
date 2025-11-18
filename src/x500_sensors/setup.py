from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'x500_sensors'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Install all launch files automatically
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='abed',
    maintainer_email='abed@todo.todo',
    description='Package containing IMU and Camera listeners + MAVROS integration',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        'circular_trajectory_node.py = x500_sensors.circular_trajectory_node:main',
        'zigzag_trajectory_node.py = x500_sensors.zigzag_trajectory_node:main',
        'polygon_trajectory_node.py = x500_sensors.polygon_trajectory_node:main',
        'straight_trajectory_node.py = x500_sensors.straight_trajectory_node:main'
        ],
    },
)

