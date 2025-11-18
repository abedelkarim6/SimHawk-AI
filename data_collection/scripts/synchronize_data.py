#!/usr/bin/env python3
"""
Post-process synchronization using REAL image timestamps from CSV
"""

import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import json


def timestamp_to_sec(sec, nsec):
    """Convert sec + nsec to float seconds"""
    return sec + nsec * 1e-9


def find_closest_timestamp(target_time, data_df, time_col='timestamp', max_diff=0.1):
    """Find closest row in dataframe to target time"""
    if data_df.empty:
        return None
    
    time_diffs = np.abs(data_df[time_col] - target_time)
    min_idx = time_diffs.idxmin()
    
    if time_diffs[min_idx] <= max_diff:
        return data_df.loc[min_idx]
    return None


def synchronize_data(images_folder, sensor_folder, output_file, max_time_diff=0.1):
    """
    Synchronize images with GPS and IMU data using REAL timestamps
    
    Args:
        images_folder: Path to folder with images AND image_timestamps.csv
        sensor_folder: Path to folder with sensor CSVs
        output_file: Output CSV file path
        max_time_diff: Maximum time difference for sync (seconds)
    """
    
    images_folder = Path(images_folder)
    sensor_folder = Path(sensor_folder)
    
    print(f"📂 Images folder: {images_folder}")
    print(f"📂 Sensor folder: {sensor_folder}")
    
    # Check if image_timestamps.csv exists
    img_timestamps_file = images_folder / "image_timestamps.csv"
    if not img_timestamps_file.exists():
        print(f"\n❌ ERROR: {img_timestamps_file} not found!")
        print("   Make sure you're using the updated imgs_collection.py that saves timestamps.")
        return
    
    # Load image timestamps
    print("\n📊 Loading image timestamps...")
    img_timestamps_df = pd.read_csv(img_timestamps_file)
    print(f"   Found {len(img_timestamps_df)} images with timestamps")
    
    # Load sensor data
    print("\n📊 Loading sensor data...")
    gps_df = pd.read_csv(sensor_folder / "gps_data.csv")
    imu_df = pd.read_csv(sensor_folder / "imu_data.csv")
    
    # Check if camera IMU file exists
    #cam_imu_file = sensor_folder / "camera_imu_data.csv"
    #if cam_imu_file.exists():
    #    cam_imu_df = pd.read_csv(cam_imu_file)
    #    has_cam_imu = True
    #else:
    #    cam_imu_df = pd.DataFrame()
    #    has_cam_imu = False
    #    print("   ⚠️  No camera_imu_data.csv found - skipping Camera IMU")
    has_cam_imu = False
    # Convert timestamps to seconds
    gps_df['timestamp'] = timestamp_to_sec(gps_df['timestamp_sec'], gps_df['timestamp_nsec'])
    imu_df['timestamp'] = timestamp_to_sec(imu_df['timestamp_sec'], imu_df['timestamp_nsec'])
    #if has_cam_imu:
    #    cam_imu_df['timestamp'] = timestamp_to_sec(cam_imu_df['timestamp_sec'], cam_imu_df['timestamp_nsec'])
    
    print(f"   GPS samples: {len(gps_df)}")
    print(f"   IMU samples: {len(imu_df)}")
    #if has_cam_imu:
    #   print(f"   Camera IMU samples: {len(cam_imu_df)}")
    
    # Time range info
    img_start_time = img_timestamps_df['timestamp'].min()
    img_end_time = img_timestamps_df['timestamp'].max()
    gps_start_time = gps_df['timestamp'].min()
    gps_end_time = gps_df['timestamp'].max()
    
    print(f"\n⏱️  Image time range: {img_start_time:.3f}s to {img_end_time:.3f}s ({img_end_time - img_start_time:.3f}s)")
    print(f"⏱️  GPS time range: {gps_start_time:.3f}s to {gps_end_time:.3f}s ({gps_end_time - gps_start_time:.3f}s)")
    
    # Create synchronized dataset
    synchronized_data = []
    
    print(f"\n🔗 Synchronizing data (max time diff: {max_time_diff}s)...")
    
    for _, img_row in img_timestamps_df.iterrows():
        img_timestamp = img_row['timestamp']
        img_filename = img_row['filename']
        img_id = img_row['image_id']
        
        # Find closest sensor data
        gps_data = find_closest_timestamp(img_timestamp, gps_df, max_diff=max_time_diff)
        imu_data = find_closest_timestamp(img_timestamp, imu_df, max_diff=max_time_diff)
        
        #if has_cam_imu:
        #    cam_imu_data = find_closest_timestamp(img_timestamp, cam_imu_df, max_diff=max_time_diff)
        #else:
        #    cam_imu_data = None
        
        # Build row
        row = {
            'image_id': img_id,
            'image_filename': img_filename,
            'image_timestamp': img_timestamp,
        }
        
        # Add GPS data
        if gps_data is not None:
            row.update({
                'gps_timestamp': gps_data['timestamp'],
                'gps_time_diff': abs(gps_data['timestamp'] - img_timestamp),
                'latitude': gps_data['latitude'],
                'longitude': gps_data['longitude'],
                'altitude': gps_data['altitude'],
                'vel_east': gps_data['vel_east'],
                'vel_north': gps_data['vel_north'],
                'vel_up': gps_data['vel_up'],
            })
        else:
            row.update({k: None for k in ['gps_timestamp', 'gps_time_diff', 'latitude', 
                                          'longitude', 'altitude', 'vel_east', 'vel_north', 'vel_up']})
        
        # Add IMU data
        if imu_data is not None:
            row.update({
                'imu_timestamp': imu_data['timestamp'],
                'imu_time_diff': abs(imu_data['timestamp'] - img_timestamp),
                'imu_orient_x': imu_data['orientation_x'],
                'imu_orient_y': imu_data['orientation_y'],
                'imu_orient_z': imu_data['orientation_z'],
                'imu_orient_w': imu_data['orientation_w'],
                'imu_ang_vel_x': imu_data['angular_vel_x'],
                'imu_ang_vel_y': imu_data['angular_vel_y'],
                'imu_ang_vel_z': imu_data['angular_vel_z'],
                'imu_lin_acc_x': imu_data['linear_accel_x'],
                'imu_lin_acc_y': imu_data['linear_accel_y'],
                'imu_lin_acc_z': imu_data['linear_accel_z'],
            })
        else:
            row.update({k: None for k in ['imu_timestamp', 'imu_time_diff', 'imu_orient_x', 'imu_orient_y', 
                                          'imu_orient_z', 'imu_orient_w', 'imu_ang_vel_x', 'imu_ang_vel_y',
                                          'imu_ang_vel_z', 'imu_lin_acc_x', 'imu_lin_acc_y', 'imu_lin_acc_z']})
        
        # Add Camera IMU data (if available)
        if has_cam_imu and cam_imu_data is not None:
            row.update({
                'cam_imu_timestamp': cam_imu_data['timestamp'],
                'cam_imu_time_diff': abs(cam_imu_data['timestamp'] - img_timestamp),
                'cam_imu_orient_x': cam_imu_data['orientation_x'],
                'cam_imu_orient_y': cam_imu_data['orientation_y'],
                'cam_imu_orient_z': cam_imu_data['orientation_z'],
                'cam_imu_orient_w': cam_imu_data['orientation_w'],
                'cam_imu_ang_vel_x': cam_imu_data['angular_vel_x'],
                'cam_imu_ang_vel_y': cam_imu_data['angular_vel_y'],
                'cam_imu_ang_vel_z': cam_imu_data['angular_vel_z'],
                'cam_imu_lin_acc_x': cam_imu_data['linear_accel_x'],
                'cam_imu_lin_acc_y': cam_imu_data['linear_accel_y'],
                'cam_imu_lin_acc_z': cam_imu_data['linear_accel_z'],
            })
        elif has_cam_imu:
            row.update({k: None for k in ['cam_imu_timestamp', 'cam_imu_time_diff', 'cam_imu_orient_x', 
                                          'cam_imu_orient_y', 'cam_imu_orient_z', 'cam_imu_orient_w',
                                          'cam_imu_ang_vel_x', 'cam_imu_ang_vel_y', 'cam_imu_ang_vel_z',
                                          'cam_imu_lin_acc_x', 'cam_imu_lin_acc_y', 'cam_imu_lin_acc_z']})
        
        synchronized_data.append(row)
        
        if (img_id + 1) % 100 == 0:
            print(f"   Processed {img_id + 1}/{len(img_timestamps_df)} images...")
    
    # Create DataFrame and save
    sync_df = pd.DataFrame(synchronized_data)
    sync_df.to_csv(output_file, index=False)
    
    # Statistics
    print(f"\n✅ Synchronized data saved to: {output_file}")
    print(f"\n📈 Synchronization statistics:")
    print(f"   Total images: {len(sync_df)}")
    print(f"   GPS matches: {sync_df['gps_timestamp'].notna().sum()} ({sync_df['gps_timestamp'].notna().sum()/len(sync_df)*100:.1f}%)")
    print(f"   IMU matches: {sync_df['imu_timestamp'].notna().sum()} ({sync_df['imu_timestamp'].notna().sum()/len(sync_df)*100:.1f}%)")
    
    if has_cam_imu:
        print(f"   Camera IMU matches: {sync_df['cam_imu_timestamp'].notna().sum()} ({sync_df['cam_imu_timestamp'].notna().sum()/len(sync_df)*100:.1f}%)")
    
    if sync_df['gps_timestamp'].notna().any():
        print(f"\n   Average GPS sync error: {sync_df['gps_time_diff'].mean():.6f}s ({sync_df['gps_time_diff'].mean()*1000:.2f}ms)")
        print(f"   Max GPS sync error: {sync_df['gps_time_diff'].max():.6f}s ({sync_df['gps_time_diff'].max()*1000:.2f}ms)")
    
    if sync_df['imu_timestamp'].notna().any():
        print(f"   Average IMU sync error: {sync_df['imu_time_diff'].mean():.6f}s ({sync_df['imu_time_diff'].mean()*1000:.2f}ms)")
        print(f"   Max IMU sync error: {sync_df['imu_time_diff'].max():.6f}s ({sync_df['imu_time_diff'].max()*1000:.2f}ms)")
    
    # Save statistics
    stats = {
        "total_images": len(sync_df),
        "gps_matches": int(sync_df['gps_timestamp'].notna().sum()),
        "imu_matches": int(sync_df['imu_timestamp'].notna().sum()),
        "gps_match_rate": float(sync_df['gps_timestamp'].notna().sum()/len(sync_df)*100),
        "imu_match_rate": float(sync_df['imu_timestamp'].notna().sum()/len(sync_df)*100),
        "avg_gps_error_ms": float(sync_df['gps_time_diff'].mean()*1000) if sync_df['gps_timestamp'].notna().any() else None,
        "avg_imu_error_ms": float(sync_df['imu_time_diff'].mean()*1000) if sync_df['imu_timestamp'].notna().any() else None,
        "max_time_diff_threshold": max_time_diff,
    }
    
    stats_file = Path(output_file).parent / (Path(output_file).stem + "_stats.json")
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\n💾 Statistics saved to: {stats_file}")


def main():
    parser = argparse.ArgumentParser(description='Synchronize image and sensor data using real timestamps')
    parser.add_argument('--images', required=True, help='Path to images folder (must contain image_timestamps.csv)')
    parser.add_argument('--sensors', required=True, help='Path to sensor data folder')
    parser.add_argument('--output', default='synchronized_data.csv', help='Output CSV file')
    parser.add_argument('--max-diff', type=float, default=0.1, help='Maximum time difference (seconds)')
    
    args = parser.parse_args()
    
    synchronize_data(args.images, args.sensors, args.output, args.max_diff)


if __name__ == "__main__":
    main()
