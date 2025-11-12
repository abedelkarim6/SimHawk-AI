#!/usr/bin/env python3
"""
Automated data collection system for multiple trajectories
Each run saves data in its own organized directory
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
import random


class DataCollectionPipeline:
    def __init__(self, base_dir="~/drone_project/data_collection", dataset_type="train", 
                 dataset_name=None, verbose=False, map_bounds=None):
        self.base_dir = Path(base_dir).expanduser()
        self.dataset_type = dataset_type  # 'train' or 'test'
        self.verbose = verbose
        
        # Determine output directory with auto-increment
        if dataset_name:
            # User provided custom name
            self.output_dir = self.base_dir / "datasets" / dataset_type / dataset_name
        else:
            # Auto-increment: find next available number
            self.output_dir = self._get_next_dataset_dir(dataset_type)
        
        # Scripts paths (now in scripts subdirectory)
        scripts_dir = self.base_dir / "scripts"
        self.sync_script = scripts_dir / "synchronize_data.py"
        self.img_collector = scripts_dir / "imgs_collection.py"
        self.sensor_collector = scripts_dir / "sensor_collector.py"
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track all runs
        self.runs_metadata = []
        
        # Map boundaries for random start positions
        self.map_bounds = map_bounds or {
            'x': (-100, 100),
            'y': (-100, 100)
        }
    
    def _get_next_dataset_dir(self, dataset_type):
        """
        Find the next available dataset number
        Format: datasets/train/dataset_001, dataset_002, etc.
        """
        datasets_dir = self.base_dir / "datasets" / dataset_type
        datasets_dir.mkdir(parents=True, exist_ok=True)
        
        # Find existing datasets
        existing = [d for d in datasets_dir.iterdir() if d.is_dir() and d.name.startswith('dataset_')]
        
        if not existing:
            next_num = 1
        else:
            # Extract numbers from existing datasets
            numbers = []
            for d in existing:
                try:
                    num = int(d.name.split('_')[1])
                    numbers.append(num)
                except (IndexError, ValueError):
                    continue
            
            next_num = max(numbers) + 1 if numbers else 1
        
        return datasets_dir / f"dataset_{next_num:03d}"
    
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
    
    def generate_random_start_position(self):
        """Generate random starting coordinates within map bounds"""
        x = random.uniform(self.map_bounds['x'][0], self.map_bounds['x'][1])
        y = random.uniform(self.map_bounds['y'][0], self.map_bounds['y'][1])
        
        self.log(f"   🎲 Random start position: x={x:.2f}, y={y:.2f}")
        return x, y
    
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
        
        # Generate random starting position
        start_x, start_y = self.generate_random_start_position()
        
        # Build ROS2 launch command with sourcing
        ros2_ws = os.path.expanduser("~/ros2_ws")
        
        # Get the relative path from data_collection base to output
        # This is needed for the launch file
        relative_output = self.output_dir.relative_to(self.base_dir)
        
        # Build trajectory launch command with run parameters
        launch_cmd = (
            f"source {ros2_ws}/install/setup.bash && "
            f"ros2 launch x500_sensors x500_trajectory.launch.py "
            f"trajectory_type:={trajectory_type} "
            f"run_number:={run_number:02d} "
            f"output_dir:={relative_output} "
            f"trajectory_duration:={float(duration)} "
            f"start_x:={start_x} "
            f"start_y:={start_y} "
        )
        
        # Add trajectory-specific parameters if provided
        if trajectory_params:
            for key, value in trajectory_params.items():
                if key != 'duration':
                    launch_cmd += f"{key}:={value} "
        
        self.log(f"   🚀 Launching trajectory with parameters...")
        self.log(f"      trajectory_type={trajectory_type}")
        self.log(f"      run_number={run_number:02d}")
        self.log(f"      start_position=({start_x:.2f}, {start_y:.2f})")
        self.log(f"      trajectory_duration={duration}s")
        if trajectory_params:
            for key, value in trajectory_params.items():
                if key != 'duration':
                    self.log(f"      {key}={value}")
        
        self.log(f"\n   📝 Full launch command:")
        self.log(f"      {launch_cmd}")
        
        try:
            # Start the trajectory
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
            
            self.log(f"   ✅ Process started (PID: {traj_process.pid})")
            
            if self.verbose:
                self.log(f"   ⏳ Monitoring launch for 15 seconds...")
                self.log(f"   --- Launch Output ---")
                
                import select
                start_time = time.time()
                while time.time() - start_time < 15:
                    if traj_process.poll() is not None:
                        self.log(f"   ❌ Launch process died early (exit code: {traj_process.returncode})!")
                        remaining = traj_process.stdout.read()
                        if remaining:
                            self.log(f"   {remaining}")
                        return False
                    
                    line = traj_process.stdout.readline()
                    if line:
                        self.log(f"   | {line.rstrip()}")
                    
                    time.sleep(0.1)
                
                self.log(f"   --- End Launch Output ---")
            else:
                self.log(f"   ⏳ Initializing launch (10s)...")
                for i in range(10):
                    time.sleep(1)
                    if traj_process.poll() is not None:
                        self.log(f"   ❌ Launch process died early (exit code: {traj_process.returncode})!")
                        self.log(f"   💡 Run with --verbose to see detailed output")
                        return False
            
            self.log(f"   ✅ Launch initialized successfully")
            self.log(f"   ⏱️  Flight in progress for {duration} seconds...")
            
            time.sleep(duration)
            
            # Stop all processes
            self.log(f"   🛑 Stopping all processes...")
            
            try:
                os.killpg(os.getpgid(traj_process.pid), signal.SIGTERM)
                self.log(f"   ⏳ Waiting for graceful shutdown...")
                time.sleep(3)
            except Exception as e:
                self.log(f"   ⚠️  SIGTERM failed: {e}")
                try:
                    traj_process.terminate()
                except:
                    pass
            
            try:
                os.killpg(os.getpgid(traj_process.pid), signal.SIGKILL)
            except:
                pass
            
            self.log(f"   🧹 Cleaning up any remaining processes...")
            subprocess.run(['pkill', '-f', 'imgs_collection.py'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'sensor_collector.py'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', f'{trajectory_type}_trajectory_node.py'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-f', 'mavros_node'], stderr=subprocess.DEVNULL)
            
            time.sleep(2)
            
            self.log(f"   ✅ {trajectory_type} Run {run_number} completed")
            
            # Verify data was collected
            run_name = f"{trajectory_type}_run{run_number:02d}"
            run_dir_check = self.output_dir / run_name
            images_dir_check = run_dir_check / "images"
            sensors_dir_check = run_dir_check / "sensors"
            
            self.log(f"   🔍 Checking collected data in:")
            self.log(f"      Images: {images_dir_check}")
            self.log(f"      Sensors: {sensors_dir_check}")
            
            img_count = len(list(images_dir_check.glob("*.png"))) if images_dir_check.exists() else 0
            sensor_files = list(sensors_dir_check.glob("*.csv")) if sensors_dir_check.exists() else []
            
            self.log(f"   📊 Collected: {img_count} images, {len(sensor_files)} sensor files")
            
            collector_check = subprocess.run(
                ['pgrep', '-f', 'imgs_collection.py'],
                capture_output=True
            )
            if collector_check.returncode == 0:
                self.log(f"   ⚠️  Image collector still running, forcing stop...")
                subprocess.run(['pkill', '-9', '-f', 'imgs_collection.py'])
                time.sleep(1)
            
            collector_check = subprocess.run(
                ['pgrep', '-f', 'sensor_collector.py'],
                capture_output=True
            )
            if collector_check.returncode == 0:
                self.log(f"   ⚠️  Sensor collector still running, forcing stop...")
                subprocess.run(['pkill', '-9', '-f', 'sensor_collector.py'])
                time.sleep(1)
            
            if img_count == 0:
                self.log(f"   ⚠️  WARNING: No images collected!")
                return False
            
            if len(sensor_files) == 0:
                self.log(f"   ⚠️  WARNING: No sensor data collected!")
                return False
            
            self.log(f"   ⏸️  Cooling down for 5 seconds...")
            time.sleep(5)
            
            return True
            
        except Exception as e:
            self.log(f"   ❌ Error: {e}")
            import traceback
            self.log(f"   {traceback.format_exc()}")
            
            try:
                traj_process.terminate()
            except:
                pass
            
            return False
    
    def synchronize_run(self, run_dir, trajectory_type, run_number):
        """Synchronize data for a single run"""
        self.log(f"🔗 Synchronizing {trajectory_type} Run {run_number}...")
        
        images_dir = run_dir / "images"
        sensors_dir = run_dir / "sensors"
        
        if not images_dir.exists() or not sensors_dir.exists():
            self.log(f"   ❌ Missing directories!")
            return None
        
        img_timestamps = images_dir / "image_timestamps.csv"
        gps_csv = sensors_dir / "gps_data.csv"
        imu_csv = sensors_dir / "imu_data.csv"
        
        if not img_timestamps.exists():
            self.log(f"   ❌ No image_timestamps.csv found")
            return None
        
        if not gps_csv.exists() or not imu_csv.exists():
            self.log(f"   ❌ Missing sensor CSV files")
            return None
        
        output_csv = run_dir / "synchronized_data.csv"
        
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
                check=True
            )
            
            if not output_csv.exists():
                self.log(f"   ❌ Synchronization output not created!")
                return None
            
            self.log(f"   ✅ Synchronized: {output_csv}")
            
            import pandas as pd
            df = pd.read_csv(output_csv)
            self.log(f"   📊 Synchronized samples: {len(df)}")
            
            return output_csv
            
        except subprocess.CalledProcessError as e:
            self.log(f"   ❌ Synchronization failed!")
            self.log(f"   Error: {e.stderr}")
            return None
        except Exception as e:
            self.log(f"   ❌ Error: {e}")
            return None
    
    def merge_all_datasets(self):
        """Merge all synchronized CSV files into one master dataset"""
        self.log("📊 Merging all datasets...")
        
        import pandas as pd
        
        run_dirs = sorted([d for d in self.output_dir.iterdir() if d.is_dir() and '_run' in d.name])
        
        if not run_dirs:
            self.log("   ⚠️  No run directories found!")
            return None
        
        self.log(f"   Found {len(run_dirs)} run directories")
        
        dfs = []
        for run_dir in run_dirs:
            sync_csv = run_dir / "synchronized_data.csv"
            
            if not sync_csv.exists():
                self.log(f"   ⚠️  Skipping {run_dir.name} - no synchronized data")
                continue
            
            df = pd.read_csv(sync_csv)
            
            parts = run_dir.name.rsplit('_run', 1)
            trajectory = parts[0]
            run = int(parts[1])
            
            df['trajectory_type'] = trajectory
            df['run_number'] = run
            
            df['image_path'] = df['image_filename'].apply(
                lambda x: f"{run_dir.name}/images/{x}"
            )
            
            dfs.append(df)
            self.log(f"   ✅ Loaded {len(df)} samples from {run_dir.name}")
        
        if not dfs:
            self.log("   ❌ No data to merge!")
            return None
        
        master_df = pd.concat(dfs, ignore_index=True)
        
        master_csv = self.output_dir / "master_dataset.csv"
        master_df.to_csv(master_csv, index=False)
        
        self.log(f"   ✅ Master dataset saved: {master_csv}")
        self.log(f"   📈 Total samples: {len(master_df)}")
        
        traj_counts = master_df.groupby('trajectory_type').size().to_dict()
        for traj, count in traj_counts.items():
            self.log(f"      {traj}: {count} samples")
        
        stats = {
            "dataset_type": self.dataset_type,
            "dataset_name": self.output_dir.name,
            "total_samples": len(master_df),
            "trajectories": master_df['trajectory_type'].value_counts().to_dict(),
            "samples_per_trajectory": traj_counts,
            "runs_per_trajectory": master_df.groupby('trajectory_type')['run_number'].nunique().to_dict(),
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
        readme_content = f"""# GPS Prediction {'Training' if self.dataset_type == 'train' else 'Testing'} Dataset

## Dataset Info
- **Type**: {self.dataset_type.upper()}
- **Name**: {self.output_dir.name}
- **Location**: {self.output_dir}

## Dataset Structure

{self.output_dir.name}/
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
```python
import pandas as pd
import os

# Load the complete dataset
df = pd.read_csv('{self.output_dir}/master_dataset.csv')

# Load images using the image_path column
IMAGE_DIR = '{self.output_dir.parent}/'
image_full_path = os.path.join(IMAGE_DIR, df.iloc[0]['image_path'])
```

### Dataset Columns

- **image_id**: Sequential image identifier within run
- **image_filename**: Image filename (img_XXXXXX.png)
- **image_path**: Relative path (e.g., circular_run01/images/img_000000.png)
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
CSV_PATH = '{self.output_dir}/master_dataset.csv'
IMAGE_DIR = '{self.output_dir.parent}/'

# In your Dataset class:
def __getitem__(self, idx):
    actual_idx = self.valid_indices[idx]
    
    # Use image_path column (includes subdirectory)
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

**Random Start Positions**: Each trajectory starts from a random location within the map to ensure diverse training data.
"""
        
        readme_file = self.output_dir / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        self.log(f"📄 README created: {readme_file}")
    
    def run_full_collection(self, config, trajectory_params):
        """Run the complete data collection pipeline"""
        self.log("="*60)
        self.log(f"🚀 Starting Automated Data Collection Pipeline")
        self.log(f"   Type: {self.dataset_type.upper()}")
        self.log(f"   Output: {self.output_dir}")
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
        
        self.log("   ℹ️  Make sure the drone is on the ground and disarmed before starting")
        response = input("\n   Is the drone on the ground and ready? (yes/no): ")
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
                
                run_dir, images_dir, sensors_dir = self.create_run_directory(trajectory_type, run_num)
                self.log(f"   📁 Run directory: {run_dir.name}")
                
                success = self.run_trajectory_collection(
                    trajectory_type, run_num, images_dir, sensors_dir, 
                    duration=traj_params.get('duration', 120),
                    trajectory_params=traj_params
                )
                
                if not success:
                    self.log(f"   ⚠️  Collection failed, skipping synchronization")
                    continue
                
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
        
        self.create_dataset_readme()
        
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
        self.log(f"  IMAGE_DIR = '{self.output_dir.parent}/'")


def main():
    parser = argparse.ArgumentParser(
        description='Automated multi-trajectory data collection for GPS prediction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create training dataset (auto-increments: dataset_001, dataset_002, etc.)
  python3 automated_data_collection.py --type train --circular 3 --zigzag 2
  
  # Create test dataset with custom name
  python3 automated_data_collection.py --type test --name test_custom --circular 1
  
  # Create test dataset (auto-increments)
  python3 automated_data_collection.py --type test --straight 2

Trajectory-specific parameters:
  Circular: --radius, --omega, --takeoff-alt
  Zigzag: --amplitude, --speed, --frequency, --direction-angle, --takeoff-alt
  Polygon: --radius, --num-vertices, --vertex-duration, --takeoff-alt
  Straight: --speed, --direction-angle, --takeoff-alt
        """
    )
    
    # Dataset type and naming
    parser.add_argument('--type', type=str, choices=['train', 'test'], default='train',
                       help='Dataset type: train or test')
    parser.add_argument('--name', type=str, default=None,
                       help='Custom dataset name (default: auto-increment dataset_XXX)')
    
    # Number of runs per trajectory
    parser.add_argument('--circular', type=int, default=0, help='Number of circular trajectory runs')
    parser.add_argument('--zigzag', type=int, default=0, help='Number of zigzag trajectory runs')
    parser.add_argument('--polygon', type=int, default=0, help='Number of polygon trajectory runs')
    parser.add_argument('--straight', type=int, default=0, help='Number of straight trajectory runs')
    
    # General parameters
    parser.add_argument('--base-dir', type=str, default='~/drone_project/data_collection', 
                       help='Base directory for data collection')
    parser.add_argument('--duration', type=int, default=120, help='Flight duration per run (seconds)')
    parser.add_argument('--takeoff-alt', type=float, default=25.0, help='Takeoff altitude (meters)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed launch output')
    
    # Map bounds
    parser.add_argument('--map-x-min', type=float, default=-100.0, help='Map X minimum bound')
    parser.add_argument('--map-x-max', type=float, default=100.0, help='Map X maximum bound')
    parser.add_argument('--map-y-min', type=float, default=-100.0, help='Map Y minimum bound')
    parser.add_argument('--map-y-max', type=float, default=100.0, help='Map Y maximum bound')
    
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
    
    if not config:
        print("❌ Error: Must specify at least one trajectory type with runs > 0")
        print("Example: --circular 3 --zigzag 2")
        return
    
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
    
    # Define map bounds
    map_bounds = {
        'x': (args.map_x_min, args.map_x_max),
        'y': (args.map_y_min, args.map_y_max)
    }
    
    total_runs = sum(config.values())
    estimated_time = total_runs * (args.duration + 35)
    
    print("\n" + "="*60)
    print("🚁 GPS PREDICTION DATA COLLECTION PIPELINE")
    print("="*60)
    print(f"\nDataset Configuration:")
    print(f"  Type: {args.type.upper()}")
    if args.name:
        print(f"  Name: {args.name}")
    else:
        print(f"  Name: Auto-increment (dataset_XXX)")
    print(f"\nTrajectory Runs:")
    for traj, runs in config.items():
        print(f"  {traj.capitalize()}: {runs} runs")
        if traj in trajectory_params:
            for key, value in trajectory_params[traj].items():
                print(f"    {key}: {value}")
    print(f"\nMap Bounds:")
    print(f"  X: [{args.map_x_min}, {args.map_x_max}]")
    print(f"  Y: [{args.map_y_min}, {args.map_y_max}]")
    print(f"\nTotal runs: {total_runs}")
    print(f"Estimated time: {estimated_time//60} minutes")
    print("\n" + "="*60)
    
    response = input("\nProceed with data collection? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Collection cancelled")
        return
    
    # Create pipeline and run
    pipeline = DataCollectionPipeline(
        base_dir=args.base_dir,
        dataset_type=args.type,
        dataset_name=args.name,
        verbose=args.verbose,
        map_bounds=map_bounds
    )
    
    pipeline.run_full_collection(config, trajectory_params)


if __name__ == "__main__":
    main()
