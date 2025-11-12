#!/usr/bin/env python3
"""
Collects GPS and IMU data from Gazebo with timestamps
"""

import csv
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    from gz.msgs10.navsat_pb2 import NavSat
    from gz.msgs10.imu_pb2 import IMU
    from gz.transport13 import Node
    GZ_AVAILABLE = True
except ImportError:
    print("⚠️  Gazebo Python bindings not available.")
    GZ_AVAILABLE = False


class SensorCollector:
    def __init__(self, output_folder="sensor_data"):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # CSV files
        self.gps_csv = open(self.output_folder / "gps_data.csv", "w", newline="")
        self.imu_csv = open(self.output_folder / "imu_data.csv", "w", newline="")
        self.cam_imu_csv = open(self.output_folder / "camera_imu_data.csv", "w", newline="")

        self.gps_writer = csv.writer(self.gps_csv)
        self.imu_writer = csv.writer(self.imu_csv)
        self.cam_imu_writer = csv.writer(self.cam_imu_csv)

        # Headers
        self.gps_writer.writerow([
            "timestamp_sec", "timestamp_nsec", "latitude", "longitude", 
            "altitude", "vel_east", "vel_north", "vel_up"
        ])
        
        imu_header = [
            "timestamp_sec", "timestamp_nsec",
            "orientation_x", "orientation_y", "orientation_z", "orientation_w",
            "angular_vel_x", "angular_vel_y", "angular_vel_z",
            "linear_accel_x", "linear_accel_y", "linear_accel_z"
        ]
        self.imu_writer.writerow(imu_header)
        self.cam_imu_writer.writerow(imu_header)

        self.gps_count = 0
        self.imu_count = 0
        self.cam_imu_count = 0

        print(f"✅ Sensor collector ready: {self.output_folder}")

    def gps_callback(self, msg: NavSat):
        try:
            self.gps_writer.writerow([
                msg.header.stamp.sec,
                msg.header.stamp.nsec,
                msg.latitude_deg,
                msg.longitude_deg,
                msg.altitude,
                msg.velocity_east,
                msg.velocity_north,
                msg.velocity_up
            ])
            self.gps_csv.flush()
            self.gps_count += 1
            if self.gps_count % 10 == 0:
                print(f"GPS: {self.gps_count}")
        except Exception as e:
            print(f"❌ GPS error: {e}")

    def imu_callback(self, msg: IMU):
        try:
            self.imu_writer.writerow([
                msg.header.stamp.sec,
                msg.header.stamp.nsec,
                msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w,
                msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
                msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z
            ])
            self.imu_csv.flush()
            self.imu_count += 1
            if self.imu_count % 50 == 0:
                print(f"IMU: {self.imu_count}")
        except Exception as e:
            print(f"❌ IMU error: {e}")

    def cam_imu_callback(self, msg: IMU):
        try:
            self.cam_imu_writer.writerow([
                msg.header.stamp.sec,
                msg.header.stamp.nsec,
                msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w,
                msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
                msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z
            ])
            self.cam_imu_csv.flush()
            self.cam_imu_count += 1
            if self.cam_imu_count % 50 == 0:
                print(f"Camera IMU: {self.cam_imu_count}")
        except Exception as e:
            print(f"❌ Camera IMU error: {e}")

    def close(self):
        for f in [self.gps_csv, self.imu_csv, self.cam_imu_csv]:
            f.close()
        
        metadata = {
            "gps_samples": self.gps_count,
            "imu_samples": self.imu_count,
            "camera_imu_samples": self.cam_imu_count,
            "collection_date": datetime.now().isoformat()
        }
        with open(self.output_folder / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✅ Collected: GPS={self.gps_count}, IMU={self.imu_count}, CamIMU={self.cam_imu_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='sensor_data', help='Output folder')
    args = parser.parse_args()

    if not GZ_AVAILABLE:
        return

    print("🚁 Gazebo Sensor Data Collector")
    print("Press Ctrl+C to stop\n")

    collector = SensorCollector(args.output)
    node = Node()

    # Subscribe to Gazebo topics
    topics = {
        "/world/baylands/model/x500_mono_cam_down_0/link/base_link/sensor/navsat_sensor/navsat": 
            (NavSat, collector.gps_callback),
        "/world/baylands/model/x500_mono_cam_down_0/link/base_link/sensor/imu_sensor/imu": 
            (IMU, collector.imu_callback),
        "/world/baylands/model/x500_mono_cam_down_0/link/camera_link/sensor/camera_imu/imu": 
            (IMU, collector.cam_imu_callback)
    }

    for topic, (msg_type, callback) in topics.items():
        if node.subscribe(msg_type, topic, callback):
            print(f"✅ {topic.split('/')[-1]}")
        else:
            print(f"❌ Failed: {topic}")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    finally:
        collector.close()


if __name__ == "__main__":
    main()
