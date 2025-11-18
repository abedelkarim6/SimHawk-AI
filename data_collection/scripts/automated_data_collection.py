#!/usr/bin/env python3
"""
Automated data collection system for multiple trajectories
Each run saves data in its own organized directory
Works with x500_trajectory.launch.py which manages collectors
"""

import subprocess
import time
import os
import shutil
import json
import signal
from pathlib import Path
from datetime import datetime
import argparse


class DataCollectionPipeline:
    def __init__(self, base_dir="~/ros2_ws/data_collection", output_dir="datasets", verbose=False):
        self.base_dir = Path(base_dir).expanduser()
        self.output_dir = self.base_dir / output_dir
        self.verbose = verbose
        
        # Synchronization script path
        self.sync_script = self.base_dir / "scripts/synchronize_data.py"
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track all runs
        self.runs_metadata = []
        
    def log(self, message):
        """Print with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
    
    def create_run_directory(self, trajectory_type, run_number):
        """Create directory for this specific run"""
        run_name = f"{trajectory_type}_run{run_number:02d}"
        run_dir = self.output_dir / run_name
        images_dir = run_dir / "images"
        sensors_dir = run_dir / "sensors"
        
        # Create directories
        run_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(exist_ok=True)
        sensors_dir.mkdir(exist_ok=True)
        
        self.log(f"   📁 Created: {run_dir}")
        
        return run_dir, images_dir, sensors_dir
    
    def kill_process_group(self, pid, signal_type=signal.SIGTERM, timeout=3):
        """Safely kill a process group with timeout"""
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal_type)
            return True
        except ProcessLookupError:
            # Process already dead
            return True
        except Exception as e:
            self.log(f"   ⚠️  Failed to kill process group: {e}")
            return False
    
    def verify_collectors_running(self, wait_time=5):
        """
        Verify that collector processes started by launch file are running
        
        Args:
            wait_time: How long to wait for collectors to appear
        
        Returns:
            True if both collectors are detected, False otherwise
        """
        self.log(f"   🔍 Verifying collectors started (waiting up to {wait_time}s)...")
        
        start_time = time.time()
        img_found = False
        sensor_found = False
        
        while time.time() - start_time < wait_time:
            # Check for image collector
            if not img_found:
                result = subprocess.run(
                    ['pgrep', '-fl', 'imgs_collection.py'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    img_found = True
                    self.log(f"      ✅ Image collector detected")
                    self.log(f"         Process: {result.stdout.strip()}")
            
            # Check for sensor collector
            if not sensor_found:
                result = subprocess.run(
                    ['pgrep', '-fl', 'sensor_collector.py'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    sensor_found = True
                    self.log(f"      ✅ Sensor collector detected")
                    self.log(f"         Process: {result.stdout.strip()}")
            
            # Both found
            if img_found and sensor_found:
                return True
            
            time.sleep(0.5)
        
        # Timeout - report what's missing
        if not img_found:
            self.log(f"      ❌ Image collector not detected")
            self.log(f"      💡 Check: python3 ~/ros2_ws/data_collection/scripts/imgs_collection.py")
        if not sensor_found:
            self.log(f"      ❌ Sensor collector not detected")
            self.log(f"      💡 Check: python3 ~/ros2_ws/data_collection/scripts/sensor_collector.py")
        
        return False
    
    def cleanup_processes(self, traj_process, trajectory_type):
        """
        Clean up launch process and all its children
        Launch file manages collectors, so killing the process group handles everything
        """
        self.log(f"   🛑 Stopping launch and all child processes...")
        
        # Try graceful shutdown first
        if traj_process and traj_process.poll() is None:
            if self.kill_process_group(traj_process.pid, signal.SIGTERM):
                self.log(f"   ⏳ Waiting for graceful shutdown (3s)...")
                
                # Wait and check if process group died
                for i in range(6):
                    time.sleep(0.5)
                    if traj_process.poll() is not None:
                        self.log(f"   ✅ Launch shutdown cleanly")
                        break
                
                # Force kill if still alive
                if traj_process.poll() is None:
                    self.log(f"   ⚠️  Process still alive, forcing kill...")
                    self.kill_process_group(traj_process.pid, signal.SIGKILL)
                    time.sleep(1)
        
        # Final cleanup - kill any stragglers by name
        self.log(f"   🧹 Final cleanup of any remaining processes...")
        process_names = [
            'imgs_collection.py',
            'sensor_collector.py',
            f'{trajectory_type}_trajectory_node.py',
            'mavros_node',
            'ros2 bag record'
        ]
        
        for proc_name in process_names:
            try:
                result = subprocess.run(
                    ['pgrep', '-f', proc_name],
                    capture_output=True
                )
                if result.returncode == 0:
                    subprocess.run(
                        ['pkill', '-9', '-f', proc_name],
                        stderr=subprocess.DEVNULL,
                        timeout=2
                    )
            except Exception:
                pass
        
        time.sleep(1)
        self.log(f"   ✅ Cleanup complete")
    
    def verify_data_collection(self, images_dir, sensors_dir):
        """Verify that data was collected successfully"""
        self.log(f"   🔍 Verifying collected data...")
        
        # Count collected files
        img_count = len(list(images_dir.glob("*.png"))) if images_dir.exists() else 0
        sensor_files = list(sensors_dir.glob("*.csv")) if sensors_dir.exists() else []
        
        self.log(f"   📊 Collected: {img_count} images, {len(sensor_files)} sensor files")
        
        if img_count == 0:
            self.log(f"   ❌ ERROR: No images collected!")
            return False
        
        if len(sensor_files) == 0:
            self.log(f"   ❌ ERROR: No sensor data collected!")
            return False
        
        # Check for required sensor files
        required_files = ['gps_data.csv', 'imu_data.csv']
        existing_files = [f.name for f in sensor_files]
        
        missing = [f for f in required_files if f not in existing_files]
        if missing:
            self.log(f"   ⚠️  WARNING: Missing sensor files: {missing}")
            return False
        
        # Check for image timestamps
        img_timestamps = images_dir / "image_timestamps.csv"
        if not img_timestamps.exists():
            self.log(f"   ❌ ERROR: No image_timestamps.csv found")
            return False
        
        self.log(f"   ✅ Data collection verified")
        return True
    
    def run_trajectory_collection(self, trajectory_type, run_number, images_dir, sensors_dir, 
                                  duration=120, trajectory_params=None):
        """
        Run trajectory using launch file which handles data collection
        
        Args:
            trajectory_type: 'circular', 'zigzag', 'polygon', 'straight'
            run_number: Run number for this trajectory type
            images_dir: Directory where images will be saved
            sensors_dir: Directory where sensor data will be saved
            duration: Flight duration in seconds
            trajectory_params: Dictionary of trajectory-specific parameters
        """
        self.log(f"🚁 Starting {trajectory_type} trajectory - Run {run_number}")
        
        # Build ROS2 launch command
        ros2_ws = os.path.expanduser("~/ros2_ws")
        
        launch_cmd = (
            f"source {ros2_ws}/install/setup.bash && "
            f"ros2 launch x500_sensors x500_trajectory.launch.py "
            f"trajectory_type:={trajectory_type} "
            f"run_number:={run_number:02d} "
            f"output_dir:={self.output_dir.name} "
            f"trajectory_duration:={float(duration)} "
        )
        
        # Add trajectory-specific parameters
        if trajectory_params:
            self.log(f"   📝 Trajectory parameters:")
            for key, value in trajectory_params.items():
                if key not in ['duration', 'trajectory_duration']:
                    launch_cmd += f"{key}:={value} "
                    self.log(f"      {key}={value}")
        
        self.log(f"   🚀 Launching trajectory...")
        self.log(f"      Type: {trajectory_type}")
        self.log(f"      Run: {run_number:02d}")
        self.log(f"      Duration: {duration}s")
        
        traj_process = None
        
        try:
            # Start the launch file
            self.log(f"\n   🚀 Starting launch process...")
            traj_process = subprocess.Popen(
                launch_cmd,
                shell=True,
                executable='/bin/bash',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                bufsize=1,
                universal_newlines=True
            )
            
            self.log(f"   ✅ Launch process started (PID: {traj_process.pid})")
            
            # Monitor launch initialization
            if self.verbose:
                self.log(f"   ⏳ Monitoring launch initialization (15s)...")
                self.log(f"   --- Launch Output ---")
                
                import select
                start_time = time.time()
                while time.time() - start_time < 15:
                    if traj_process.poll() is not None:
                        self.log(f"   ❌ Launch died early (exit code: {traj_process.returncode})!")
                        remaining = traj_process.stdout.read()
                        if remaining:
                            for line in remaining.split('\n'):
                                if line.strip():
                                    self.log(f"   | {line}")
                        return False
                    
                    line = traj_process.stdout.readline()
                    if line:
                        self.log(f"   | {line.rstrip()}")
                    
                    time.sleep(0.1)
                
                self.log(f"   --- End Launch Output ---")
            else:
                # Quick check that process started
                self.log(f"   ⏳ Initializing launch (5s)...")
                for i in range(5):
                    time.sleep(1)
                    if traj_process.poll() is not None:
                        self.log(f"   ❌ Launch died early (exit code: {traj_process.returncode})!")
                        self.log(f"   💡 Run with --verbose to see detailed output")
                        return False
            
            # Verify collectors started (launch file starts them with 3s delay)
            if not self.verify_collectors_running(wait_time=8):
                self.log(f"   ❌ Data collectors failed to start!")
                self.log(f"   💡 Check that imgs_collection.py and sensor_collector.py exist")
                self.cleanup_processes(traj_process, trajectory_type)
                return False
            
            self.log(f"   ✅ Launch and collectors initialized successfully")
            
            # Wait for trajectory to complete with progress updates
            self.log(f"   ⏱️  Flight in progress for {duration} seconds...")
            progress_interval = max(10, duration // 6)
            elapsed = 0
            
            while elapsed < duration:
                wait_time = min(progress_interval, duration - elapsed)
                time.sleep(wait_time)
                elapsed += wait_time
                
                # Check if process died unexpectedly
                if traj_process.poll() is not None:
                    self.log(f"   ❌ Launch process died at {elapsed}s!")
                    return False
                
                # Progress update
                if elapsed < duration:
                    percent = int(elapsed * 100 / duration)
                    self.log(f"   ⏱️  Progress: {elapsed}/{duration}s ({percent}%)")
            
            self.log(f"   ✅ Flight duration completed")
            
            # Clean up all processes
            self.cleanup_processes(traj_process, trajectory_type)
            
            self.log(f"   ✅ {trajectory_type} Run {run_number} completed")
            
            # Verify data was collected
            if not self.verify_data_collection(images_dir, sensors_dir):
                return False
            
            # Cooling period before next run
            self.log(f"   ⏸️  Cooling down for 5 seconds...")
            time.sleep(5)
            
            return True
            
        except KeyboardInterrupt:
            self.log(f"   ⚠️  Collection interrupted by user")
            self.cleanup_processes(traj_process, trajectory_type)
            raise
            
        except Exception as e:
            self.log(f"   ❌ Error: {e}")
            import traceback
            self.log(f"   {traceback.format_exc()}")
            
            self.cleanup_processes(traj_process, trajectory_type)
            return False
    
    def synchronize_run(self, run_dir, trajectory_type, run_number):
        """
        Synchronize data for a single run
        
        Args:
            run_dir: Directory containing images/ and sensors/ subdirectories
            trajectory_type: Type of trajectory
            run_number: Run number
            
        Returns:
            Path to synchronized CSV file or None
        """
        self.log(f"🔗 Synchronizing {trajectory_type} Run {run_number}...")
        
        images_dir = run_dir / "images"
        sensors_dir = run_dir / "sensors"
        
        # Verify folders exist
        if not images_dir.exists() or not sensors_dir.exists():
            self.log(f"   ❌ Missing directories!")
            return None
        
        # Check for required files
        img_timestamps = images_dir / "image_timestamps.csv"
        gps_csv = sensors_dir / "gps_data.csv"
        imu_csv = sensors_dir / "imu_data.csv"
        
        if not img_timestamps.exists():
            self.log(f"   ❌ No image_timestamps.csv found")
            return None
        
        if not gps_csv.exists() or not imu_csv.exists():
            self.log(f"   ❌ Missing sensor CSV files")
            return None
        
        # Create output filename in the run directory
        output_csv = run_dir / "synchronized_data.csv"
        
        # Run synchronization script
        sync_cmd = [
            'python3', str(self.sync_script),
            '--images', str(images_dir),
            '--sensors', str(sensors_dir),
            '--output', str(output_csv),
            '--max-diff', '0.1'
        ]
        
        self.log(f"   Running synchronization...")
        
        try:
            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            if not output_csv.exists():
                self.log(f"   ❌ Synchronization output not created!")
                return None
            
            self.log(f"   ✅ Synchronized: {output_csv}")
            
            # Count synchronized samples
            import pandas as pd
            df = pd.read_csv(output_csv)
            self.log(f"   📊 Synchronized samples: {len(df)}")
            
            return output_csv
            
        except subprocess.TimeoutExpired:
            self.log(f"   ❌ Synchronization timed out!")
            return None
        except subprocess.CalledProcessError as e:
            self.log(f"   ❌ Synchronization failed!")
            if e.stderr:
                self.log(f"   Error: {e.stderr}")
            return None
        except Exception as e:
            self.log(f"   ❌ Error: {e}")
            return None
    
    def merge_all_datasets(self):
        """
        Merge all synchronized CSV files into one master dataset
        """
        self.log("📊 Merging all datasets...")
        
        import pandas as pd
        
        # Find all run directories
        run_dirs = sorted([d for d in self.output_dir.iterdir() if d.is_dir() and '_run' in d.name])
        
        if not run_dirs:
            self.log("   ⚠️  No run directories found!")
            return None
        
        self.log(f"   Found {len(run_dirs)} run directories")
        
        # Read all synchronized CSV files
        dfs = []
        for run_dir in run_dirs:
            sync_csv = run_dir / "synchronized_data.csv"
            
            if not sync_csv.exists():
                self.log(f"   ⚠️  Skipping {run_dir.name} - no synchronized data")
                continue
            
            try:
                df = pd.read_csv(sync_csv)
                
                # Extract trajectory type and run number from directory name
                parts = run_dir.name.rsplit('_run', 1)
                if len(parts) != 2:
                    self.log(f"   ⚠️  Skipping {run_dir.name} - invalid directory name")
                    continue
                
                trajectory = parts[0]
                run = int(parts[1])
                
                df['trajectory_type'] = trajectory
                df['run_number'] = run
                
                # Update image paths to be relative to output directory
                df['image_path'] = df['image_filename'].apply(
                    lambda x: f"{run_dir.name}/images/{x}"
                )
                
                dfs.append(df)
                self.log(f"   ✅ Loaded {len(df)} samples from {run_dir.name}")
                
            except Exception as e:
                self.log(f"   ⚠️  Error loading {run_dir.name}: {e}")
                continue
        
        if not dfs:
            self.log("   ❌ No data to merge!")
            return None
        
        # Merge all dataframes
        master_df = pd.concat(dfs, ignore_index=True)
        
        # Save master dataset
        master_csv = self.output_dir / "master_dataset.csv"
        master_df.to_csv(master_csv, index=False)
        
        self.log(f"   ✅ Master dataset saved: {master_csv}")
        self.log(f"   📈 Total samples: {len(master_df)}")
        
        # Statistics by trajectory
        self.log(f"\n   📊 Samples per trajectory:")
        traj_counts = master_df.groupby('trajectory_type').size().to_dict()
        for traj, count in sorted(traj_counts.items()):
            self.log(f"      {traj}: {count} samples")
        
        # Save statistics
        stats = {
            "total_samples": int(len(master_df)),
            "trajectories": {k: int(v) for k, v in master_df['trajectory_type'].value_counts().to_dict().items()},
            "samples_per_trajectory": {k: int(v) for k, v in traj_counts.items()},
            "runs_per_trajectory": {k: int(v) for k, v in master_df.groupby('trajectory_type')['run_number'].nunique().to_dict().items()},
            "total_runs": len(run_dirs),
            "collection_date": datetime.now().isoformat(),
            "gps_match_rate": float(master_df['latitude'].notna().sum() / len(master_df) * 100),
            "imu_match_rate": float(master_df['imu_orient_x'].notna().sum() / len(master_df) * 100),
        }
        
        stats_file = self.output_dir / "dataset_statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        self.log(f"   ✅ Statistics saved: {stats_file}")
        
        return master_csv
    
    def create_dataset_readme(self):
        """Create a README file explaining the dataset structure"""
        readme_content = """# GPS Prediction Training Dataset

## Dataset Structure

```
training_dataset/
├── master_dataset.csv              # Combined dataset from all runs
├── dataset_statistics.json         # Dataset statistics
├── README.md                        # This file
├── circular_run01/                 # Each run in its own directory
│   ├── images/                     # Images from this run
│   │   ├── img_000000.png
│   │   ├── img_000001.png
│   │   └── image_timestamps.csv
│   ├── sensors/                    # Sensor data from this run
│   │   ├── gps_data.csv
│   │   ├── imu_data.csv
│   │   └── camera_imu_data.csv
│   └── synchronized_data.csv       # Synchronized data for this run
├── circular_run02/
├── zigzag_run01/
├── polygon_run01/
└── straight_run01/
```

## Using the Dataset

### Load Master Dataset
```python
import pandas as pd
import os

# Load the complete dataset
df = pd.read_csv('training_dataset/master_dataset.csv')

# Load images using the image_path column
IMAGE_DIR = 'training_dataset/'
image_full_path = os.path.join(IMAGE_DIR, df.iloc[0]['image_path'])
```

### Dataset Columns

- **image_id**: Sequential image identifier within run
- **image_filename**: Image filename (img_XXXXXX.png)
- **image_path**: Relative path from training_dataset/
- **image_timestamp**: Image capture timestamp (seconds)
- **trajectory_type**: Trajectory type (circular, zigzag, polygon, straight)
- **run_number**: Run number for this trajectory

#### GPS Data
- **latitude, longitude, altitude**: GPS coordinates
- **vel_east, vel_north, vel_up**: Velocity components
- **gps_timestamp**: GPS measurement timestamp
- **gps_time_diff**: Time difference between image and GPS

#### IMU Data
- **imu_orient_x/y/z/w**: Orientation quaternion
- **imu_ang_vel_x/y/z**: Angular velocity
- **imu_lin_acc_x/y/z**: Linear acceleration
- **imu_timestamp**: IMU measurement timestamp
- **imu_time_diff**: Time difference between image and IMU

## Training with PyTorch

```python
CSV_PATH = 'training_dataset/master_dataset.csv'
IMAGE_DIR = 'training_dataset/'

def __getitem__(self, idx):
    actual_idx = self.valid_indices[idx]
    img_path = os.path.join(self.image_dir, self.df.iloc[actual_idx]['image_path'])
    image = Image.open(img_path).convert('RGB')
    # ...
```

## Collection Details

Each run represents a complete trajectory flight with synchronized:
- Camera images (512x512 pixels)
- GPS data (position and velocity)
- IMU data (orientation, angular velocity, linear acceleration)

All data is time-synchronized with sub-100ms accuracy.
"""
        
        readme_file = self.output_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        self.log(f"📄 README created: {readme_file}")
    
    def run_full_collection(self, config, trajectory_params):
        """
        Run the complete data collection pipeline
        
        Args:
            config: Dictionary with trajectory configurations
            trajectory_params: Dictionary with parameters for each trajectory type
        """
        self.log("="*60)
        self.log("🚀 Starting Automated Data Collection Pipeline")
        self.log("="*60)
        
        # Check prerequisites
        self.log("\n🔍 Checking prerequisites...")
        gazebo_running = False
        
        for process_name in ['gzserver', 'gazebo', 'px4']:
            check = subprocess.run(['pgrep', '-f', process_name], capture_output=True)
            if check.returncode == 0:
                gazebo_running = True
                self.log(f"   ✅ Found {process_name} process running")
                break
        
        if not gazebo_running:
            self.log("   ⚠️  WARNING: PX4/Gazebo processes not detected!")
            self.log("   Please ensure PX4 SITL is running:")
            self.log("   cd ~/PX4-Autopilot && make px4_sitl gazebo")
            response = input("\n   Continue anyway? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                self.log("   ❌ Collection cancelled")
                return
        
        self.log("   ℹ️  Make sure the drone is on the ground and disarmed")
        response = input("\n   Is the drone ready? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            self.log("   ❌ Please reset simulation and try again")
            return
        
        self.log("\n⏳ Waiting 3 seconds for system to stabilize...")
        time.sleep(3)
        
        total_runs = sum(config.values())
        current_run = 0
        
        for trajectory_type, num_runs in config.items():
            self.log(f"\n📍 Trajectory: {trajectory_type.upper()}")
            self.log(f"   Planned runs: {num_runs}")
            
            traj_params = trajectory_params.get(trajectory_type, {})
            
            for run_num in range(1, num_runs + 1):
                current_run += 1
                self.log(f"\n{'='*60}")
                self.log(f"Progress: {current_run}/{total_runs} runs")
                self.log(f"{'='*60}")
                
                # Create directory
                run_dir, images_dir, sensors_dir = self.create_run_directory(trajectory_type, run_num)
                self.log(f"   📁 Run directory: {run_dir.name}")
                
                # Run trajectory and collect data
                success = self.run_trajectory_collection(
                    trajectory_type, run_num, images_dir, sensors_dir, 
                    duration=traj_params.get('duration', 120),
                    trajectory_params=traj_params
                )
                
                if not success:
                    self.log(f"   ⚠️  Collection failed, skipping synchronization")
                    continue
                
                # Synchronize the data
                sync_csv = self.synchronize_run(run_dir, trajectory_type, run_num)
                
                if sync_csv:
                    self.runs_metadata.append({
                        'trajectory': trajectory_type,
                        'run': run_num,
                        'directory': str(run_dir),
                        'sync_csv': str(sync_csv),
                        'timestamp': datetime.now().isoformat()
                    })
        
        # Merge all datasets
        self.log(f"\n{'='*60}")
        self.log("📊 Creating Master Dataset")
        self.log(f"{'='*60}")
        master_csv = self.merge_all_datasets()
        
        if not master_csv:
            self.log("❌ Failed to create master dataset!")
            return
        
        # Create README
        self.create_dataset_readme()
        
        # Save run metadata
        metadata_file = self.output_dir / "collection_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.runs_metadata, f, indent=2)
        
        self.log(f"\n{'='*60}")
        self.log("✅ DATA COLLECTION COMPLETE!")
        self.log(f"{'='*60}")
        self.log(f"📁 Dataset location: {self.output_dir}")
        self.log(f"📊 Master dataset: {master_csv}")
        self.log(f"📈 Total runs collected: {len(self.runs_metadata)}")
        self.log(f"\nYou can now train your model with:")
        self.log(f"  CSV_PATH = '{master_csv}'")
        self.log(f"  IMAGE_DIR = '{self.output_dir}/'")


def main():
    parser = argparse.ArgumentParser(
        description='Automated multi-trajectory data collection for GPS prediction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Trajectory-specific parameters:
  Circular: --radius, --omega, --takeoff-alt
  Zigzag: --amplitude, --speed, --frequency, --direction-angle, --takeoff-alt
  Polygon: --radius, --num-vertices, --vertex-duration, --takeoff-alt
  Straight: --speed, --direction-angle, --takeoff-alt
        """
    )
    
    # Number of runs per trajectory
    parser.add_argument('--circular', type=int, default=3, help='Number of circular trajectory runs')
    parser.add_argument('--zigzag', type=int, default=2, help='Number of zigzag trajectory runs')
    parser.add_argument('--polygon', type=int, default=2, help='Number of polygon trajectory runs')
    parser.add_argument('--straight', type=int, default=2, help='Number of straight trajectory runs')
    
    # General parameters
    parser.add_argument('--output', type=str, default='datasets', help='Output directory name')
    parser.add_argument('--base-dir', type=str, default='~/ros2_ws/data_collection', help='Base directory')
    parser.add_argument('--duration', type=int, default=120, help='Flight duration per run (seconds)')
    parser.add_argument('--takeoff-alt', type=float, default=25.0, help='Takeoff altitude (meters)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed launch output')
    
    # Circular trajectory parameters
    parser.add_argument('--radius', type=float, default=35.0, help='Circular/Polygon radius (meters)')
    parser.add_argument('--omega', type=float, default=0.2, help='Circular angular velocity (rad/s)')
    
    # Zigzag trajectory parameters
    parser.add_argument('--amplitude', type=float, default=10.0, help='Zigzag amplitude (meters)')
    parser.add_argument('--speed', type=float, default=1.0, help='Zigzag/Straight speed (m/s)')
    parser.add_argument('--frequency', type=float, default=0.3, help='Zigzag frequency (Hz)')
    parser.add_argument('--direction-angle', type=float, default=0.0, help='Zigzag/Straight direction (degrees)')
    
    # Polygon trajectory parameters
    parser.add_argument('--num-vertices', type=int, default=6, help='Polygon number of vertices')
    parser.add_argument('--vertex-duration', type=float, default=5.0, help='Polygon hover time at vertices (s)')
    
    args = parser.parse_args()
    
    # Configuration for number of runs
    config = {
        'circular': args.circular,
        'zigzag': args.zigzag,
        'polygon': args.polygon,
        'straight': args.straight
    }
    
    # Remove trajectories with 0 runs
    config = {k: v for k, v in config.items() if v > 0}
    
    # Build trajectory-specific parameters
    trajectory_params = {}
    
    if 'circular' in config:
        trajectory_params['circular'] = {
            'takeoff_alt': args.takeoff_alt,
            'radius': args.radius,
            'omega': args.omega,
            'duration': args.duration
        }
    
    if 'zigzag' in config:
        trajectory_params['zigzag'] = {
            'takeoff_alt': args.takeoff_alt,
            'amplitude': args.amplitude,
            'speed': args.speed,
            'frequency': args.frequency,
            'direction_angle': args.direction_angle,
            'duration': args.duration
        }
    
    if 'polygon' in config:
        trajectory_params['polygon'] = {
            'takeoff_alt': args.takeoff_alt,
            'radius': args.radius,
            'num_vertices': args.num_vertices,
            'vertex_duration': args.vertex_duration,
            'duration': args.duration
        }
    
    if 'straight' in config:
        trajectory_params['straight'] = {
            'takeoff_alt': args.takeoff_alt,
            'speed': args.speed,
            'direction_angle': args.direction_angle,
            'duration': args.duration
        }
    
    total_runs = sum(config.values())
    estimated_time = total_runs * (args.duration + 35)  # flight + overhead per run
    
    print("\n" + "="*60)
    print("🚁 GPS PREDICTION DATA COLLECTION PIPELINE")
    print("="*60)
    print(f"\nConfiguration:")
    for traj, runs in config.items():
        print(f"  {traj.capitalize()}: {runs} runs")
        if traj in trajectory_params:
            for key, value in trajectory_params[traj].items():
                print(f"    {key}: {value}")
    print(f"\nTotal runs: {total_runs}")
    print(f"Estimated time: {estimated_time//60} minutes")
    print(f"Output directory: {args.output}")
    print("\n" + "="*60)
    
    response = input("\nProceed with data collection? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Collection cancelled")
        return
    
    # Create pipeline and run
    pipeline = DataCollectionPipeline(
        base_dir=args.base_dir,
        output_dir=args.output,
        verbose=args.verbose
    )
    
    pipeline.run_full_collection(config, trajectory_params)


if __name__ == "__main__":
    main()
