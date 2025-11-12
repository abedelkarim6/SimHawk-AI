#!/usr/bin/env python3
"""
Multi-sensor data collector for Gazebo X500 drone.
Collects: Camera images, GPS (NavSat), IMU, and Camera IMU data.

Requirements:
    pip install opencv-python numpy gz-transport13 gz-msgs10
"""

import cv2
import csv
import json
import time
import numpy as np
from datetime import datetime
from pathlib import Path

# Try importing Gazebo Transport bindings
try:
    from gz.msgs10.image_pb2 import Image
    from gz.msgs10.navsat_pb2 import NavSat
    from gz.msgs10.imu_pb2 import IMU
    from gz.transport13 import Node
    GZ_AVAILABLE = True
except ImportError:
    print("⚠️  Gazebo Python bindings not available.")
    print("   Install with: pip install gz-transport13 gz-msgs10")
    GZ_AVAILABLE = False


class MultiSensorCollector:
    def __init__(self, output_folder="collected_data"):
        self.output_folder = Path(output_folder)
        self.image_folder = self.output_folder / "images"
        self.data_folder = self.output_folder / "sensor_data"
        self.image_folder.mkdir(parents=True, exist_ok=True)
        self.data_folder.mkdir(parents=True, exist_ok=True)

        self.image_count = 0
        self.width, self.height = 512, 512

        # CSV setup
        self.gps_csv = open(self.data_folder / "gps_data.csv", "w", newline="")
        self.imu_csv = open(self.data_folder / "imu_data.csv", "w", newline="")
        self.cam_imu_csv = open(self.data_folder / "camera_imu_data.csv", "w", newline="")

        self.gps_writer = csv.writer(self.gps_csv)
        self.imu_writer = csv.writer(self.imu_csv)
        self.cam_imu_writer = csv.writer(self.cam_imu_csv)

        # Write headers
        self.gps_writer.writerow([
            "timestamp", "image_id", "latitude", "longitude", "altitude",
            "vel_east", "vel_north", "vel_up"
        ])
        imu_header = [
            "timestamp", "image_id",
            "orientation_x", "orientation_y", "orientation_z", "orientation_w",
            "angular_vel_x", "angular_vel_y", "angular_vel_z",
            "linear_accel_x", "linear_accel_y", "linear_accel_z"
        ]
        self.imu_writer.writerow(imu_header)
        self.cam_imu_writer.writerow(imu_header)

        print(f"✅ Output folders ready:\n   Images: {self.image_folder}\n   Data:   {self.data_folder}")

    # ----------------- CALLBACKS -----------------
    def camera_callback(self, msg: Image):
        try:
            timestamp = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape((self.height, self.width, 3))
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            filename = f"img_{self.image_count:06d}.png"
            cv2.imwrite(str(self.image_folder / filename), img_bgr)
            print(f"[{self.image_count:06d}] Image saved at t={timestamp:.3f}s")
            self.image_count += 1
        except Exception as e:
            print(f"❌ Error processing image: {e}")

    def gps_callback(self, msg: NavSat):
        try:
            timestamp = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            self.gps_writer.writerow([
                timestamp, self.image_count - 1,
                msg.latitude_deg, msg.longitude_deg, msg.altitude,
                msg.velocity_east, msg.velocity_north, msg.velocity_up
            ])
            self.gps_csv.flush()
        except Exception as e:
            print(f"❌ GPS error: {e}")

    def imu_callback(self, msg: IMU, writer, label="IMU"):
        try:
            timestamp = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            writer.writerow([
                timestamp, self.image_count - 1,
                msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w,
                msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
                msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z
            ])
            self.imu_csv.flush()
        except Exception as e:
            print(f"❌ {label} error: {e}")

    # ----------------- CLEANUP -----------------
    def save_metadata(self):
        metadata = {
            "total_images": self.image_count,
            "image_resolution": f"{self.width}x{self.height}",
            "collection_date": datetime.now().isoformat()
        }
        with open(self.data_folder / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        print("💾 Metadata saved.")

    def close(self):
        for f in [self.gps_csv, self.imu_csv, self.cam_imu_csv]:
            f.close()
        self.save_metadata()
        print("🧹 Closed all files cleanly.")


# ----------------- MAIN -----------------
def main():
    if not GZ_AVAILABLE:
        return

    print("=" * 60)
    print("🚁 Gazebo Multi-Sensor Data Collector")
    print("=" * 60)
    print("Collecting:\n  • Camera images\n  • GPS/NavSat\n  • IMU\n  • Camera IMU")
    print("Press Ctrl+C to stop.\n")

    collector = MultiSensorCollector()
    node = Node()

    # ---- Subscriptions ----
    topics = {
        "/down_camera": (Image, collector.camera_callback),
        "/x500/gps": (NavSat, collector.gps_callback),
        "/x500/imu": (IMU, lambda msg: collector.imu_callback(msg, collector.imu_writer, "IMU")),
        "/camera_imu": (IMU, lambda msg: collector.imu_callback(msg, collector.cam_imu_writer, "Camera IMU"))
    }

    for topic, (msg_type, callback) in topics.items():
        if node.subscribe(msg_type, topic, callback):
            print(f"✅ Subscribed to {topic}")
        else:
            print(f"⚠️  Failed to subscribe: {topic}")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping data collection...")
    finally:
        collector.close()
        print("✅ Done.")


if __name__ == "__main__":
    main()

