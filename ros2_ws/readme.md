This documentation explains the **full data collection system**, the **inputs**, the **launch files**, the **trajectory nodes**, the **sensor setup**, and how everything connects. You can copy it directly.

---
# Automated Multi-Trajectory GPS/IMU Data Collection Pipeline

## Overview

This repository provides a fully automated **data collection pipeline** to generate high-quality datasets for training Visual-Inertial SLAM (VI-SLAM) or GPS prediction models. The system supports multiple trajectory types and modular sensor integration, allowing flexibility and diversity in the dataset.

The main script, `automated_data_collection.py`, coordinates:

1. **Trajectory execution** using ROS2 launch files.
2. **Image and sensor collection** from onboard cameras, GPS, and IMU.
3. **Data synchronization** to align images with sensor readings.
4. **Dataset merging and statistics generation** for training-ready datasets.

---

## Pipeline Components

### 1. Main Script: `automated_data_collection.py`

This script manages the **entire data collection pipeline**.

**Key Features:**

- Modular trajectories:
  - `circular`
  - `zigzag`
  - `polygon`
  - `straight`
- Adjustable number of runs per trajectory.
- Optional **shuffled execution** to increase dataset diversity.
- Supports **custom trajectory parameters**, e.g., radius, speed, omega.
- Automatic synchronization of images and sensors.
- Creates a **master dataset CSV** with paths to images and synchronized sensor data.
- Generates dataset statistics and a README for clarity.

**Usage Example:**

```bash
python3 automated_data_collection.py \
    --circular 3 --zigzag 2 --polygon 2 --straight 2 \
    --trajectory-duration 120 \
    --circular-radius 35 --circular-omega 0.2 \
    --polygon-num-vertices 6 --polygon-radius 20 --polygon-vertex-duration 5 \
    --zigzag-amplitude 10 --zigzag-speed 1 --zigzag-frequency 0.3 \
    --straight-speed 1.5 --straight-direction-angle 0 \
    --output training_dataset \
    --shuffle
````

---

### 2. Launch File: `x500_trajectory.launch.py`

The ROS2 launch file executes the **drone trajectory nodes** and sensor collection nodes.

* Receives parameters from `automated_data_collection.py`.
* Spawns **trajectory nodes** for the chosen pattern.
* Ensures the **sensors are recording** in parallel:

  * Camera images (`imgs_collection.py`)
  * GPS (`sensor_collector.py`)
  * IMU (`sensor_collector.py`)
* Takes `trajectory_duration`, trajectory-specific parameters, and `run_number`.

---

### 3. Trajectory Nodes

Each trajectory node implements a specific drone path:

* **Circular:** Fly in a circle with radius `R` and angular speed `ω`.
* **Zigzag:** Fly in zigzag motion with amplitude `A` and frequency `f`.
* **Polygon:** Fly along a polygonal path with a configurable number of vertices.
* **Straight:** Fly straight at a fixed speed and direction.

**Key Parameters:**

| Trajectory | Parameters                            |
| ---------- | ------------------------------------- |
| Circular   | radius, omega                         |
| Polygon    | num_vertices, radius, vertex_duration |
| Zigzag     | amplitude, speed, frequency           |
| Straight   | speed, direction_angle                |

---

### 4. Sensors

The pipeline collects the following **sensor data**:

1. **Camera Images**

   * Saved as PNG files in `<run_dir>/images/`
   * Image timestamps logged in `image_timestamps.csv`

2. **GPS**

   * Latitude, longitude, altitude
   * Velocity components: `vel_east`, `vel_north`, `vel_up`
   * Timestamps saved in `gps_data.csv`

3. **IMU**

   * Orientation quaternion: `imu_orient_x/y/z/w`
   * Angular velocity: `imu_ang_vel_x/y/z`
   * Linear acceleration: `imu_lin_acc_x/y/z`
   * Timestamps saved in `imu_data.csv`

---

### 5. Data Synchronization

* Executed via `synchronize_data.py`
* Aligns images with GPS and IMU measurements using timestamp matching.
* Outputs `synchronized_data.csv` for each run.
* Ensures sub-100ms accuracy between camera and sensors.

---

### 6. Dataset Structure

After running the pipeline, the `training_dataset/` directory will look like this:

```
training_dataset/
├── master_dataset.csv              # Combined dataset from all runs
├── dataset_statistics.json         # Dataset statistics
├── README.md                        # This file
├── circular_run01/                 # Each run in its own directory
│   ├── images/                     # Images from this run
│   │   ├── img_000000.png
│   │   └── image_timestamps.csv
│   ├── sensors/                    # Sensor data from this run
│   │   ├── gps_data.csv
│   │   └── imu_data.csv
│   └── synchronized_data.csv       # Synchronized dataset
├── zigzag_run01/
├── polygon_run01/
└── straight_run01/
```

---

### 7. Customizing Data Collection

All trajectory parameters are **modifiable via command-line arguments**:

* `--circular-radius`, `--circular-omega`
* `--polygon-num-vertices`, `--polygon-radius`, `--polygon-vertex-duration`
* `--zigzag-amplitude`, `--zigzag-speed`, `--zigzag-frequency`
* `--straight-speed`, `--straight-direction-angle`

Other options:

* `--trajectory-duration`: Duration of each trajectory in seconds.
* `--shuffle`: Randomize the order of trajectories to improve dataset diversity.

---

### 8. Workflow Summary

1. **Start pipeline**: Run `automated_data_collection.py` with desired arguments.
2. **Trajectory execution**: ROS2 launch file runs the drone along specified trajectories.
3. **Data collection**: Images and sensor data are recorded in organized directories.
4. **Synchronization**: Align images with GPS and IMU data for accurate training input.
5. **Dataset merging**: Generate `master_dataset.csv` for all runs.
6. **Analysis & stats**: Dataset statistics are saved to `dataset_statistics.json`.
7. **Training ready**: Dataset can be directly used in VI-SLAM or GPS prediction models.

---

### 9. Notes

* Requires **ROS2 workspace** with `x500_sensors` package installed.
* Ensure drone simulation or real hardware is properly set up for each trajectory node.
* Image and sensor data collection is synchronized automatically, but verify timestamps for real-world applications.
* Designed for **Python3**, with dependencies including `pandas` and `numpy`.

---

### 10. Example Python Usage for Training

```python
import pandas as pd
import os
from PIL import Image

CSV_PATH = 'training_dataset/master_dataset.csv'
IMAGE_DIR = 'training_dataset/'

df = pd.read_csv(CSV_PATH)

for idx, row in df.iterrows():
    img_path = os.path.join(IMAGE_DIR, row['image_path'])
    img = Image.open(img_path).convert('RGB')
    gps_coords = (row['latitude'], row['longitude'], row['altitude'])
    imu_data = (row['imu_orient_x'], row['imu_orient_y'], row['imu_orient_z'], row['imu_orient_w'])
    # Feed to VI-SLAM or neural network
```

---

### 11. Summary

This **modular pipeline** connects:

* `automated_data_collection.py` → orchestrates everything
* ROS2 **launch files** → trajectory execution + sensor nodes
* Trajectory nodes → control drone motion
* Sensors → camera, GPS, IMU
* Synchronization → produce aligned CSV datasets
* Dataset merging → training-ready master CSV

It allows **scalable, reproducible, and flexible dataset collection** for research or production VI-SLAM systems.

```

---



