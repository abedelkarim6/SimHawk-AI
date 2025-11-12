#!/usr/bin/env python3
"""
Image collector with timestamp recording
Saves images AND timestamps for accurate synchronization
"""

import cv2
import csv
import numpy as np
import os
import argparse
from datetime import datetime

try:
    from gz.msgs10.image_pb2 import Image
    from gz.transport13 import Node
    GZ_AVAILABLE = True
except ImportError:
    print("Warning: Gazebo Python bindings not available.")
    print("Install with: pip install gz-transport13 gz-msgs10")
    GZ_AVAILABLE = False


class ImageSubscriber:
    def __init__(self, output_folder="captured_images"):
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        self.image_count = 0
        self.width = 512
        self.height = 512
        
        # Create timestamp CSV
        self.csv_file = open(os.path.join(output_folder, "image_timestamps.csv"), "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["image_id", "filename", "timestamp_sec", "timestamp_nsec", "timestamp"])
        
        print(f"✅ Image collector ready: {output_folder}")
        print("   Saving images with timestamps")
        
    def callback(self, msg: Image):
        """Callback when image is received"""
        try:
            # Extract timestamp from message
            timestamp_sec = msg.header.stamp.sec
            timestamp_nsec = msg.header.stamp.nsec
            timestamp = timestamp_sec + timestamp_nsec * 1e-9
            
            # Extract image data
            img_data = np.frombuffer(msg.data, dtype=np.uint8)
            img_data = img_data.reshape((self.height, self.width, 3))
            
            # Convert RGB to BGR for OpenCV
            img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
            
            # Save image
            filename = f"img_{self.image_count:06d}.png"
            filepath = os.path.join(self.output_folder, filename)
            cv2.imwrite(filepath, img_bgr)
            
            # Save timestamp to CSV
            self.csv_writer.writerow([
                self.image_count, 
                filename, 
                timestamp_sec, 
                timestamp_nsec, 
                timestamp
            ])
            self.csv_file.flush()
            
            self.image_count += 1
            if self.image_count % 10 == 0:
                print(f"[{self.image_count:06d}] t={timestamp:.3f}s")
            
        except Exception as e:
            print(f"Error processing image: {e}")
    
    def close(self):
        self.csv_file.close()
        print(f"\n✅ Total images saved: {self.image_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='captured_images', help='Output folder')
    args = parser.parse_args()
    
    if not GZ_AVAILABLE:
        return
    
    print("🚁 Gazebo Image Collector (with timestamps)")
    print("Press Ctrl+C to stop\n")
    
    subscriber = ImageSubscriber(args.output)
    
    # Create node and subscribe
    node = Node()
    topic = "/world/baylands/model/x500_mono_cam_down_0/link/camera_link/sensor/imager/image"
    topic = "/down_camera"
    
    if not node.subscribe(Image, topic, subscriber.callback):
        print(f"Error subscribing to topic: {topic}")
        return
    
    print(f"✅ Subscribed to camera")
    
    # Keep running
    try:
        import time
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n🛑 Stopping...")
    finally:
        subscriber.close()


if __name__ == "__main__":
    main()
