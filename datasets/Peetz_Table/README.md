# Peetz Table

| Instrumentation | Latitude, Longitude |
| --------------- | ------------------- |
| Met tower       | 40.9943, -103.5251  |
| Profiling lidar | 49.9943, -103.5252  |
| Sodar (north)   | 40.9950, -103.5251  |
| Sodar (south)   | 40.9883, -103.5163  |

Analyses:

* `sodar_lidar_met_correlation.ipynb`: Comparison of north sodar data with
  nearby co-located met-tower and profiling lidar instruments. Good correlation
  with a +28 deg bias was observed.
* `sodar_north_south_comparison.ipynb`: Comparison of north and south sodar
  wind measurements. The south sodar wind direction differs from the corrected
  north sodar wind direction by -1 deg. It is unclear whether a bias truly
  exists or if this offset lies within the uncertainty bounds of the north
  sodar offset estimate.

